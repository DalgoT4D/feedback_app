import streamlit as st
import pandas as pd
import altair as alt
from datetime import date, timedelta
from services.db_helper import (
    get_connection,
    get_active_review_cycle,
    get_all_cycles,
)
from app_pages.components.feedback_display import (
    render_rating_card,
    render_text_card,
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

start_str = start_date.strftime("%Y-%m-%d")
end_str = end_date.strftime("%Y-%m-%d")

st.markdown("---")

# Tab layout for different views
tab_summary, tab_detailed = st.tabs(
    [
        "Summary",
        "Detailed View",
    ]
)

with tab_summary:
    st.subheader("Feedback Completion Summary")

    conn = get_connection()

    try:
        # Build cycle filter and shared parameters
        cycle_filter = "AND fr.cycle_id = ?" if selected_cycle_id else ""
        date_params = [start_str, end_str]
        params_with_cycle = date_params + (
            [selected_cycle_id] if selected_cycle_id else []
        )

        # Get summary statistics
        summary_stats = conn.execute(
            f"""
            SELECT 
                COUNT(DISTINCT fr.request_id) as total_completed,
                COUNT(DISTINCT fr.requester_id) as unique_recipients,
                COUNT(DISTINCT fr.reviewer_id) as unique_reviewers,
                COUNT(DISTINCT rc.cycle_id) as cycles_involved,
                AVG(LENGTH(resp.response_value)) as avg_response_length
            FROM feedback_requests fr
            JOIN feedback_responses resp ON fr.request_id = resp.request_id
            JOIN review_cycles rc ON fr.cycle_id = rc.cycle_id
            WHERE fr.workflow_state = 'completed' 
                AND DATE(fr.completed_at) BETWEEN ? AND ?
                {cycle_filter}
        """,
            tuple(params_with_cycle),
        ).fetchone()

        if summary_stats and summary_stats[0]:
            completed_forms = summary_stats[0] or 0
            unique_recipients = summary_stats[1] or 0
            unique_reviewers = summary_stats[2] or 0
            cycles_involved = summary_stats[3] or 0
            avg_length = summary_stats[4] or 0

            # Display key metrics
            col1, col2, col3, col4 = st.columns(4)

            with col1:
                st.metric("Feedback Submissions", completed_forms)
            with col2:
                st.metric("Employees with Feedback", unique_recipients)
            with col3:
                st.metric("Active Reviewers", unique_reviewers)
            with col4:
                st.metric("Cycles Involved", cycles_involved)

            st.metric("Avg Response Length", f"{avg_length:.0f} chars")

            # Completion trends
            st.subheader("Completion Trends")

            trend_params = params_with_cycle
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
                tuple(trend_params),
            ).fetchall()

            if trend_data:
                trend_df = pd.DataFrame(
                    trend_data, columns=["Date", "Completions", "Recipients"]
                )
                trend_df["Date"] = pd.to_datetime(trend_df["Date"])

                st.line_chart(trend_df.set_index("Date")[["Completions"]])

            # Rating distribution moved up from Analytics tab
            st.subheader("Rating Distribution")

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
                    {cycle_filter}
                GROUP BY resp.rating_value
                ORDER BY resp.rating_value
            """,
                tuple(params_with_cycle),
            ).fetchall()

            if rating_dist:
                rating_df = pd.DataFrame(rating_dist, columns=["Rating", "Count"])
                rating_chart = (
                    alt.Chart(rating_df)
                    .mark_bar(color="#1E4796")
                    .encode(
                        x=alt.X(
                            "Rating:N",
                            axis=alt.Axis(labelAngle=0, title="Rating"),
                            sort=None,
                        ),
                        y=alt.Y("Count:Q", axis=alt.Axis(title="Responses")),
                    )
                    .properties(height=260)
                )
                st.altair_chart(rating_chart, use_container_width=True)

                total_ratings = rating_df["Count"].sum()
                rating_df["Percent"] = rating_df["Count"].apply(
                    lambda c: f"{(c / total_ratings * 100):.1f}%"
                    if total_ratings > 0
                    else "0%"
                )
                st.dataframe(
                    rating_df,
                    use_container_width=True,
                    hide_index=True,
                )

            # Response quality summary
            st.subheader("Response Quality by Relationship")

            quality_stats = conn.execute(
                f"""
                SELECT 
                    fr.relationship_type,
                    COUNT(DISTINCT fr.request_id) as completed_forms,
                    AVG(LENGTH(resp.response_value)) as avg_length,
                    AVG(resp.rating_value) as avg_rating
                FROM feedback_requests fr
                JOIN feedback_responses resp ON fr.request_id = resp.request_id
                WHERE fr.workflow_state = 'completed' 
                    AND DATE(fr.completed_at) BETWEEN ? AND ?
                    {cycle_filter}
                GROUP BY fr.relationship_type
                ORDER BY completed_forms DESC
            """,
                tuple(params_with_cycle),
            ).fetchall()

            if quality_stats:
                quality_df = pd.DataFrame(
                    quality_stats,
                    columns=[
                        "Relationship Type",
                        "Completed Feedbacks",
                        "Avg Length",
                        "Avg Rating",
                    ],
                )
                quality_df["Relationship Type"] = (
                    quality_df["Relationship Type"].str.replace("_", " ").str.title()
                )
                quality_df["Avg Length"] = quality_df["Avg Length"].round(0)
                quality_df["Avg Rating"] = quality_df["Avg Rating"].round(2)
                quality_df.insert(0, "No.", range(1, len(quality_df) + 1))

                st.dataframe(
                    quality_df,
                    use_container_width=True,
                    hide_index=True,
                )

            st.subheader("Completion by Department")

            dept_data = conn.execute(
                f"""
                SELECT 
                    u.vertical,
                    COUNT(DISTINCT fr.request_id) as completed_reviews,
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
                tuple(params_with_cycle),
            ).fetchall()

            if dept_data:
                dept_rows = []
                for idx, row in enumerate(dept_data, start=1):
                    dept_rows.append(
                        {
                            "No.": idx,
                            "Department": row[0] or "Unknown",
                            "Completed Feedbacks": row[1] or 0,
                            "Employees": row[2] or 0,
                            "Avg Length": f"{(row[3] or 0):.0f}",
                        }
                    )
                dept_df = pd.DataFrame(dept_rows)
                st.dataframe(
                    dept_df,
                    use_container_width=True,
                    hide_index=True,
                )
        else:
            st.info("No completed feedback found in the selected period and filters")

    except Exception as e:
        st.error(f"Error loading summary data: {e}")

