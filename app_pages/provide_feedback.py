import streamlit as st
from services.db_helper import (
    get_pending_reviews_for_user,
    get_questions_by_relationship_type,
    get_draft_responses,
    save_draft_response,
    submit_final_feedback,
    get_active_review_cycle,
    check_user_deadline_enforcement,
)

st.title("Complete Feedback")

# Check if there's an active review cycle
active_cycle = get_active_review_cycle()
if not active_cycle:
    st.warning(
        "⚠️ No active review cycle found. Contact HR to start a new feedback cycle."
    )
    st.stop()

st.info(
    f"**Active Cycle:** {active_cycle['cycle_name']} | **Feedback Deadline:** {active_cycle['feedback_deadline']}"
)

user_id = st.session_state["user_data"]["user_type_id"]

# Check deadline enforcement
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
    st.info("🎉 No pending feedback requests.")
    st.stop()

# Check if a specific review was selected
selected_review_id = st.session_state.get("selected_review_id")
selected_idx = None

if selected_review_id:
    # Find the index of the selected review
    for i, review in enumerate(pending_reviews):
        if review[0] == selected_review_id:
            selected_idx = i
            break
    # Clear the selection
    st.session_state["selected_review_id"] = None

# Select review to complete
if selected_idx is None:
    review_options = [
        f"{row[1]} {row[2]} ({row[3]}) - {row[5].replace('_', ' ').title()}"
        for row in pending_reviews
    ]
    selected_idx = st.selectbox(
        "Select feedback request to complete:",
        range(len(review_options)),
        format_func=lambda x: review_options[x],
    )

if selected_idx is not None:
    review = pending_reviews[selected_idx]
    request_id = review[0]
    requester_name = f"{review[1]} {review[2]}"
    requester_vertical = review[3]
    relationship_type = review[5]

    st.info(f"**Providing feedback for:** {requester_name} ({requester_vertical})")
    st.info(f"**Your relationship:** {relationship_type.replace('_', ' ').title()}")

    # Get questions for this relationship type
    questions = get_questions_by_relationship_type(relationship_type)

    if not questions:
        st.error("No questions found for this relationship type.")
        st.stop()

    # Load existing draft responses
    draft_responses = get_draft_responses(request_id)

    # Form for feedback
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
                col_low, col_slider, col_high = st.columns([0.15, 0.7, 0.15])
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
                        label_visibility="collapsed" # Hide the default label as we are adding custom ones
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

        # Action buttons
        col1, col2, col3 = st.columns([1, 1, 1])

        with col1:
            save_draft = st.form_submit_button(
                "💾 Save Draft", help="Save your progress and continue later"
            )

        with col2:
            submit_final = st.form_submit_button(
                "✅ Submit Final Feedback", type="primary", disabled=not all_complete
            )

        with col3:
            if st.form_submit_button("← Back to Reviews"):
                st.switch_page("app_pages/my_reviews.py")

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
                st.success("💾 Draft saved successfully! You can continue later.")
            else:
                st.error("❌ Error saving some responses. Please try again.")

        if submit_final:
            if not all_complete:
                st.error("❌ Please complete all text questions before submitting.")
            else:
                if submit_final_feedback(request_id, responses):
                    st.success("🎉 Feedback submitted successfully!")
                    st.info(
                        "Your feedback has been recorded and will be shared anonymously."
                    )

                    # Clear from pending reviews and refresh
                    if st.button("Continue to Next Review"):
                        st.rerun()
                else:
                    st.error("❌ Error submitting feedback. Please try again.")

# Show progress
if len(pending_reviews) > 1:
    st.sidebar.write(f"**Reviews Remaining:** {len(pending_reviews)}")
    st.sidebar.write("You can switch between reviews using the dropdown above.")

# Guidelines
with st.expander("💡 Feedback Guidelines"):
    st.write(
        """
    **Providing Effective Feedback:**
    - Be specific and constructive
    - Focus on behaviors, not personality
    - Provide examples when possible
    - Be honest but respectful
    - Consider the person's growth and development
    
    **Rating Scale:**
    - **1-2**: Needs significant improvement
    - **3**: Meets expectations
    - **4-5**: Exceeds expectations
    
    **Remember:** Your feedback is anonymous and will help your colleague grow professionally.
    """
    )
