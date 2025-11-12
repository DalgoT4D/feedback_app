import streamlit as st
import pandas as pd
from datetime import datetime
from io import BytesIO
from services.db_helper import (
    get_anonymized_feedback_for_user, 
    get_feedback_progress_for_user,
    generate_feedback_excel_data,
    get_active_review_cycle,
    get_all_cycles,
    get_feedback_by_cycle
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
if progress['completed_requests'] > 0:
    st.subheader("Export Your Feedback")
    
    if st.button("Download My Feedback (Excel)", type="primary"):
        excel_data = generate_feedback_excel_data(user_id)
        
        if excel_data:
            df = pd.DataFrame(excel_data)
            
            # Create Excel file in memory
            output = BytesIO()
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                df.to_excel(writer, sheet_name='My_Feedback', index=False)
                
                # Auto-adjust column widths
                worksheet = writer.sheets['My_Feedback']
                for column in worksheet.columns:
                    max_length = 0
                    column = [cell for cell in column]
                    for cell in column:
                        try:
                            if len(str(cell.value)) > max_length:
                                max_length = len(str(cell.value))
                        except:
                            pass
                    adjusted_width = min(max_length + 2, 50)
                    worksheet.column_dimensions[column[0].column_letter].width = adjusted_width
            
            output.seek(0)
            
            st.download_button(
                label="Download Excel File",
                data=output.getvalue(),
                file_name=f"my_feedback_{user_id}_{datetime.now().strftime('%Y%m%d')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
            st.success("Excel file ready for download!")

# Display anonymized feedback
feedback_data = get_anonymized_feedback_for_user(user_id)

if feedback_data:
    st.subheader("Feedback Results (Anonymized)")
    st.info("All feedback is anonymized - you cannot see who provided each review.")
    
    for i, (request_id, feedback) in enumerate(feedback_data.items(), 1):
        with st.expander(f"Review #{i} - {feedback['relationship_type'].replace('_', ' ').title()}", expanded=False):
            st.write(f"**Completed:** {feedback['completed_at']}")
            st.write(f"**Reviewer Type:** {feedback['relationship_type'].replace('_', ' ').title()}")
            
            st.markdown("**Responses:**")
            
            for response in feedback['responses']:
                st.markdown(f"**{response['question_text']}**")
                
                if response['question_type'] == 'rating':
                    rating = response['rating_value']
                    stars = "*" * rating + "-" * (5 - rating)
                    st.write(f"{stars} ({rating}/5)")
                else:
                    if response['response_value']:
                        st.write(f"Response: {response['response_value']}")
                    else:
                        st.write("*No response provided*")
                
                st.write("")
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
    st.info(f"You have {progress['pending_requests']} pending responses. You can send anonymous reminders from the 'Reviews to Complete' page.")
