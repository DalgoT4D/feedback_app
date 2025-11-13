"""
Employee Dashboard - Landing page showing cycle deadlines and personal progress
"""

import streamlit as st
from datetime import datetime, date
from services.db_helper import (
    get_active_review_cycle,
    get_user_deadline,
    get_feedback_progress_for_user,
    is_deadline_passed,
    get_pending_reviews_for_user,
    get_pending_reviewer_requests,
)

# Check authentication
if "authenticated" not in st.session_state or not st.session_state.authenticated:
    st.warning("Please log in to access this page.")
    st.stop()

# Get user info
user_id = st.session_state.user_id
user_name = f"{st.session_state.first_name} {st.session_state.last_name}"

st.title(f"👋 Welcome, {user_name}!")

# Get active cycle
active_cycle = get_active_review_cycle()

if not active_cycle:
    st.warning("⚠️ No active review cycle found.")
    st.info(
        "Please check back later or contact HR for information about upcoming review cycles."
    )
    st.stop()

# Display cycle information
st.header(f"📋 Current Cycle: {active_cycle['cycle_display_name']}")

if active_cycle.get("cycle_description"):
    st.info(active_cycle["cycle_description"])

# Deadlines Section
st.subheader("🕐 Important Deadlines")

# Get user-specific deadlines (considering extensions)
cycle_id = active_cycle["cycle_id"]
user_nomination_deadline = get_user_deadline(cycle_id, user_id, "nomination")
user_feedback_deadline = get_user_deadline(cycle_id, user_id, "feedback")

# If no user-specific deadline, use cycle deadlines
if not user_nomination_deadline:
    user_nomination_deadline = active_cycle["nomination_deadline"]
if not user_feedback_deadline:
    user_feedback_deadline = active_cycle["feedback_deadline"]

# Display deadlines with status
col1, col2 = st.columns(2)

with col1:
    nom_deadline_date = datetime.strptime(user_nomination_deadline, "%Y-%m-%d").date()
    nom_passed = is_deadline_passed(nom_deadline_date)
    nom_days_left = (nom_deadline_date - date.today()).days

    deadline_color = "🔴" if nom_passed else ("🟡" if nom_days_left <= 3 else "🟢")

    st.markdown(
        f"""
    **{deadline_color} Nomination Deadline**
    
    **Date:** {nom_deadline_date.strftime('%B %d, %Y')}
    
    **Status:** {"❌ Passed" if nom_passed else f"✅ {nom_days_left} days left"}
    """
    )

with col2:
    feedback_deadline_date = datetime.strptime(
        user_feedback_deadline, "%Y-%m-%d"
    ).date()
    feedback_passed = is_deadline_passed(feedback_deadline_date)
    feedback_days_left = (feedback_deadline_date - date.today()).days

    deadline_color = (
        "🔴" if feedback_passed else ("🟡" if feedback_days_left <= 3 else "🟢")
    )

    st.markdown(
        f"""
    **{deadline_color} Feedback Deadline**
    
    **Date:** {feedback_deadline_date.strftime('%B %d, %Y')}
    
    **Status:** {"❌ Passed" if feedback_passed else f"✅ {feedback_days_left} days left"}
    """
    )

# Show extension notice if user has extensions
if (
    user_nomination_deadline != active_cycle["nomination_deadline"]
    or user_feedback_deadline != active_cycle["feedback_deadline"]
):
    st.success(
        "📝 **Note:** You have been granted deadline extensions. The dates above reflect your personalized deadlines."
    )

st.markdown("---")

# Personal Progress Section
st.subheader("📊 Your Progress")

# Get user's feedback progress
progress = get_feedback_progress_for_user(user_id)

# Display progress metrics
col1, col2, col3, col4 = st.columns(4)

with col1:
    st.metric(
        "Requests Submitted",
        progress["total_requests"],
        help="Total feedback requests you have submitted",
    )

with col2:
    st.metric(
        "Awaiting Approval",
        progress["awaiting_approval"],
        help="Requests waiting for manager approval",
    )

with col3:
    st.metric(
        "Pending Reviews",
        progress["pending_requests"],
        help="Approved requests waiting for reviewer response",
    )

with col4:
    st.metric(
        "Completed",
        progress["completed_requests"],
        help="Feedback forms that have been completed",
    )

# Quick Action Buttons
st.subheader("🚀 Quick Actions")

col1, col2, col3 = st.columns(3)

