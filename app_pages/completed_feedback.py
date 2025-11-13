import streamlit as st
import pandas as pd
from datetime import datetime, date, timedelta
from services.db_helper import (
    get_connection,
    get_active_review_cycle,
    get_all_cycles,
    generate_feedback_excel_data,
)

st.title("Completed Feedback Overview")
st.markdown("Monitor and analyze all completed feedback in the system")

# Get active cycle info
active_cycle = get_active_review_cycle()
all_cycles = get_all_cycles()

# Cycle selector and date range
col1, col2 = st.columns([2, 1])
with col1:
    cycle_options = ["All Cycles"] + [
        f"{c['cycle_display_name']} ({c['cycle_year']} {c['cycle_quarter']})"
        for c in all_cycles
        if c.get("cycle_display_name")
    ]
    selected_cycle_option = st.selectbox("Filter by Cycle:", cycle_options)

    # Parse selected cycle
    selected_cycle_id = None
    if selected_cycle_option != "All Cycles":
        for cycle in all_cycles:
            cycle_display = f"{cycle['cycle_display_name']} ({cycle['cycle_year']} {cycle['cycle_quarter']})"
            if cycle_display == selected_cycle_option:
                selected_cycle_id = cycle["cycle_id"]
                break

with col2:
    if active_cycle:
        st.info(f"**Active:** {active_cycle['cycle_display_name']}")
    else:
        st.warning("No active cycle")

# Date range filter
col1, col2 = st.columns(2)
with col1:
    start_date = st.date_input("From Date:", value=date.today() - timedelta(days=90))
with col2:
    end_date = st.date_input("To Date:", value=date.today())

st.markdown("---")

# Tab layout for different views
tab1, tab2, tab3, tab4, tab5 = st.tabs(
    [
        "Summary",
        "Detailed View",
        "By Employee",
        "Analytics",
        "Export",
    ]
)

with tab1:
    st.subheader("Feedback Completion Summary")

    conn = get_connection()

    try:
        # Build cycle filter
        cycle_filter = ""
        params = [start_date.strftime("%Y-%m-%d"), end_date.strftime("%Y-%m-%d")]

        if selected_cycle_id:
            cycle_filter = "AND fr.cycle_id = ?"
            params.append(selected_cycle_id)

        # Get summary statistics
        summary_stats = conn.execute(
            f"""
            SELECT 
                COUNT(DISTINCT fr.request_id) as total_completed,
                COUNT(DISTINCT fr.requester_id) as unique_recipients,
                COUNT(DISTINCT fr.reviewer_id) as unique_reviewers,
                COUNT(DISTINCT rc.cycle_id) as cycles_involved,
                AVG(LENGTH(resp.response_value)) as avg_response_length,
                COUNT(resp.response_id) as total_responses
            FROM feedback_requests fr
            JOIN feedback_responses resp ON fr.request_id = resp.request_id
            JOIN review_cycles rc ON fr.cycle_id = rc.cycle_id
            WHERE fr.workflow_state = 'completed' 
                AND DATE(fr.completed_at) BETWEEN ? AND ?
                {cycle_filter}
        """,
            tuple(params),
        ).fetchone()

        if summary_stats and summary_stats[0]:
            # Display key metrics
            col1, col2, col3, col4 = st.columns(4)

            with col1:
                st.metric("Completed Reviews", summary_stats[0])
            with col2:
                st.metric("Employees with Feedback", summary_stats[1])
            with col3:
                st.metric("Active Reviewers", summary_stats[2])
            with col4:
                st.metric("Cycles Involved", summary_stats[3])

            col1, col2 = st.columns(2)
            with col1:
                st.metric("Total Responses", summary_stats[5])
            with col2:
                avg_length = summary_stats[4] or 0
                st.metric("Avg Response Length", f"{avg_length:.0f} chars")

            # Completion trends
            st.subheader("Completion Trends")

            trend_data = conn.execute(
                f"""
                SELECT 
                    DATE(fr.completed_at) as completion_date,
                    COUNT(fr.request_id) as completions,
                    COUNT(DISTINCT fr.requester_id) as unique_recipients
                FROM feedback_requests fr
                WHERE fr.workflow_state = 'completed' 
                    AND DATE(fr.completed_at) BETWEEN ? AND ?
                    {cycle_filter}
                GROUP BY DATE(fr.completed_at)
                ORDER BY completion_date
            """,
                tuple(params),
            ).fetchall()

            if trend_data:
                trend_df = pd.DataFrame(
                    trend_data, columns=["Date", "Completions", "Recipients"]
                )
                trend_df["Date"] = pd.to_datetime(trend_df["Date"])

                st.line_chart(trend_df.set_index("Date")[["Completions"]])

            # Department breakdown
            st.subheader("Completion by Department")

            dept_data = conn.execute(
                f"""
                SELECT 
                    u.vertical,
                    COUNT(fr.request_id) as completed_reviews,
                    COUNT(DISTINCT fr.requester_id) as employees_with_feedback,
                    AVG(LENGTH(resp.response_value)) as avg_response_length
                FROM feedback_requests fr
                JOIN users u ON fr.requester_id = u.user_type_id
                JOIN feedback_responses resp ON fr.request_id = resp.request_id
                WHERE fr.workflow_state = 'completed' 
                    AND DATE(fr.completed_at) BETWEEN ? AND ?
                    {cycle_filter}
                GROUP BY u.vertical
                ORDER BY completed_reviews DESC
            """,
                tuple(params),
            ).fetchall()

            if dept_data:
                dept_df = pd.DataFrame(
                    dept_data,
                    columns=["Department", "Reviews", "Employees", "Avg Length"],
                )
                st.dataframe(dept_df, use_container_width=True)
        else:
            st.info("No completed feedback found in the selected period and filters")

    except Exception as e:
        st.error(f"Error loading summary data: {e}")

