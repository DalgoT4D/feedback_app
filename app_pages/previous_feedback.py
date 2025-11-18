import streamlit as st
from services.db_helper import (
    get_anonymized_feedback_for_user,
    generate_feedback_excel_data,
    get_all_cycles,
)
from app_pages.components.feedback_display import (
    ensure_feedback_styles,
    render_rating_card,
    render_text_card,
    build_feedback_excel,
)

st.title("Previous Feedback Cycle Results")

# Get all cycles
all_cycles = get_all_cycles()
completed_cycles = [c for c in all_cycles if not c["is_active"]]

# Cycle selection for historical data
if completed_cycles:
    cycle_options = [
        f"{c['cycle_display_name']} ({c['cycle_year']} {c['cycle_quarter']})"
        for c in completed_cycles
    ]
    selected_cycle_display = st.selectbox(
        "View Cycle:", cycle_options, key="cycle_selector"
    )

    selected_cycle_index = cycle_options.index(selected_cycle_display)
    selected_cycle_id = completed_cycles[selected_cycle_index]["cycle_id"]
else:
    selected_cycle_id = None

user_id = st.session_state["user_data"]["user_type_id"]

# Display anonymized feedback - filter by cycle if selected
if selected_cycle_id:
    feedback_data = get_feedback_by_cycle(user_id, selected_cycle_id)
    st.subheader(f"📊 Historical Feedback: {selected_cycle_display}")
else:
    feedback_data = None

feedback_data = {}
if selected_cycle_id:
    feedback_data = get_anonymized_feedback_for_user(user_id, selected_cycle_id)
    st.subheader(f"📊 Historical Feedback: {selected_cycle_display}")
    ensure_feedback_styles()

    excel_rows = generate_feedback_excel_data(user_id, selected_cycle_id)
    excel_bytes, excel_filename = build_feedback_excel(
        excel_rows, selected_cycle_id, sheet_name="Cycle_Feedback"
    )
    if excel_bytes:
        st.download_button(
            label="Download Cycle Feedback (Excel)",
            data=excel_bytes,
            file_name=excel_filename,
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            type="primary",
            use_container_width=True,
        )

if feedback_data:
    ensure_feedback_styles()
    st.subheader("Feedback Results (Anonymized)")
    st.info("All feedback is anonymized - you cannot see who provided each review.")

    sorted_feedback = sorted(
        feedback_data.items(),
        key=lambda item: item[1]["completed_at"] or "",
        reverse=True,
    )

    for i, (request_id, feedback) in enumerate(sorted_feedback, 1):
        with st.expander(
            f"Review #{i} - {feedback['relationship_type'].replace('_', ' ').title()}",
            expanded=False,
        ):
            st.write(f"**Completed:** {feedback['completed_at']}")
            st.write(
                f"**Reviewer Type:** {feedback['relationship_type'].replace('_', ' ').title()}"
            )

            st.markdown("**Responses:**")

            for response in feedback["responses"]:
                if response["question_type"] == "rating":
                    render_rating_card(response["question_text"], response["rating_value"])
                else:
                    render_text_card(response["question_text"], response["response_value"])
else:
    if selected_cycle_id:
        st.info("📭 No feedback results available for the selected cycle.")
    else:
        st.info("📭 No completed feedback cycles are available yet.")
