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

st.title("Previous Feedback Results")

# Get all cycles
all_cycles = get_all_cycles()
completed_cycles = [c for c in all_cycles if not c['is_active']]

# Cycle selection for historical data
if completed_cycles:
    cycle_options = [f"{c['cycle_display_name']} ({c['cycle_year']} {c['cycle_quarter']})" for c in completed_cycles]
    selected_cycle_display = st.selectbox("View Cycle:", cycle_options, key="cycle_selector")
    
    selected_cycle_index = cycle_options.index(selected_cycle_display)
    selected_cycle_id = completed_cycles[selected_cycle_index]['cycle_id']
else:
    selected_cycle_id = None

user_id = st.session_state["user_data"]["user_type_id"]

# Display anonymized feedback - filter by cycle if selected
if selected_cycle_id:
    feedback_data = get_feedback_by_cycle(user_id, selected_cycle_id)
    st.subheader(f"📊 Historical Feedback: {selected_cycle_display}")
else:
    feedback_data = None

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
    st.info("📭 No feedback results available for the selected cycle.")
