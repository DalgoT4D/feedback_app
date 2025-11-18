import streamlit as st
from datetime import datetime, timedelta, date
from services.db_helper import (
    get_hr_dashboard_metrics,
    get_users_with_pending_reviews,
    create_new_review_cycle,
    create_named_cycle,
    get_active_review_cycle,
    get_current_cycle_phase,
    get_all_cycles,
    mark_cycle_complete,
)
from services.email_service import send_reminder_email

st.title("HR Analytics Dashboard")

# Current cycle status
st.subheader("Current Review Cycle")
active_cycle = get_active_review_cycle()
current_phase = get_current_cycle_phase()

if active_cycle:
    col1, col2 = st.columns(2)
    with col1:
        st.info(
            f"**{active_cycle['cycle_display_name'] or active_cycle['cycle_name']}**"
        )
        st.write(f"Current Phase: **{current_phase}**")
        if active_cycle["cycle_description"]:
            st.caption(active_cycle["cycle_description"])
    with col2:
        st.write(f"Nomination Deadline: {active_cycle['nomination_deadline']}")
        st.write(f"Feedback Deadline: {active_cycle['feedback_deadline']}")
        if active_cycle["cycle_year"] and active_cycle["cycle_quarter"]:
            st.write(
                f"Period: {active_cycle['cycle_year']} {active_cycle['cycle_quarter']}"
            )
else:
    st.warning(
        "No active review cycle found. Create a new review cycle to begin the feedback process."
    )

# Create new cycle section
st.subheader("Cycle Management")

if active_cycle:
    # Show cycle management options when there's an active cycle
    col1, col2 = st.columns(2)
    with col1:
        if st.button("Manage Cycle Deadlines", use_container_width=True):
            st.switch_page("app_pages/manage_cycle_deadlines.py")
    with col2:
        if st.button("Mark Cycle Complete", use_container_width=True):
            st.session_state.show_complete_form = True

    st.info(
        "**Note:** You cannot create a new cycle while one is active. Modify the current cycle or mark it complete first."
    )
    st.markdown("---")  # Add separator here
else:
    # Only show create button when no active cycle
    if st.button("Create New Review Cycle"):
        st.session_state.show_cycle_form = True

