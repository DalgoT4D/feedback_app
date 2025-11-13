"""
Cycle Deadline Management Page
Allows HR to modify overall cycle deadlines and extend individual user deadlines.
"""

import streamlit as st
import pandas as pd
from datetime import datetime, date, timedelta
from services.db_helper import (
    get_active_review_cycle, get_users_progress_summary, 
    extend_user_deadline, get_user_deadline_extensions,
    update_cycle_deadlines, auto_accept_expired_nominations,
    get_users_for_selection, create_user_deadline_extension_table
)

# Check authentication and permissions
if 'authenticated' not in st.session_state or not st.session_state.authenticated:
    st.warning("Please log in to access this page.")
    st.stop()

if 'hr' not in [role['role_name'] for role in st.session_state.user_roles]:
    st.warning("You don't have permission to access this page.")
    st.stop()

# Create the deadline extension table if it doesn't exist
create_user_deadline_extension_table()

st.title("🕐 Cycle Deadline Management")

# Get active cycle
active_cycle = get_active_review_cycle()
if not active_cycle:
    st.warning("No active review cycle found.")
    st.stop()

st.info(f"Managing deadlines for: **{active_cycle['cycle_display_name']}**")

# Tab layout
tab1, tab2, tab3 = st.tabs(["📅 Modify Cycle Deadlines", "👥 Extend User Deadlines", "📊 Progress Overview"])

# Tab 1: Modify Overall Cycle Deadlines
with tab1:
    st.header("Modify Overall Cycle Deadlines")
    
    # Show current deadlines
    st.subheader("Current Deadlines")
    col1, col2 = st.columns(2)
    
    with col1:
        st.metric("Nomination Deadline", active_cycle['nomination_deadline'])
    with col2:
        st.metric("Feedback Deadline", active_cycle['feedback_deadline'])
    
    st.markdown("---")
    
    # Form to update deadlines
    st.subheader("Update Deadlines")
    with st.form("update_deadlines"):
        current_nom_deadline = datetime.strptime(active_cycle['nomination_deadline'], '%Y-%m-%d').date()
        current_feedback_deadline = datetime.strptime(active_cycle['feedback_deadline'], '%Y-%m-%d').date()
        
        new_nomination_deadline = st.date_input(
            "New Nomination Deadline",
            value=current_nom_deadline,
            min_value=date.today()
        )
        
        new_feedback_deadline = st.date_input(
            "New Feedback Deadline",
            value=current_feedback_deadline,
            min_value=new_nomination_deadline
        )
        
        if st.form_submit_button("Update Cycle Deadlines", type="primary"):
            if new_feedback_deadline <= new_nomination_deadline:
                st.error("Feedback deadline must be after nomination deadline.")
            else:
                success = update_cycle_deadlines(
                    active_cycle['cycle_id'],
                    new_nomination_deadline.strftime('%Y-%m-%d'),
                    new_feedback_deadline.strftime('%Y-%m-%d')
                )
                
                if success:
                    st.success("Cycle deadlines updated successfully!")
                    st.rerun()
                else:
                    st.error("Failed to update cycle deadlines.")

# Tab 2: Extend User Deadlines
with tab2:
    st.header("Extend Individual User Deadlines")
    
    # Show existing extensions
    existing_extensions = get_user_deadline_extensions(active_cycle['cycle_id'])
    
    if existing_extensions:
        st.subheader("Current Extensions")
        df_extensions = pd.DataFrame(existing_extensions)
        df_extensions = df_extensions[['user_name', 'deadline_type', 'original_deadline', 'extended_deadline', 'reason', 'extended_by']]
        df_extensions.columns = ['User', 'Deadline Type', 'Original', 'Extended To', 'Reason', 'Extended By']
        st.dataframe(df_extensions, use_container_width=True)
        st.markdown("---")
    
    # Form to create new extension
    st.subheader("Extend Deadline for User")
    
    with st.form("extend_user_deadline"):
        # User selection
        all_users = get_users_for_selection()
        user_options = {f"{user['name']} ({user['email']})": user['user_type_id'] for user in all_users}
        
        selected_user_str = st.selectbox(
            "Select User",
            options=list(user_options.keys()),
            help="Choose the user whose deadline you want to extend"
        )
        
        if selected_user_str:
            selected_user_id = user_options[selected_user_str]
            
            # Deadline type selection
            deadline_type = st.selectbox(
                "Deadline Type",
                options=['nomination', 'feedback'],
                help="Select which deadline to extend"
            )
            
            # Get current deadline for this user
            current_deadline_str = active_cycle[f'{deadline_type}_deadline']
            current_deadline = datetime.strptime(current_deadline_str, '%Y-%m-%d').date()
            
            st.info(f"Current {deadline_type} deadline: **{current_deadline}**")
            
            # New deadline input
            new_deadline = st.date_input(
                f"New {deadline_type.title()} Deadline",
                value=current_deadline + timedelta(days=7),
                min_value=current_deadline,
                help="Select the new deadline (must be after current deadline)"
            )
            
            # Reason for extension
            reason = st.text_area(
                "Reason for Extension",
                placeholder="Please provide a reason for this deadline extension...",
                help="Explain why this extension is being granted"
            )
            
            if st.form_submit_button("Extend Deadline", type="primary"):
                if not reason.strip():
                    st.error("Please provide a reason for the extension.")
                elif new_deadline <= current_deadline:
                    st.error("New deadline must be after the current deadline.")
                else:
                    success, message = extend_user_deadline(
                        active_cycle['cycle_id'],
                        selected_user_id,
                        deadline_type,
                        new_deadline.strftime('%Y-%m-%d'),
                        reason.strip(),
                        st.session_state["user_data"]["user_type_id"]
                    )
                    
                    if success:
                        st.success(f"Deadline extended successfully! {message}")
                        st.rerun()
                    else:
                        st.error(f"Failed to extend deadline: {message}")

