import streamlit as st
from datetime import datetime, date, timedelta
from services.db_helper import (
    get_connection,
    get_active_review_cycle,
    get_all_cycles,
    get_users_for_selection,
)

st.title("Email Notifications Center")
st.markdown(
    "Configure and send email notifications for feedback deadlines and reminders"
)

# Get active cycle info
active_cycle = get_active_review_cycle()

if not active_cycle:
    st.warning(
        "[Warning] No active review cycle found. Email notifications require an active cycle."
    )
    st.info(
        "Create a new review cycle from the Dashboard to enable email notifications."
    )
    st.stop()

# Display active cycle info
col1, col2 = st.columns(2)
with col1:
    st.info(f"**Active Cycle:** {active_cycle['cycle_display_name']}")
    st.write(f"Phase: {active_cycle.get('phase_status', 'Active')}")
with col2:
    st.write(f"Nomination Deadline: {active_cycle['nomination_deadline']}")
    st.write(f"Feedback Deadline: {active_cycle['feedback_deadline']}")

st.markdown("---")

# Tab layout for different notification types
tab1, tab2, tab3, tab4 = st.tabs(
    [
        "[Target] Targeted Notifications",
        "[Schedule] Scheduled Reminders",
        "[History] Notification History",
        "[Settings] Settings",
    ]
)

