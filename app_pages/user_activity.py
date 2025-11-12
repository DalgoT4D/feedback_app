import streamlit as st
import pandas as pd
from datetime import datetime, date, timedelta
from services.db_helper import get_connection, get_active_review_cycle, get_all_cycles

st.title("User Activity Monitor")
st.markdown("Monitor and track user engagement across the feedback system")

# Get active cycle info
active_cycle = get_active_review_cycle()
all_cycles = get_all_cycles()

# Cycle selector
col1, col2 = st.columns([3, 1])
with col1:
    if active_cycle:
        st.info(f"**Active Cycle:** {active_cycle['cycle_display_name']}")
    else:
        st.warning("[Warning] No active review cycle")

with col2:
    cycle_options = ["All Cycles", "Active Only"] + [
        f"{c['cycle_display_name']} ({c['cycle_year']} {c['cycle_quarter']})"
        for c in all_cycles
        if c.get("cycle_display_name")
    ]
    selected_cycle = st.selectbox("View Cycle:", cycle_options)

# Date range filter
col1, col2 = st.columns(2)
with col1:
    start_date = st.date_input("From Date:", value=date.today() - timedelta(days=30))
with col2:
    end_date = st.date_input("To Date:", value=date.today())

st.markdown("---")

# Tab layout for different activity views
tab1, tab2, tab3, tab4, tab5 = st.tabs(
    ["Overview", "Nominations", "Approvals", "Feedback", "Recent Activity"]
)

with tab1:
    st.subheader("User Engagement Overview")

    conn = get_connection()

    # Get summary statistics
    try:
        # Total active users
        total_users = conn.execute(
            "SELECT COUNT(*) FROM users WHERE is_active = 1"
        ).fetchone()[0]

        # Users who have participated (made nominations)
        participating_users = (
            conn.execute(
                """
            SELECT COUNT(DISTINCT requester_id) FROM feedback_requests 
            WHERE cycle_id = (SELECT cycle_id FROM review_cycles WHERE is_active = 1)
        """
            ).fetchone()[0]
            if active_cycle
            else 0
        )

        # Users with completed reviews
        completed_users = (
            conn.execute(
                """
            SELECT COUNT(DISTINCT requester_id) FROM feedback_requests 
            WHERE status = 'completed' AND cycle_id = (SELECT cycle_id FROM review_cycles WHERE is_active = 1)
        """
            ).fetchone()[0]
            if active_cycle
            else 0
        )

        # Users who have reviewed others
        reviewers_active = (
            conn.execute(
                """
            SELECT COUNT(DISTINCT reviewer_id) FROM feedback_requests 
            WHERE status = 'completed' AND cycle_id = (SELECT cycle_id FROM review_cycles WHERE is_active = 1)
        """
            ).fetchone()[0]
            if active_cycle
            else 0
        )

        # Display metrics
        col1, col2, col3, col4 = st.columns(4)

        with col1:
            st.metric("Total Users", total_users)

        with col2:
            participation_rate = (
                (participating_users / total_users * 100) if total_users > 0 else 0
            )
            st.metric(
                "Participation Rate",
                f"{participation_rate:.1f}%",
                delta=f"{participating_users} users",
            )

        with col3:
            completion_rate = (
                (completed_users / participating_users * 100)
                if participating_users > 0
                else 0
            )
            st.metric(
                "Completion Rate",
                f"{completion_rate:.1f}%",
                delta=f"{completed_users} users",
            )

        with col4:
            review_rate = (
                (reviewers_active / total_users * 100) if total_users > 0 else 0
            )
            st.metric(
                "Active Reviewers",
                f"{review_rate:.1f}%",
                delta=f"{reviewers_active} users",
            )

        # Engagement breakdown by department
        st.subheader("Department Engagement")

        dept_stats = conn.execute(
            """
            SELECT 
                u.vertical,
                COUNT(DISTINCT u.user_type_id) as total_users,
                COUNT(DISTINCT fr.requester_id) as participating_users,
                COUNT(DISTINCT CASE WHEN fr.status = 'completed' THEN fr.requester_id END) as completed_users,
                COUNT(DISTINCT CASE WHEN fr.status = 'completed' THEN fr.reviewer_id END) as active_reviewers
            FROM users u
            LEFT JOIN feedback_requests fr ON u.user_type_id = fr.requester_id 
                AND fr.cycle_id = (SELECT cycle_id FROM review_cycles WHERE is_active = 1)
            WHERE u.is_active = 1
            GROUP BY u.vertical
            ORDER BY total_users DESC
        """
        ).fetchall()

        if dept_stats:
            dept_data = []
            for row in dept_stats:
                total = row[1]
                participating = row[2] or 0
                completed = row[3] or 0
                reviewers = row[4] or 0

                dept_data.append(
                    {
                        "Department": row[0] or "Unknown",
                        "Total Users": total,
                        "Participating": participating,
                        "Participation %": (
                            f"{(participating/total*100):.1f}%" if total > 0 else "0%"
                        ),
                        "Completed": completed,
                        "Completion %": (
                            f"{(completed/participating*100):.1f}%"
                            if participating > 0
                            else "0%"
                        ),
                        "Active Reviewers": reviewers,
                    }
                )

            dept_df = pd.DataFrame(dept_data)
            st.dataframe(dept_df, use_container_width=True)

            # Visual representation
            if len(dept_data) > 1:
                st.subheader("Participation by Department")
                chart_data = pd.DataFrame(
                    {
                        "Department": [d["Department"] for d in dept_data],
                        "Participation Rate": [
                            float(d["Participation %"].rstrip("%")) for d in dept_data
                        ],
                    }
                )
                st.bar_chart(chart_data.set_index("Department"))

    except Exception as e:
        st.error(f"Error loading overview data: {e}")

