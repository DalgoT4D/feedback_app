import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from services.db_helper import get_connection, get_active_review_cycle, get_all_cycles

st.title("System Overview")
st.subheader("Super Admin Dashboard - Complete System View")

# Get connection
conn = get_connection()

# Overview metrics
col1, col2, col3, col4 = st.columns(4)

# Get overall system stats
stats_query = """
SELECT 
    (SELECT COUNT(*) FROM users WHERE is_active = 1) as total_users,
    (SELECT COUNT(*) FROM feedback_requests) as total_requests,
    (SELECT COUNT(*) FROM feedback_requests WHERE status = 'completed') as completed_requests,
    (SELECT COUNT(*) FROM review_cycles) as total_cycles
"""

cursor = conn.execute(stats_query)
system_stats = cursor.fetchone()

with col1:
    st.metric("Active Users", system_stats[0])
with col2:
    st.metric("Total Requests", system_stats[1])
with col3:
    st.metric("Completed Reviews", system_stats[2])
with col4:
    st.metric("Review Cycles", system_stats[3])

# Tab layout for different admin views
tab1, tab2, tab3, tab4 = st.tabs(
    [
        "User Management",
        "System Analytics",
        "Cycle Management",
        "Data Export",
    ]
)

with tab1:
    st.subheader("User Management & Activity")

    # User activity summary
    user_activity_query = """
    SELECT 
        u.user_type_id,
        u.first_name || ' ' || u.last_name as full_name,
        u.email,
        u.vertical,
        u.designation,
        GROUP_CONCAT(DISTINCT r.role_name) as roles,
        COUNT(DISTINCT fr1.request_id) as requests_made,
        COUNT(DISTINCT fr2.request_id) as reviews_assigned,
        COUNT(DISTINCT fr3.request_id) as reviews_completed,
        u.created_at,
        u.is_active
    FROM users u
    LEFT JOIN user_roles ur ON u.user_type_id = ur.user_type_id
    LEFT JOIN roles r ON ur.role_id = r.role_id
    LEFT JOIN feedback_requests fr1 ON u.user_type_id = fr1.requester_id
    LEFT JOIN feedback_requests fr2 ON u.user_type_id = fr2.reviewer_id
    LEFT JOIN feedback_requests fr3 ON u.user_type_id = fr3.reviewer_id AND fr3.status = 'completed'
    GROUP BY u.user_type_id, u.first_name, u.last_name, u.email, u.vertical, u.designation, u.created_at, u.is_active
    ORDER BY u.first_name
    """

    cursor = conn.execute(user_activity_query)
    user_data = cursor.fetchall()

    if user_data:
        # Convert to DataFrame
        user_df = pd.DataFrame(
            user_data,
            columns=[
                "User ID",
                "Name",
                "Email",
                "Department",
                "Designation",
                "Roles",
                "Requests Made",
                "Reviews Assigned",
                "Reviews Completed",
                "Joined",
                "Active",
            ],
        )

        # Filter controls
        col1, col2, col3 = st.columns(3)
        with col1:
            dept_filter = st.multiselect(
                "Filter by Department:",
                options=sorted(user_df["Department"].unique()),
                default=sorted(user_df["Department"].unique()),
            )
        with col2:
            role_filter = st.multiselect(
                "Filter by Role:",
                options=["employee", "hr", "super_admin"],
                default=["employee", "hr", "super_admin"],
            )
        with col3:
            status_filter = st.selectbox(
                "Filter by Status:", options=["All", "Active", "Inactive"], index=0
            )

        # Apply filters
        filtered_users = user_df[user_df["Department"].isin(dept_filter)]

        if status_filter == "Active":
            filtered_users = filtered_users[filtered_users["Active"] == 1]
        elif status_filter == "Inactive":
            filtered_users = filtered_users[filtered_users["Active"] == 0]

        # Role filter
        if role_filter:
            role_mask = filtered_users["Roles"].apply(
                lambda x: any(role in str(x) for role in role_filter) if x else False
            )
            filtered_users = filtered_users[role_mask]

        st.write(f"**{len(filtered_users)}** users found")

        # Display user data
        for idx, row in filtered_users.iterrows():
            with st.expander(
                f"👤 {row['Name']} ({row['Department']}) - {row['Designation']}"
            ):
                col1, col2, col3 = st.columns(3)

                with col1:
                    st.write(f"**Email:** {row['Email']}")
                    st.write(f"**Roles:** {row['Roles'] or 'None'}")
                    st.write(f"**Status:** {'Active' if row['Active'] else 'Inactive'}")

                with col2:
                    st.write(f"**Requests Made:** {row['Requests Made']}")
                    st.write(f"**Reviews Assigned:** {row['Reviews Assigned']}")
                    st.write(f"**Reviews Completed:** {row['Reviews Completed']}")

                with col3:
                    completion_rate = (
                        (row["Reviews Completed"] / row["Reviews Assigned"] * 100)
                        if row["Reviews Assigned"] > 0
                        else 0
                    )
                    st.write(f"**Completion Rate:** {completion_rate:.1f}%")
                    st.write(f"**Joined:** {row['Joined'][:10]}")

                    # Quick actions
                    if st.button(
                        f"[Activity] View Activity", key=f"activity_{row['User ID']}"
                    ):
                        st.info("User activity details coming soon!")

