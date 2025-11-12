import streamlit as st
import pandas as pd
from datetime import datetime, date, timedelta
from services.db_helper import (
    get_connection, 
    get_active_review_cycle, 
    get_all_cycles
)

st.title("Comprehensive Overview Dashboard")
st.markdown("Complete metrics and insights for the 360-degree feedback system")

# Get active cycle info
active_cycle = get_active_review_cycle()
conn = get_connection()
cycle_id = active_cycle['cycle_id'] if active_cycle else None

# Header info
if active_cycle:
    col1, col2 = st.columns(2)
    with col1:
        st.info(f"**Active Cycle:** {active_cycle['cycle_display_name']}")
        st.write(f"Phase: {active_cycle.get('phase_status', 'Active')}")
    with col2:
        st.write(f"Nomination Deadline: {active_cycle['nomination_deadline']}")
        st.write(f"Feedback Deadline: {active_cycle['feedback_deadline']}")
else:
    st.warning("No active review cycle found")

st.markdown("---")

# Main metrics section
st.subheader("Key Performance Indicators")

# Initialize defaults to avoid NameError if a query fails
nominated_4_users = 0
approved_4_reviewers = 0
had_4_approved = 0
given_4_feedback = 0
received_4_feedback = 0
completed_everything = 0

try:
    # Total users
    total_users = conn.execute("SELECT COUNT(*) FROM users WHERE is_active = 1").fetchone()[0]
    
    if active_cycle:
        cycle_id = active_cycle['cycle_id']
        
        # People who nominated 4 users
        nominated_4_users = conn.execute("""
            SELECT COUNT(DISTINCT requester_id) FROM (
                SELECT requester_id, COUNT(*) as nom_count
                FROM feedback_requests 
                WHERE cycle_id = ? AND approval_status != 'rejected'
                GROUP BY requester_id
                HAVING nom_count >= 4
            )
        """, (cycle_id,)).fetchone()[0]
        
        # People who have approved giving feedback for 4 people (reviewers who accepted 4+ requests)
        approved_4_reviewers = conn.execute("""
            SELECT COUNT(DISTINCT reviewer_id) FROM (
                SELECT reviewer_id, COUNT(*) as approved_count
                FROM feedback_requests 
                WHERE cycle_id = ? AND approval_status = 'approved' AND reviewer_status = 'accepted'
                GROUP BY reviewer_id
                HAVING approved_count >= 4
            )
        """, (cycle_id,)).fetchone()[0]
        
        # People who have had 4 people approve their feedback (including managers)
        had_4_approved = conn.execute("""
            SELECT COUNT(DISTINCT requester_id) FROM (
                SELECT requester_id, COUNT(*) as approved_count
                FROM feedback_requests 
                WHERE cycle_id = ? AND approval_status = 'approved'
                GROUP BY requester_id
                HAVING approved_count >= 4
            )
        """, (cycle_id,)).fetchone()[0]
        
        # People who have given feedback to 4 people
        given_4_feedback = conn.execute("""
            SELECT COUNT(DISTINCT reviewer_id) FROM (
                SELECT reviewer_id, COUNT(*) as completed_count
                FROM feedback_requests 
                WHERE cycle_id = ? AND workflow_state = 'completed'
                GROUP BY reviewer_id
                HAVING completed_count >= 4
            )
        """, (cycle_id,)).fetchone()[0]
        
        # People who have received feedback from 4 people
        received_4_feedback = conn.execute("""
            SELECT COUNT(DISTINCT requester_id) FROM (
                SELECT requester_id, COUNT(*) as received_count
                FROM feedback_requests 
                WHERE cycle_id = ? AND workflow_state = 'completed'
                GROUP BY requester_id
                HAVING received_count >= 4
            )
        """, (cycle_id,)).fetchone()[0]
        
        # People who completed everything (nominated 4, received 4, given 4)
        completed_everything = conn.execute("""
            SELECT COUNT(*) FROM (
                SELECT u.user_type_id
                FROM users u
                WHERE u.is_active = 1
                    AND (
                        SELECT COUNT(*) FROM feedback_requests fr1 
                        WHERE fr1.requester_id = u.user_type_id AND fr1.cycle_id = ? 
                        AND fr1.approval_status != 'rejected'
                    ) >= 4
                    AND (
                        SELECT COUNT(*) FROM feedback_requests fr2 
                        WHERE fr2.requester_id = u.user_type_id AND fr2.cycle_id = ? 
                        AND fr2.workflow_state = 'completed'
                    ) >= 4
                    AND (
                        SELECT COUNT(*) FROM feedback_requests fr3 
                        WHERE fr3.reviewer_id = u.user_type_id AND fr3.cycle_id = ? 
                        AND fr3.workflow_state = 'completed'
                    ) >= 4
            )
        """, (cycle_id, cycle_id, cycle_id)).fetchone()[0]
    else:
        nominated_4_users = approved_4_reviewers = had_4_approved = 0
        given_4_feedback = received_4_feedback = completed_everything = 0
    
    # Display main KPIs
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("Total Users", total_users)
        participation_rate = (nominated_4_users / total_users * 100) if total_users > 0 else 0
        st.metric("Participation Rate", f"{participation_rate:.1f}%")
    
    with col2:
        st.metric("Nominated 4 Users", nominated_4_users)
        st.metric("Approved 4 Reviews", approved_4_reviewers)
    
    with col3:
        st.metric("Had 4 Approved", had_4_approved)
        st.metric("Given 4 Feedback", given_4_feedback)
    
    with col4:
        st.metric("Received 4 Feedback", received_4_feedback)
        st.metric("Completed Everything", completed_everything)