with tab2:
    st.subheader("Nomination Activity")

    try:
        # Nomination statistics
        if active_cycle:
            nom_stats = conn.execute(
                """
                SELECT 
                    COUNT(*) as total_nominations,
                    COUNT(DISTINCT requester_id) as users_with_nominations,
                    AVG(nomination_count) as avg_nominations_per_user
                FROM (
                    SELECT requester_id, COUNT(*) as nomination_count
                    FROM feedback_requests
                    WHERE cycle_id = ?
                    GROUP BY requester_id
                )
            """,
                (active_cycle["cycle_id"],),
            ).fetchone()

            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Total Nominations", nom_stats[0] or 0)
            with col2:
                st.metric("Users Who Nominated", nom_stats[1] or 0)
            with col3:
                avg_noms = nom_stats[2] or 0
                st.metric("Avg Nominations/User", f"{avg_noms:.1f}")

        # Recent nomination activity
        st.subheader("Recent Nominations")

        recent_nominations = conn.execute(
            """
            SELECT 
                u1.first_name || ' ' || u1.last_name as requester_name,
                u1.vertical as requester_dept,
                u2.first_name || ' ' || u2.last_name as reviewer_name,
                u2.vertical as reviewer_dept,
                fr.relationship_type,
                fr.created_at,
                fr.approval_status
            FROM feedback_requests fr
            JOIN users u1 ON fr.requester_id = u1.user_type_id
            LEFT JOIN users u2 ON fr.reviewer_id = u2.user_type_id
            WHERE DATE(fr.created_at) >= ?
            ORDER BY fr.created_at DESC
            LIMIT 20
        """,
            (start_date.strftime("%Y-%m-%d"),),
        ).fetchall()

        if recent_nominations:
            for nom in recent_nominations:
                status_icon = (
                    "[Approved]"
                    if nom[6] == "approved"
                    else "[Pending]" if nom[6] == "pending" else "[Rejected]"
                )

                col1, col2, col3 = st.columns([3, 2, 1])
                with col1:
                    st.write(f"**{nom[0]}** → **{nom[2] or 'External'}**")
                    st.caption(
                        f"{nom[1]} → {nom[3] or 'External'} | {nom[4].replace('_', ' ').title()}"
                    )

                with col2:
                    st.write(f"Created: {nom[5][:10]}")
                    st.write(f"Status: {nom[6]}")

                with col3:
                    st.write(f"{status_icon}")

                st.divider()
        else:
            st.info("No recent nominations found")

        # Nomination completion by user
        st.subheader("Nomination Progress by User")

        user_progress = conn.execute(
            """
            SELECT 
                u.first_name || ' ' || u.last_name as user_name,
                u.vertical,
                COUNT(fr.request_id) as nominations_made,
                SUM(CASE WHEN fr.approval_status = 'approved' THEN 1 ELSE 0 END) as approved,
                SUM(CASE WHEN fr.approval_status = 'pending' THEN 1 ELSE 0 END) as pending,
                SUM(CASE WHEN fr.approval_status = 'rejected' THEN 1 ELSE 0 END) as rejected
            FROM users u
            LEFT JOIN feedback_requests fr ON u.user_type_id = fr.requester_id 
                AND fr.cycle_id = (SELECT cycle_id FROM review_cycles WHERE is_active = 1)
            WHERE u.is_active = 1
            GROUP BY u.user_type_id, u.first_name, u.last_name, u.vertical
            HAVING COUNT(fr.request_id) > 0
            ORDER BY nominations_made DESC
        """
        ).fetchall()

        if user_progress:
            # Show users who haven't reached 4 nominations
            incomplete_users = [user for user in user_progress if user[2] < 4]

            if incomplete_users:
                st.write(
                    f"**{len(incomplete_users)} users** have not completed their nominations:"
                )

                for user in incomplete_users[:10]:  # Show top 10
                    col1, col2, col3, col4 = st.columns([3, 1, 1, 1])

                    with col1:
                        st.write(f"**{user[0]}** ({user[1]})")
                    with col2:
                        progress = user[2] / 4.0
                        st.progress(progress)
                        st.caption(f"{user[2]}/4")
                    with col3:
                        st.write(f"[Approved] {user[3]}")
                    with col4:
                        st.write(f"[Pending] {user[4]}")

    except Exception as e:
        st.error(f"Error loading nomination data: {e}")

