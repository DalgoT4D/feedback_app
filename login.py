import streamlit as st
from services.auth_service import authenticate_user, check_user_needs_password_setup

# Display logo
st.image("assets/login_logo.jpg", width=200)
st.title("360° Feedback System")

if "authenticated" not in st.session_state:
    st.session_state["authenticated"] = False

if not st.session_state["authenticated"]:
    # Step 1: Email entry
    if "email_entered" not in st.session_state:
        st.session_state["email_entered"] = False

    if not st.session_state["email_entered"]:
        st.subheader("Login")
        with st.form("email_form"):
            email = st.text_input("Email Address")
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
        # Step 2: Password entry or setup
        email = st.session_state["login_email"]
        needs_setup = st.session_state.get("needs_password_setup", False)

        if needs_setup:
            # First time login - password setup
            st.subheader(f"Welcome! Set up your password")
            st.info(f"Email: {email}")

            with st.form("password_setup_form"):
                password = st.text_input("Create Password", type="password")
                confirm_password = st.text_input("Confirm Password", type="password")
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
                            st.success("Password created successfully! Please login.")
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