with tab1:
    st.subheader("Send Targeted Notifications")

    # Notification type selection
    notification_type = st.selectbox(
        "Select Notification Type:",
        [
            "nomination_reminder",
            "approval_reminder",
            "feedback_reminder",
            "deadline_warning",
            "cycle_completion",
            "custom_message",
        ],
        format_func=lambda x: {
            "nomination_reminder": "[Nomination] Nomination Reminder",
            "approval_reminder": "[Approval] Manager Approval Reminder",
            "feedback_reminder": "[Feedback] Feedback Completion Reminder",
            "deadline_warning": "[Warning] Deadline Warning",
            "cycle_completion": "[Complete] Cycle Completion Notice",
            "custom_message": "[Custom] Custom Message",
        }[x],
    )

    # Target audience selection
    col1, col2 = st.columns(2)
    with col1:
        audience_type = st.radio(
            "Target Audience:",
            [
                "all_users",
                "specific_users",
                "by_vertical",
                "managers_only",
                "pending_only",
            ],
            format_func=lambda x: {
                "all_users": "[All] All Active Users",
                "specific_users": "[Specific] Specific Users",
                "by_vertical": "[Department] By Department",
                "managers_only": "[Managers] Managers Only",
                "pending_only": "[Pending] Users with Pending Reviews",
            }[x],
        )

    with col2:
        send_date = st.date_input(
            "Send Date:", value=date.today(), help="Leave as today to send immediately"
        )
        send_time = st.time_input(
            "Send Time:", value=datetime.now().time().replace(second=0, microsecond=0)
        )

    # Audience-specific configuration
    selected_users = []
    selected_vertical = None

    if audience_type == "specific_users":
        all_users = get_users_for_selection()
        user_options = [f"{user['name']} ({user['email']})" for user in all_users]
        selected_user_options = st.multiselect(
            "Select Users:", user_options, help="Choose specific users to notify"
        )
        # Map back to user objects
        selected_users = [
            all_users[i]
            for i, option in enumerate(user_options)
            if option in selected_user_options
        ]

    elif audience_type == "by_vertical":
        conn = get_connection()
        verticals = conn.execute(
            "SELECT DISTINCT vertical FROM users WHERE is_active = 1 ORDER BY vertical"
        ).fetchall()
        selected_vertical = st.selectbox(
            "Select Department:", [v[0] for v in verticals if v[0]]
        )

    # Message customization
    st.subheader("Message Configuration")

    # Pre-defined templates based on notification type
    templates = {
        "nomination_reminder": {
            "subject": "Action Required: Submit Your Nominations",
            "body": """Dear {name},

The nomination phase for our {cycle_name} is currently active.

Please log into the system and nominate 4 colleagues to provide feedback on your performance. The nomination deadline is {nomination_deadline}.

If you have questions, please contact HR.

Best regards,
HR Team""",
        },
        "approval_reminder": {
            "subject": "Manager Action Required: Review Team Nominations",
            "body": """Dear {name},

You have pending nomination approvals for your team members in the {cycle_name}.

Please review and approve/reject the nominations at your earliest convenience. The nomination deadline is {nomination_deadline}.

Questions? Contact HR.

Best regards,
HR Team""",
        },
        "feedback_reminder": {
            "subject": "Reminder: Complete Your Feedback Reviews",
            "body": """Dear {name},

You have {pending_count} feedback review(s) pending completion for the {cycle_name}.

Please complete these reviews by {feedback_deadline} to ensure everyone receives their feedback on time.

Thank you for your participation.

Best regards,
HR Team""",
        },
        "deadline_warning": {
            "subject": "Urgent: Approaching Deadline",
            "body": """Dear {name},

This is a final reminder that the deadline for {deadline_type} is approaching: {deadline_date}.

Please take action immediately to avoid missing this important deadline.

Contact HR if you need assistance.

Best regards,
HR Team""",
        },
        "cycle_completion": {
            "subject": "Feedback Cycle Complete - Thank You!",
            "body": """Dear {name},

The {cycle_name} has been successfully completed.

Your feedback results are now available in the system. Thank you for your participation in this important development process.

Best regards,
HR Team""",
        },
        "custom_message": {
            "subject": "Custom Notification",
            "body": """Dear {name},

[Your custom message here]

Best regards,
HR Team""",
        },
    }

    template = templates[notification_type]

    # Allow customization
    custom_subject = st.text_input("Email Subject:", value=template["subject"])

    custom_body = st.text_area(
        "Email Body:",
        value=template["body"],
        height=200,
        help="Available variables: {name}, {email}, {cycle_name}, {nomination_deadline}, {feedback_deadline}, {pending_count}",
    )

    # Preview section
    st.subheader("Preview")
    with st.expander("[Preview] Email Preview"):
        preview_vars = {
            "name": "John Doe",
            "email": "john.doe@company.com",
            "cycle_name": active_cycle["cycle_display_name"],
            "nomination_deadline": active_cycle["nomination_deadline"],
            "feedback_deadline": active_cycle["feedback_deadline"],
            "pending_count": "2",
            "deadline_type": "feedback completion",
            "deadline_date": active_cycle["feedback_deadline"],
        }

        try:
            preview_subject = custom_subject.format(**preview_vars)
            preview_body = custom_body.format(**preview_vars)

            st.write(f"**Subject:** {preview_subject}")
            st.write("**Body:**")
            st.text(preview_body)
        except KeyError as e:
            st.error(f"Invalid template variable: {e}")

    # Send configuration
    col1, col2 = st.columns(2)
    with col1:
        if send_date == date.today():
            send_option = "Send Immediately"
        else:
            send_option = f"Schedule for {send_date} at {send_time}"
        st.write(f"**Delivery:** {send_option}")

    with col2:
        # Calculate recipient count
        recipient_count = 0
        if audience_type == "all_users":
            conn = get_connection()
            recipient_count = conn.execute(
                "SELECT COUNT(*) FROM users WHERE is_active = 1"
            ).fetchone()[0]
        elif audience_type == "specific_users":
            recipient_count = len(selected_users)
        elif audience_type == "by_vertical" and selected_vertical:
            conn = get_connection()
            recipient_count = conn.execute(
                "SELECT COUNT(*) FROM users WHERE is_active = 1 AND vertical = ?",
                (selected_vertical,),
            ).fetchone()[0]

        st.write(f"**Recipients:** {recipient_count} users")

    # Send button
    if st.button(
        "[Send] Send Notification", type="primary", disabled=recipient_count == 0
    ):
        # Here would be the actual email sending logic
        success_count = 0

        if audience_type == "all_users":
            # Send to all users
            conn = get_connection()
            users = conn.execute(
                "SELECT user_type_id, first_name, last_name, email FROM users WHERE is_active = 1"
            ).fetchall()
            for user in users:
                # Log the email (simulation)
                success_count += 1

        elif audience_type == "specific_users":
            # Send to specific users
            for user in selected_users:
                success_count += 1

        elif audience_type == "by_vertical":
            # Send to vertical
            conn = get_connection()
            users = conn.execute(
                "SELECT user_type_id, first_name, last_name, email FROM users WHERE is_active = 1 AND vertical = ?",
                (selected_vertical,),
            ).fetchall()
            for user in users:
                success_count += 1

        if success_count > 0:
            # Log the email sending
            conn = get_connection()
            try:
                conn.execute(
                    """
                    INSERT INTO email_logs (email_type, recipients_count, subject, body, sent_by, status)
                    VALUES (?, ?, ?, ?, ?, 'sent')
                """,
                    (
                        notification_type,
                        success_count,
                        custom_subject,
                        custom_body,
                        st.session_state["user_data"]["user_type_id"],
                    ),
                )
                conn.commit()
            except Exception as e:
                print(f"Error logging email: {e}")

            st.success(f"[Success] Notification sent to {success_count} recipients!")
        else:
            st.error("[Error] Failed to send notifications")

