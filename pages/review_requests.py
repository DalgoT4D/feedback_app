import streamlit as st
from services.db_helper import get_pending_reviewer_requests, handle_reviewer_response

st.title("Review Requests")

current_user_id = st.session_state["user_data"]["user_type_id"]
user_name = f"{st.session_state['user_data']['first_name']} {st.session_state['user_data']['last_name']}"

# Get pending requests for this reviewer
pending_requests = get_pending_reviewer_requests(current_user_id)

if not pending_requests:
    st.info("[Complete] You have no pending review requests to respond to.")
    st.write(
        "Once colleagues nominate you for feedback and their managers approve, requests will appear here for your acceptance."
    )
else:
    st.info(
        f"[Pending] You have {len(pending_requests)} feedback request{'s' if len(pending_requests) > 1 else ''} waiting for your response."
    )
    st.write(
        "**Please review each request and decide whether to accept or decline providing feedback.**"
    )

    for request in pending_requests:
        with st.expander(
            f"[Request] Request from {request['requester_name']} - {request['relationship_type'].replace('_', ' ').title()}",
            expanded=True,
        ):
            cols = st.columns([2, 1, 1])

            with cols[0]:
                st.write(f"**Requester:** {request['requester_name']}")
                st.write(f"**Department:** {request['requester_vertical']}")
                st.write(f"**Designation:** {request['requester_designation']}")
                st.write(
                    f"**Your Relationship:** {request['relationship_type'].replace('_', ' ').title()}"
                )
                st.write(f"**Cycle:** {request['cycle_name']}")
                st.caption(f"Requested on: {request['created_at'][:10]}")

            with cols[1]:
                if st.button(
                    f"[Accept] Accept",
                    key=f"accept_{request['request_id']}",
                    type="primary",
                ):
                    success, message = handle_reviewer_response(
                        request["request_id"], current_user_id, "accept"
                    )
                    if success:
                        st.success(
                            "[Accepted] Request accepted! You can now complete the feedback."
                        )
                        st.rerun()
                    else:
                        st.error(f"Error: {message}")

            with cols[2]:
                if st.button(
                    f"[Decline] Decline", key=f"decline_{request['request_id']}"
                ):
                    st.session_state[f"show_decline_{request['request_id']}"] = True
                    st.rerun()

            # Show decline reason form if user clicked decline
            if st.session_state.get(f"show_decline_{request['request_id']}", False):
                st.markdown("---")
                st.write(
                    "**Please provide a reason for declining this feedback request:**"
                )

                decline_reason = st.text_area(
                    "Reason for declining (required):",
                    key=f"decline_reason_{request['request_id']}",
                    placeholder="e.g., Limited availability, insufficient working relationship, conflict of interest, etc.",
                    help="This reason will be shared with HR for review.",
                )

                col1, col2 = st.columns(2)
                with col1:
                    if st.button(
                        f"Submit Decline",
                        key=f"submit_decline_{request['request_id']}",
                        type="secondary",
                    ):
                        if decline_reason.strip():
                            success, message = handle_reviewer_response(
                                request["request_id"],
                                current_user_id,
                                "reject",
                                decline_reason.strip(),
                            )
                            if success:
                                st.success(
                                    "[Declined] Request declined. Reason sent to HR for review."
                                )
                                # Clear the form state
                                if (
                                    f"show_decline_{request['request_id']}"
                                    in st.session_state
                                ):
                                    del st.session_state[
                                        f"show_decline_{request['request_id']}"
                                    ]
                                st.rerun()
                            else:
                                st.error(f"Error: {message}")
                        else:
                            st.error("Please provide a reason for declining.")

                with col2:
                    if st.button(
                        f"Cancel", key=f"cancel_decline_{request['request_id']}"
                    ):
                        # Clear the form state
                        if f"show_decline_{request['request_id']}" in st.session_state:
                            del st.session_state[
                                f"show_decline_{request['request_id']}"
                            ]
                        st.rerun()

st.markdown("---")
st.subheader("About Review Requests")
st.write(
    """
When colleagues nominate you for 360-degree feedback:
1. **Manager Approval**: Their manager first approves the nomination
2. **Your Choice**: You can then accept or decline the request
3. **Feedback Process**: If you accept, you'll complete a brief feedback form
4. **Anonymity**: Your feedback will be anonymized in the final report

**Common reasons to decline:**
- Limited working relationship with the requester
- Potential conflicts of interest
- You feel unable to provide constructive feedback

All decline reasons are reviewed by HR to ensure the feedback process remains fair and constructive.
"""
)
