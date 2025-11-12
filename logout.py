"""
Logout page for 360° Feedback Application
Clears session state and redirects to login.
"""

import streamlit as st

st.title("Logging Out...")

# Clear session state
if "authenticated" in st.session_state:
    st.session_state["authenticated"] = False
if "email" in st.session_state:
    st.session_state["email"] = None
if "user_data" in st.session_state:
    st.session_state["user_data"] = None
if "user_roles" in st.session_state:
    st.session_state["user_roles"] = []

# Clear any other session state data that might be present
session_keys_to_clear = [
    "show_cycle_form",
    "show_complete_form", 
    "active_cycle_cache",
    "temp_disable_badges"
]

for key in session_keys_to_clear:
    if key in st.session_state:
        del st.session_state[key]

# Show success message
st.success("Successfully logged out!")
st.info("You will be redirected to the login page automatically.")

# Use a meta refresh to redirect to login page after a brief delay
st.markdown("""
<meta http-equiv="refresh" content="2; url=/" />
<script>
setTimeout(function() {
    window.location.href = '/';
}, 2000);
</script>
""", unsafe_allow_html=True)

st.markdown("If you are not redirected automatically, please [click here to login](/).")