with tab_detailed:
    st.subheader("Detailed Feedback Reviews")

    conn = get_connection()
    if not conn:
        st.error("Unable to connect to the database. Please try again.")
    else:
        try:
            rel_col, dept_col, emp_col, length_col = st.columns(4)

            with rel_col:
                relationship_filter = st.multiselect(
                    "Relationship:",
                    [
                        "peer",
                        "direct_reportee",
                        "internal_collaborator",
                        "external_stakeholder",
                        "manager",
                    ],
                    default=[],
                    help="Limit the list to specific reviewer relationships",
                )

            with dept_col:
                departments = conn.execute(
                    "SELECT DISTINCT vertical FROM users WHERE is_active = 1 ORDER BY vertical"
                ).fetchall()
                dept_options = [d[0] for d in departments if d[0]]
                dept_filter = st.multiselect(
                    "Department:",
                    dept_options,
                    default=[],
                    help="Filter by the recipient's department",
                )

            with emp_col:
                employee_list = conn.execute(
                    """
                    SELECT DISTINCT 
                        u.user_type_id,
                        u.email,
                        u.first_name || ' ' || u.last_name as full_name
                    FROM users u
                    JOIN feedback_requests fr ON fr.requester_id = u.user_type_id
                    WHERE fr.workflow_state = 'completed'
                    ORDER BY u.first_name, u.last_name
                    """
                ).fetchall()
                employee_mapping = {
                    f"{row[2]} ({row[1]})": row[0] for row in employee_list if row[1]
                }
                employee_filter_label = st.selectbox(
                    "Employee:",
                    options=["All Employees"] + list(employee_mapping.keys()),
                    index=0,
                )
                selected_employee_id = (
                    employee_mapping.get(employee_filter_label)
                    if employee_filter_label != "All Employees"
                    else None
                )

            with length_col:
                min_length = st.number_input(
                    "Min response length",
                    min_value=0,
                    value=0,
                    step=10,
                    help="Filter out reviews whose average response text is shorter than this value",
                )

            st.markdown("---")

            filters = [
                "fr.workflow_state = 'completed'",
                "DATE(fr.completed_at) BETWEEN ? AND ?",
            ]
            params: list = [start_str, end_str]

            if selected_cycle_id:
                filters.append("fr.cycle_id = ?")
                params.append(selected_cycle_id)

            if relationship_filter:
                placeholders = ",".join(["?"] * len(relationship_filter))
                filters.append(f"fr.relationship_type IN ({placeholders})")
                params.extend(relationship_filter)

            if dept_filter:
                placeholders = ",".join(["?"] * len(dept_filter))
                filters.append(f"u1.vertical IN ({placeholders})")
                params.extend(dept_filter)

            if selected_employee_id:
                filters.append("fr.requester_id = ?")
                params.append(selected_employee_id)

            where_clause = " AND ".join(filters)

            base_query = f"""
                SELECT 
                    fr.request_id,
                    u1.first_name || ' ' || u1.last_name as recipient_name,
                    u1.vertical as recipient_dept,
                    COALESCE(u2.first_name || ' ' || u2.last_name, 'External Reviewer') as reviewer_name,
                    COALESCE(u2.vertical, 'External') as reviewer_dept,
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
                WHERE {where_clause}
                GROUP BY fr.request_id, recipient_name, recipient_dept, reviewer_name, reviewer_dept, fr.relationship_type, fr.completed_at, rc.cycle_display_name
                HAVING AVG(LENGTH(resp.response_value)) >= ?
            """

            params_with_min = params + [min_length]

            count_query = f"SELECT COUNT(*) FROM ({base_query}) base"
            try:
                total_reviews = conn.execute(
                    count_query, tuple(params_with_min)
                ).fetchone()[0]
            except Exception:
                total_reviews = 0

            if total_reviews == 0:
                st.info("No feedback reviews match your current filters")
                detailed_reviews = []
            else:
                col_page1, col_page2, col_page3 = st.columns(3)
                with col_page1:
                    page_size = st.selectbox(
                        "Reviews per page",
                        [10, 25, 50, 100],
                        index=1,
                    )

                max_page = max(1, (total_reviews + page_size - 1) // page_size)
                with col_page2:
                    current_page = st.number_input(
                        "Page",
                        min_value=1,
                        max_value=max_page,
                        value=1,
                        step=1,
                    )

                with col_page3:
                    start_record = (current_page - 1) * page_size + 1
                    end_record = min(current_page * page_size, total_reviews)
                    st.caption(f"Showing {start_record}-{end_record} of {total_reviews}")

                offset = (current_page - 1) * page_size
                paged_query = (
                    base_query + " ORDER BY fr.completed_at DESC LIMIT ? OFFSET ?"
                )
                detailed_reviews = conn.execute(
                    paged_query,
                    tuple(params_with_min + [page_size, offset]),
                ).fetchall()

            if detailed_reviews:
                for review in detailed_reviews:
                    relationship_label = review[5].replace("_", " ").title()
                    header = f"{review[1]} ← {review[3]} | {relationship_label}"
                    with st.expander(header):
                        col_meta, col_metrics = st.columns(2)
                        with col_meta:
                            st.write(
                                f"**Recipient:** {review[1]} ({review[2] or 'Unknown'})"
                            )
                            st.write(f"**Reviewer:** {review[3]} ({review[4]})")
                            st.write(f"**Cycle:** {review[7]}")
                            st.write(f"**Relationship:** {relationship_label}")
                        with col_metrics:
                            completed_label = (
                                review[6][:10] if review[6] else "Not captured"
                            )
                            st.write(f"**Completed:** {completed_label}")
                            st.write(f"**Responses:** {review[8]}")
                            if review[9] is not None:
                                st.write(
                                    f"**Avg Length:** {review[9]:.0f} characters"
                                )
                            st.write(f"**Ratings Submitted:** {review[10]}")

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
                            st.markdown("**Responses**")
                            for question_text, response_value, rating_value in responses:
                                if rating_value is not None:
                                    render_rating_card(question_text, rating_value)
                                else:
                                    render_text_card(question_text, response_value)
                        else:
                            st.info("No responses recorded for this review")
        except Exception as e:
            st.error(f"Error loading detailed data: {e}")



st.markdown("---")
# Quick Actions removed - use navigation menu
