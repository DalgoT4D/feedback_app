import streamlit as st
from services.db_helper import get_user_nominations_status, can_user_request_feedback

st.title("Current Nominations")

if "user_data" not in st.session_state:
    st.error("You need to be logged in to view your nominations.")
    st.stop()

user = st.session_state["user_data"]
user_id = user["user_type_id"]

# Fetch nominations snapshot
nominations_status = get_user_nominations_status(user_id)
existing_nominations = nominations_status["existing_nominations"]
rejected_nominations = nominations_status["rejected_nominations"]
remaining_slots = nominations_status["remaining_slots"]
can_nominate_more = nominations_status["can_nominate_more"]

st.info(
    "This page shows the status of every reviewer you've nominated in the current cycle."
)

cta_col1, cta_col2 = st.columns([2, 1])
with cta_col1:
    st.metric("Nominations Used", f"{nominations_status['total_count']} / 4")
with cta_col2:
    if st.button("Go to Request Feedback", type="primary"):
        st.switch_page("app_pages/request_feedback.py")

if not can_user_request_feedback(user_id):
    st.warning(
        "Requesting new feedback is disabled for your profile, but you can still see previous nominations below."
    )

st.markdown("---")

if existing_nominations:
    st.subheader("Active Nominations")
    st.caption(
        "Each card shows both the manager approval status and the reviewer status so you know where things stand."
    )
    for nomination in existing_nominations:
        with st.expander(
            f"{nomination['reviewer_name']} · {nomination['relationship_type'].replace('_', ' ').title()}",
            expanded=False,
        ):
            cols = st.columns([2, 1, 1])
            with cols[0]:
                st.write(f"**Name:** {nomination['reviewer_name']}")
                st.write(f"**Designation:** {nomination['designation']}")
                if nomination["vertical"] != "External":
                    st.write(f"**Vertical:** {nomination['vertical']}")
                st.write(
                    f"**Relationship:** {nomination['relationship_type'].replace('_', ' ').title()}"
                )
            with cols[1]:
                st.caption("Manager Approval")
                if nomination["approval_status"] == "pending":
                    st.warning("Pending")
                elif nomination["approval_status"] == "approved":
                    st.success("Approved")
                else:
                    st.info(nomination["approval_status"].title())
            with cols[2]:
                st.caption("Reviewer Status")
                reviewer_label = nomination.get("reviewer_status_label", "Pending")
                reviewer_state = reviewer_label.lower()
                if "rejected" in reviewer_state:
                    st.error(reviewer_label)
                elif reviewer_label == "Completed":
                    st.success(reviewer_label)
                elif reviewer_label in (
                    "In progress",
                    "Waiting for reviewer approval",
                    "Waiting for manager approval",
                ):
                    st.info(reviewer_label)
                elif reviewer_label == "Expired":
                    st.warning(reviewer_label)
                else:
                    st.info(reviewer_label)
            st.caption(f"Nominated on: {nomination['created_at'][:10]}")
else:
    st.info("You have not nominated anyone yet.")

st.markdown("---")

if rejected_nominations:
    st.subheader("Rejected Nominations")
    st.caption(
        "These nominations were rejected by either your manager or the reviewer. You can nominate someone else in their place."
    )

    for rejection in rejected_nominations:
        if rejection["workflow_state"] == "manager_rejected":
            rejection_by = "Rejected by Manager"
            rejection_reason = rejection.get("rejection_reason", "No reason provided")
        elif rejection["workflow_state"] == "reviewer_rejected":
            rejection_by = "Rejected by Nominee"
            rejection_reason = rejection.get(
                "reviewer_rejection_reason", "No reason provided"
            )
        else:
            rejection_by = "Rejected"
            rejection_reason = "Unknown reason"

        with st.expander(
            f"{rejection['reviewer_name']} · {rejection['relationship_type'].replace('_', ' ').title()} ({rejection_by})",
            expanded=False,
        ):
            cols = st.columns([2, 1])
            with cols[0]:
                st.write(f"**Name:** {rejection['reviewer_name']}")
                st.write(f"**Designation:** {rejection['designation']}")
                if rejection["vertical"] != "External":
                    st.write(f"**Vertical:** {rejection['vertical']}")
                st.write(
                    f"**Relationship:** {rejection['relationship_type'].replace('_', ' ').title()}"
                )
                if rejection_reason and rejection_reason != "No reason provided":
                    st.error(f"**Reason:** {rejection_reason}")
                else:
                    st.error("**Reason:** No specific reason provided")
            with cols[1]:
                st.error(rejection_by)
            st.caption(f"Nominated on: {rejection['created_at'][:10]}")
else:
    st.info("No nominations have been rejected.")

st.markdown("---")

if remaining_slots > 0 and can_nominate_more:
    st.success(
        f"You can still nominate {remaining_slots} more reviewer{'s' if remaining_slots > 1 else ''}."
    )
else:
    st.info("You've used all 4 nomination slots for this cycle.")