with tab2:
    st.subheader("Detailed Feedback Reviews")

    # Additional filters
    col1, col2, col3 = st.columns(3)
    with col1:
        relationship_filter = st.multiselect(
            "Filter by Relationship:",
            [
                "peer",
                "direct_reportee",
                "internal_collaborator",
                "external_stakeholder",
                "manager",
            ],
            default=[],
        )

    with col2:
        conn = get_connection()
        departments = conn.execute(
            "SELECT DISTINCT vertical FROM users WHERE is_active = 1 ORDER BY vertical"
        ).fetchall()
        dept_filter = st.multiselect(
            "Filter by Department:", [d[0] for d in departments if d[0]], default=[]
        )

    with col3:
        min_length = st.number_input(
            "Min response length:", min_value=0, value=0, step=10
        )

    try:
        # Build detailed query
        detail_query = f"""
            SELECT 
                fr.request_id,
                u1.first_name || ' ' || u1.last_name as recipient_name,
                u1.vertical as recipient_dept,
                u2.first_name || ' ' || u2.last_name as reviewer_name,
                u2.vertical as reviewer_dept,
                fr.relationship_type,
                fr.completed_at,
                rc.cycle_display_name,
                COUNT(resp.response_id) as response_count,
                AVG(LENGTH(resp.response_value)) as avg_response_length,
                SUM(CASE WHEN resp.rating_value IS NOT NULL THEN 1 ELSE 0 END) as rating_count
            FROM feedback_requests fr
            JOIN users u1 ON fr.requester_id = u1.user_type_id
            LEFT JOIN users u2 ON fr.reviewer_id = u2.user_type_id
            JOIN review_cycles rc ON fr.cycle_id = rc.cycle_id
            JOIN feedback_responses resp ON fr.request_id = resp.request_id
            WHERE fr.workflow_state = 'completed' 
                AND DATE(fr.completed_at) BETWEEN ? AND ?
        """

        params = [start_date.strftime("%Y-%m-%d"), end_date.strftime("%Y-%m-%d")]

        if selected_cycle_id:
            detail_query += " AND fr.cycle_id = ?"
            params.append(selected_cycle_id)

        if relationship_filter:
            placeholders = ",".join(["?" for _ in relationship_filter])
            detail_query += f" AND fr.relationship_type IN ({placeholders})"
            params.extend(relationship_filter)

        if dept_filter:
            placeholders = ",".join(["?" for _ in dept_filter])
            detail_query += f" AND u1.vertical IN ({placeholders})"
            params.extend(dept_filter)

        detail_query += """
            GROUP BY fr.request_id, u1.first_name, u1.last_name, u1.vertical, 
                     u2.first_name, u2.last_name, u2.vertical, fr.relationship_type, 
                     fr.completed_at, rc.cycle_display_name
            HAVING AVG(LENGTH(resp.response_value)) >= ?
            ORDER BY fr.completed_at DESC
        """
        params.append(min_length)

        detailed_reviews = conn.execute(detail_query, tuple(params)).fetchall()

        if detailed_reviews:
            st.write(
                f"**{len(detailed_reviews)} feedback reviews** match your filters:"
            )

            for review in detailed_reviews:
                with st.expander(
                    f"[Feedback] {review[1]} <- {review[3] or 'External'} | {review[5].replace('_', ' ').title()}"
                ):
                    col1, col2 = st.columns(2)

                    with col1:
                        st.write("**[Review] Review Details:**")
                        st.write(f"**Recipient:** {review[1]} ({review[2]})")
                        st.write(
                            f"**Reviewer:** {review[3] or 'External Reviewer'} ({review[4] or 'External'})"
                        )
                        st.write(
                            f"**Relationship:** {review[5].replace('_', ' ').title()}"
                        )
                        st.write(f"**Cycle:** {review[7]}")

                    with col2:
                        st.write("**[Metrics] Response Metrics:**")
                        st.write(f"**Completed:** {review[6][:10]}")
                        st.write(f"**Responses:** {review[8]}")
                        if review[9]:
                            st.write(f"**Avg Length:** {review[9]:.0f} characters")
                        if review[10]:
                            st.write(f"**Ratings:** {review[10]}")

                    # Show actual responses
                    if st.button("[View] View Responses", key=f"view_{review[0]}"):
                        responses = conn.execute(
                            """
                            SELECT fq.question_text, resp.response_value, resp.rating_value
                            FROM feedback_responses resp
                            JOIN feedback_questions fq ON resp.question_id = fq.question_id
                            WHERE resp.request_id = ?
                            ORDER BY fq.sort_order
                        """,
                            (review[0],),
                        ).fetchall()

                        if responses:
                            st.write("**[Responses] Feedback Responses:**")
                            for i, (question, response, rating) in enumerate(
                                responses, 1
                            ):
                                st.write(f"**Q{i}:** {question}")
                                if rating:
                                    st.write(f"**Rating:** {rating}/5")
                                if response:
                                    st.write(f"**Response:** {response}")
                                st.divider()
        else:
            st.info("No feedback reviews match your current filters")

    except Exception as e:
        st.error(f"Error loading detailed data: {e}")

