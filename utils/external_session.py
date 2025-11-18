import streamlit as st


def reset_external_session(clear_login_type: bool = True) -> None:
    """Clear external stakeholder session state safely."""
    st.session_state["external_authenticated"] = False
    st.session_state["external_token_data"] = None

    if clear_login_type:
        st.session_state["login_type"] = None

    # Remove transient UI flags if present
    for key in [
        "external_responses",
        "show_decline_form",
        "show_rejection_form",
    ]:
        if key in st.session_state:
            del st.session_state[key]
