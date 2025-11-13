"""
Manual Reminder System
Allows HR to send custom reminder emails to users about feedback deadlines and tasks.
"""

import streamlit as st
from datetime import datetime, date, timedelta
from services.db_helper import (
    get_connection,
    get_active_review_cycle,
    get_all_users,
)
from services.email_service import (
    send_manual_reminder,
    send_cycle_deadline_reminder,
    get_email_log,
)

# Check HR access
if not st.session_state.get("authenticated"):
    st.error("Please log in to access this page")
    st.stop()


# Avoid importing main (it triggers app bootstrap and navigation again)
def _has_role(role_name: str) -> bool:
    roles = st.session_state.get("user_roles", [])
    return any(r.get("role_name") == role_name for r in roles)


if not _has_role("hr"):
    st.error("Access denied. HR role required.")
    st.stop()

st.title("📧 Manual Reminder System")

# Tabs for different reminder types
tab1, tab2, tab3, tab4 = st.tabs(
    ["📝 Custom Reminders", "⏰ Deadline Reminders", "📊 Email Log", "🚀 Quick Actions"]
)

with tab1:
    st.subheader("Send Custom Reminder")
    st.info("Send personalized reminder emails to specific users or groups.")

    # Recipient selection
    col1, col2 = st.columns([2, 1])

    with col1:
        recipient_type = st.selectbox(
            "Select Recipients",
            [
                "Individual Users",
                "All Users",
                "Users with Pending Tasks",
                "Custom Email List",
            ],
        )

    with col2:
        if st.button("🔄 Refresh User List", key="refresh_users"):
            st.rerun()

    recipients = []
    recipient_emails = []

    if recipient_type == "Individual Users":
        # Get all users
        users = get_all_users()
        if users:
            selected_users = st.multiselect(
                "Select Users",
                options=users,
                format_func=lambda user: f"{user['name']} ({user['email']}) - {user['designation']}",
            )
            recipient_emails = [user["email"] for user in selected_users]
            recipients = [user["name"] for user in selected_users]

    elif recipient_type == "All Users":
        users = get_all_users()
        if users:
            recipient_emails = [user["email"] for user in users if user["is_active"]]
            recipients = [user["name"] for user in users if user["is_active"]]
            st.info(f"Selected {len(recipient_emails)} active users")

    elif recipient_type == "Users with Pending Tasks":
        task_type = st.selectbox(
            "Task Type", ["Pending Nominations", "Pending Reviews", "Pending Approvals"]
        )

        # Get users with pending tasks based on selection
        try:
            conn = get_connection()
            active_cycle = get_active_review_cycle()

            if active_cycle and task_type == "Pending Nominations":
                query = """
                    SELECT DISTINCT u.email, u.first_name || ' ' || u.last_name as name
                    FROM users u
                    LEFT JOIN (
                        SELECT requester_id, COUNT(*) as nomination_count
                        FROM feedback_requests 
                        WHERE cycle_id = ? AND approval_status != 'rejected'
                        GROUP BY requester_id
                    ) fr ON u.user_type_id = fr.requester_id
                    WHERE u.is_active = 1 
                    AND (fr.nomination_count IS NULL OR fr.nomination_count < 4)
                    AND u.date_of_joining <= DATE('now', '-90 days')
                """
                result = conn.execute(query, (active_cycle["cycle_id"],))

            elif active_cycle and task_type == "Pending Reviews":
                query = """
                    SELECT DISTINCT u.email, u.first_name || ' ' || u.last_name as name
                    FROM users u
                    JOIN feedback_requests fr ON u.user_type_id = fr.reviewer_id
                    WHERE fr.cycle_id = ? AND fr.approval_status = 'approved' 
                    AND fr.workflow_state != 'completed' AND u.is_active = 1
                """
                result = conn.execute(query, (active_cycle["cycle_id"],))

            elif active_cycle and task_type == "Pending Approvals":
                query = """
                    SELECT DISTINCT m.email, m.first_name || ' ' || m.last_name as name
                    FROM feedback_requests fr
                    JOIN users u ON fr.requester_id = u.user_type_id
                    JOIN users m ON u.reporting_manager_email = m.email
                    WHERE fr.cycle_id = ? AND fr.approval_status = 'pending' 
                    AND m.is_active = 1
                """
                result = conn.execute(query, (active_cycle["cycle_id"],))
            else:
                result = []

            pending_users = result.fetchall() if result else []
            recipient_emails = [row[0] for row in pending_users]
            recipients = [row[1] for row in pending_users]

            if pending_users:
                st.info(
                    f"Found {len(pending_users)} users with pending {task_type.lower()}"
                )
            else:
                st.warning(f"No users found with pending {task_type.lower()}")

        except Exception as e:
            st.error(f"Error finding users with pending tasks: {e}")

    elif recipient_type == "Custom Email List":
        email_input = st.text_area(
            "Enter Email Addresses (one per line)",
            placeholder="user1@tech4dev.com\nuser2@tech4dev.com\nuser3@tech4dev.com",
            height=100,
        )
        if email_input:
            recipient_emails = [
                email.strip() for email in email_input.split("\n") if email.strip()
            ]
            recipients = recipient_emails.copy()

    # Email content
    st.subheader("Email Content")

    # Pre-defined templates
    template = st.selectbox(
        "Choose Template",
        [
            "Custom",
            "Nomination Reminder",
            "Review Reminder",
            "General Deadline",
            "Final Warning",
        ],
    )

    # Template content
    if template == "Nomination Reminder":
        default_subject = "Reminder: Submit Your Feedback Nominations"
        default_body = """
        <h2>Feedback Nomination Reminder</h2>
        <p>Hello,</p>
        <p>This is a friendly reminder that the nomination deadline is approaching. Please submit your feedback nominations through the 360° Feedback System.</p>
        <p><strong>What you need to do:</strong></p>
        <ul>
            <li>Login to the feedback portal</li>
            <li>Go to "Request Feedback"</li>
            <li>Select up to 4 colleagues to provide feedback</li>
            <li>Submit your nominations for manager approval</li>
        </ul>
        <p>Don't miss the deadline - your participation is important!</p>
        <p>Best regards,<br>Talent Management</p>
        """
    elif template == "Review Reminder":
        default_subject = "Reminder: Complete Your Feedback Reviews"
        default_body = """
        <h2>Pending Reviews Reminder</h2>
        <p>Hello,</p>
        <p>You have pending feedback reviews that need to be completed. Please log in to provide feedback for your colleagues.</p>
        <p><strong>What you need to do:</strong></p>
        <ul>
            <li>Login to the feedback portal</li>
            <li>Go to "Complete Reviews"</li>
            <li>Complete all pending feedback forms</li>
            <li>Submit your responses</li>
        </ul>
        <p>Your insights are valuable - please complete your reviews promptly.</p>
        <p>Best regards,<br>Talent Management</p>
        """
    elif template == "General Deadline":
        default_subject = "Reminder: Upcoming Feedback Cycle Deadline"
        default_body = """
        <h2>Feedback Deadline Reminder</h2>
        <p>Hello,</p>
        <p>This is a reminder about the upcoming deadline for the current feedback cycle.</p>
        <p>Please ensure you have completed all required tasks including nominations and reviews.</p>
        <p>If you need assistance, please contact Talent Management.</p>
        <p>Best regards,<br>Talent Management</p>
        """
    elif template == "Final Warning":
        default_subject = "URGENT: Final Reminder - Feedback Deadline Today"
        default_body = """
        <h2>🚨 URGENT: Final Reminder</h2>
        <p>Hello,</p>
        <p><strong>This is the final reminder</strong> that today is the deadline for feedback submissions.</p>
        <p>Please complete any pending tasks immediately to avoid missing the deadline.</p>
        <p>If you're experiencing technical issues, contact HR immediately.</p>
        <p>Best regards,<br>Talent Management</p>
        """
    else:
        default_subject = ""
        default_body = ""

    subject = st.text_input("Email Subject", value=default_subject)

    body = st.text_area(
        "Email Body (HTML supported)",
        value=default_body,
        height=300,
        help="You can use HTML tags for formatting",
    )

    # Preview and send
    col1, col2 = st.columns([1, 1])

    with col1:
        if st.button(
            "📧 Send Reminders",
            type="primary",
            disabled=not (recipient_emails and subject and body),
        ):
            if recipient_emails and subject and body:
                with st.spinner(
                    f"Sending emails to {len(recipient_emails)} recipients..."
                ):
                    results = send_manual_reminder(recipient_emails, subject, body)

                    successful = sum(1 for success in results.values() if success)
                    failed = len(results) - successful

                    if successful > 0:
                        st.success(f"✅ Successfully sent {successful} emails")
                    if failed > 0:
                        st.error(f"❌ Failed to send {failed} emails")

                    # Show detailed results
                    with st.expander("View Detailed Results"):
                        for email, success in results.items():
                            if success:
                                st.write(f"✅ {email}")
                            else:
                                st.write(f"❌ {email}")
            else:
                st.error("Please fill in all required fields")

    with col2:
        if st.button("👁️ Preview Email"):
            if subject and body:
                st.subheader("Email Preview")
                st.write(f"**Subject:** {subject}")
                st.write(f"**Recipients:** {len(recipient_emails)} users")
                st.markdown("**Body:**")
                st.markdown(body, unsafe_allow_html=True)
            else:
                st.warning("Please enter subject and body to preview")

