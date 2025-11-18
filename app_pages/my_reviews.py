import streamlit as st
import time
from services.db_helper import (
    get_pending_reviews_for_user,
    get_active_review_cycle,
    get_all_cycles,
    get_questions_by_relationship_type,
    get_draft_responses,
    save_draft_response,
    submit_final_feedback,
    check_user_deadline_enforcement,
)
from utils.badge_utils import update_local_badge

st.title("Provide Feedback")

# Check if there's an active review cycle
active_cycle = get_active_review_cycle()
pending_reviews = []  # Initialize pending_reviews
if not active_cycle:
    st.warning(
        "No active review cycle found. Contact HR to start a new feedback cycle."
    )

    # Show historical cycles
    all_cycles = get_all_cycles()
    if all_cycles:
        st.subheader("Previous Cycles")
        st.info(
            "While there's no active cycle, here are the previous feedback cycles for reference:"
        )
        for cycle in all_cycles[:3]:  # Show last 3 cycles
            status_icon = "[Active]" if cycle["is_active"] else "[Completed]"
            st.write(
                f"{status_icon} **{cycle['cycle_display_name']}** ({cycle['cycle_year']} {cycle['cycle_quarter']}) - Status: {cycle['phase_status']}"
            )
else:
    st.info(
        f"**Active Cycle:** {active_cycle['cycle_display_name'] or active_cycle['cycle_name']} | **Feedback Deadline:** {active_cycle['feedback_deadline']}"
    )

    user_id = st.session_state["user_data"]["user_type_id"]

    can_provide_feedback, deadline_message = check_user_deadline_enforcement(
        user_id, "feedback"
    )
    if not can_provide_feedback:
        st.error(f"🚫 {deadline_message}")
        st.info(
            "The feedback deadline has passed. You can no longer complete feedback forms."
        )
        st.stop()

    # Get pending reviews
    pending_reviews = get_pending_reviews_for_user(user_id)

    if not pending_reviews:
        st.success("You have no pending feedback reviews!")
        st.info(
            "When colleagues request your feedback, their requests will appear here."
        )
    else:
        active_review_id = st.session_state.get("active_review_id")
        selected_review = None
        if active_review_id:
            for review in pending_reviews:
                if review[0] == active_review_id:
                    selected_review = review
                    break
            if not selected_review:
                st.session_state.pop("active_review_id", None)

        st.write(f"You have **{len(pending_reviews)}** feedback review(s) to complete:")

        for i, review in enumerate(pending_reviews, 1):
            request_id = review[0]
            requester_name = f"{review[1]} {review[2]}"
            requester_vertical = review[3]
            created_at = review[4]
            relationship_type = review[5]
            draft_count = review[6]

            with st.container():
                col1, col2, col3 = st.columns([3, 2, 1])

                with col1:
                    st.write(f"**{i}. Feedback for {requester_name}**")
                    st.write(f"Department: {requester_vertical}")
                    st.write(
                        f"Relationship: {relationship_type.replace('_', ' ').title()}"
                    )

                with col2:
                    st.write(f"Requested: {created_at[:10]}")
                    if draft_count > 0:
                        st.write("*Draft saved*")
                    else:
                        st.write("*Not started*")

                with col3:
                    button_label = (
                        "Resume Review" if draft_count > 0 else "Start Review"
                    )
                    if st.button(
                        button_label, key=f"complete_{request_id}", type="primary"
                    ):
                        st.session_state["active_review_id"] = request_id
                        st.rerun()

                st.divider()

        if selected_review:
            st.subheader("Provide Feedback Form")

            request_id = selected_review[0]
            requester_name = f"{selected_review[1]} {selected_review[2]}"
            requester_vertical = selected_review[3]
            relationship_type = selected_review[5]

            st.info(
                f"**Providing feedback for:** {requester_name} ({requester_vertical})"
            )
            st.info(
                f"**Your relationship:** {relationship_type.replace('_', ' ').title()}"
            )

            questions = get_questions_by_relationship_type(relationship_type)
            if not questions:
                st.error("No questions found for this relationship type.")
            else:
                draft_responses = get_draft_responses(request_id)

                with st.form(f"feedback_form_{request_id}"):
                    responses = {}
                    all_complete = True

                    st.subheader("Please provide your feedback:")

                    for question in questions:
                        question_id = question[0]
                        question_text = question[1]
                        question_type = question[2]

                        st.markdown(f"**{question_text}**")

                        existing_draft = draft_responses.get(question_id, {})

                        if question_type == "rating":
                            col_low, col_slider, col_high = st.columns(
                                [0.15, 0.7, 0.15]
                            )
                            with col_low:
                                st.markdown("Low")
                            with col_slider:
                                rating = st.slider(
                                    "Rating (1-5):",
                                    min_value=1,
                                    max_value=5,
                                    value=existing_draft.get("rating_value", 3),
                                    key=f"rating_{question_id}",
                                    help="1 = Needs Improvement, 3 = Meets Expectations, 5 = Exceeds Expectations",
                                    label_visibility="collapsed",
                                )
                            with col_high:
                                st.markdown("High")
                            responses[question_id] = {"rating_value": rating}

                        elif question_type == "text":
                            text_response = st.text_area(
                                "Your response:",
                                value=existing_draft.get("response_value", ""),
                                key=f"text_{question_id}",
                                height=120,
                                help="Please provide specific, constructive feedback",
                            )
                            responses[question_id] = {"response_value": text_response}

                            if not text_response.strip():
                                all_complete = False

                        st.markdown("---")

                    col1, col2, col3 = st.columns([1, 1, 1])

                    with col1:
                        save_draft = st.form_submit_button(
                            "💾 Save Draft",
                            help="Save your progress and continue later",
                        )

                    with col2:
                        submit_final = st.form_submit_button(
                            "✅ Submit Final Feedback", type="primary"
                        )

                    with col3:
                        if st.form_submit_button("← Back to list"):
                            st.session_state.pop("active_review_id", None)
                            st.rerun()

                    if save_draft:
                        success_count = 0
                        for q_id, response_data in responses.items():
                            if save_draft_response(
                                request_id,
                                q_id,
                                response_data.get("response_value"),
                                response_data.get("rating_value"),
                            ):
                                success_count += 1

                        if success_count == len(responses):
                            st.success(
                                "💾 Draft saved successfully! Returning to list..."
                            )
                            time.sleep(1)
                            st.session_state.pop("active_review_id", None)
                            st.rerun()
                        else:
                            st.error(
                                "❌ Error saving some responses. Please try again."
                            )

                    if submit_final:
                        if not all_complete:
                            st.error(
                                "❌ Please complete all text questions before submitting."
                            )
                        else:
                            if submit_final_feedback(request_id, responses):
                                st.success("🎉 Feedback submitted successfully!")
                                st.info(
                                    "Your feedback has been recorded and will be shared anonymously."
                                )

                                remaining_reviews = get_pending_reviews_for_user(
                                    user_id
                                )
                                if len(remaining_reviews) <= 1:
                                    update_local_badge("feedback_forms", completed=True)

                                st.success("Returning to list...")
                                time.sleep(1)
                                st.session_state.pop("active_review_id", None)
                                st.rerun()
                            else:
                                st.error(
                                    "❌ Error submitting feedback. Please try again."
                                )

st.markdown("---")
st.subheader("About Providing Feedback")
st.write(
    """
- **Confidential**: Your responses will be anonymized when shared with the requester
- **Draft Saving**: You can save your progress and complete reviews later
- **Different Questions**: Question sets vary based on your relationship with the requester
- **Thoughtful Responses**: Take time to provide constructive and helpful feedback
"""
)

# Show information about question types
with st.expander("What types of questions will I see?"):
    st.write(
        """
    **For Peers/Internal Stakeholders/Managers:**
    - Collaboration, Communication, Reliability, Ownership (Trust)
    - Open-ended questions about strengths and areas for improvement
    
    **For Direct Reportees (reviewing your manager/lead):**
    - Approachability, Openness to feedback, Clarity in direction, Communication effectiveness
    - Leadership feedback
    
    **For External Stakeholders:**
    - Professionalism, Reliability, Responsiveness, Communication clarity
    - Understanding of needs, Quality of delivery
    - Collaboration and delivery examples
    """
    )

if pending_reviews:
    st.info(
        "**Tip:** You can save drafts and return later to complete your reviews. All questions must be answered before final submission."
    )
