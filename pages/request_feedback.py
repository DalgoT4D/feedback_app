import streamlit as st
from datetime import datetime
from services.db_helper import (
    get_users_for_selection,
    create_feedback_requests_with_approval,
    check_external_stakeholder_permission,
    get_active_review_cycle,
    get_all_cycles,
    get_user_nominations_status,
    get_user_nominated_reviewers,
    get_user_direct_manager,
    determine_relationship_type,
    get_relationship_with_preview,
    get_users_for_selection_with_limits,
    is_reviewer_at_limit,
)

st.title("Request 360° Feedback")

# Add custom CSS for styling
st.markdown(
    """
<style>
.already-nominated {
    color: #888888 !important;
    text-decoration: line-through;
    opacity: 0.6;
}
.direct-manager {
    color: #888888 !important;
    opacity: 0.7;
    font-style: italic;
}
.at-limit {
    color: #ff6b6b !important;
    opacity: 0.7;
    font-style: italic;
}
</style>
""",
    unsafe_allow_html=True,
)

# Check if there's an active review cycle
active_cycle = get_active_review_cycle()
if not active_cycle:
    st.error(
        "[Warning] No active review cycle found. Please contact HR to start a new feedback cycle."
    )

    # Show historical cycles
    all_cycles = get_all_cycles()
    if all_cycles:
        st.subheader("Previous Cycles")
        st.info(
            "While there's no active cycle, here are the previous feedback cycles for reference:"
        )
        completed_cycles = [
            cycle for cycle in all_cycles if cycle["status"] == "completed"
        ]
        for cycle in completed_cycles[:3]:  # Show last 3 cycles
            status_icon = "[Completed]"
            st.write(
                f"{status_icon} **{cycle['cycle_display_name']}** ({cycle['cycle_year']} {cycle['cycle_quarter']}) - Status: {cycle['status']}"
            )
    st.stop()

col1, col2 = st.columns([3, 1])
with col1:
    st.info(
        f"**Active Cycle:** {active_cycle['cycle_display_name'] or active_cycle['cycle_name']}"
    )
with col2:
    today = datetime.now().date()
    if isinstance(active_cycle["nomination_deadline"], str):
        deadline = datetime.strptime(
            active_cycle["nomination_deadline"], "%Y-%m-%d"
        ).date()
    else:
        deadline = active_cycle["nomination_deadline"]
    days_left = max(0, (deadline - today).days)
    st.metric("Days Left", days_left)

st.info(f"**Nomination Deadline:** {active_cycle['nomination_deadline']}")

current_user_id = st.session_state["user_data"]["user_type_id"]
user_name = f"{st.session_state['user_data']['first_name']} {st.session_state['user_data']['last_name']}"

# Check external stakeholder permission
can_request_external = check_external_stakeholder_permission(current_user_id)

# Get user's current nominations status
nominations_status = get_user_nominations_status(current_user_id)
existing_nominations = nominations_status["existing_nominations"]
rejected_nominations = nominations_status["rejected_nominations"]
total_nominations = nominations_status["total_count"]
can_nominate_more = nominations_status["can_nominate_more"]
remaining_slots = nominations_status["remaining_slots"]
already_nominated = get_user_nominated_reviewers(current_user_id)
direct_manager = get_user_direct_manager(current_user_id)
manager_id = direct_manager["user_type_id"] if direct_manager else None

st.write("Select up to 4 colleagues to provide feedback on your performance:")
st.write(
    "You can nominate **up to 4 reviewers** total. You don't need to nominate all 4 at once."
)

if direct_manager:
    st.info(
        f"[Info] Note: You cannot nominate your direct manager ({direct_manager['name']}) as they will be providing feedback through the separate manager evaluation process."
    )

if can_request_external:
    st.success(
        "[Approved] As a manager-level employee, you can request feedback from external stakeholders."
    )
else:
    st.info(
        "[Info] Only manager-level and above can request feedback from external stakeholders."
    )

# Get available reviewers with nomination limit information
users = get_users_for_selection_with_limits(
    exclude_user_id=current_user_id, requester_user_id=current_user_id
)

