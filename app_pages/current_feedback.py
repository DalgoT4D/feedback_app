import streamlit as st
from services.db_helper import (
    get_anonymized_feedback_for_user, 
    get_feedback_progress_for_user,
    generate_feedback_excel_data,
    get_active_review_cycle,
)
from app_pages.components.feedback_display import (
    ensure_feedback_styles,
    render_rating_card,
    render_text_card,
    build_feedback_excel,
)

st.title("Current Feedback Results")

# Check if there's an active review cycle
active_cycle = get_active_review_cycle()

if active_cycle:
    st.info(f"**Active Cycle:** {active_cycle['cycle_display_name'] or active_cycle['cycle_name']} | **Feedback Deadline:** {active_cycle['feedback_deadline']}")
else:
    st.warning("No active review cycle found.")
    st.stop()

user_id = st.session_state["user_data"]["user_type_id"]

# Progress tracking
progress = get_feedback_progress_for_user(user_id)
st.subheader("Feedback Progress")

col1, col2, col3 = st.columns(3)
with col1:
    st.metric("Responses Received", f"{progress['completed_requests']}/{progress['total_requests']}")
with col2:
    st.metric("Pending Responses", progress['pending_requests'])
with col3:
    st.metric("Awaiting Approval", progress['awaiting_approval'])

# Download Excel section
excel_rows = []
excel_bytes = None
excel_filename = None
if progress['completed_requests'] > 0:
    st.subheader("Export Your Feedback")
    excel_rows = generate_feedback_excel_data(user_id)
    excel_bytes, excel_filename = build_feedback_excel(
        excel_rows, f"my_feedback_{user_id}", sheet_name="My_Feedback"
    )
    if excel_bytes:
        st.download_button(
            label="Download My Feedback (Excel)",
            data=excel_bytes,
            file_name=excel_filename,
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            type="primary",
            use_container_width=True,
        )

# Display anonymized feedback
feedback_data = get_anonymized_feedback_for_user(user_id)

if feedback_data:
    ensure_feedback_styles()
    st.subheader("Feedback Results (Anonymized)")
    st.info("All feedback is anonymized - you cannot see who provided each review.")
    
    for i, (request_id, feedback) in enumerate(feedback_data.items(), 1):
        with st.expander(f"Review #{i} - {feedback['relationship_type'].replace('_', ' ').title()}", expanded=False):
            st.write(f"**Completed:** {feedback['completed_at']}")
            st.write(f"**Reviewer Type:** {feedback['relationship_type'].replace('_', ' ').title()}")
            
            st.markdown("**Responses:**")
            
            for response in feedback['responses']:
                if response['question_type'] == 'rating':
                    render_rating_card(response['question_text'], response['rating_value'])
                else:
                    render_text_card(response['question_text'], response['response_value'])
else:
    if progress['total_requests'] == 0:
        st.info("You haven't requested any feedback yet. Use the 'Request Feedback' page to get started!")
    elif progress['awaiting_approval'] > 0:
        st.info("Your feedback requests are awaiting manager approval.")
    elif progress['pending_requests'] > 0:
        st.info("Your feedback requests have been approved and sent to reviewers. Results will appear here once completed.")
    else:
        st.info("📭 No feedback results available yet.")

# Show helpful information
st.markdown("---")
st.subheader("About Your Feedback")
st.write("""
- **Anonymized**: You can see the feedback but not who provided it
- **Complete Picture**: Different question sets based on your relationship with each reviewer
- **Export Option**: Download your feedback to Excel for personal records
- **Progress Tracking**: See how many responses you've received without knowing who responded
""")

if progress['pending_requests'] > 0:
    st.info(f"You have {progress['pending_requests']} pending responses. You can send anonymous reminders from the 'Provide Feedback' page.")