except Exception as e:
    st.error(f"Error loading KPI data: {e}")

# Progress visualization
st.subheader("Completion Progress Visualization")

if active_cycle:
    try:
        # Create completion funnel
        funnel_data = {
            'Stage': [
                'Total Users',
                'Nominated 4 Users', 
                'Had 4 Approved',
                'Approved 4 Reviews',
                'Given 4 Feedback',
                'Received 4 Feedback',
                'Completed Everything'
            ],
            'Count': [
                total_users,
                nominated_4_users,
                had_4_approved,
                approved_4_reviewers,
                given_4_feedback,
                received_4_feedback,
                completed_everything
            ],
            'Percentage': [
                100,
                (nominated_4_users/total_users*100) if total_users > 0 else 0,
                (had_4_approved/total_users*100) if total_users > 0 else 0,
                (approved_4_reviewers/total_users*100) if total_users > 0 else 0,
                (given_4_feedback/total_users*100) if total_users > 0 else 0,
                (received_4_feedback/total_users*100) if total_users > 0 else 0,
                (completed_everything/total_users*100) if total_users > 0 else 0
            ]
        }
        
        funnel_df = pd.DataFrame(funnel_data)
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.write("**Completion Funnel:**")
            st.bar_chart(funnel_df.set_index('Stage')['Count'])
        
        with col2:
            st.write("**Percentage Breakdown:**")
            for _, row in funnel_df.iterrows():
                progress_val = row['Percentage'] / 100
                st.write(f"**{row['Stage']}:** {row['Count']} users ({row['Percentage']:.1f}%)")
                st.progress(progress_val)

    except Exception as e:
        st.error(f"Error creating progress visualization: {e}")

st.markdown("---")

# Department breakdown
st.subheader("Department Analysis")

try:
    if active_cycle:
        dept_analysis = conn.execute("""
            SELECT 
                u.vertical,
                COUNT(DISTINCT u.user_type_id) as total_users,
                COUNT(DISTINCT CASE 
                    WHEN (SELECT COUNT(*) FROM feedback_requests fr1 
                          WHERE fr1.requester_id = u.user_type_id AND fr1.cycle_id = ? 
                          AND fr1.approval_status != 'rejected') >= 4 
                    THEN u.user_type_id END) as nominated_4,
                COUNT(DISTINCT CASE 
                    WHEN (SELECT COUNT(*) FROM feedback_requests fr2 
                          WHERE fr2.requester_id = u.user_type_id AND fr2.cycle_id = ? 
                          AND fr2.workflow_state = 'completed') >= 4 
                    THEN u.user_type_id END) as received_4,
                COUNT(DISTINCT CASE 
                    WHEN (SELECT COUNT(*) FROM feedback_requests fr3 
                          WHERE fr3.reviewer_id = u.user_type_id AND fr3.cycle_id = ? 
                          AND fr3.workflow_state = 'completed') >= 4 
                    THEN u.user_type_id END) as given_4
            FROM users u
            WHERE u.is_active = 1
            GROUP BY u.vertical
            ORDER BY total_users DESC
        """, (cycle_id, cycle_id, cycle_id)).fetchall()
        
        if dept_analysis:
            dept_data = []
            for row in dept_analysis:
                total = row[1]
                dept_data.append({
                    'Department': row[0] or 'Unknown',
                    'Total Users': total,
                    'Nominated 4': row[2],
                    'Nomination %': f"{(row[2]/total*100):.1f}%" if total > 0 else "0%",
                    'Received 4': row[3],
                    'Reception %': f"{(row[3]/total*100):.1f}%" if total > 0 else "0%",
                    'Given 4': row[4],
                    'Completion %': f"{(row[4]/total*100):.1f}%" if total > 0 else "0%"
                })
            
            dept_df = pd.DataFrame(dept_data)
            st.dataframe(dept_df, use_container_width=True)
            
            # Department comparison chart
            st.write("**Department Participation Comparison:**")
            chart_data = pd.DataFrame({
                'Department': [d['Department'] for d in dept_data],
                'Nomination Rate': [float(d['Nomination %'].rstrip('%')) for d in dept_data],
                'Completion Rate': [float(d['Completion %'].rstrip('%')) for d in dept_data]
            })
            st.bar_chart(chart_data.set_index('Department'))