with tab3:
    st.subheader("Manager Approval Activity")

    try:
        # Approval statistics
        if active_cycle:
            approval_stats = conn.execute(
                """
                SELECT 
                    COUNT(*) as total_pending_approvals,
                    COUNT(DISTINCT approved_by) as active_approvers,
                    SUM(CASE WHEN approval_status = 'approved' THEN 1 ELSE 0 END) as total_approved,
                    SUM(CASE WHEN approval_status = 'rejected' THEN 1 ELSE 0 END) as total_rejected
                FROM feedback_requests
                WHERE cycle_id = ? AND approval_status != 'pending'
            """,
                (active_cycle["cycle_id"],),
            ).fetchone()

            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric(
                    "Total Processed",
                    (approval_stats[2] or 0) + (approval_stats[3] or 0),
                )
            with col2:
                st.metric("Approved", approval_stats[2] or 0)
            with col3:
                st.metric("Rejected", approval_stats[3] or 0)
            with col4:
                st.metric("Active Approvers", approval_stats[1] or 0)

        # Manager approval activity
        st.subheader("Manager Approval Performance")

        manager_stats = conn.execute(
            """
            SELECT 
                m.first_name || ' ' || m.last_name as manager_name,
                m.vertical as manager_dept,
                COUNT(fr.request_id) as total_requests,
                SUM(CASE WHEN fr.approval_status = 'approved' THEN 1 ELSE 0 END) as approved,
                SUM(CASE WHEN fr.approval_status = 'rejected' THEN 1 ELSE 0 END) as rejected,
                SUM(CASE WHEN fr.approval_status = 'pending' THEN 1 ELSE 0 END) as pending,
                MIN(fr.approval_date) as first_approval,
                MAX(fr.approval_date) as last_approval
            FROM feedback_requests fr
            JOIN users req ON fr.requester_id = req.user_type_id
            JOIN users m ON req.reporting_manager_email = m.email
            WHERE fr.cycle_id = (SELECT cycle_id FROM review_cycles WHERE is_active = 1)
            GROUP BY m.user_type_id, m.first_name, m.last_name, m.vertical
            HAVING COUNT(fr.request_id) > 0
            ORDER BY total_requests DESC
        """
        ).fetchall()

        if manager_stats:
            for manager in manager_stats:
                with st.expander(
                    f"[Manager] {manager[0]} ({manager[1]}) - {manager[2]} requests"
                ):
                    col1, col2 = st.columns(2)

                    with col1:
                        st.write(f"**Total Requests:** {manager[2]}")
                        st.write(
                            f"**Approved:** {manager[3]} ({(manager[3]/manager[2]*100):.1f}%)"
                        )
                        st.write(
                            f"**Rejected:** {manager[4]} ({(manager[4]/manager[2]*100):.1f}%)"
                        )
                        st.write(f"**Pending:** {manager[5]}")

                    with col2:
                        if manager[6]:
                            st.write(f"**First Approval:** {manager[6][:10]}")
                        if manager[7]:
                            st.write(f"**Last Approval:** {manager[7][:10]}")

                        if manager[5] > 0:
                            st.warning(
                                f"[Warning] {manager[5]} approvals still pending"
                            )
        else:
            st.info("No manager approval activity found")

    except Exception as e:
        st.error(f"Error loading approval data: {e}")

