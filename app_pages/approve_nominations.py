import streamlit as st
from services.db_helper import (
    get_pending_approvals_for_manager,
    approve_reject_feedback_request,
    get_active_review_cycle,
)

st.title("Approve Team Nominations")

# Check if there's an active review cycle
active_cycle = get_active_review_cycle()
if not active_cycle:
    st.warning(
        "[Warning] No active review cycle found. Contact HR to start a new feedback cycle."
    )
else:
    st.info(
        f"**Active Cycle:** {active_cycle['cycle_name']} | **Nomination Deadline:** {active_cycle['nomination_deadline']}"
    )

    user_id = st.session_state["user_data"]["user_type_id"]
    manager_name = f"{st.session_state['user_data']['first_name']} {st.session_state['user_data']['last_name']}"

    # Get pending approvals
    pending_approvals = get_pending_approvals_for_manager(user_id)

    if not pending_approvals:
        st.success("[Complete] No pending nominations to review!")
        st.info(
            "When your team members submit feedback requests, they will appear here for your approval."
        )
    else:
        st.write(
            f"You have **{len(pending_approvals)}** nomination(s) pending your approval:"
        )

        for i, approval in enumerate(pending_approvals, 1):
            request_id = approval[0]
            requester_id = approval[1]
            reviewer_id = approval[2]
            relationship_type = approval[3]
            requester_name = f"{approval[4]} {approval[5]}"
            reviewer_name = f"{approval[6]} {approval[7]}".strip()
            reviewer_vertical = approval[8]
            reviewer_designation = approval[9]
            external_email = approval[11] if len(approval) > 11 else None
            if not reviewer_name:
                reviewer_name = external_email or "External Reviewer"
            created_at = approval[10]

            with st.container():
                st.subheader(f"Request #{i}")

                col1, col2 = st.columns([2, 1])

                with col1:
                    st.write(f"**Requester:** {requester_name}")
                    st.write(f"**Wants feedback from:** {reviewer_name}")
                    st.write(
                        f"**Reviewer Details:** {reviewer_vertical} - {reviewer_designation}"
                    )
                    st.write(
                        f"**Relationship Type:** {relationship_type.replace('_', ' ').title()}"
                    )
                    st.write(f"**Requested on:** {created_at[:10]}")

                with col2:
                    # Action buttons
                    col_approve, col_reject = st.columns(2)

                    with col_approve:
                        if st.button(
                            "Approve",
                            key=f"approve_{request_id}",
                            type="primary",
                        ):
                            if approve_reject_feedback_request(
                                request_id, user_id, "approve"
                            ):
                                st.success("[Success] Request approved!")
                                # Refresh list to remove the approved item
                                st.rerun()
                            else:
                                st.error("[Error] Error approving request.")

                    with col_reject:
                        if st.button(f"Reject", key=f"reject_{request_id}"):
                            st.session_state[f"show_reject_form_{request_id}"] = True

                    # Rejection form
                    if st.session_state.get(f"show_reject_form_{request_id}", False):
                        with st.form(f"reject_form_{request_id}"):
                            st.write("**Reason for rejection:**")
                            rejection_reason = st.text_area(
                                "Please provide a reason:",
                                key=f"rejection_reason_{request_id}",
                                help="This will be sent to the requester",
                            )

                            col_submit, col_cancel = st.columns(2)
                            with col_submit:
                                submit_rejection = st.form_submit_button(
                                    "Submit Rejection"
                                )
                            with col_cancel:
                                cancel_rejection = st.form_submit_button("Cancel")

                            if submit_rejection:
                                if rejection_reason.strip():
                                    if approve_reject_feedback_request(
                                        request_id, user_id, "reject", rejection_reason
                                    ):
                                        st.success("[Success] Request rejected!")
                                        st.session_state[
                                            f"show_reject_form_{request_id}"
                                        ] = False
                                        # Refresh list to remove the rejected item
                                        st.rerun()
                                    else:
                                        st.error("[Error] Error rejecting request.")
                                else:
                                    st.error("Please provide a reason for rejection.")

                            if cancel_rejection:
                                st.session_state[f"show_reject_form_{request_id}"] = False

                st.divider()

            st.divider()

    st.markdown("---")
    st.subheader("Approval Guidelines")

    with st.expander("[Guidelines] What to consider when approving nominations"):
        st.write(
            """
        **Approve nominations when:**
        - The reviewer has direct working experience with the requester
        - The relationship type is accurately declared
        - The reviewer is not overloaded (system prevents >4 nominations automatically)
        - The feedback would be valuable and constructive
        
        **Consider rejecting when:**
        - Minimal working relationship between requester and reviewer
        - Potential conflict of interest
        - Inappropriate relationship type declared
        - Reviewer may not have sufficient context to provide meaningful feedback
        
        **Remember:**
        - Rejected nominations cannot be resubmitted for the same reviewer
        - The requester will receive your rejection reason
        - Approved requests will be sent directly to the reviewers
        """
        )

    # Show notification about external stakeholders
    st.info(
        "[Info] **Note:** Only manager-level employees and above can request feedback from external stakeholders. The system automatically enforces this rule."
    )

    if pending_approvals:
        st.warning(
            "[Action] **Action Required:** Please review and approve/reject these nominations promptly to keep the feedback process on track."
        )