with tab2:
    st.subheader("Deadline Reminder System")
    st.info("Send automated deadline reminders based on cycle dates.")

    active_cycle = get_active_review_cycle()
    if not active_cycle:
        st.warning(
            "No active review cycle found. Deadline reminders are not available."
        )
    else:
        st.success(f"Active Cycle: {active_cycle['cycle_name']}")

        col1, col2 = st.columns(2)

        with col1:
            st.write(
                "**Nomination Deadline:**",
                active_cycle.get("nomination_deadline", "Not set"),
            )
            st.write(
                "**Feedback Deadline:**",
                active_cycle.get("feedback_deadline", "Not set"),
            )

        with col2:
            # Calculate days remaining
            today = date.today()
            if active_cycle.get("nomination_deadline"):
                try:
                    nom_deadline = datetime.strptime(
                        active_cycle["nomination_deadline"], "%Y-%m-%d"
                    ).date()
                    nom_days = (nom_deadline - today).days
                    st.write(f"**Nomination Days Remaining:** {nom_days}")
                except:
                    nom_days = 0
            else:
                nom_days = 0

            if active_cycle.get("feedback_deadline"):
                try:
                    feedback_deadline = datetime.strptime(
                        active_cycle["feedback_deadline"], "%Y-%m-%d"
                    ).date()
                    feedback_days = (feedback_deadline - today).days
                    st.write(f"**Feedback Days Remaining:** {feedback_days}")
                except:
                    feedback_days = 0
            else:
                feedback_days = 0

        st.markdown("---")

        # Quick deadline reminders
        deadline_type = st.selectbox(
            "Reminder Type", ["Nomination Deadline", "Feedback Deadline"]
        )

        days_ahead = st.selectbox(
            "Send Reminder For",
            [1, 2, 3, 5, 7, 10],
            format_func=lambda x: f"{x} day{'s' if x > 1 else ''} before deadline",
        )

        if st.button("🔔 Send Deadline Reminders"):
            # Get users who need deadline reminders
            try:
                users = get_all_users()
                reminder_count = 0

                deadline_date = (
                    active_cycle.get("nomination_deadline")
                    if deadline_type == "Nomination Deadline"
                    else active_cycle.get("feedback_deadline")
                )

                for user in users:
                    if user["is_active"]:
                        success = send_cycle_deadline_reminder(
                            user_email=user["email"],
                            user_name=user["name"],
                            deadline_type=deadline_type.lower().replace(
                                " deadline", ""
                            ),
                            deadline_date=deadline_date,
                            days_remaining=days_ahead,
                        )
                        if success:
                            reminder_count += 1

                st.success(f"Sent {reminder_count} deadline reminders successfully!")

            except Exception as e:
                st.error(f"Error sending deadline reminders: {e}")