with tab2:
    st.subheader("System Analytics & Performance")

    # Time-based analytics
    st.subheader("[Trends] Request Trends")

    # Daily request creation over last 30 days
    trend_query = """
    SELECT 
        DATE(created_at) as request_date,
        COUNT(*) as requests_count
    FROM feedback_requests
    WHERE created_at >= datetime('now', '-30 days')
    GROUP BY DATE(created_at)
    ORDER BY request_date
    """

    cursor = conn.execute(trend_query)
    trend_data = cursor.fetchall()

    if trend_data:
        trend_df = pd.DataFrame(trend_data, columns=["Date", "Requests"])
        st.line_chart(trend_df.set_index("Date"))

    # Relationship type distribution
    st.subheader("[Relationship] Relationship Type Distribution")

    rel_query = """
    SELECT 
        relationship_type,
        COUNT(*) as count,
        AVG(CASE WHEN status = 'completed' THEN 1.0 ELSE 0.0 END) * 100 as completion_rate
    FROM feedback_requests
    GROUP BY relationship_type
    ORDER BY count DESC
    """

    cursor = conn.execute(rel_query)
    rel_data = cursor.fetchall()

    if rel_data:
        rel_df = pd.DataFrame(
            rel_data, columns=["Relationship Type", "Count", "Completion Rate %"]
        )
        rel_df["Relationship Type"] = (
            rel_df["Relationship Type"].str.replace("_", " ").str.title()
        )
        rel_df["Completion Rate %"] = rel_df["Completion Rate %"].round(1)

        col1, col2 = st.columns(2)
        with col1:
            st.bar_chart(rel_df.set_index("Relationship Type")["Count"])
        with col2:
            st.dataframe(rel_df, use_container_width=True)

    # Department performance
    st.subheader("[Department] Department Performance")

    dept_perf_query = """
    SELECT 
        u.vertical as department,
        COUNT(DISTINCT u.user_type_id) as total_employees,
        COUNT(DISTINCT fr1.requester_id) as active_requesters,
        COUNT(DISTINCT fr2.reviewer_id) as active_reviewers,
        AVG(CASE WHEN fr2.status = 'completed' THEN 1.0 ELSE 0.0 END) * 100 as avg_completion_rate
    FROM users u
    LEFT JOIN feedback_requests fr1 ON u.user_type_id = fr1.requester_id
    LEFT JOIN feedback_requests fr2 ON u.user_type_id = fr2.reviewer_id
    WHERE u.is_active = 1
    GROUP BY u.vertical
    ORDER BY total_employees DESC
    """

    cursor = conn.execute(dept_perf_query)
    dept_perf_data = cursor.fetchall()

    if dept_perf_data:
        dept_perf_df = pd.DataFrame(
            dept_perf_data,
            columns=[
                "Department",
                "Total Employees",
                "Active Requesters",
                "Active Reviewers",
                "Avg Completion Rate %",
            ],
        )
        dept_perf_df["Avg Completion Rate %"] = dept_perf_df[
            "Avg Completion Rate %"
        ].round(1)
        st.dataframe(dept_perf_df, use_container_width=True)

