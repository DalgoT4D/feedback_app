import streamlit as st
import pandas as pd
from io import BytesIO
from datetime import datetime
from services.db_helper import (
    get_direct_reports,
    get_anonymized_feedback_for_user,
    get_feedback_progress_for_user,
    generate_feedback_excel_data,
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
    if st.button("Download Reportee Feedback (Excel)", type="primary"):
        excel_data = generate_feedback_excel_data(reportee['user_type_id'])
        if excel_data:
            df = pd.DataFrame(excel_data)
            output = BytesIO()
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                df.to_excel(writer, sheet_name='Reportee_Feedback', index=False)
            output.seek(0)
            st.download_button(
                label="Download Excel File",
                data=output.getvalue(),
                file_name=f"reportee_feedback_{reportee['user_type_id']}_{datetime.now().strftime('%Y%m%d')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )

st.markdown("---")
st.subheader("Anonymized Responses")
st.info("Reviewer identities are hidden. Only relationship type is shown.")

feedback_data = get_anonymized_feedback_for_user(reportee['user_type_id'])

if feedback_data:
    for i, (request_id, feedback) in enumerate(feedback_data.items(), 1):
        with st.expander(f"Review #{i} - {feedback['relationship_type'].replace('_', ' ').title()}"):
            st.write(f"Completed: {feedback['completed_at']}")
            for response in feedback['responses']:
                st.markdown(f"**{response['question_text']}**")
                if response['question_type'] == 'rating':
                    rating = response['rating_value']
                    stars = "*" * rating + "-" * (5 - rating)
                    st.write(f"{stars} ({rating}/5)")
                else:
                    st.write(response['response_value'] or "*No response provided*")
                st.write("")
else:
    st.info("No completed feedback available yet for this reportee.")