with tab3:
    st.subheader("Feedback by Employee")

    try:
        # Employee feedback summary
        employee_summary = conn.execute(
            f"""
            SELECT 
                u.user_type_id,
                u.first_name || ' ' || u.last_name as employee_name,
                u.vertical,
                u.designation,
                COUNT(fr.request_id) as feedback_received,
                COUNT(DISTINCT fr.cycle_id) as cycles_participated,
                AVG(resp.rating_value) as avg_rating,
                COUNT(resp.response_id) as total_responses,
                MIN(fr.completed_at) as first_feedback,
                MAX(fr.completed_at) as latest_feedback
            FROM users u
            JOIN feedback_requests fr ON u.user_type_id = fr.requester_id
            JOIN feedback_responses resp ON fr.request_id = resp.request_id
            WHERE fr.workflow_state = 'completed' 
                AND DATE(fr.completed_at) BETWEEN ? AND ?
                {cycle_filter if selected_cycle_id else ""}
            GROUP BY u.user_type_id, u.first_name, u.last_name, u.vertical, u.designation
            ORDER BY feedback_received DESC
        """,
            tuple(params[:2] + ([selected_cycle_id] if selected_cycle_id else [])),
        ).fetchall()

        if employee_summary:
            # Search functionality
            search_term = st.text_input(
                "[Search] Search employees:", placeholder="Enter name or department..."
            )

            # Filter employees based on search
            filtered_employees = employee_summary
            if search_term:
                filtered_employees = [
                    emp
                    for emp in employee_summary
                    if search_term.lower() in emp[1].lower()
                    or search_term.lower() in (emp[2] or "").lower()
                ]

            st.write(
                f"**{len(filtered_employees)} employees** with completed feedback:"
            )

            for employee in filtered_employees:
                with st.expander(
                    f"[Employee] {employee[1]} ({employee[2]}) - {employee[4]} reviews received"
                ):
                    col1, col2, col3 = st.columns(3)

                    with col1:
                        st.write("**[Employee] Employee Info:**")
                        st.write(f"**Name:** {employee[1]}")
                        st.write(f"**Department:** {employee[2]}")
                        st.write(f"**Designation:** {employee[3]}")

                    with col2:
                        st.write("**[Stats] Feedback Stats:**")
                        st.write(f"**Reviews Received:** {employee[4]}")
                        st.write(f"**Cycles Participated:** {employee[5]}")
                        st.write(f"**Total Responses:** {employee[7]}")

                    with col3:
                        st.write("**[Performance] Performance:**")
                        if employee[6]:
                            st.write(f"**Avg Rating:** {employee[6]:.1f}/5")
                        if employee[8]:
                            st.write(f"**First Feedback:** {employee[8][:10]}")
                        if employee[9]:
                            st.write(f"**Latest Feedback:** {employee[9][:10]}")

                    # Action buttons
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        if st.button(
                            "[Details] View Details", key=f"details_{employee[0]}"
                        ):
                            st.info("Detailed view coming soon!")
                    with col2:
                        if st.button("[Export] Export", key=f"export_{employee[0]}"):
                            # Generate Excel data for this employee
                            excel_data = generate_feedback_excel_data(employee[0])
                            if excel_data:
                                df = pd.DataFrame(excel_data)
                                csv = df.to_csv(index=False)
                                st.download_button(
                                    label="Download CSV",
                                    data=csv,
                                    file_name=f"feedback_{employee[1].replace(' ', '_')}_{datetime.now().strftime('%Y%m%d')}.csv",
                                    mime="text/csv",
                                    key=f"download_{employee[0]}",
                                )
                            else:
                                st.warning("No data to export")
                    with col3:
                        if st.button("[Email] Send Summary", key=f"send_{employee[0]}"):
                            st.info("Email summary feature coming soon!")
        else:
            st.info("No employees with completed feedback in the selected period")

    except Exception as e:
        st.error(f"Error loading employee data: {e}")

