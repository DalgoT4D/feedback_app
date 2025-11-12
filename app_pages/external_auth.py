"""
External Stakeholder Authentication Page
Allows external stakeholders to login using email and token.
"""

import streamlit as st
from services.db_helper import (
    validate_external_token,
    accept_external_stakeholder_request,
    get_active_review_cycle,
)

st.set_page_config(
    page_title="External Stakeholder Login",
    page_icon="🤝",
    layout="centered"
)

# Display logo and title
st.image("assets/login_logo.jpg", width=200)
st.title("External Stakeholder Login")

# Initialize session state
if "external_authenticated" not in st.session_state:
    st.session_state["external_authenticated"] = False

if "external_token_data" not in st.session_state:
    st.session_state["external_token_data"] = None

# If already authenticated as external, show options
if st.session_state["external_authenticated"] and st.session_state["external_token_data"]:
    token_data = st.session_state["external_token_data"]
    
    st.success("✅ Authenticated as External Stakeholder")

    # Auto-accept: external stakeholders do not need to approve
    if token_data['status'] == 'pending':
        if accept_external_stakeholder_request(token_data):
            st.session_state["external_token_data"]["status"] = "accepted"
        else:
            st.warning("We couldn't auto-accept your request. You can still proceed to the form.")

    # Show only the feedback deadline info
    active_cycle = get_active_review_cycle()
    if active_cycle and active_cycle.get("feedback_deadline"):
        st.info(f"Feedback Deadline: {active_cycle['feedback_deadline']}")

    # Minimal "Complete Reviews" style summary with a single action
    st.subheader("Complete Reviews")
    st.write(
        f"1 pending review for {token_data['requester_name']} "
        f"({token_data['relationship_type'].replace('_', ' ').title()})"
    )

    if st.button("Provide Feedback", type="primary", use_container_width=True):
            st.switch_page("app_pages/external_feedback.py")

    st.markdown("---")
    
    # Back to main login option
    if st.button("← Return to Main Login", key="back_to_main"):
        # Clear external session data
        st.session_state["external_authenticated"] = False
        st.session_state["external_token_data"] = None
        st.session_state["login_type"] = None
        if "show_rejection_form" in st.session_state:
            del st.session_state["show_rejection_form"]
        st.switch_page("main.py")

else:
    # Authentication form
    st.subheader("Enter Your Credentials")
    st.info("Please enter the email address and token from your invitation email.")
    
    # Back button
    if st.button("← Back to Login Options"):
        st.session_state["login_type"] = None
        st.switch_page("main.py")
    
    with st.form("external_auth_form"):
        email = st.text_input(
            "Email Address",
            placeholder="Enter the email where you received the invitation",
            help="This should match the email address where you received the feedback request"
        )
        
        token = st.text_input(
            "Access Token",
            placeholder="Enter the token from your invitation email",
            help="Copy and paste the token exactly as it appears in your email"
        )
        
        submit_auth = st.form_submit_button("Authenticate", type="primary")
        
        if submit_auth:
            if not email or not token:
                st.error("Please enter both email address and token.")
            else:
                # Validate the token
                token_data = validate_external_token(email.strip(), token.strip())
                
                if token_data:
                    st.session_state["external_authenticated"] = True
                    st.session_state["external_token_data"] = token_data
                    st.success("Authentication successful! Redirecting...")
                    st.rerun()
                else:
                    st.error("Invalid email or token. Please check your credentials and try again.")
                    st.info("Make sure you're using the exact email and token from your invitation.")

# Help section
with st.expander("❓ Need Help?"):
    st.markdown("""
    **Common Issues:**
    
    - **Token not working?** Make sure you copy the entire token exactly as it appears in your email
    - **Email not recognized?** Use the exact email address where you received the invitation
    - **Lost your invitation?** Contact the person who requested your feedback
    
    **About External Feedback:**
    
    - Your feedback will remain anonymous
    - The process takes about 10-15 minutes
    - You can decline to participate if needed
    - Your token does not expire
    
    **Questions?** Contact the HR team for assistance.
    """)

# Footer
st.markdown("---")
st.caption("360° Feedback System - External Stakeholder Access")
