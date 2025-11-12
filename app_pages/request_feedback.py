import streamlit as st
from datetime import datetime
from services.db_helper import (
    get_users_for_selection,
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
    check_user_deadline_enforcement,
    can_user_request_feedback,
)
from services.db_helper import create_feedback_request_fixed

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
    st.stop()

# Check deadline enforcement
user_id = st.session_state.get("user_id")
if user_id:
    can_nominate, deadline_message = check_user_deadline_enforcement(
        user_id, "nomination"
    )
    if not can_nominate:
        st.error(f"🚫 {deadline_message}")
        st.info(
            "All pending nominations have been automatically approved after the deadline passed."
        )
        st.stop()

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

# Enforce date-of-joining policy for requesting feedback
if not can_user_request_feedback(current_user_id):
    st.warning(
        "Request Feedback is unavailable based on your date of joining. You can still be invited to give feedback."
    )
    st.stop()

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

if remaining_slots > 0:
    st.write(
        "Select up to four colleagues to share feedback that can support your growth and development."
    )
    st.write(
        "You can nominate up to four reviewers in total. You don't need to add all four at once."
    )

if direct_manager:
    st.info(
        f"Note: Your direct manager ({direct_manager['name']}) cannot be nominated — their feedback is shared through ongoing discussions and review touchpoints like check-ins or H1 assessments."
    )

if can_request_external and remaining_slots > 0:
    st.success(
        "Managers and above level are encouraged to include external stakeholders, where relevant, in their feedback nominations."
    )

# Get available reviewers with nomination limit information
users = get_users_for_selection_with_limits(
    exclude_user_id=current_user_id, requester_user_id=current_user_id
)

# Filter and mark already nominated users, direct manager, and at-limit reviewers
available_users = []
selectable_users = []  # Only users that can actually be selected

for user in users:
    user_copy = user.copy()
    if user["user_type_id"] in already_nominated:
        user_copy["already_nominated"] = True
        user_copy["is_manager"] = False
        user_copy["at_limit"] = False
        user_copy["is_selectable"] = False
        user_copy["display_name"] = (
            f"[Already Nominated] {user['name']} ({user['designation']})"
        )
    elif user["user_type_id"] == manager_id:
        user_copy["already_nominated"] = False
        user_copy["is_manager"] = True
        user_copy["at_limit"] = False
        user_copy["is_selectable"] = False
        user_copy["display_name"] = (
            f"[Manager] {user['name']} ({user['designation']}) - Your Direct Manager"
        )
    elif user["at_limit"]:
        user_copy["already_nominated"] = False
        user_copy["is_manager"] = False
        user_copy["at_limit"] = True
        user_copy["is_selectable"] = False
        user_copy["display_name"] = (
            f"[Limit Reached] {user['name']} ({user['designation']}) - At Nomination Limit (4/4)"
        )
    else:
        user_copy["already_nominated"] = False
        user_copy["is_manager"] = False
        user_copy["at_limit"] = False
        user_copy["is_selectable"] = True
        user_copy["display_name"] = (
            f"{user['name']} ({user['designation']}) ({user['nomination_count']}/4)"
        )

    available_users.append(user_copy)

    # Only add selectable users to the options list
    if user_copy["is_selectable"]:
        selectable_users.append(user_copy)

users = available_users

if not users:
    st.error("No available reviewers found.")
    st.stop()

# Selection interface
selected_reviewers = []

st.subheader("Available Reviewers")

# Show non-selectable users (greyed out) for transparency
non_selectable_users = [user for user in available_users if not user["is_selectable"]]
if non_selectable_users:
    st.markdown("**Cannot Be Selected (for reference):**")
    for user in non_selectable_users:
        if user["is_manager"]:
            st.markdown(
                f"<span class='direct-manager'>• {user['display_name']}</span>",
                unsafe_allow_html=True,
            )
        elif user["already_nominated"]:
            st.markdown(
                f"<span class='already-nominated'>• {user['display_name']}</span>",
                unsafe_allow_html=True,
            )
        elif user["at_limit"]:
            st.markdown(
                f"<span class='at-limit'>• {user['display_name']}</span>",
                unsafe_allow_html=True,
            )
    st.markdown("")

selected_reviewers = []

# Internal reviewers - only show selectable ones
if selectable_users:
    internal_reviewers = st.multiselect(
        "Select internal reviewers from Tech4Dev:",
        options=selectable_users,
        format_func=lambda user: user["display_name"],
        disabled=(remaining_slots <= 0),
    )

    # Respect remaining slots: ignore any selections if no slots left
    valid_internal_reviewers = [] if remaining_slots <= 0 else internal_reviewers
else:
    st.warning("[Warning] No reviewers available for selection at this time.")
    valid_internal_reviewers = []

internal_reviewers = valid_internal_reviewers

# External stakeholder (disabled when no slots remain)
if can_request_external and remaining_slots > 0:
    external_reviewer = st.text_input("Enter email of external stakeholder (optional):")
    if external_reviewer:
        external_reviewer_clean = external_reviewer.strip().lower()
        already_nominated_lower = [
            str(email).lower() if isinstance(email, str) else str(email)
            for email in already_nominated
        ]

        # Check if they're trying to enter their manager's email
        manager_email = (
            direct_manager.get("email", "").lower() if direct_manager else ""
        )

        if external_reviewer_clean == manager_email:
            st.error(
                f"[Error] You cannot nominate your direct manager ({external_reviewer}) as an external stakeholder."
            )
        elif external_reviewer_clean in already_nominated_lower:
            st.error(
                f"[Error] You have already nominated {external_reviewer}. Please enter a different email address."
            )
        else:
            selected_reviewers.append(
                (external_reviewer.strip(), "external_stakeholder")
            )

