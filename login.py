import streamlit as st
from services.auth_service import authenticate_user, check_user_needs_password_setup
from services.db_helper import (
    validate_external_token,
    accept_external_stakeholder_request,
    reject_external_stakeholder_request,
)

# Display logo
st.image("assets/login_logo.jpg", width=200)
st.title("360° Feedback System")

if "authenticated" not in st.session_state:
    st.session_state["authenticated"] = False

if not st.session_state["authenticated"]:
    # Initialize login type session state
    if "login_type" not in st.session_state:
        st.session_state["login_type"] = None

    # Step 1: Choose login type
    if st.session_state["login_type"] is None:
        st.subheader("Select Login Type")

        col1, col2 = st.columns(2)

        with col1:
            if st.button("Employee Login", use_container_width=True, type="primary"):
                st.session_state["login_type"] = "employee"
                st.session_state["email_entered"] = False
                st.rerun()

        with col2:
            if st.button(
                "External Stakeholder Login", use_container_width=True, type="secondary"
            ):
                st.session_state["login_type"] = "external"
                st.rerun()

        st.markdown("---")
        st.info("**Employees**: Use your regular company email to log in.")
        st.info(
            "**External Stakeholders**: Use the email and token received in your invitation."
        )

    # Step 2: Handle employee login
    elif st.session_state["login_type"] == "employee":
        if "email_entered" not in st.session_state:
            st.session_state["email_entered"] = False

        if not st.session_state["email_entered"]:
            st.subheader("Employee Login")

            if st.button("← Back to Login Type Selection", key="back_from_employee"):
                st.session_state["login_type"] = None
                st.rerun()

            with st.form("email_form"):
                email = st.text_input("Company Email Address")
                submit_email = st.form_submit_button("Continue")

                if submit_email:
                    if email:
                        # Check if user exists and needs password setup
                        needs_setup, user_data = check_user_needs_password_setup(email)

                        if user_data:  # User exists
                            st.session_state["login_email"] = email
                            st.session_state["email_entered"] = True
                            st.session_state["needs_password_setup"] = needs_setup
                            st.rerun()
                        else:
                            st.error(
                                "Email not found in the system. Please contact your administrator."
                            )
                    else:
                        st.error("Please enter your email address.")

        else:
            # Step 2: Password entry or setup for employee
            email = st.session_state["login_email"]
            needs_setup = st.session_state.get("needs_password_setup", False)

            if needs_setup:
                # First time login - password setup
                st.subheader("Welcome! Set up your password")
                st.info(f"Email: {email}")

                with st.form("password_setup_form"):
                    password = st.text_input("Create Password", type="password")
                    confirm_password = st.text_input(
                        "Confirm Password", type="password"
                    )
                    submit_setup = st.form_submit_button("Set Password")

                    if submit_setup:
                        if not password:
                            st.error("Please enter a password.")
                        elif len(password) < 6:
                            st.error("Password must be at least 6 characters long.")
                        elif password != confirm_password:
                            st.error("Passwords do not match.")
                        else:
                            from services.auth_service import create_user_password

                            if create_user_password(email, password):
                                st.success(
                                    "Password created successfully! Please login."
                                )
                                # Reset and go to login
                                st.session_state["email_entered"] = False
                                st.session_state["needs_password_setup"] = False
                                st.rerun()
                            else:
                                st.error("Error creating password. Please try again.")

            else:
                # Regular login
                st.subheader("Enter Password")
                st.info(f"Email: {email}")

                with st.form("password_form"):
                    password = st.text_input("Password", type="password")

                    # Buttons on the same line - Login on left, Forgot Password on right
                    col1, col2 = st.columns([1, 1])
                    with col1:
                        submit_login = st.form_submit_button("Login", type="primary")
                    with col2:
                        reset_password = st.form_submit_button("Forgot Password?")

                    if submit_login:
                        if password:
                            success, error_message, user_data = authenticate_user(
                                email, password
                            )

                            if success:
                                st.session_state["authenticated"] = True
                                st.session_state["email"] = email
                                st.session_state["user_data"] = user_data
                                st.session_state["user_roles"] = user_data["roles"]
                                # Clear login session data
                                st.session_state["email_entered"] = False
                                st.success("Login successful!")
                                st.rerun()
                            else:
                                st.error(error_message)
                        else:
                            st.error("Please enter your password.")

                    if reset_password:
                        st.session_state["show_password_reset"] = True
                        st.rerun()

            # Back button
            if st.button("← Back to Email Entry"):
                st.session_state["email_entered"] = False
                st.rerun()

    # Step 3: Handle external stakeholder login
    elif st.session_state["login_type"] == "external":
        st.subheader("External Stakeholder Login")

        if st.button("← Back to Login Type Selection", key="back_from_external"):
            st.session_state["login_type"] = None
            st.rerun()

        # Handle external authentication
        if not st.session_state.get("external_authenticated", False):
            st.info(
                "Please enter the email address and token from your invitation email."
            )

            with st.form("external_auth_form"):
                email = st.text_input(
                    "Email Address",
                    placeholder="Enter the email where you received the invitation",
                    help="This should match the email address where you received the feedback request",
                )

                token = st.text_input(
                    "Access Token",
                    placeholder="Enter the token from your invitation email",
                    help="Copy and paste the token exactly as it appears in your email",
                )

                submit_auth = st.form_submit_button("Authenticate", type="primary")

                if submit_auth:
                    if not email or not token:
                        st.error("Please enter both email address and token.")
                    else:
                        # Validate the token
                        token_data = validate_external_token(
                            email.strip(), token.strip()
                        )

                        if token_data:
                            st.session_state["external_authenticated"] = True
                            st.session_state["external_token_data"] = token_data
                            st.success("Authentication successful!")
                            st.rerun()
                        else:
                            st.error(
                                "Invalid email or token. Please check your credentials and try again."
                            )
                            st.info(
                                "Make sure you're using the exact email and token from your invitation."
                            )

        else:
            # External user is authenticated - show request details and actions
            token_data = st.session_state["external_token_data"]

            st.success("✅ Successfully authenticated!")

            # Display request details
            st.subheader("Feedback Request Details")

            col1, col2 = st.columns(2)
            with col1:
                st.write(f"**Requested by:** {token_data['requester_name']}")
                st.write(f"**Department:** {token_data['requester_vertical']}")
            with col2:
                st.write(f"**Review Cycle:** {token_data['cycle_name']}")
                st.write(
                    f"**Your Role:** {token_data['relationship_type'].replace('_', ' ').title()}"
                )

            st.markdown("---")

            # Handle different statuses
            if token_data["status"] == "pending":
                st.subheader("Response Required")
                st.info(
                    "Please choose whether you would like to participate in providing feedback:"
                )

                col1, col2 = st.columns(2)

                with col1:
                    if st.button(
                        "✅ Accept and Provide Feedback",
                        type="primary",
                        use_container_width=True,
                    ):
                        success = accept_external_stakeholder_request(token_data)
                        if success:
                            st.session_state["external_token_data"][
                                "status"
                            ] = "accepted"
                            st.success(
                                "Thank you for accepting! Redirecting to feedback form..."
                            )
                            st.rerun()
                        else:
                            st.error("Failed to process acceptance. Please try again.")

                with col2:
                    if st.button("❌ Decline to Participate", use_container_width=True):
                        st.session_state["show_rejection_form"] = True
                        st.rerun()

                # Show rejection form if triggered
                if st.session_state.get("show_rejection_form", False):
                    st.markdown("---")
                    st.subheader("Decline Participation")

                    with st.form("rejection_form"):
                        st.write(
                            "**Optional:** Please provide a brief reason for declining (this will remain confidential):"
                        )
                        rejection_reason = st.text_area(
                            "Reason for declining",
                            placeholder="e.g., Limited interaction, Time constraints, etc.",
                            help="This information helps improve the feedback process",
                        )

                        col1, col2 = st.columns(2)
                        with col1:
                            submit_rejection = st.form_submit_button(
                                "Submit Decline", type="secondary"
                            )
                        with col2:
                            cancel_rejection = st.form_submit_button("Cancel")

                        if submit_rejection:
                            reason = (
                                rejection_reason.strip()
                                if rejection_reason
                                else "No reason provided"
                            )
                            success = reject_external_stakeholder_request(
                                token_data, reason
                            )
                            if success:
                                st.success(
                                    "Thank you for your response. Your decision has been recorded."
                                )
                                st.session_state["external_token_data"][
                                    "status"
                                ] = "rejected"
                                st.session_state["show_rejection_form"] = False
                                st.rerun()
                            else:
                                st.error(
                                    "Failed to process rejection. Please try again."
                                )

                        if cancel_rejection:
                            st.session_state["show_rejection_form"] = False
                            st.rerun()

            elif token_data["status"] == "accepted":
                st.success("✅ You have accepted this feedback request!")

                if st.button(
                    "Continue to Feedback Form",
                    type="primary",
                    use_container_width=True,
                ):
                    st.switch_page("app_pages/external_feedback.py")

            elif token_data["status"] == "rejected":
                st.info("You have declined to participate in this feedback request.")
                st.write("Thank you for your time.")

            elif token_data["status"] == "completed":
                st.success(
                    "✅ You have already completed the feedback for this request."
                )
                st.write("Thank you for your valuable feedback!")

            st.markdown("---")

            # Back to main login option
            if st.button("← Return to Main Login", key="back_to_main_from_external"):
                # Clear external session data
                st.session_state["external_authenticated"] = False
                st.session_state["external_token_data"] = None
                st.session_state["login_type"] = None
                if "show_rejection_form" in st.session_state:
                    del st.session_state["show_rejection_form"]
                st.rerun()

    # No other login type - should not reach here

    # Password Reset Flow
    if st.session_state.get("show_password_reset", False):
        st.markdown("---")
        st.subheader("🔐 Password Reset")

        # Step 1: Choose reset method
        if "reset_method" not in st.session_state:
            st.session_state["reset_method"] = "request"

        method = st.radio(
            "Choose an option:",
            ["Send me a reset token", "I have a reset token"],
            key="reset_method_radio",
        )

        if method == "Send me a reset token":
            st.write("**Request Password Reset**")
            email = st.session_state.get("login_email", "")
            st.info(f"Reset token will be sent to: {email}")

            col1, col2 = st.columns(2)
            with col1:
                if st.button("Send Reset Token", type="primary"):
                    from services.auth_service import generate_password_reset_token

                    success, message = generate_password_reset_token(email)
                    if success:
                        st.success(message)
                        st.info(
                            "Check your email for the reset token, then select 'I have a reset token' above."
                        )
                    else:
                        st.error(message)

            with col2:
                if st.button("Cancel Reset"):
                    st.session_state["show_password_reset"] = False
                    st.rerun()

        else:  # "I have a reset token"
            st.write("**Enter Reset Token and New Password**")

            with st.form("reset_password_form"):
                reset_token = st.text_input(
                    "Reset Token", help="Copy and paste the token from your email"
                )
                new_password = st.text_input("New Password", type="password")
                confirm_password = st.text_input(
                    "Confirm New Password", type="password"
                )

                col1, col2 = st.columns(2)
                with col1:
                    submit_reset = st.form_submit_button(
                        "Reset Password", type="primary"
                    )
                with col2:
                    cancel_reset = st.form_submit_button("Cancel")

                if submit_reset:
                    if not reset_token:
                        st.error("Please enter the reset token.")
                    elif not new_password:
                        st.error("Please enter a new password.")
                    elif len(new_password) < 6:
                        st.error("Password must be at least 6 characters long.")
                    elif new_password != confirm_password:
                        st.error("Passwords do not match.")
                    else:
                        from services.auth_service import reset_password_with_token

                        success, message = reset_password_with_token(
                            reset_token, new_password
                        )
                        if success:
                            st.success(message)
                            st.success("You can now login with your new password!")
                            # Clear reset state and go back to login
                            st.session_state["show_password_reset"] = False
                            st.session_state["email_entered"] = False
                            st.balloons()
                            st.rerun()
                        else:
                            st.error(message)

                if cancel_reset:
                    st.session_state["show_password_reset"] = False
                    st.rerun()

else:
    user_data = st.session_state.get("user_data", {})
    st.success(f"Welcome back, {user_data.get('first_name', 'User')}!")
    st.info(
        "Use the navigation menu to access the different sections of the application."
    )