with tab3:
    st.subheader("Review Cycle Management")

    # Get all cycles with detailed stats
    cycle_stats_query = """
    SELECT 
        rc.cycle_id,
        rc.cycle_display_name,
        rc.cycle_name,
        rc.cycle_year,
        rc.cycle_quarter,
        rc.cycle_description,
        rc.is_active,
        rc.status,
        rc.nomination_start_date,
        rc.nomination_deadline,
        rc.feedback_deadline,
        rc.results_deadline,
        rc.created_at,
        u.first_name || ' ' || u.last_name as created_by_name,
        COUNT(fr.request_id) as total_requests,
        SUM(CASE WHEN fr.status = 'completed' THEN 1 ELSE 0 END) as completed_requests
    FROM review_cycles rc
    LEFT JOIN users u ON rc.created_by = u.user_type_id
    LEFT JOIN feedback_requests fr ON rc.cycle_id = fr.cycle_id
    GROUP BY rc.cycle_id, rc.cycle_display_name, rc.cycle_name, rc.cycle_year, 
             rc.cycle_quarter, rc.cycle_description, rc.is_active, rc.status,
             rc.nomination_start_date, rc.nomination_deadline, rc.feedback_deadline,
             rc.results_deadline, rc.created_at, u.first_name, u.last_name
    ORDER BY rc.created_at DESC
    """

    cursor = conn.execute(cycle_stats_query)
    cycle_data = cursor.fetchall()

    if cycle_data:
        for cycle in cycle_data:
            status_emoji = "[Active]" if cycle[6] else "[Completed]"
            cycle_name = cycle[1] or cycle[2]

            with st.expander(
                f"{status_emoji} {cycle_name} ({cycle[3]} {cycle[4]}) - {cycle[14]} requests"
            ):
                col1, col2, col3 = st.columns(3)

                with col1:
                    st.write(f"**Description:** {cycle[5] or 'No description'}")
                    st.write(f"**Created by:** {cycle[13]}")
                    st.write(f"**Created:** {cycle[12][:10]}")
                    st.write(f"**Status:** {cycle[7]}")

                with col2:
                    st.write(f"**Nomination Start:** {cycle[8]}")
                    st.write(f"**Nomination Deadline:** {cycle[9]}")
                    st.write(f"**Feedback Deadline:** {cycle[10]}")
                    st.write(f"**Results Deadline:** {cycle[11]}")

                with col3:
                    st.write(f"**Total Requests:** {cycle[14]}")
                    st.write(f"**Completed:** {cycle[15]}")
                    if cycle[14] > 0:
                        completion_rate = (cycle[15] / cycle[14]) * 100
                        st.write(f"**Completion Rate:** {completion_rate:.1f}%")
                        st.progress(completion_rate / 100)

                    if not cycle[6] and cycle[7] != "completed":
                        if st.button(
                            f"[Manage] Manage Cycle", key=f"manage_cycle_{cycle[0]}"
                        ):
                            st.info("Cycle management features coming soon!")
    else:
        st.info("No review cycles found.")

