import streamlit as st
from services.db_helper import get_pending_reviews_for_user, get_active_review_cycle, get_all_cycles

st.title("Complete Reviews")

# Check if there's an active review cycle
active_cycle = get_active_review_cycle()
pending_reviews = [] # Initialize pending_reviews
if not active_cycle:
    st.warning("No active review cycle found. Contact HR to start a new feedback cycle.")
    
    # Show historical cycles
    all_cycles = get_all_cycles()
    if all_cycles:
        st.subheader("Previous Cycles")
        st.info("While there's no active cycle, here are the previous feedback cycles for reference:")
        for cycle in all_cycles[:3]:  # Show last 3 cycles
            status_icon = "[Active]" if cycle['is_active'] else "[Completed]"
            st.write(f"{status_icon} **{cycle['cycle_display_name']}** ({cycle['cycle_year']} {cycle['cycle_quarter']}) - Status: {cycle['status']}")
else:
    st.info(f"**Active Cycle:** {active_cycle['cycle_display_name'] or active_cycle['cycle_name']} | **Feedback Deadline:** {active_cycle['feedback_deadline']}")

    user_id = st.session_state["user_data"]["user_type_id"]

    # Get pending reviews
    pending_reviews = get_pending_reviews_for_user(user_id)

    if not pending_reviews:
        st.success("You have no pending feedback reviews!")
        st.info("When colleagues request your feedback, their requests will appear here.")
    else:
        st.write(f"You have **{len(pending_reviews)}** feedback review(s) to complete:")
        
        for i, review in enumerate(pending_reviews, 1):
            request_id = review[0]
            requester_name = f"{review[1]} {review[2]}"
            requester_vertical = review[3]
            created_at = review[4]
            relationship_type = review[5]
            draft_count = review[6]
            
            with st.container():
                col1, col2, col3 = st.columns([3, 2, 1])
                
                with col1:
                    st.write(f"**{i}. Feedback for {requester_name}**")
                    st.write(f"Department: {requester_vertical}")
                    st.write(f"Relationship: {relationship_type.replace('_', ' ').title()}")
                
                with col2:
                    st.write(f"Requested: {created_at[:10]}")
                    if draft_count > 0:
                        st.write("*Draft saved*")
                    else:
                        st.write("*Not started*")
                
                with col3:
                    if st.button(f"Complete Review", key=f"complete_{request_id}", type="primary"):
                        # Set the selected review in session state and switch to provide feedback page
                        st.session_state['selected_review_id'] = request_id
                        st.switch_page("app_pages/provide_feedback.py")
                
                st.divider()

st.markdown("---")
st.subheader("About Feedback Reviews")
st.write("""
- **Confidential**: Your responses will be anonymized when shared with the requester
- **Draft Saving**: You can save your progress and complete reviews later
- **Different Questions**: Question sets vary based on your relationship with the requester
- **Thoughtful Responses**: Take time to provide constructive and helpful feedback
""")

# Show information about question types
with st.expander("What types of questions will I see?"):
    st.write("""
    **For Peers/Internal Stakeholders/Managers:**
    - Collaboration, Communication, Reliability, Ownership (Trust)
    - Open-ended questions about strengths and areas for improvement
    
    **For Direct Reportees (reviewing your manager/lead):**
    - Approachability, Openness to feedback, Clarity in direction, Communication effectiveness
    - Leadership feedback
    
    **For External Stakeholders:**
    - Professionalism, Reliability, Responsiveness, Communication clarity
    - Understanding of needs, Quality of delivery
    - Collaboration and delivery examples
    """)

if pending_reviews:
    st.info("**Tip:** You can save drafts and return later to complete your reviews. All questions must be answered before final submission.")