# Filter and mark already nominated users, direct manager, and at-limit reviewers
available_users = []
for user in users:
    user_copy = user.copy()
    if user["user_type_id"] in already_nominated:
        user_copy["already_nominated"] = True
        user_copy["is_manager"] = False
        user_copy["at_limit"] = False
        user_copy["display_name"] = (
            f"[Already Nominated] {user['name']} ({user['designation']})"
        )
    elif user["user_type_id"] == manager_id:
        user_copy["already_nominated"] = False
        user_copy["is_manager"] = True
        user_copy["at_limit"] = False
        user_copy["display_name"] = (
            f"[Manager] {user['name']} ({user['designation']}) - Your Direct Manager"
        )
    elif user["at_limit"]:
        user_copy["already_nominated"] = False
        user_copy["is_manager"] = False
        user_copy["at_limit"] = True
        user_copy["display_name"] = (
            f"[Limit Reached] {user['name']} ({user['designation']}) - At Nomination Limit (4/4)"
        )
    else:
        user_copy["already_nominated"] = False
        user_copy["is_manager"] = False
        user_copy["at_limit"] = False
        user_copy["display_name"] = (
            f"{user['name']} ({user['designation']}) ({user['nomination_count']}/4)"
        )
    available_users.append(user_copy)

users = available_users

if not users:
    st.error("No available reviewers found.")
    st.stop()

# Selection interface
selected_reviewers = []

st.subheader("Available Reviewers")

# Internal reviewers
internal_reviewers = st.multiselect(
    "Select internal reviewers from Tech4Dev:",
    options=users,
    format_func=lambda user: user["display_name"],
)

# Filter out already nominated users, direct manager, and at-limit reviewers from selection
valid_internal_reviewers = []
invalid_selections = []
manager_selections = []
at_limit_selections = []

for reviewer in internal_reviewers:
    if reviewer["already_nominated"]:
        invalid_selections.append(reviewer["name"])
    elif reviewer["is_manager"]:
        manager_selections.append(reviewer["name"])
    elif reviewer["at_limit"]:
        at_limit_selections.append(reviewer["name"])
    else:
        valid_internal_reviewers.append(reviewer)

if invalid_selections:
    st.error(
        f"[Error] You have already nominated: {', '.join(invalid_selections)}. Please select different reviewers."
    )

if manager_selections:
    st.error(
        f"[Error] You cannot nominate your direct manager ({', '.join(manager_selections)}) for feedback. Please select different reviewers."
    )

if at_limit_selections:
    st.error(
        f"[Error] The following reviewers are at their nomination limit (4/4): {', '.join(at_limit_selections)}. Please select different reviewers."
    )

internal_reviewers = valid_internal_reviewers

# External stakeholder
if can_request_external:
    external_reviewer = st.text_input("Enter email of external stakeholder (optional):")
    if external_reviewer:
        external_reviewer_clean = external_reviewer.strip().lower()
        already_nominated_lower = [
            str(email).lower() if isinstance(email, str) else str(email)
            for email in already_nominated
        ]

        if external_reviewer_clean in already_nominated_lower:
            st.error(
                f"[Error] You have already nominated {external_reviewer}. Please enter a different email address."
            )
        else:
            selected_reviewers.append((external_reviewer.strip(), "placeholder"))

# Add selected internal reviewers to the list (with placeholder relationship)
for reviewer in valid_internal_reviewers:
    selected_reviewers.append((reviewer["user_type_id"], "placeholder"))

# Validation and submission
st.subheader("Review Your Selection")

if len(selected_reviewers) == 0:
    st.warning("[Warning] Please select at least 1 reviewer to add.")
elif len(selected_reviewers) + total_nominations > 4:
    st.error(
        f"[Error] You have selected {len(selected_reviewers)} reviewers, but you only have {remaining_slots} slot{'s' if remaining_slots != 1 else ''} remaining. Please reduce your selection."
    )
