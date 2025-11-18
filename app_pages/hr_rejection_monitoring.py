import streamlit as st
from services.db_helper import get_hr_rejections_dashboard
from datetime import datetime

st.title("Rejection Monitoring")

st.info(
    "Monitor all nomination rejections across both manager approvals and reviewer acceptances. "
    "This helps identify patterns and ensure the feedback process runs smoothly."
)

# Get all rejections for current cycle
rejections = get_hr_rejections_dashboard()

if not rejections:
    st.success(
        "No rejections found for the current cycle. The feedback process is running smoothly!"
    )
else:
    st.warning(
        f"Found {len(rejections)} rejection{'s' if len(rejections) > 1 else ''} to review."
    )

    # Tabs for different rejection types
    manager_rejections = [
        r for r in rejections if r["rejection_type"] == "manager_rejection"
    ]
    reviewer_rejections = [
        r for r in rejections if r["rejection_type"] == "reviewer_rejection"
    ]

    tab1, tab2 = st.tabs(
        [
            f"Manager Rejections ({len(manager_rejections)})",
            f"Reviewer Rejections ({len(reviewer_rejections)})",
        ]
    )

    with tab1:
        st.subheader("Manager Approval Rejections")
        if manager_rejections:
            st.info(
                "These nominations were rejected by managers during the approval process. "
                "Employees can nominate different reviewers for these slots."
            )

            for rejection in manager_rejections:
                with st.expander(
                    f"[Manager Rejection] {rejection['requester_name']} → {rejection['reviewer_name']}",
                    expanded=False,
                ):
                    cols = st.columns([2, 1, 1])

                    with cols[0]:
                        st.write(
                            f"**Requester:** {rejection['requester_name']} ({rejection['requester_email']})"
                        )
                        st.write(f"**Rejected Reviewer:** {rejection['reviewer_name']}")
                        st.write(
                            f"**Relationship:** {rejection['relationship_type'].replace('_', ' ').title()}"
                        )
                        st.write(f"**Rejected By:** {rejection['rejected_by_name']}")

                    with cols[1]:
                        st.write(f"**Date:** {rejection['rejected_at'][:10]}")
                        st.write(f"**Time:** {rejection['rejected_at'][11:19]}")

                    with cols[2]:
                        if not rejection["viewed_by_hr"]:
                            st.error("[New] New rejection")
                        else:
                            st.success("[Reviewed] Reviewed")

                    if rejection["rejection_reason"]:
                        st.error(
                            f"**Rejection Reason:** {rejection['rejection_reason']}"
                        )
                    else:
                        st.warning("**Rejection Reason:** No specific reason provided")
        else:
            st.success("[Complete] No manager rejections found.")

    with tab2:
        st.subheader("Reviewer Acceptance Rejections")
        if reviewer_rejections:
            st.info(
                "These feedback requests were declined by the nominated reviewers. "
                "Employees can nominate different reviewers for these slots."
            )

            for rejection in reviewer_rejections:
                with st.expander(
                    f"[Reviewer Rejection] {rejection['requester_name']} → {rejection['reviewer_name']}",
                    expanded=False,
                ):
                    cols = st.columns([2, 1, 1])

                    with cols[0]:
                        st.write(
                            f"**Requester:** {rejection['requester_name']} ({rejection['requester_email']})"
                        )
                        st.write(
                            f"**Reviewer Who Declined:** {rejection['reviewer_name']}"
                        )
                        st.write(
                            f"**Relationship:** {rejection['relationship_type'].replace('_', ' ').title()}"
                        )

                    with cols[1]:
                        st.write(f"**Date:** {rejection['rejected_at'][:10]}")
                        st.write(f"**Time:** {rejection['rejected_at'][11:19]}")

                    with cols[2]:
                        if not rejection["viewed_by_hr"]:
                            st.error("[New] New rejection")
                        else:
                            st.success("[Reviewed] Reviewed")

                    if rejection["rejection_reason"]:
                        st.error(
                            f"**Rejection Reason:** {rejection['rejection_reason']}"
                        )
                    else:
                        st.warning("**Rejection Reason:** No specific reason provided")
        else:
            st.success("No reviewer rejections found.")

# Summary statistics
if rejections:
    st.markdown("---")
    st.subheader("Rejection Analysis")

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric("Total Rejections", len(rejections))
    with col2:
        st.metric("Manager Rejections", len(manager_rejections))
    with col3:
        st.metric("Reviewer Rejections", len(reviewer_rejections))
    with col4:
        unreviewed = len([r for r in rejections if not r["viewed_by_hr"]])
        st.metric("New/Unreviewed", unreviewed)

    # Common rejection reasons
    if rejections:
        st.subheader("Common Rejection Patterns")

        # Group by rejection reason
        reason_counts = {}
        for rejection in rejections:
            reason = rejection["rejection_reason"] or "No reason provided"
            reason_counts[reason] = reason_counts.get(reason, 0) + 1

        if reason_counts:
            st.write("**Most Common Rejection Reasons:**")
            for reason, count in sorted(
                reason_counts.items(), key=lambda x: x[1], reverse=True
            )[:5]:
                st.write(f"• {reason}: {count} occurrence{'s' if count > 1 else ''}")

st.markdown("---")

st.subheader("How Rejections Work")
st.write(
    """
**Manager Rejection Process:**
1. Employee nominates reviewers
2. Manager reviews nominations during approval phase
3. Manager can reject nominations with reasons
4. Rejected nominations don't count toward 4-person limit
5. Employee can nominate different reviewers

**Reviewer Rejection Process:**
1. Manager-approved nominations are sent to reviewers
2. Reviewers can accept or decline requests
3. Declined requests are tracked with reasons
4. Declined requests don't count toward 4-person limit
5. Employee can nominate different reviewers

**Important:** Employees cannot re-nominate the same person who was previously rejected in the same cycle.
"""
)