with tab4:
    st.subheader("Feedback Analytics")

    try:
        # Response quality analysis
        st.write("**[Quality] Response Quality Analysis**")

        quality_stats = conn.execute(
            f"""
            SELECT 
                fr.relationship_type,
                COUNT(resp.response_id) as total_responses,
                AVG(LENGTH(resp.response_value)) as avg_length,
                COUNT(CASE WHEN LENGTH(resp.response_value) >= 100 THEN 1 END) as detailed_responses,
                COUNT(CASE WHEN resp.rating_value IS NOT NULL THEN 1 END) as with_ratings,
                AVG(resp.rating_value) as avg_rating
            FROM feedback_requests fr
            JOIN feedback_responses resp ON fr.request_id = resp.request_id
            WHERE fr.workflow_state = 'completed' 
                AND DATE(fr.completed_at) BETWEEN ? AND ?
                {cycle_filter if selected_cycle_id else ""}
            GROUP BY fr.relationship_type
            ORDER BY total_responses DESC
        """,
            tuple(params[:2] + ([selected_cycle_id] if selected_cycle_id else [])),
        ).fetchall()

        if quality_stats:
            quality_df = pd.DataFrame(
                quality_stats,
                columns=[
                    "Relationship Type",
                    "Total Responses",
                    "Avg Length",
                    "Detailed Responses",
                    "With Ratings",
                    "Avg Rating",
                ],
            )
            quality_df["Relationship Type"] = (
                quality_df["Relationship Type"].str.replace("_", " ").str.title()
            )
            quality_df["Avg Length"] = quality_df["Avg Length"].round(0)
            quality_df["Avg Rating"] = quality_df["Avg Rating"].round(2)

            st.dataframe(quality_df, use_container_width=True)

        # Rating distribution
        st.write("**[Star] Rating Distribution**")

        rating_dist = conn.execute(
            f"""
            SELECT 
                resp.rating_value,
                COUNT(*) as count
            FROM feedback_requests fr
            JOIN feedback_responses resp ON fr.request_id = resp.request_id
            WHERE fr.workflow_state = 'completed' 
                AND resp.rating_value IS NOT NULL
                AND DATE(fr.completed_at) BETWEEN ? AND ?
                {cycle_filter if selected_cycle_id else ""}
            GROUP BY resp.rating_value
            ORDER BY resp.rating_value
        """,
            tuple(params[:2] + ([selected_cycle_id] if selected_cycle_id else [])),
        ).fetchall()

        if rating_dist:
            col1, col2 = st.columns(2)

            with col1:
                rating_df = pd.DataFrame(rating_dist, columns=["Rating", "Count"])
                st.bar_chart(rating_df.set_index("Rating"))

            with col2:
                total_ratings = sum([r[1] for r in rating_dist])
                for rating, count in rating_dist:
                    percentage = (
                        (count / total_ratings * 100) if total_ratings > 0 else 0
                    )
                    st.write(f"[Star] {rating}/5: {count} ({percentage:.1f}%)")

        # Feedback frequency by month
        st.write("**[Timeline] Feedback Completion by Month**")

        monthly_data = conn.execute(
            f"""
            SELECT 
                strftime('%Y-%m', fr.completed_at) as month,
                COUNT(fr.request_id) as completions,
                COUNT(DISTINCT fr.requester_id) as unique_recipients
            FROM feedback_requests fr
            WHERE fr.workflow_state = 'completed' 
                AND DATE(fr.completed_at) BETWEEN ? AND ?
                {cycle_filter if selected_cycle_id else ""}
            GROUP BY strftime('%Y-%m', fr.completed_at)
            ORDER BY month
        """,
            tuple(params[:2] + ([selected_cycle_id] if selected_cycle_id else [])),
        ).fetchall()

        if monthly_data:
            monthly_df = pd.DataFrame(
                monthly_data, columns=["Month", "Completions", "Recipients"]
            )
            st.line_chart(monthly_df.set_index("Month"))

    except Exception as e:
        st.error(f"Error loading analytics data: {e}")