with tab3:
    st.subheader("Email Activity Log")
    st.info("Monitor recent email activity and troubleshoot delivery issues.")

    # Filters
    col1, col2, col3 = st.columns(3)

    with col1:
        log_limit = st.selectbox("Show Last", [50, 100, 200, 500], index=1)

    with col2:
        email_type_filter = st.selectbox(
            "Email Type",
            [
                "All Types",
                "external_stakeholder_invite",
                "nominee_invite",
                "manager_approval_request",
                "nomination_approved",
                "nomination_rejected",
                "feedback_submitted_notification",
                "deadline_reminder",
                "manual_reminder",
                "password_reset",
            ],
        )

    with col3:
        success_filter = st.selectbox(
            "Status", ["All", "Successful Only", "Failed Only"]
        )

    if st.button("🔍 Load Email Log"):
        with st.spinner("Loading email log..."):
            try:
                log_entries = get_email_log(limit=log_limit)

                # Apply filters
                if email_type_filter != "All Types":
                    log_entries = [
                        entry
                        for entry in log_entries
                        if entry["email_type"] == email_type_filter
                    ]

                if success_filter == "Successful Only":
                    log_entries = [entry for entry in log_entries if entry["success"]]
                elif success_filter == "Failed Only":
                    log_entries = [
                        entry for entry in log_entries if not entry["success"]
                    ]

                if log_entries:
                    st.success(f"Found {len(log_entries)} email log entries")

                    # Display as table
                    for entry in log_entries:
                        with st.expander(
                            f"{'✅' if entry['success'] else '❌'} {entry['to_email']} - {entry['subject'][:50]}{'...' if len(entry['subject']) > 50 else ''}"
                        ):
                            col1, col2 = st.columns(2)
                            with col1:
                                st.write(f"**To:** {entry['to_email']}")
                                st.write(f"**Type:** {entry['email_type']}")
                                st.write(f"**Sent:** {entry['sent_at']}")
                            with col2:
                                st.write(
                                    f"**Status:** {'Success' if entry['success'] else 'Failed'}"
                                )
                                st.write(f"**From:** {entry['sender_email']}")
                                if entry["error_message"]:
                                    st.error(f"**Error:** {entry['error_message']}")

                            st.write(f"**Subject:** {entry['subject']}")
                else:
                    st.info("No email log entries found matching the filters.")

            except Exception as e:
                st.error(f"Error loading email log: {e}")