# Tab 3: Progress Overview
with tab3:
    st.header("User Progress Overview")
    
    # Auto-acceptance controls
    st.subheader("Auto-Acceptance Controls")
    col1, col2 = st.columns([2, 1])
    
    with col1:
        st.info("""
        **Auto-Acceptance Rules:**
        - When nomination deadline passes, all pending manager approvals and reviewer acceptances are automatically approved
        - When feedback deadline passes, users can no longer fill out feedback forms
        """)
    
    with col2:
        if st.button("🔄 Run Auto-Acceptance", type="secondary"):
            success, message = auto_accept_expired_nominations()
            if success:
                st.success(message)
                st.rerun()
            else:
                st.info(message)
    
    st.markdown("---")
    
    # Progress accordions
    users_progress = get_users_progress_summary()
    
    if users_progress:
        # Create three accordions
        with st.expander("📝 Nomination Progress", expanded=True):
            nomination_data = []
            for user in users_progress:
                nomination_data.append({
                    'User': user['name'],
                    'Email': user['email'],
                    'Vertical': user['vertical'],
                    'Requested': user['nomination_progress']['requested'],
                    'Manager Approved': user['nomination_progress']['manager_approved'],
                    'Respondents Approved': user['nomination_progress']['respondent_approved'],
                    'Status': '✅ Complete' if user['nomination_progress']['is_complete'] else '⏳ Pending'
                })
            
            df_nomination = pd.DataFrame(nomination_data)
            
            # Color coding
            def color_nomination_status(val):
                if val == '✅ Complete':
                    return 'background-color: lightgreen'
                else:
                    return 'background-color: lightyellow'
            
            styled_df = df_nomination.style.map(color_nomination_status, subset=['Status'])
            st.dataframe(styled_df, use_container_width=True)
        
        with st.expander("📊 Feedback Progress"):
            feedback_data = []
            for user in users_progress:
                feedback_data.append({
                    'User': user['name'],
                    'Email': user['email'],
                    'Vertical': user['vertical'],
                    'Assigned Feedback': user['feedback_progress']['assigned'],
                    'Completed Feedback': user['feedback_progress']['completed'],
                    'Status': '✅ Complete' if user['feedback_progress']['is_complete'] else 
                             ('❌ No Feedback' if user['feedback_progress']['assigned'] == 0 else '⏳ Pending')
                })
            
            df_feedback = pd.DataFrame(feedback_data)
            
            # Color coding for feedback
            def color_feedback_status(val):
                if val == '✅ Complete':
                    return 'background-color: lightgreen'
                elif val == '❌ No Feedback':
                    return 'background-color: lightgray'
                else:
                    return 'background-color: lightyellow'
            
            styled_df_feedback = df_feedback.style.map(color_feedback_status, subset=['Status'])
            st.dataframe(styled_df_feedback, use_container_width=True)
        
        with st.expander("📈 Overall Summary"):
            # Calculate summary statistics
            total_users = len(users_progress)
            nomination_complete = sum(1 for u in users_progress if u['nomination_progress']['is_complete'])
            feedback_complete = sum(1 for u in users_progress if u['feedback_progress']['is_complete'])
            
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                st.metric("Total Users", total_users)
            with col2:
                st.metric("Nomination Complete", f"{nomination_complete}/{total_users}")
            with col3:
                st.metric("Feedback Complete", f"{feedback_complete}/{total_users}")
            with col4:
                completion_rate = round((nomination_complete + feedback_complete) / (2 * total_users) * 100, 1) if total_users > 0 else 0
                st.metric("Overall Completion", f"{completion_rate}%")
    else:
        st.info("No user progress data available for the current cycle.")
