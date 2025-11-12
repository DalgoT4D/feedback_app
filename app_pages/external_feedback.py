"""
External Stakeholder Feedback Form
Allows external stakeholders to provide feedback using their validated token.
"""

import streamlit as st
from services.db_helper import (
    get_questions_by_relationship_type, 
    complete_external_stakeholder_feedback,
    reject_external_stakeholder_request,
    get_active_review_cycle,
)

# Page config is handled by main.py

# Check if external authentication is valid
if not st.session_state.get("external_authenticated") or not st.session_state.get("external_token_data"):
    st.error("❌ Access denied. Please authenticate first.")
    if st.button("← Go to Login"):
        st.switch_page("login.py")
    st.stop()

token_data = st.session_state["external_token_data"]

# Check if already completed
if token_data["status"] == "completed":
    st.success("✅ You have already completed this feedback.")
    st.info("Thank you for your valuable feedback!")
    if st.button("← Return to Login"):
        st.switch_page("login.py")
    st.stop()

# Check if not accepted yet
if token_data["status"] != "accepted":
    st.warning("⚠️ Please accept the feedback request first.")
    if st.button("← Return to Login"):
        st.switch_page("login.py")
    st.stop()

# Display header
st.title("📝 Provide Feedback")

# Show only the feedback deadline prominently
active_cycle = get_active_review_cycle()
if active_cycle and active_cycle.get("feedback_deadline"):
    st.info(f"Feedback Deadline: {active_cycle['feedback_deadline']}")

# Show request details
st.subheader("Feedback Request Details")
col1, col2, col3 = st.columns(3)

with col1:
    st.write(f"**For:** {token_data['requester_name']}")
    st.write(f"**Department:** {token_data['requester_vertical']}")

with col2:
    st.write(f"**Your Role:** {token_data['relationship_type'].replace('_', ' ').title()}")
    st.write(f"**Review Cycle:** {token_data['cycle_name']}")

with col3:
    st.write(f"**Status:** Providing Feedback")

st.markdown("---")

# Get questions for the relationship type
questions = get_questions_by_relationship_type(token_data['relationship_type'])

if not questions:
    st.error("No questions found for this relationship type.")
    st.stop()

# Initialize response storage
if "external_responses" not in st.session_state:
    st.session_state["external_responses"] = {}

st.subheader("Feedback Questions")
st.info("Your responses will remain anonymous. Please provide honest and constructive feedback.")

# Create the feedback form
responses = {}
all_required_answered = True

for question in questions:
    question_id = question['question_id']
    question_text = question['question_text']
    question_type = question['question_type']
    
    st.markdown(f"**{question_text}**")
    
    if question_type == 'rating':
        # Rating scale (1-5)
        rating = st.select_slider(
            f"Rating for question {question_id}",
            options=[1, 2, 3, 4, 5],
            value=st.session_state["external_responses"].get(question_id, {}).get("rating_value", 3),
            format_func=lambda x: {
                1: "1 - Poor", 
                2: "2 - Below Average", 
                3: "3 - Average", 
                4: "4 - Good", 
                5: "5 - Excellent"
            }[x],
            key=f"rating_{question_id}",
            label_visibility="collapsed"
        )
        responses[question_id] = {"rating_value": rating, "response_value": None}
        
    elif question_type == 'text':
        # Text response
        existing_text = st.session_state["external_responses"].get(question_id, {}).get("response_value", "")
        text_response = st.text_area(
            f"Response for question {question_id}",
            value=existing_text,
            placeholder="Please provide your feedback here...",
            height=100,
            key=f"text_{question_id}",
            label_visibility="collapsed"
        )
        responses[question_id] = {"rating_value": None, "response_value": text_response}
        
        # Check if required text question is answered
        if not text_response.strip():
            all_required_answered = False
    
    st.markdown("---")

# Store responses in session state for recovery
st.session_state["external_responses"] = responses

# Action buttons
st.subheader("Submit Your Feedback")

col1, col2, col3 = st.columns([2, 1, 1])

with col1:
    if st.button("💾 Save as Draft", use_container_width=True):
        st.success("✅ Draft saved! You can continue later with the same token.")
        st.info("Your responses have been temporarily saved. You can return to complete them later.")

with col2:
    # Option to decline at this stage
    if st.button("❌ Decline to Continue", use_container_width=True):
        st.session_state["show_decline_form"] = True
        st.rerun()

with col3:
    # Submit button - check if all required fields are completed
    if not all_required_answered:
        st.button("📝 Submit Feedback", disabled=True, use_container_width=True)
        st.warning("⚠️ Please answer all text questions before submitting.")
    else:
        if st.button("📝 Submit Feedback", type="primary", use_container_width=True):
            # Final confirmation
            st.session_state["show_submit_confirmation"] = True
            st.rerun()