if st.session_state.get("show_cycle_form", False):
    st.subheader("Create New Review Cycle")

    with st.form("new_cycle_form"):
        col1, col2 = st.columns([2, 1])

        with col1:
            display_name = st.text_input(
                "Cycle Display Name",
                value=f"Q{((datetime.now().month-1)//3)+1} {datetime.now().year} Performance Review",
                help="User-friendly name that will be displayed throughout the application",
            )

        with col2:
            cycle_year = st.selectbox(
                "Year", options=[datetime.now().year, datetime.now().year + 1], index=0
            )
            cycle_quarter = st.selectbox(
                "Quarter",
                options=["Q1", "Q2", "Q3", "Q4"],
                index=((datetime.now().month - 1) // 3),
            )

        description = st.text_area(
            "Cycle Description",
            value="Performance review and development feedback cycle",
            help="Description of the cycle's purpose and objectives",
        )

        # Auto-generate internal cycle name
        internal_name = f"cycle_{cycle_year}_{cycle_quarter.lower()}_{int(datetime.now().timestamp())}"
        st.caption(f"Internal cycle ID: {internal_name}")

        st.divider()
        st.write("**Timeline Configuration**")

        col1, col2 = st.columns(2)
        with col1:
            nomination_start = st.date_input(
                "Nomination Start Date", value=date.today()
            )

        with col2:
            nomination_deadline = st.date_input(
                "Nomination Deadline", value=nomination_start + timedelta(weeks=2)
            )

        feedback_deadline = st.date_input(
            "Feedback Deadline",
            value=nomination_deadline + timedelta(weeks=3),
            help="Final deadline for completing all feedback forms",
        )

        # Submit buttons
        col1, col2 = st.columns(2)
        with col1:
            create_cycle = st.form_submit_button("Create Cycle", type="primary")
        with col2:
            cancel_cycle = st.form_submit_button("Cancel")

        if create_cycle:
            if display_name and description:
                user_id = st.session_state["user_data"]["user_type_id"]

                try:
                    # Convert date objects to strings for database compatibility
                    nomination_start_str = nomination_start.strftime("%Y-%m-%d")
                    nomination_deadline_str = nomination_deadline.strftime("%Y-%m-%d")
                    feedback_deadline_str = feedback_deadline.strftime("%Y-%m-%d")

                    success, info = create_named_cycle(
                        display_name,
                        description,
                        cycle_year,
                        cycle_quarter,
                        internal_name,
                        nomination_start_str,
                        nomination_deadline_str,
                        feedback_deadline_str,
                        user_id,
                    )

                    if success:
                        st.success(f"Review cycle created successfully (ID {info})!")
                        st.session_state.show_cycle_form = False
                        # Clear any cached data
                        if hasattr(st.session_state, "active_cycle_cache"):
                            del st.session_state.active_cycle_cache
                        # Temporarily disable badges during rerun to avoid conflicts
                        st.session_state.temp_disable_badges = True
                        st.rerun()
                    else:
                        st.error(f"Error creating cycle: {info}")
                except Exception as e:
                    st.error(f"Exception during cycle creation: {str(e)}")
            else:
                st.error("Please enter both display name and description")

        if cancel_cycle:
            st.session_state.show_cycle_form = False

# Complete cycle form
if st.session_state.get("show_complete_form", False):
    st.subheader("Mark Cycle Complete")

    with st.form("complete_cycle_form"):
        st.warning(
            f"You are about to mark **{active_cycle['cycle_display_name'] or active_cycle['cycle_name']}** as complete."
        )
        st.write("This action will:")
        st.write("- Set the cycle status to 'completed'")
        st.write("- Deactivate the cycle")
        st.write("- Allow creation of new cycles")
        st.write("- Preserve all feedback data")

        completion_notes = st.text_area(
            "Completion Notes (Optional)",
            help="Add any notes about this cycle's completion",
        )

        # Submit buttons
        col1, col2 = st.columns(2)
        with col1:
            complete_cycle = st.form_submit_button("Mark Complete", type="primary")
        with col2:
            cancel_complete = st.form_submit_button("Cancel")

        if complete_cycle:
            try:
                success, message = mark_cycle_complete(
                    active_cycle["cycle_id"], completion_notes
                )
                if success:
                    st.success("Cycle marked as complete!")
                    st.session_state.show_complete_form = False
                    # Single rerun to reflect completed status and enable new cycle creation
                    st.rerun()
                else:
                    st.error(f"Error marking cycle complete: {message}")
            except Exception as e:
                st.error(f"Exception marking cycle complete: {str(e)}")

        if cancel_complete:
            st.session_state.show_complete_form = False

if active_cycle:  # Wrap the entire section
    # Historical cycles section
    st.subheader("Cycle History")
    all_cycles = get_all_cycles()
    if all_cycles:
        if len(all_cycles) > 1 or (
            len(all_cycles) == 1 and not all_cycles[0]["is_active"]
        ):
            st.write("**Previous and Completed Cycles:**")

            for cycle in all_cycles[:5]:  # Show last 5 cycles
                col1, col2, col3, col4 = st.columns([3, 1, 1, 1])

                with col1:
                    status_icon = "[Active]" if cycle["is_active"] else "[Completed]"
                    cycle_name = cycle["cycle_display_name"] or cycle["cycle_name"]
                    st.write(f"{status_icon} **{cycle_name}**")
                    if cycle["cycle_description"]:
                        st.caption(cycle["cycle_description"])

                with col2:
                    if cycle["cycle_year"] and cycle["cycle_quarter"]:
                        st.write(f"{cycle['cycle_year']} {cycle['cycle_quarter']}")
                    else:
                        st.write("—")

                with col3:
                    # Use correct status logic
                    if cycle["is_active"]:
                        display_status = "active"
                    else:
                        display_status = cycle.get("phase_status", "completed")
                    st.write(f"Status: {display_status}")

                # Removed non-functional View button

            st.divider()
        else:
            st.info("No previous cycles to display.")
    else:
        st.info("No cycles found. Create your first cycle above!")
    st.markdown("---")  # Add separator