with tab5:
    st.subheader("Export Feedback Data")

    # Export options
    col1, col2 = st.columns(2)

    with col1:
        export_format = st.selectbox(
            "Export Format:", ["CSV", "Excel Summary", "Detailed Report"]
        )

        export_scope = st.selectbox(
            "Export Scope:",
            [
                "All Completed Feedback",
                "Selected Cycle Only",
                "Selected Department",
                "Selected Date Range",
            ],
        )

        # Department filter for export, only shown if "Selected Department" is chosen
        export_dept_filter = []
        if export_scope == "Selected Department":
            conn = get_connection()  # Ensure connection is available
            departments = conn.execute(
                "SELECT DISTINCT vertical FROM users WHERE is_active = 1 ORDER BY vertical"
            ).fetchall()
            export_dept_filter = st.multiselect(
                "Select Department(s) for Export:",
                [d[0] for d in departments if d[0]],
                default=[],
            )

    with col2:
        include_options = st.multiselect(
            "Include in Export:",
            [
                "Employee Information",
                "Reviewer Information",
                "Response Text",
                "Ratings",
                "Timestamps",
                "Cycle Information",
            ],
            default=["Employee Information", "Response Text", "Ratings"],
        )

    # Generate export
    if st.button("Generate Export", type="primary"):
        try:
            # Build export query based on options
            export_query = """
                SELECT
                    fr.request_id,
                    u1.first_name || ' ' || u1.last_name as recipient_name,
                    u1.email as recipient_email,
                    u1.vertical as recipient_dept,
                    u2.first_name || ' ' || u2.last_name as reviewer_name,
                    u2.email as reviewer_email,
                    u2.vertical as reviewer_dept,
                    fr.relationship_type,
                    fq.question_text,
                    resp.response_value,
                    resp.rating_value,
                    fr.completed_at,
                    rc.cycle_display_name
                FROM feedback_requests fr
                JOIN users u1 ON fr.requester_id = u1.user_type_id
                LEFT JOIN users u2 ON fr.reviewer_id = u2.user_type_id
                JOIN feedback_responses resp ON fr.request_id = resp.request_id
                JOIN feedback_questions fq ON resp.question_id = fq.question_id
                JOIN review_cycles rc ON fr.cycle_id = rc.cycle_id
                WHERE fr.workflow_state = 'completed'
            """

            export_params = []

            if export_scope == "Selected Date Range":
                export_query += " AND DATE(fr.completed_at) BETWEEN ? AND ?"
                export_params.extend(
                    [start_date.strftime("%Y-%m-%d"), end_date.strftime("%Y-%m-%d")]
                )

            if export_scope == "Selected Cycle Only" and selected_cycle_id:
                export_query += " AND fr.cycle_id = ?"
                export_params.append(selected_cycle_id)

            if export_scope == "Selected Department" and export_dept_filter:
                placeholders = ",".join(["?" for _ in export_dept_filter])
                export_query += f" AND u1.vertical IN ({placeholders})"
                export_params.extend(export_dept_filter)

            export_query += (
                " ORDER BY fr.completed_at DESC, fr.request_id, fq.sort_order"
            )

            export_data = conn.execute(export_query, tuple(export_params)).fetchall()
            if export_data:
                # Prepare DataFrame
                columns = [
                    "Request ID",
                    "Recipient Name",
                    "Recipient Email",
                    "Recipient Dept",
                    "Reviewer Name",
                    "Reviewer Email",
                    "Reviewer Dept",
                    "Relationship Type",
                    "Question",
                    "Response",
                    "Rating",
                    "Completed At",
                    "Cycle",
                ]

                df = pd.DataFrame(export_data, columns=columns)

                # Filter columns based on include options
                final_columns = ["Request ID", "Question", "Response"]

                if "Employee Information" in include_options:
                    final_columns.extend(
                        ["Recipient Name", "Recipient Email", "Recipient Dept"]
                    )

                if "Reviewer Information" in include_options:
                    final_columns.extend(
                        ["Reviewer Name", "Reviewer Email", "Reviewer Dept"]
                    )

                if "Ratings" in include_options:
                    final_columns.append("Rating")

                if "Timestamps" in include_options:
                    final_columns.append("Completed At")

                if "Cycle Information" in include_options:
                    final_columns.extend(["Cycle", "Relationship Type"])

                # Filter and export
                export_df = df[final_columns]
                csv_data = export_df.to_csv(index=False)

                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"feedback_export_{timestamp}.csv"

                st.download_button(
                    label="[Download] Download Export",
                    data=csv_data,
                    file_name=filename,
                    mime="text/csv",
                )

                st.success(
                    f"Export generated successfully! {len(export_data)} records ready for download."
                )
            else:
                st.warning("No data available for export with current filters")

        except Exception as e:
            st.error(f"Error generating export: {e}")

st.markdown("---")
# Quick Actions removed - use navigation menu
