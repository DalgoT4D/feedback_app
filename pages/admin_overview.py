import streamlit as st
import pandas as pd
from datetime import datetime
from services.db_helper import (
    get_connection,
    get_active_review_cycle,
    get_all_cycles
)

st.title("HR Admin Overview")
st.subheader("All Employee Reviews & Requests")

# Get connection
conn = get_connection()

# Cycle filter
active_cycle = get_active_review_cycle()
all_cycles = get_all_cycles()

col1, col2 = st.columns([3, 1])
with col1:
    if active_cycle:
        st.info(f"**Active Cycle:** {active_cycle['cycle_display_name'] or active_cycle['cycle_name']}")
    else:
        st.warning("No active review cycle")

with col2:
    if all_cycles:
        cycle_options = ["All Cycles", "Active Only"] + [f"{c['cycle_display_name']} ({c['cycle_year']} {c['cycle_quarter']})" for c in all_cycles]
        selected_filter = st.selectbox("Filter by Cycle:", cycle_options)
    else:
        selected_filter = "All Cycles"

# Tab layout for different views
tab1, tab2, tab3, tab4 = st.tabs(["All Requests", "Completed Reviews", "Pending Reviews", "Analytics"])

with tab1:
    st.subheader("All Feedback Requests")
    
    # Get all feedback requests with details
    query = """
    SELECT 
        fr.request_id,
        u1.first_name || ' ' || u1.last_name as requester_name,
        u1.email as requester_email,
        u1.vertical as requester_vertical,
        u2.first_name || ' ' || u2.last_name as reviewer_name,
        u2.email as reviewer_email,
        u2.vertical as reviewer_vertical,
        fr.relationship_type,
        fr.status,
        fr.approval_status,
        u3.first_name || ' ' || u3.last_name as approved_by_name,
        fr.created_at,
        fr.completed_at,
        rc.cycle_display_name,
        rc.cycle_year,
        rc.cycle_quarter,
        fr.rejection_reason
    FROM feedback_requests fr
    JOIN users u1 ON fr.requester_id = u1.user_type_id
    JOIN users u2 ON fr.reviewer_id = u2.user_type_id
    LEFT JOIN users u3 ON fr.approved_by = u3.user_type_id
    JOIN review_cycles rc ON fr.cycle_id = rc.cycle_id
    ORDER BY fr.created_at DESC
    """
    
    cursor = conn.execute(query)
    requests_data = cursor.fetchall()
    
    if requests_data:
        # Convert to DataFrame for easier filtering
        df = pd.DataFrame(requests_data, columns=[
            'Request ID', 'Requester', 'Requester Email', 'Requester Dept',
            'Reviewer', 'Reviewer Email', 'Reviewer Dept', 'Relationship',
            'Status', 'Approval Status', 'Approved By', 'Created At', 'Completed At',
            'Cycle Name', 'Cycle Year', 'Cycle Quarter', 'Rejection Reason'
        ])
        
        # Filter controls
        col1, col2, col3 = st.columns(3)
        with col1:
            status_filter = st.multiselect(
                "Filter by Status:",
                options=df['Status'].unique(),
                default=df['Status'].unique()
            )
        with col2:
            approval_filter = st.multiselect(
                "Filter by Approval:",
                options=df['Approval Status'].unique(),
                default=df['Approval Status'].unique()
            )
        with col3:
            dept_filter = st.multiselect(
                "Filter by Department:",
                options=sorted(df['Requester Dept'].unique()),
                default=sorted(df['Requester Dept'].unique())
            )
        
        # Apply filters
        filtered_df = df[
            (df['Status'].isin(status_filter)) &
            (df['Approval Status'].isin(approval_filter)) &
            (df['Requester Dept'].isin(dept_filter))
        ]
        
        st.write(f"**{len(filtered_df)}** requests found")
        
        # Display data in expandable format
        for idx, row in filtered_df.iterrows():
            status_emoji = "Completed" if row['Status'] == 'completed' else "In Progress" if row['Status'] == 'approved' else "Rejected" if row['Approval Status'] == 'rejected' else "Pending"
            
            with st.expander(f"[{status_emoji}] {row['Requester']} → {row['Reviewer']} ({row['Relationship'].replace('_', ' ').title()})"):
                col1, col2 = st.columns(2)
                
                with col1:
                    st.write(f"**Requester:** {row['Requester']} ({row['Requester Dept']})")
                    st.write(f"**Email:** {row['Requester Email']}")
                    st.write(f"**Reviewer:** {row['Reviewer']} ({row['Reviewer Dept']})")
                    st.write(f"**Email:** {row['Reviewer Email']}")
                
                with col2:
                    st.write(f"**Status:** {row['Status']}")
                    st.write(f"**Approval:** {row['Approval Status']}")
                    if row['Approved By']:
                        st.write(f"**Approved By:** {row['Approved By']}")
                    st.write(f"**Cycle:** {row['Cycle Name']}")
                    st.write(f"**Created:** {row['Created At'][:10]}")
                    if row['Completed At']:
                        st.write(f"**Completed:** {row['Completed At'][:10]}")
                
                if row['Rejection Reason']:
                    st.write(f"**Rejection Reason:** {row['Rejection Reason']}")
    else:
        st.info("No feedback requests found.")