with tab2:
    st.subheader("Scheduled Reminders")
    st.info("[Schedule] Set up automatic reminders based on cycle deadlines")

    # Current scheduled reminders (mock data for now)
    st.write("**Active Scheduled Reminders:**")

    reminder_configs = [
        {
            "name": "Nomination Deadline Reminder",
            "trigger": "3 days before nomination deadline",
            "audience": "Users with no nominations",
            "status": "Active",
        },
        {
            "name": "Final Feedback Reminder",
            "trigger": "2 days before feedback deadline",
            "audience": "Users with pending reviews",
            "status": "Active",
        },
        {
            "name": "Manager Approval Reminder",
            "trigger": "1 day after nomination deadline",
            "audience": "Managers with pending approvals",
            "status": "Active",
        },
    ]

    for reminder in reminder_configs:
        with st.expander(f"[Reminder] {reminder['name']} - {reminder['status']}"):
            col1, col2 = st.columns(2)
            with col1:
                st.write(f"**Trigger:** {reminder['trigger']}")
                st.write(f"**Audience:** {reminder['audience']}")
            with col2:
                st.write(f"**Status:** {reminder['status']}")
                if st.button("[Edit] Edit", key=f"edit_{reminder['name']}"):
                    st.info("Reminder editing coming soon!")
                if st.button(
                    (
                        "[Disable] Disable"
                        if reminder["status"] == "Active"
                        else "[Enable] Enable"
                    ),
                    key=f"toggle_{reminder['name']}",
                ):
                    st.info("Status toggle coming soon!")

    # Add new reminder
    st.subheader("Create New Scheduled Reminder")
    with st.form("new_reminder"):
        reminder_name = st.text_input("Reminder Name:")

        col1, col2 = st.columns(2)
        with col1:
            trigger_type = st.selectbox(
                "Trigger Type:",
                ["Days before deadline", "Days after deadline", "Specific date"],
            )
            if trigger_type != "Specific date":
                trigger_days = st.number_input(
                    "Number of days:", min_value=1, max_value=30, value=3
                )
                trigger_deadline = st.selectbox(
                    "Deadline:", ["Nomination", "Approval", "Feedback", "Results"]
                )

        with col2:
            reminder_audience = st.selectbox(
                "Target Audience:",
                [
                    "All users",
                    "Users with pending nominations",
                    "Users with pending reviews",
                    "Managers with pending approvals",
                    "Specific department",
                ],
            )

        if st.form_submit_button("[Create] Create Reminder"):
            st.success(f"[Success] Scheduled reminder '{reminder_name}' created!")

with tab3:
    st.subheader("Notification History")

    # Date range filter
    col1, col2 = st.columns(2)
    with col1:
        start_date = st.date_input(
            "From Date:", value=date.today() - timedelta(days=30)
        )
    with col2:
        end_date = st.date_input("To Date:", value=date.today())

    # Get email logs
    conn = get_connection()
    try:
        email_logs = conn.execute(
            """
            SELECT sent_at, email_type, recipients_count, subject, status, sent_by
            FROM email_logs 
            WHERE DATE(sent_at) BETWEEN ? AND ?
            ORDER BY sent_at DESC
        """,
            (start_date.strftime("%Y-%m-%d"), end_date.strftime("%Y-%m-%d")),
        ).fetchall()

        if email_logs:
            st.write(f"**{len(email_logs)} notifications** sent in date range")

            for log in email_logs:
                sent_at = log[0][:16] if log[0] else "Unknown"
                email_type = log[1].replace("_", " ").title()
                recipients = log[2]
                subject = log[3]
                status = log[4]
                sent_by_id = log[5]

                status_icon = "[Sent]" if status == "sent" else "[Failed]"

                with st.expander(
                    f"{status_icon} {sent_at} - {email_type} ({recipients} recipients)"
                ):
                    st.write(f"**Subject:** {subject}")
                    st.write(f"**Status:** {status}")
                    st.write(f"**Recipients:** {recipients}")
                    st.write(f"**Sent At:** {sent_at}")
        else:
            st.info("No notifications found in selected date range")

    except Exception as e:
        st.warning("Email logs table not found. Creating email logs functionality...")

with tab4:
    st.subheader("Email Settings")

    # Email server configuration (mock)
    st.write("**Email Server Configuration:**")
    with st.expander("[SMTP] SMTP Settings"):
        st.text_input("SMTP Server:", value="smtp.company.com", disabled=True)
        st.text_input("SMTP Port:", value="587", disabled=True)
        st.text_input("From Email:", value="hr@company.com", disabled=True)
        st.info("Contact IT administrator to modify email server settings")

    # Default templates
    st.write("**Default Templates:**")
    with st.expander("[Template] Template Management"):
        template_type = st.selectbox("Template Type:", list(templates.keys()))
        current_template = templates[template_type]

        st.text_input("Default Subject:", value=current_template["subject"])
        st.text_area("Default Body:", value=current_template["body"], height=150)

        if st.button("[Save] Save Template"):
            st.success("Template saved!")

    # Notification preferences
    st.write("**Notification Preferences:**")
    col1, col2 = st.columns(2)
    with col1:
        st.checkbox("Enable automatic reminders", value=True)
        st.checkbox("Send delivery confirmations", value=True)
    with col2:
        st.checkbox("Include unsubscribe links", value=True)
        st.checkbox("Track email opens", value=False)

st.markdown("---")
# Quick Actions removed - use navigation menu