with tab4:
    st.subheader("Data Export Center")

    st.write("Export comprehensive system data for analysis:")

    col1, col2 = st.columns(2)

    with col1:
        if st.button("[Export] Export All Users", type="primary"):
            cursor = conn.execute(
                "SELECT * FROM users WHERE is_active = 1 ORDER BY first_name"
            )
            users_export = cursor.fetchall()

            if users_export:
                # Get column names
                cursor = conn.execute("PRAGMA table_info(users)")
                columns = [col[1] for col in cursor.fetchall()]

                users_df = pd.DataFrame(users_export, columns=columns)
                csv = users_df.to_csv(index=False)

                st.download_button(
                    label="[Download] Download Users CSV",
                    data=csv,
                    file_name=f"users_export_{datetime.now().strftime('%Y%m%d')}.csv",
                    mime="text/csv",
                )

        if st.button("[Completed] Export All Feedback Requests"):
            export_query = """
            SELECT 
                fr.*,
                u1.first_name || ' ' || u1.last_name as requester_name,
                u2.first_name || ' ' || u2.last_name as reviewer_name,
                rc.cycle_display_name
            FROM feedback_requests fr
            JOIN users u1 ON fr.requester_id = u1.user_type_id
            JOIN users u2 ON fr.reviewer_id = u2.user_type_id
            JOIN review_cycles rc ON fr.cycle_id = rc.cycle_id
            ORDER BY fr.created_at DESC
            """

            cursor = conn.execute(export_query)
            requests_export = cursor.fetchall()

            if requests_export:
                # Create DataFrame with proper column names
                columns = [
                    "request_id",
                    "cycle_id",
                    "requester_id",
                    "reviewer_id",
                    "relationship_type",
                    "status",
                    "approval_status",
                    "approved_by",
                    "rejection_reason",
                    "approval_date",
                    "created_at",
                    "completed_at",
                    "requester_name",
                    "reviewer_name",
                    "cycle_name",
                ]

                requests_df = pd.DataFrame(requests_export, columns=columns)
                csv = requests_df.to_csv(index=False)

                st.download_button(
                    label="[Download] Download Requests CSV",
                    data=csv,
                    file_name=f"feedback_requests_export_{datetime.now().strftime('%Y%m%d')}.csv",
                    mime="text/csv",
                )

    with col2:
        if st.button("[Export] Export System Analytics"):
            # Create a comprehensive analytics report
            analytics_data = []

            # Add system overview
            cursor = conn.execute(stats_query)
            system_overview = cursor.fetchone()
            analytics_data.append(
                ["System Overview", "Total Users", system_overview[0]]
            )
            analytics_data.append(
                ["System Overview", "Total Requests", system_overview[1]]
            )
            analytics_data.append(
                ["System Overview", "Completed Requests", system_overview[2]]
            )
            analytics_data.append(
                ["System Overview", "Total Cycles", system_overview[3]]
            )

            # Add department stats
            cursor = conn.execute(dept_perf_query)
            dept_stats = cursor.fetchall()
            for dept in dept_stats:
                analytics_data.append(
                    ["Department Stats", f"{dept[0]} - Total Employees", dept[1]]
                )
                analytics_data.append(
                    ["Department Stats", f"{dept[0]} - Active Requesters", dept[2]]
                )
                analytics_data.append(
                    [
                        "Department Stats",
                        f"{dept[0]} - Completion Rate",
                        f"{dept[4]:.1f}%",
                    ]
                )

            analytics_df = pd.DataFrame(
                analytics_data, columns=["Category", "Metric", "Value"]
            )
            csv = analytics_df.to_csv(index=False)

            st.download_button(
                label="[Download] Download Analytics CSV",
                data=csv,
                file_name=f"system_analytics_{datetime.now().strftime('%Y%m%d')}.csv",
                mime="text/csv",
            )


# System health check
st.sidebar.subheader("[Health] System Health")

# Database connection status
try:
    cursor = conn.execute("SELECT 1")
    result = cursor.fetchone()
    if result:
        st.sidebar.success("[Success] Database Connected")
except:
    st.sidebar.error("[Error] Database Connection Failed")

# Last activity
try:
    cursor = conn.execute("SELECT MAX(created_at) FROM feedback_requests")
    last_activity = cursor.fetchone()[0]
    if last_activity:
        st.sidebar.info(f"Last Request: {last_activity[:16]}")
    else:
        st.sidebar.info("No activity recorded")
except:
    st.sidebar.warning("[Warning] Cannot fetch activity data")