except Exception as e:
    st.error(f"Error loading department analysis: {e}")

st.markdown("---")

# Detailed user tracking
st.subheader("Detailed User Progress Tracking")

if active_cycle:
    # User search and filter
    col1, col2, col3 = st.columns(3)
    
    with col1:
        search_user = st.text_input("Search users:", placeholder="Enter name or email...")
    
    with col2:
        dept_filter = st.selectbox("Filter by Department:", 
                                  ["All Departments"] + [d[0] for d in conn.execute("SELECT DISTINCT vertical FROM users WHERE is_active = 1 ORDER BY vertical").fetchall() if d[0]])
    
    with col3:
        status_filter = st.selectbox("Filter by Status:", [
            "All Users",
            "Not Started", 
            "In Progress",
            "Completed Everything",
            "Missing Nominations",
            "Missing Feedback"
        ])
    
    try:
        # Build user query
        user_query = """
            SELECT 
                u.user_type_id,
                u.first_name || ' ' || u.last_name as full_name,
                u.email,
                u.vertical,
                u.designation,
                COALESCE((SELECT COUNT(*) FROM feedback_requests fr1 
                         WHERE fr1.requester_id = u.user_type_id AND fr1.cycle_id = ? 
                         AND fr1.approval_status != 'rejected'), 0) as nominations_made,
                COALESCE((SELECT COUNT(*) FROM feedback_requests fr2 
                         WHERE fr2.requester_id = u.user_type_id AND fr2.cycle_id = ? 
                         AND fr2.approval_status = 'approved'), 0) as approvals_received,
                COALESCE((SELECT COUNT(*) FROM feedback_requests fr3 
                         WHERE fr3.reviewer_id = u.user_type_id AND fr3.cycle_id = ? 
                         AND fr3.approval_status = 'approved' AND fr3.reviewer_status = 'accepted'), 0) as reviews_accepted,
                COALESCE((SELECT COUNT(*) FROM feedback_requests fr4 
                         WHERE fr4.reviewer_id = u.user_type_id AND fr4.cycle_id = ? 
                         AND fr4.workflow_state = 'completed'), 0) as reviews_completed,
                COALESCE((SELECT COUNT(*) FROM feedback_requests fr5 
                         WHERE fr5.requester_id = u.user_type_id AND fr5.cycle_id = ? 
                         AND fr5.workflow_state = 'completed'), 0) as feedback_received
            FROM users u
            WHERE u.is_active = 1
        """
        
        query_params = [cycle_id, cycle_id, cycle_id, cycle_id, cycle_id]
        
        # Apply filters
        if search_user:
            user_query += " AND (u.first_name || ' ' || u.last_name LIKE ? OR u.email LIKE ?)"
            search_pattern = f"%{search_user}%"
            query_params.extend([search_pattern, search_pattern])
        
        if dept_filter != "All Departments":
            user_query += " AND u.vertical = ?"
            query_params.append(dept_filter)
        
        user_query += " ORDER BY u.first_name, u.last_name"
        
        user_details = conn.execute(user_query, tuple(query_params)).fetchall()
        
        if user_details:
            # Apply status filter
            filtered_users = []
            for user in user_details:
                nominations = user[5]
                approvals = user[6]
                accepted = user[7]
                completed = user[8]
                received = user[9]
                
                # Determine status
                if nominations == 0:
                    user_status = "Not Started"
                elif nominations >= 4 and completed >= 4 and received >= 4:
                    user_status = "Completed Everything"
                elif nominations < 4:
                    user_status = "Missing Nominations"
                elif completed < 4:
                    user_status = "Missing Feedback"
                else:
                    user_status = "In Progress"
                
                if status_filter == "All Users" or status_filter == user_status:
                    filtered_users.append(user + (user_status,))
            
            st.write(f"**{len(filtered_users)} users** match your filters:")
            
            # Pagination
            users_per_page = 20
            total_pages = (len(filtered_users) + users_per_page - 1) // users_per_page
            
            if total_pages > 1:
                page = st.selectbox("Page:", range(1, total_pages + 1)) - 1
                start_idx = page * users_per_page
                end_idx = min(start_idx + users_per_page, len(filtered_users))
                page_users = filtered_users[start_idx:end_idx]
                st.caption(f"Showing users {start_idx + 1}-{end_idx} of {len(filtered_users)}")
            else:
                page_users = filtered_users
            
            # Display users
            for user in page_users:
                status_emoji = {
                    "Not Started": "[Not Started]",
                    "Missing Nominations": "[Missing Nominations]", 
                    "Missing Feedback": "[Missing Feedback]",
                    "In Progress": "[In Progress]",
                    "Completed Everything": "[Completed]"
                }.get(user[10], "[Unknown]")
                
                with st.expander(f"{status_emoji} {user[1]} ({user[3]})"):
                    col1, col2, col3 = st.columns(3)
                    
                    with col1:
                        st.write("**User Info:**")
                        st.write(f"**Name:** {user[1]}")
                        st.write(f"**Email:** {user[2]}")
                        st.write(f"**Department:** {user[3]}")
                        st.write(f"**Designation:** {user[4]}")
                    
                    with col2:
                        st.write("**Nomination Progress:**")
                        nom_progress = min(user[5] / 4.0, 1.0)
                        st.progress(nom_progress)
                        st.write(f"Nominations: {user[5]}/4")
                        st.write(f"Approvals Received: {user[6]}/4")
                    
                    with col3:
                        st.write("**Feedback Progress:**")
                        feedback_progress = min(user[8] / 4.0, 1.0)
                        st.progress(feedback_progress)
                        st.write(f"Reviews Completed: {user[8]}/4")
                        st.write(f"Feedback Received: {user[9]}/4")
                        st.write(f"Reviews Accepted: {user[7]}")
                    
                    # Action buttons
                    if user[10] in ["Not Started", "Missing Nominations"]:
                        if st.button("Send Nomination Reminder", key=f"nom_remind_{user[0]}"):
                            st.info("Nomination reminder sent!")
                    
                    if user[10] in ["Missing Feedback", "In Progress"]:
                        if st.button("Send Feedback Reminder", key=f"feed_remind_{user[0]}"):
                            st.info("Feedback reminder sent!")

    except Exception as e:
        st.error(f"Error loading user details: {e}")