with tab2:
    st.subheader("Completed Reviews")
    
    # Get completed feedback with responses
    query = """
    SELECT 
        fr.request_id,
        u1.first_name || ' ' || u1.last_name as requester_name,
        u2.first_name || ' ' || u2.last_name as reviewer_name,
        fr.relationship_type,
        fr.completed_at,
        rc.cycle_display_name,
        COUNT(resp.response_id) as response_count
    FROM feedback_requests fr
    JOIN users u1 ON fr.requester_id = u1.user_type_id
    JOIN users u2 ON fr.reviewer_id = u2.user_type_id
    JOIN review_cycles rc ON fr.cycle_id = rc.cycle_id
    LEFT JOIN feedback_responses resp ON fr.request_id = resp.request_id
    WHERE fr.status = 'completed'
    GROUP BY fr.request_id, u1.first_name, u1.last_name, u2.first_name, u2.last_name, 
             fr.relationship_type, fr.completed_at, rc.cycle_display_name
    ORDER BY fr.completed_at DESC
    """
    
    cursor = conn.execute(query)
    completed_data = cursor.fetchall()
    
    if completed_data:
        for row in completed_data:
            col1, col2, col3 = st.columns([3, 2, 1])
            
            with col1:
                st.write(f"**{row[0]}:** {row[1]} ← {row[2]}")
                st.caption(f"{row[3].replace('_', ' ').title()} | {row[5]}")
            
            with col2:
                st.write(f"Completed: {row[4][:10]}")
                st.write(f"Responses: {row[6]}")
            
            with col3:
                if st.button("View", key=f"view_completed_{row[0]}"):
                    # TODO: Add detailed view
                    st.info("Detailed view coming soon!")
            
            st.divider()
    else:
        st.info("No completed reviews found.")

with tab3:
    st.subheader("Pending Reviews")
    
    # Get pending reviews (approved but not completed)
    query = """
    SELECT 
        fr.request_id,
        u1.first_name || ' ' || u1.last_name as requester_name,
        u1.email as requester_email,
        u2.first_name || ' ' || u2.last_name as reviewer_name,
        u2.email as reviewer_email,
        fr.relationship_type,
        fr.created_at,
        rc.cycle_display_name,
        COALESCE(draft_count.count, 0) as draft_responses
    FROM feedback_requests fr
    JOIN users u1 ON fr.requester_id = u1.user_type_id
    JOIN users u2 ON fr.reviewer_id = u2.user_type_id
    JOIN review_cycles rc ON fr.cycle_id = rc.cycle_id
    LEFT JOIN (
        SELECT request_id, COUNT(*) as count
        FROM draft_responses
        GROUP BY request_id
    ) draft_count ON fr.request_id = draft_count.request_id
    WHERE fr.status = 'approved' AND fr.approval_status = 'approved'
    ORDER BY fr.created_at ASC
    """
    
    cursor = conn.execute(query)
    pending_data = cursor.fetchall()
    
    if pending_data:
        st.write(f"**{len(pending_data)}** reviews pending completion")
        
        for row in pending_data:
            col1, col2, col3 = st.columns([3, 2, 1])
            
            with col1:
                st.write(f"**{row[1]}** requested feedback from")
                st.write(f"**{row[3]}** ({row[5].replace('_', ' ').title()})")
                st.caption(f"Reviewer: {row[4]}")
            
            with col2:
                days_pending = (datetime.now() - datetime.fromisoformat(row[6])).days
                st.write(f"Pending: {days_pending} days")
                if row[8] > 0:
                    st.write(f"Draft responses: {row[8]}")
                else:
                    st.write("Status: Not started")
                st.write(f"Cycle: {row[7]}")
            
            with col3:
                if st.button("Send Reminder", key=f"remind_{row[0]}"):
                    # TODO: Add reminder functionality
                    st.info("Reminder sent!")
            
            st.divider()
    else:
        st.success("No pending reviews!")

with tab4:
    st.subheader("Analytics Overview")
    
    # Get summary statistics
    stats_query = """
    SELECT 
        COUNT(*) as total_requests,
        SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) as completed_requests,
        SUM(CASE WHEN status = 'approved' AND approval_status = 'approved' THEN 1 ELSE 0 END) as pending_requests,
        SUM(CASE WHEN approval_status = 'rejected' THEN 1 ELSE 0 END) as rejected_requests,
        SUM(CASE WHEN approval_status = 'pending' THEN 1 ELSE 0 END) as awaiting_approval
    FROM feedback_requests
    """
    
    cursor = conn.execute(stats_query)
    stats = cursor.fetchone()
    
    if stats:
        col1, col2, col3, col4, col5 = st.columns(5)
        
        with col1:
            st.metric("Total Requests", stats[0])
        with col2:
            st.metric("Completed", stats[1])
        with col3:
            st.metric("Pending", stats[2])
        with col4:
            st.metric("Rejected", stats[3])
        with col5:
            st.metric("Awaiting Approval", stats[4])
        
        # Completion rate
        if stats[0] > 0:
            completion_rate = (stats[1] / stats[0]) * 100
            st.metric("Completion Rate", f"{completion_rate:.1f}%")
            
            progress_bar = st.progress(completion_rate / 100)
    
    # Department-wise breakdown
    dept_query = """
    SELECT 
        u.vertical,
        COUNT(*) as total_requests,
        SUM(CASE WHEN fr.status = 'completed' THEN 1 ELSE 0 END) as completed
    FROM feedback_requests fr
    JOIN users u ON fr.requester_id = u.user_type_id
    GROUP BY u.vertical
    ORDER BY total_requests DESC
    """
    
    cursor = conn.execute(dept_query)
    dept_data = cursor.fetchall()
    
    if dept_data:
        st.subheader("Department-wise Summary")
        
        dept_df = pd.DataFrame(dept_data, columns=['Department', 'Total Requests', 'Completed'])
        dept_df['Completion Rate %'] = (dept_df['Completed'] / dept_df['Total Requests'] * 100).round(1)
        
        st.dataframe(dept_df, use_container_width=True)