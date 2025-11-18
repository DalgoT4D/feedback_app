import streamlit as st
import pandas as pd
from datetime import datetime
from services.db_helper import get_reviewer_rejections_for_hr

st.title("Reviewer Rejections")
st.markdown("Monitor and review feedback request rejections by reviewers")

# Get all reviewer rejections
rejections = get_reviewer_rejections_for_hr()

if not rejections:
    st.info("No reviewer rejections to review.")
    st.write(
        "When reviewers decline feedback requests, they will appear here with their reasons."
    )
else:
    st.write(f"**Total Rejections:** {len(rejections)}")

    # Summary metrics
    col1, col2, col3 = st.columns(3)

    with col1:
        # Count by cycle
        cycles = set(r["cycle_name"] for r in rejections)
        st.metric("Active Cycles with Rejections", len(cycles))

    with col2:
        # Recent rejections (last 7 days)
        recent_count = 0
        for rejection in rejections:
            if rejection["rejection_date"]:
                try:
                    rejection_date = datetime.strptime(
                        rejection["rejection_date"][:10], "%Y-%m-%d"
                    ).date()
                    days_ago = (datetime.now().date() - rejection_date).days
                    if days_ago <= 7:
                        recent_count += 1
                except:
                    pass
        st.metric("Rejections (Last 7 Days)", recent_count)

    with col3:
        # Unique reviewers who have rejected
        unique_reviewers = set(r["reviewer_email"] for r in rejections)
        st.metric("Reviewers with Rejections", len(unique_reviewers))

    st.markdown("---")

    # Filter options
    st.subheader("Filter Rejections")
    col1, col2 = st.columns(2)

    with col1:
        cycle_filter = st.selectbox(
            "Filter by Cycle", ["All Cycles"] + list(cycles), index=0
        )

    with col2:
        vertical_filter = st.selectbox(
            "Filter by Reviewer Department",
            ["All Departments"]
            + list(
                set(
                    r["reviewer_vertical"] for r in rejections if r["reviewer_vertical"]
                )
            ),
            index=0,
        )

    # Apply filters
    filtered_rejections = rejections
    if cycle_filter != "All Cycles":
        filtered_rejections = [
            r for r in filtered_rejections if r["cycle_name"] == cycle_filter
        ]
    if vertical_filter != "All Departments":
        filtered_rejections = [
            r for r in filtered_rejections if r["reviewer_vertical"] == vertical_filter
        ]

    st.write(f"Showing {len(filtered_rejections)} of {len(rejections)} rejections")

    # Display rejections
    for rejection in filtered_rejections:
        with st.expander(
            f" {rejection['reviewer_name']} declined {rejection['requester_name']} - {rejection['rejection_date'][:10] if rejection['rejection_date'] else 'N/A'}"
        ):

            col1, col2 = st.columns([2, 1])

            with col1:
                st.write("**Rejection Details:**")
                st.write(f"**Reason:** {rejection['rejection_reason']}")
                st.write(
                    f"**Date:** {rejection['rejection_date'][:10] if rejection['rejection_date'] else 'N/A'}"
                )
                st.write(
                    f"**Relationship:** {rejection['relationship_type'].replace('_', ' ').title()}"
                )
                st.write(f"**Cycle:** {rejection['cycle_name']}")

            with col2:
                st.write("**People Involved:**")
                st.write(f"**Requester:** {rejection['requester_name']}")
                st.write(f"**Requester Dept:** {rejection['requester_vertical']}")
                st.write(f"**Reviewer:** {rejection['reviewer_name']}")
                st.write(f"**Reviewer Dept:** {rejection['reviewer_vertical']}")

                # Contact information
                st.write("**Contact Info:**")
                st.code(f"Requester: {rejection['requester_email']}")
                st.code(f"Reviewer: {rejection['reviewer_email']}")

    # Export functionality
    st.markdown("---")
    st.subheader("Export Data")

    if st.button("Export to Excel", type="secondary"):
        # Prepare data for export
        export_data = []
        for rejection in filtered_rejections:
            export_data.append(
                {
                    "Rejection_Date": (
                        rejection["rejection_date"][:10]
                        if rejection["rejection_date"]
                        else ""
                    ),
                    "Cycle": rejection["cycle_name"],
                    "Requester_Name": rejection["requester_name"],
                    "Requester_Email": rejection["requester_email"],
                    "Requester_Department": rejection["requester_vertical"],
                    "Reviewer_Name": rejection["reviewer_name"],
                    "Reviewer_Email": rejection["reviewer_email"],
                    "Reviewer_Department": rejection["reviewer_vertical"],
                    "Relationship_Type": rejection["relationship_type"],
                    "Rejection_Reason": rejection["rejection_reason"],
                }
            )

        if export_data:
            df = pd.DataFrame(export_data)
            csv = df.to_csv(index=False)
            st.download_button(
                label="Download CSV",
                data=csv,
                file_name=f"reviewer_rejections_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                mime="text/csv",
            )
        else:
            st.warning("No data to export with current filters.")