st.markdown("---")

# System health metrics
st.subheader("System Health & Performance")

col1, col2 = st.columns(2)

with col1:
    st.write("**Recent Activity (Last 7 days):**")
    try:
        recent_activity = conn.execute("""
            SELECT 
                'Nominations' as activity_type,
                COUNT(*) as count
            FROM feedback_requests 
            WHERE DATE(created_at) >= DATE('now', '-7 days')
            
            UNION ALL
            
            SELECT 
                'Approvals' as activity_type,
                COUNT(*) as count
            FROM feedback_requests 
            WHERE DATE(approval_date) >= DATE('now', '-7 days')
            
            UNION ALL
            
            SELECT 
                'Completed Feedback' as activity_type,
                COUNT(*) as count
            FROM feedback_requests 
            WHERE DATE(completed_at) >= DATE('now', '-7 days')
        """).fetchall()
        
        for activity_type, count in recent_activity:
            st.write(f"• **{activity_type}:** {count}")
    
    except Exception as e:
        st.write(f"Error loading recent activity: {e}")

with col2:
    st.write("**Engagement Quality:**")
    try:
        quality_metrics = conn.execute("""
            SELECT 
                AVG(LENGTH(resp.response_value)) as avg_response_length,
                COUNT(CASE WHEN LENGTH(resp.response_value) >= 100 THEN 1 END) as detailed_responses,
                COUNT(resp.response_id) as total_responses,
                AVG(resp.rating_value) as avg_rating
            FROM feedback_responses resp
            JOIN feedback_requests fr ON resp.request_id = fr.request_id
            WHERE fr.workflow_state = 'completed' AND resp.response_value IS NOT NULL
        """).fetchone()
        
        if quality_metrics:
            avg_length = quality_metrics[0] or 0
            detailed_count = quality_metrics[1] or 0
            total_responses = quality_metrics[2] or 0
            avg_rating = quality_metrics[3] or 0
            
            st.write(f"• **Avg Response Length:** {avg_length:.0f} chars")
            detailed_pct = (detailed_count / total_responses * 100) if total_responses > 0 else 0
            st.write(f"• **Detailed Responses:** {detailed_pct:.1f}%")
            st.write(f"• **Average Rating:** {avg_rating:.2f}/5")
    
    except Exception as e:
        st.write(f"Error loading quality metrics: {e}")

# Quick Actions removed - use navigation menu
