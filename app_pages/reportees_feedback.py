import streamlit as st
from services.db_helper import (
    get_direct_reports,
    get_anonymized_feedback_for_user,
    get_feedback_progress_for_user,
    generate_feedback_excel_data,
)
from app_pages.components.feedback_display import (
    ensure_feedback_styles,
    render_rating_card,
    render_text_card,
    build_feedback_excel,
)

st.title("Reportees' Feedback (Anonymized)")
st.markdown("View anonymized feedback received by your direct reports.")

user_data = st.session_state.get("user_data", {})
manager_email = user_data.get("email")

if not manager_email:
    st.error("Unable to determine your user details. Please re-login.")
    st.stop()

# Load direct reports
reportees = get_direct_reports(manager_email)

if not reportees:
    st.info("No direct reports found or you do not have any active reportees.")
    st.stop()

# Selection UI
options = [f"{r['name']} ({r['designation'] or 'N/A'})" for r in reportees]
selected = st.selectbox("Select a reportee:", options)
selected_index = options.index(selected)
reportee = reportees[selected_index]

st.markdown("---")
st.subheader(f"Feedback for {reportee['name']}")
st.caption(f"Department: {reportee['vertical'] or 'N/A'} | Email: {reportee['email']}")

# Progress for the reportee
progress = get_feedback_progress_for_user(reportee['user_type_id'])

col1, col2, col3 = st.columns(3)
with col1:
    st.metric("Responses Received", f"{progress['completed_requests']}/{progress['total_requests']}")
with col2:
    st.metric("Pending Responses", progress['pending_requests'])
with col3:
    st.metric("Awaiting Approval", progress['awaiting_approval'])

# Export anonymized feedback
if progress['completed_requests'] > 0:
    excel_rows = generate_feedback_excel_data(reportee['user_type_id'])
    excel_bytes, excel_filename = build_feedback_excel(
        excel_rows,
        f"reportee_feedback_{reportee['user_type_id']}",
        sheet_name="Reportee_Feedback",
    )
    if excel_bytes:
        st.download_button(
            label="Download Reportee Feedback (Excel)",
            data=excel_bytes,
            file_name=excel_filename,
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            type="primary",
            use_container_width=True,
        )

st.markdown("---")
st.subheader("Anonymized Responses")
st.info("Reviewer identities are hidden. Only relationship type is shown.")

feedback_data = get_anonymized_feedback_for_user(reportee['user_type_id'])

if feedback_data:
    ensure_feedback_styles()
    for i, (request_id, feedback) in enumerate(feedback_data.items(), 1):
        with st.expander(f"Review #{i} - {feedback['relationship_type'].replace('_', ' ').title()}"):
            st.write(f"Completed: {feedback['completed_at']}")
            for response in feedback['responses']:
                if response['question_type'] == 'rating':
                    render_rating_card(response['question_text'], response['rating_value'])
                else:
                    render_text_card(response['question_text'], response['response_value'])
else:
    st.info("No completed feedback available yet for this reportee.")