# Add selected internal reviewers to the list (with placeholder relationship)
for reviewer in valid_internal_reviewers:
    selected_reviewers.append((reviewer["user_type_id"], "placeholder"))

# Guard against duplicate selections within the same submission
deduped_reviewers = []
duplicate_labels = []
seen_internal = set()
seen_external = set()

for reviewer_identifier, relationship_type in selected_reviewers:
    if isinstance(reviewer_identifier, int):
        if reviewer_identifier in seen_internal:
            reviewer_info = next(
                (u for u in users if u["user_type_id"] == reviewer_identifier), None
            )
            duplicate_labels.append(
                reviewer_info["name"]
                if reviewer_info
                else f"User #{reviewer_identifier}"
            )
            continue
        seen_internal.add(reviewer_identifier)
    else:
        normalized_email = reviewer_identifier.strip().lower()
        if normalized_email in seen_external:
            duplicate_labels.append(reviewer_identifier.strip())
            continue
        seen_external.add(normalized_email)
    deduped_reviewers.append((reviewer_identifier, relationship_type))

if duplicate_labels:
    duplicates_display = ", ".join(duplicate_labels)
    st.error(
        f"[Error] Duplicate reviewer{'s' if len(duplicate_labels) > 1 else ''} detected: {duplicates_display}. "
        "Each reviewer can only be nominated once per cycle."
    )

selected_reviewers = deduped_reviewers
duplicate_detected = len(duplicate_labels) > 0

"""Validation and submission"""
st.subheader("Review Your Selection")

if remaining_slots <= 0:
    st.info("You have no nomination slots remaining for this cycle.")
elif len(selected_reviewers) == 0:
    st.warning("[Warning] Please select at least one reviewer to add.")
elif duplicate_detected:
    st.info("Remove duplicate reviewers to continue.")
elif len(selected_reviewers) + total_nominations > 4:
    # Friendlier message when exceeding remaining capacity
    plural = "reviewer" if remaining_slots == 1 else "reviewers"
    st.error(
        f"You can add {remaining_slots} more {plural}. Deselect some selections to continue."
    )
else:
    st.success(f"[Success] You have selected {len(selected_reviewers)} reviewers.")

    # Get automatically assigned relationships
    reviewer_identifiers = [
        reviewer[0] for reviewer in selected_reviewers
    ]  # Extract just the identifiers
    relationships_with_preview = get_relationship_with_preview(
        current_user_id, reviewer_identifiers
    )

    # Merge in external selections that won't be returned by relationship mapper
    external_pairs = [
        (rid, rtype)
        for (rid, rtype) in selected_reviewers
        if not isinstance(rid, int)
    ]
    # Build combined list, preserving mapped internal relationships
    mapped_ids = set(
        rid for (rid, _rtype) in relationships_with_preview
    )
    combined_pairs = list(relationships_with_preview)
    for rid, rtype in external_pairs:
        if rid not in mapped_ids:
            combined_pairs.append((rid, "external_stakeholder"))

    # Show summary with relationships (internal mapped; externals explicit)
    st.write("**Selected Reviewers with Auto-Assigned Relationships:**")
    st.info("Relationships are automatically determined based on organizational structure")

    for reviewer_identifier, relationship_type in combined_pairs:
        if isinstance(reviewer_identifier, int):
            reviewer_info = next(
                u for u in users if u["user_type_id"] == reviewer_identifier
            )
            relationship_display = relationship_type.replace("_", " ").title()
            st.write(f" **{reviewer_info['name']}** - {relationship_display}")
        else:
            st.write(f"**{reviewer_identifier}** - External Stakeholder")

    if st.button(
        f"Add {len(selected_reviewers)} Reviewer{'s' if len(selected_reviewers) > 1 else ''}",
        type="primary",
    ):
        # Use the relationships with auto-assigned types
        success, message = create_feedback_request_fixed(
            current_user_id, combined_pairs
        )

        if success:
            st.success("[Success] Feedback requests added successfully!")
            st.info(
                "Your new requests have been sent to your manager for approval. You will be notified once they are processed."
            )
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

        with st.expander(
            f"{nomination['reviewer_name']} - {nomination['relationship_type'].replace('_', ' ').title()}"
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
    st.info("You can nominate up to 4 reviewers total.")

st.markdown("---")

st.subheader("How it works:")
st.write(
    """
1. **Select Reviewers**: Please nominate up to four collaborators you’ve worked closely with, within or outside Tech4Dev.
2. **Flexible Nomination**: Add reviewers one at a time or in small groups - no need to nominate all 4 at once
3. **Automatic Relationship Assignment**: The system determines relationships based on organizational structure:
   - **Peers**: Same team, no direct reporting relationship
   - **Internal Collaborators**: Different teams, cross-team collaboration  
   - **Direct Reportees**: People who report directly to you
   - **External Stakeholders**: People outside the organization
4. **Manager Approval**: Your manager will review and approve your selections
5. **Feedback Collection**: Approved reviewers will receive feedback forms
6. **Anonymous Results**: You'll receive anonymized feedback once completed
"""
)

# Show nomination limits info
st.info(
    "**Note:** Each person can only receive a maximum of four feedback requests to prevent overload."
)
# moved