# Handle decline form
if st.session_state.get("show_decline_form", False):
    st.markdown("---")
    st.subheader("Decline to Continue")
    
    with st.form("decline_form"):
        st.write("Are you sure you want to decline to provide feedback?")
        decline_reason = st.text_area(
            "Reason for declining (optional)",
            placeholder="e.g., Insufficient working relationship, time constraints, etc."
        )
        
        col1, col2 = st.columns(2)
        with col1:
            confirm_decline = st.form_submit_button("Confirm Decline", type="secondary")
        with col2:
            cancel_decline = st.form_submit_button("Continue Feedback")
        
        if confirm_decline:
            reason = decline_reason.strip() if decline_reason else "Declined during feedback completion"
            success = reject_external_stakeholder_request(token_data, reason)
            if success:
                st.success("Your decision has been recorded. Thank you for your time.")
                st.session_state["external_token_data"]["status"] = "rejected"
                st.session_state["show_decline_form"] = False
                # Clear responses
                if "external_responses" in st.session_state:
                    del st.session_state["external_responses"]
                st.rerun()
            else:
                st.error("Failed to record your decision. Please try again.")
        
        if cancel_decline:
            st.session_state["show_decline_form"] = False
            st.rerun()

# Handle submit confirmation
if st.session_state.get("show_submit_confirmation", False):
    st.markdown("---")
    st.subheader("Confirm Submission")
    
    with st.form("submit_confirmation"):
        st.write("**Please confirm that you want to submit your feedback.**")
        st.info("Once submitted, you will not be able to modify your responses.")
        
        # Show summary of responses
        st.write("**Summary of your responses:**")
        for question in questions:
            question_id = question['question_id']
            question_text = question['question_text']
            response_data = responses.get(question_id, {})
            
            if question['question_type'] == 'rating':
                rating = response_data.get('rating_value', 'N/A')
                st.write(f"• {question_text}: **{rating}/5**")
            else:
                text_resp = response_data.get('response_value', 'N/A')
                preview = text_resp[:100] + "..." if len(text_resp) > 100 else text_resp
                st.write(f"• {question_text}: *{preview}*")
        
        col1, col2 = st.columns(2)
        with col1:
            final_submit = st.form_submit_button("✅ Final Submit", type="primary")
        with col2:
            cancel_submit = st.form_submit_button("← Review Responses")
        
        if final_submit:
            # Submit the feedback
            success = complete_external_stakeholder_feedback(token_data['request_id'], responses)
            if success:
                st.success("🎉 Thank you! Your feedback has been submitted successfully.")
                st.session_state["external_token_data"]["status"] = "completed"
                st.session_state["show_submit_confirmation"] = False
                # Clear responses
                if "external_responses" in st.session_state:
                    del st.session_state["external_responses"]
                st.rerun()
            else:
                st.error("Failed to submit feedback. Please try again.")
        
        if cancel_submit:
            st.session_state["show_submit_confirmation"] = False
            st.rerun()

# Navigation
st.markdown("---")
col1, col2 = st.columns(2)

with col1:
    if st.button("← Back to Login"):
        # Clear external session data  
        st.session_state["external_authenticated"] = False
        st.session_state["external_token_data"] = None
        st.session_state["login_type"] = None
        if "external_responses" in st.session_state:
            del st.session_state["external_responses"]
        st.switch_page("login.py")

with col2:
    if st.button("🏠 Exit to Main Login"):
        # Clear all external session data
        st.session_state["external_authenticated"] = False
        st.session_state["external_token_data"] = None
        st.session_state["login_type"] = None
        if "external_responses" in st.session_state:
            del st.session_state["external_responses"]
        if "show_decline_form" in st.session_state:
            del st.session_state["show_decline_form"]
        if "show_submit_confirmation" in st.session_state:
            del st.session_state["show_submit_confirmation"]
        st.switch_page("login.py")

# Help section
with st.expander("❓ Need Help?"):
    st.markdown("""
    **Rating Scale:**
    - **1 - Poor:** Significantly below expectations
    - **2 - Below Average:** Somewhat below expectations
    - **3 - Average:** Meets expectations
    - **4 - Good:** Above expectations
    - **5 - Excellent:** Significantly exceeds expectations
    
    **Text Responses:**
    - Be specific and constructive
    - Focus on behaviors and impact
    - Provide actionable suggestions when possible
    
    **Privacy:**
    - Your responses are anonymous
    - Only aggregated feedback will be shared
    - Individual responses are not linked to your identity
    """)

# Footer
st.markdown("---")
st.caption(f"Providing feedback for: {token_data['requester_name']} | {token_data['cycle_name']}")