else:
    st.success(f"[Success] You have selected {len(selected_reviewers)} reviewers.")

    # Get automatically assigned relationships
    relationships_with_preview = get_relationship_with_preview(
        current_user_id, selected_reviewers
    )

    # Show summary with automatically assigned relationships
    st.write("**Selected Reviewers with Auto-Assigned Relationships:**")
    st.info(
        "Relationships are automatically determined based on organizational structure"
    )

    for reviewer_identifier, relationship_type in relationships_with_preview:
        if isinstance(reviewer_identifier, int):
            reviewer_info = next(
                u for u in users if u["user_type_id"] == reviewer_identifier
            )
            relationship_display = relationship_type.replace("_", " ").title()
            if relationship_type == "peer":
                icon = "[Peer]"
            elif relationship_type == "direct_reportee":
                icon = "[Reportee]"
            elif relationship_type == "internal_stakeholder":
                icon = "[Internal]"
            else:
                icon = "[External]"
            st.write(f"{icon} **{reviewer_info['name']}** - {relationship_display}")
        else:
            st.write(f"[External] **{reviewer_identifier}** - External Stakeholder")

    if st.button(
        f"Add {len(selected_reviewers)} Reviewer{'s' if len(selected_reviewers) > 1 else ''}",
        type="primary",
    ):
        # Use the relationships with auto-assigned types
        success, message = create_feedback_requests_with_approval(
            current_user_id, relationships_with_preview
        )

        if success:
            st.success("[Success] Feedback requests added successfully!")
            st.info(
                "Your new requests have been sent to your manager for approval. You will be notified once they are processed."
            )
            st.balloons()
            st.rerun()
        else:
            st.error(f"Error submitting requests: {message}")

st.markdown("---")


# Show existing nominations
if existing_nominations:
    st.subheader(f"Your Current Nominations ({total_nominations}/4)")
    for nomination in existing_nominations:
        # Get relationship icon
        relationship_type = nomination["relationship_type"]
        if relationship_type == "peer":
            icon = "[Peer]"
        elif relationship_type == "direct_reportee":
            icon = "[Reportee]"
        elif relationship_type == "internal_stakeholder":
            icon = "[Internal]"
        elif relationship_type == "external_stakeholder":
            icon = "[External]"
        else:
            icon = "[Review]"

        with st.expander(
            f"{icon} {nomination['reviewer_name']} - {nomination['relationship_type'].replace('_', ' ').title()}"
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
                if nomination["approval_status"] == "pending":
                    st.warning("[Pending] Pending Approval")
                elif nomination["approval_status"] == "approved":
                    st.success("[Approved] Approved")
            with cols[2]:
                if nomination["status"] == "completed":
                    st.success("[Completed] Completed")
                elif nomination["status"] == "approved":
                    st.info("[In Progress] In Progress")
                else:
                    st.info("[Pending] Pending")
            st.caption(f"Nominated on: {nomination['created_at'][:10]}")

# Show rejected nominations
if rejected_nominations:
    st.subheader("Rejected Nominations")
    st.warning(
        "[Warning] Your manager has rejected some of your nominations. You can nominate different reviewers for the remaining slots."
    )

    for rejection in rejected_nominations:
        with st.expander(
            f"[Rejected] {rejection['reviewer_name']} - {rejection['relationship_type'].replace('_', ' ').title()} (REJECTED)",
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
                if rejection["rejection_reason"]:
                    st.error(f"**Rejection Reason:** {rejection['rejection_reason']}")
                else:
                    st.error("**Rejection Reason:** No specific reason provided")
            with cols[1]:
                st.error("[Rejected] Rejected by Manager")
            st.caption(f"Nominated on: {rejection['created_at'][:10]}")

    if remaining_slots > 0:
        st.info(
            f"[Available] You can nominate **{remaining_slots} more reviewer{'s' if remaining_slots > 1 else ''}** for this cycle."
        )
    else:
        st.success(
            "[Complete] You've nominated the maximum of 4 reviewers for this cycle!"
        )
        st.stop()
else:
    st.info(
        "[Start] You haven't nominated anyone yet. You can nominate up to 4 reviewers total."
    )

st.markdown("---")

st.subheader("How it works:")
st.write(
    """
1. **Select Reviewers**: Choose up to 4 colleagues who work closely with you
2. **Flexible Nomination**: Add reviewers one at a time or in small groups - no need to nominate all 4 at once
3. **Automatic Relationship Assignment**: The system determines relationships based on organizational structure:
   - [Peer] **Peers**: Same team, no direct reporting relationship
   - [Internal] **Internal Stakeholders**: Different teams, no direct reporting relationship  
   - [Reportee] **Direct Reportees**: People who report directly to you
   - [External] **External Stakeholders**: People outside the organization
4. **Manager Approval**: Your manager will review and approve your selections
5. **Feedback Collection**: Approved reviewers will receive feedback forms
6. **Anonymous Results**: You'll receive anonymized feedback once completed
"""
)

# Show nomination limits info
st.info(
    "**Note:** Each person can only receive a maximum of 4 feedback requests to prevent overload."
)