with tab4:
    st.subheader("Feedback Completion Activity")

    try:
        # Feedback completion stats
        if active_cycle:
            feedback_stats = conn.execute(
                """
                SELECT 
                    COUNT(*) as total_requests,
                    SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) as completed,
                    SUM(CASE WHEN status = 'approved' AND reviewer_status = 'accepted' THEN 1 ELSE 0 END) as in_progress,
                    COUNT(DISTINCT reviewer_id) as total_reviewers,
                    COUNT(DISTINCT CASE WHEN status = 'completed' THEN reviewer_id END) as active_reviewers
                FROM feedback_requests
                WHERE cycle_id = ? AND approval_status = 'approved'
            """,
                (active_cycle["cycle_id"],),
            ).fetchone()

            col1, col2, col3, col4, col5 = st.columns(5)
            with col1:
                st.metric("Total Requests", feedback_stats[0] or 0)
            with col2:
                st.metric("Completed", feedback_stats[1] or 0)
            with col3:
                completion_rate = (
                    (feedback_stats[1] / feedback_stats[0] * 100)
                    if feedback_stats[0] > 0
                    else 0
                )
                st.metric("Completion Rate", f"{completion_rate:.1f}%")
            with col4:
                st.metric("In Progress", feedback_stats[2] or 0)
            with col5:
                st.metric("Active Reviewers", feedback_stats[4] or 0)

        # Top feedback contributors
        st.subheader("Top Feedback Contributors")

        top_reviewers = conn.execute(
            """
            SELECT 
                u.first_name || ' ' || u.last_name as reviewer_name,
                u.vertical,
                COUNT(fr.request_id) as completed_reviews,
                AVG(LENGTH(resp.response_value)) as avg_response_length,
                MAX(fr.completed_at) as last_completion
            FROM feedback_requests fr
            JOIN users u ON fr.reviewer_id = u.user_type_id
            LEFT JOIN feedback_responses resp ON fr.request_id = resp.request_id
            WHERE fr.status = 'completed' 
                AND fr.cycle_id = (SELECT cycle_id FROM review_cycles WHERE is_active = 1)
            GROUP BY fr.reviewer_id, u.first_name, u.last_name, u.vertical
            ORDER BY completed_reviews DESC
            LIMIT 10
        """
        ).fetchall()

        if top_reviewers:
            for i, reviewer in enumerate(top_reviewers, 1):
                col1, col2, col3, col4 = st.columns([1, 3, 2, 2])

                with col1:
                    medal = (
                        "[1st]"
                        if i == 1
                        else "[2nd]" if i == 2 else "[3rd]" if i == 3 else f"[{i}]"
                    )
                    st.write(medal)

                with col2:
                    st.write(f"**{reviewer[0]}**")
                    st.caption(f"{reviewer[1]}")

                with col3:
                    st.write(f"{reviewer[2]} reviews")
                    if reviewer[3]:
                        st.caption(f"Avg response: {reviewer[3]:.0f} chars")

                with col4:
                    if reviewer[4]:
                        st.write(f"Last: {reviewer[4][:10]}")

        # Pending feedback by reviewer
        st.subheader("Reviewers with Pending Feedback")

        pending_reviewers = conn.execute(
            """
            SELECT 
                u.first_name || ' ' || u.last_name as reviewer_name,
                u.email,
                u.vertical,
                COUNT(fr.request_id) as pending_count,
                MIN(fr.created_at) as oldest_request,
                COUNT(dr.request_id) as draft_count
            FROM feedback_requests fr
            JOIN users u ON fr.reviewer_id = u.user_type_id
            LEFT JOIN draft_responses dr ON fr.request_id = dr.request_id
            WHERE fr.status = 'approved' AND fr.approval_status = 'approved' AND fr.reviewer_status = 'accepted'
                AND fr.cycle_id = (SELECT cycle_id FROM review_cycles WHERE is_active = 1)
            GROUP BY fr.reviewer_id, u.first_name, u.last_name, u.email, u.vertical
            ORDER BY pending_count DESC, oldest_request ASC
        """
        ).fetchall()

        if pending_reviewers:
            st.write(f"**{len(pending_reviewers)} reviewers** have pending feedback:")

            for reviewer in pending_reviewers:
                col1, col2, col3, col4 = st.columns([3, 2, 1, 1])

                with col1:
                    st.write(f"**{reviewer[0]}**")
                    st.caption(f"[Email] {reviewer[1]}")

                with col2:
                    st.write(f"[Dept] {reviewer[2]}")
                    if reviewer[4]:
                        days_old = (
                            datetime.now() - datetime.fromisoformat(reviewer[4])
                        ).days
                        st.caption(f"Oldest: {days_old} days")

                with col3:
                    st.write(f"**{reviewer[3]}** pending")
                    if reviewer[5] > 0:
                        st.caption(f"[Drafts] {reviewer[5]} drafts")

                with col4:
                    if st.button(
                        "[Remind] Remind", key=f"remind_feedback_{reviewer[1]}"
                    ):
                        st.info("Reminder sent!")
        else:
            st.success("[Complete] No pending feedback reviews!")

    except Exception as e:
        st.error(f"Error loading feedback data: {e}")