with tab4:
    st.subheader("Quick Actions")
    st.info("Common reminder scenarios with one-click sending.")

    # Quick action buttons
    col1, col2 = st.columns(2)

    with col1:
        if st.button("📢 Remind All: Complete Nominations", use_container_width=True):
            # Send nomination reminder to all users who haven't completed nominations
            st.info(
                "This would send nomination reminders to users with incomplete nominations."
            )

        if st.button("📝 Remind All: Complete Reviews", use_container_width=True):
            # Send review reminder to all users with pending reviews
            st.info(
                "This would send review reminders to users with pending feedback reviews."
            )

        if st.button("⚠️ Final Warning: 24 Hours Left", use_container_width=True):
            # Send final warning to all users with pending tasks
            st.info(
                "This would send final warning emails to users with any pending tasks."
            )

    with col2:
        if st.button("👥 Remind Managers: Approve Pending", use_container_width=True):
            # Send reminder to managers with pending approvals
            st.info(
                "This would send reminders to managers with pending approval requests."
            )

        if st.button("📊 Cycle Status Summary", use_container_width=True):
            # Show cycle completion status
            active_cycle = get_active_review_cycle()
            if active_cycle:
                try:
                    conn = get_connection()

                    # Get completion statistics
                    stats_query = """
                        SELECT 
                            COUNT(DISTINCT CASE WHEN fr.approval_status = 'pending' THEN fr.requester_id END) as pending_nominations,
                            COUNT(DISTINCT CASE WHEN fr.approval_status = 'approved' AND fr.workflow_state != 'completed' THEN fr.reviewer_id END) as pending_reviews,
                            COUNT(DISTINCT CASE WHEN fr.workflow_state = 'completed' THEN fr.request_id END) as completed_reviews,
                            COUNT(DISTINCT fr.request_id) as total_requests
                        FROM feedback_requests fr
                        WHERE fr.cycle_id = ?
                    """
                    result = conn.execute(stats_query, (active_cycle["cycle_id"],))
                    stats = result.fetchone()

                    if stats:
                        st.success("**Cycle Completion Status:**")
                        st.write(f"- **Pending Nominations:** {stats[0]}")
                        st.write(f"- **Pending Reviews:** {stats[1]}")
                        st.write(f"- **Completed Reviews:** {stats[2]}")
                        st.write(f"- **Total Requests:** {stats[3]}")

                        if stats[3] > 0:
                            completion_rate = (stats[2] / stats[3]) * 100
                            st.metric("Completion Rate", f"{completion_rate:.1f}%")

                except Exception as e:
                    st.error(f"Error getting cycle stats: {e}")
            else:
                st.warning("No active cycle found.")

        if st.button("📧 Test Email Configuration", use_container_width=True):
            # Test email sending
            test_email = st.text_input("Enter test email address:", key="test_email")
            if test_email:
                from services.email_service import send_email

                success = send_email(
                    to_email=test_email,
                    subject="Test Email - 360° Feedback System",
                    html_body="<p>This is a test email from the 360° Feedback System. If you received this, email configuration is working correctly!</p>",
                    email_type="test",
                )
                if success:
                    st.success(f"✅ Test email sent successfully to {test_email}")
                else:
                    st.error(f"❌ Failed to send test email to {test_email}")

# Footer
st.markdown("---")
st.caption(
    "💡 **Tip:** Use deadline reminders strategically to maintain engagement without overwhelming users. Monitor the email log to ensure successful delivery."
)