with col1:
    if st.button("📝 Request Feedback", type="primary", use_container_width=True):
        if nom_passed:
            st.error(
                "The nomination deadline has passed. You can no longer request new feedback."
            )
        else:
            st.switch_page("app_pages/request_feedback.py")

with col2:
    pending_reviews = len(get_pending_reviews_for_user(user_id))
    button_text = (
        f"✍️ Provide Feedback ({pending_reviews})"
        if pending_reviews > 0
        else "✍️ Provide Feedback"
    )

    if st.button(button_text, use_container_width=True):
        if feedback_passed:
            st.error(
                "The feedback deadline has passed. You can no longer fill out feedback forms."
            )
        else:
            st.switch_page("app_pages/provide_feedback.py")

with col3:
    if st.button("📄 View My Results", use_container_width=True):
        st.switch_page("app_pages/my_reviews.py")

# Pending Actions Section
pending_reviewer_requests = get_pending_reviewer_requests(user_id)
pending_reviews = get_pending_reviews_for_user(user_id)

if pending_reviewer_requests or pending_reviews:
    st.subheader("⏰ Actions Required")

    if pending_reviewer_requests:
        st.markdown("**🔔 Feedback Requests Needing Your Response:**")
        for req in pending_reviewer_requests[:3]:  # Show max 3
            requester_name = req["requester_name"]
            relationship = req["relationship_type"].replace("_", " ").title()

            with st.expander(f"Request from {requester_name} ({relationship})"):
                st.write(f"**Requester:** {requester_name}")
                st.write(f"**Relationship:** {relationship}")
                st.write(f"**Vertical:** {req['requester_vertical']}")
                st.write(f"**Requested:** {req['created_at']}")

                if st.button(
                    f"Respond to {requester_name}", key=f"respond_{req['request_id']}"
                ):
                    if nom_passed:
                        st.error(
                            "The nomination deadline has passed. All pending requests have been auto-accepted."
                        )
                    else:
                        st.switch_page("app_pages/approve_nominations.py")

        if len(pending_reviewer_requests) > 3:
            st.info(
                f"... and {len(pending_reviewer_requests) - 3} more requests. Visit the Approve Nominations page to see all."
            )

    if pending_reviews:
        st.markdown("**📝 Feedback Forms to Complete:**")
        for review in pending_reviews[:3]:  # Show max 3
            requester_name = f"{review[1]} {review[2]}"
            relationship = review[5].replace("_", " ").title()

            with st.expander(f"Feedback for {requester_name} ({relationship})"):
                st.write(f"**For:** {requester_name}")
                st.write(f"**Relationship:** {relationship}")
                st.write(f"**Vertical:** {review[3]}")
                st.write(f"**Due:** Soon")

                if st.button(
                    f"Complete Feedback for {requester_name}",
                    key=f"feedback_{review[0]}",
                ):
                    if feedback_passed:
                        st.error(
                            "The feedback deadline has passed. You can no longer fill out feedback forms."
                        )
                    else:
                        st.switch_page("app_pages/provide_feedback.py")

        if len(pending_reviews) > 3:
            st.info(
                f"... and {len(pending_reviews) - 3} more feedback forms. Visit the Provide Feedback page to see all."
            )

# Deadline Enforcement Notice
if nom_passed or feedback_passed:
    st.markdown("---")
    st.subheader("⚠️ Important Notice")

    if nom_passed:
        st.warning(
            """
        **Nomination Deadline Has Passed**
        
        - You can no longer submit new feedback requests
        - All pending manager approvals have been automatically approved
        - All pending reviewer responses have been automatically accepted
        """
        )

    if feedback_passed:
        st.warning(
            """
        **Feedback Deadline Has Passed**
        
        - You can no longer complete feedback forms
        - Please check back for results when they become available
        """
        )

# Help Section
with st.expander("❓ Need Help?"):
    st.markdown(
        """
    **Common Questions:**
    
    - **How do I request feedback?** Click "Request Feedback" and select up to 4 reviewers
    - **What if my manager hasn't approved my requests?** Requests are automatically approved after the nomination deadline
    - **When will I see my results?** Results become available after all feedback is collected
    - **Can I get deadline extensions?** Contact HR if you need additional time due to special circumstances
    
    **Need more help?** Contact Diana or your manager.
    """
    )

# Footer
st.markdown("---")
st.caption(
    f"Review Cycle: {active_cycle['cycle_name']} | Last Updated: {datetime.now().strftime('%Y-%m-%d %H:%M')}"
)