with tab5:
    st.subheader("Recent System Activity")

    # Real-time activity feed
    try:
        # Recent feedback submissions
        recent_feedback = conn.execute(
            """
            SELECT 
                'feedback_completed' as activity_type,
                u1.first_name || ' ' || u1.last_name as user_name,
                u2.first_name || ' ' || u2.last_name as target_name,
                fr.completed_at as activity_time,
                'completed feedback for' as action_text
            FROM feedback_requests fr
            JOIN users u1 ON fr.reviewer_id = u1.user_type_id
            JOIN users u2 ON fr.requester_id = u2.user_type_id
            WHERE fr.status = 'completed' AND DATE(fr.completed_at) >= ?
            
            UNION ALL
            
            SELECT 
                'nomination_submitted' as activity_type,
                u1.first_name || ' ' || u1.last_name as user_name,
                u2.first_name || ' ' || u2.last_name as target_name,
                fr.created_at as activity_time,
                'nominated' as action_text
            FROM feedback_requests fr
            JOIN users u1 ON fr.requester_id = u1.user_type_id
            LEFT JOIN users u2 ON fr.reviewer_id = u2.user_type_id
            WHERE DATE(fr.created_at) >= ?
            
            UNION ALL
            
            SELECT 
                'approval_processed' as activity_type,
                u1.first_name || ' ' || u1.last_name as user_name,
                u2.first_name || ' ' || u2.last_name as target_name,
                fr.approval_date as activity_time,
                CASE 
                    WHEN fr.approval_status = 'approved' THEN 'approved nomination for'
                    ELSE 'rejected nomination for'
                END as action_text
            FROM feedback_requests fr
            JOIN users u1 ON fr.approved_by = u1.user_type_id
            JOIN users u2 ON fr.requester_id = u2.user_type_id
            WHERE fr.approval_date IS NOT NULL AND DATE(fr.approval_date) >= ?
            
            ORDER BY activity_time DESC
            LIMIT 50
        """,
            (
                start_date.strftime("%Y-%m-%d"),
                start_date.strftime("%Y-%m-%d"),
                start_date.strftime("%Y-%m-%d"),
            ),
        ).fetchall()

        if recent_feedback:
            st.write(
                f"**{len(recent_feedback)} recent activities** in selected period:"
            )

            for activity in recent_feedback:
                activity_type = activity[0]
                user_name = activity[1]
                target_name = activity[2] or "external reviewer"
                activity_time = activity[3]
                action_text = activity[4]

                # Activity type icon
                icon = {
                    "feedback_completed": "[Completed]",
                    "nomination_submitted": "[Submitted]",
                    "approval_processed": "[Processed]",
                }.get(activity_type, "[Activity]")

                col1, col2 = st.columns([4, 1])
                with col1:
                    st.write(f"{icon} **{user_name}** {action_text} **{target_name}**")
                with col2:
                    if activity_time:
                        time_str = (
                            activity_time[:16]
                            if len(activity_time) > 16
                            else activity_time
                        )
                        st.caption(time_str)

                st.divider()
        else:
            st.info("No recent activity found in selected period")

        # Activity summary by day
        st.subheader("Daily Activity Summary")

        daily_activity = conn.execute(
            """
            SELECT 
                DATE(activity_time) as activity_date,
                activity_type,
                COUNT(*) as count
            FROM (
                SELECT 'feedback_completed' as activity_type, completed_at as activity_time
                FROM feedback_requests WHERE completed_at IS NOT NULL
                
                UNION ALL
                
                SELECT 'nomination_submitted' as activity_type, created_at as activity_time
                FROM feedback_requests
                
                UNION ALL
                
                SELECT 'approval_processed' as activity_type, approval_date as activity_time
                FROM feedback_requests WHERE approval_date IS NOT NULL
            ) activities
            WHERE DATE(activity_time) BETWEEN ? AND ?
            GROUP BY DATE(activity_time), activity_type
            ORDER BY activity_date DESC
        """,
            (start_date.strftime("%Y-%m-%d"), end_date.strftime("%Y-%m-%d")),
        ).fetchall()

        if daily_activity:
            # Group by date
            daily_summary = {}
            for row in daily_activity:
                date_key = row[0]
                if date_key not in daily_summary:
                    daily_summary[date_key] = {}
                daily_summary[date_key][row[1]] = row[2]

            # Display summary
            for date_key in sorted(daily_summary.keys(), reverse=True):
                activities = daily_summary[date_key]

                total_activities = sum(activities.values())

                with st.expander(f"[Date] {date_key} - {total_activities} activities"):
                    col1, col2, col3 = st.columns(3)

                    with col1:
                        nominations = activities.get("nomination_submitted", 0)
                        st.metric("Nominations", nominations)

                    with col2:
                        approvals = activities.get("approval_processed", 0)
                        st.metric("Approvals", approvals)

                    with col3:
                        feedback = activities.get("feedback_completed", 0)
                        st.metric("Feedback", feedback)

    except Exception as e:
        st.error(f"Error loading activity data: {e}")

st.markdown("---")
# Quick Actions removed - use navigation menu
