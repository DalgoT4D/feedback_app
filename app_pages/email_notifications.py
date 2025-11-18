import streamlit as st
from datetime import datetime
from services.db_helper import (
    get_connection,
    get_active_review_cycle,
    get_all_cycles,
    get_users_for_selection,
    get_pending_approvals_for_manager,
    get_pending_reviewer_requests,
    get_pending_reviews_for_user,
    get_user_nominations_status,
)
from utils.cache_helper import (
    get_cached_departments,
    get_cached_active_users,
    get_cached_active_cycle,
    get_page_cached_user_data,
    SafeCache,
    invalidate_on_user_action
)
from services.email_service import send_email

# Helper functions for calculating specific user groups
def get_users_with_pending_nominations():
    """Get users who have incomplete nomination process using optimized JOIN query."""
    conn = get_connection()
    
    # Get active cycle
    active_cycle = get_active_review_cycle()
    if not active_cycle:
        return []
    
    cycle_id = active_cycle['cycle_id']
    
    # Single optimized query using JOINs to find users with pending nomination issues
    # This replaces the N+1 query pattern with a single database call
    query = """
        SELECT DISTINCT 
            u.user_type_id,
            u.first_name || ' ' || u.last_name as name,
            u.email,
            u.vertical,
            u.designation
        FROM users u
        WHERE u.is_active = 1 
        AND (
            -- Users who can nominate more (haven't reached 4 approved)
            (SELECT COUNT(*) 
             FROM feedback_requests fr 
             WHERE fr.requester_id = u.user_type_id 
             AND fr.cycle_id = ? 
             AND fr.status = 'approved') < 4
            
            OR
            
            -- Users with requests awaiting manager approval
            EXISTS (
                SELECT 1 FROM feedback_requests fr2
                WHERE fr2.requester_id = u.user_type_id 
                AND fr2.cycle_id = ?
                AND fr2.status = 'pending_manager_approval'
            )
            
            OR
            
            -- Users with requests awaiting reviewer acceptance
            EXISTS (
                SELECT 1 FROM feedback_requests fr3
                WHERE fr3.requester_id = u.user_type_id 
                AND fr3.cycle_id = ?
                AND fr3.status = 'pending_reviewer_acceptance'
            )
        )
        ORDER BY u.first_name, u.last_name
    """
    
    result = conn.execute(query, (cycle_id, cycle_id, cycle_id))
    users = result.fetchall()
    
    # Convert to expected format
    return [{
        'user_type_id': user[0],
        'name': user[1],
        'email': user[2],
        'vertical': user[3],
        'designation': user[4]
    } for user in users]

def get_managers_with_pending_approvals():
    """Get managers who have pending approval requests using optimized JOIN query."""
    conn = get_connection()
    
    # Get active cycle
    active_cycle = get_active_review_cycle()
    if not active_cycle:
        return []
    
    cycle_id = active_cycle['cycle_id']
    
    # Single optimized query using JOINs to find managers with pending approvals
    # This replaces the N+1 query pattern with a single database call
    query = """
        SELECT DISTINCT 
            m.user_type_id,
            m.email,
            m.first_name || ' ' || m.last_name as name,
            m.vertical
        FROM users m
        INNER JOIN users u ON u.reporting_manager_email = m.email AND u.is_active = 1
        INNER JOIN feedback_requests fr ON fr.requester_id = u.user_type_id
        WHERE m.is_active = 1
        AND fr.cycle_id = ?
        AND fr.status = 'pending_manager_approval'
        ORDER BY m.first_name, m.last_name
    """
    
    result = conn.execute(query, (cycle_id,))
    managers = result.fetchall()
    
    # Convert to expected format
    return [{
        'user_type_id': manager[0],
        'email': manager[1],
        'name': manager[2],
        'vertical': manager[3]
    } for manager in managers]

def get_users_with_pending_reviews():
    """Get users who have accepted reviews but haven't completed them using optimized JOIN query."""
    conn = get_connection()
    
    # Get active cycle
    active_cycle = get_active_review_cycle()
    if not active_cycle:
        return []
    
    cycle_id = active_cycle['cycle_id']
    
    # Single optimized query using JOINs to find users with pending reviews to complete
    # This replaces the N+1 query pattern with a single database call
    query = """
        SELECT 
            u.user_type_id,
            u.first_name,
            u.last_name,
            u.email,
            u.vertical,
            u.designation,
            COUNT(fr.request_id) as pending_count
        FROM users u
        INNER JOIN feedback_requests fr ON fr.reviewer_id = u.user_type_id
        WHERE u.is_active = 1
        AND fr.cycle_id = ?
        AND fr.status = 'approved'
        AND NOT EXISTS (
            SELECT 1 FROM final_responses fres
            WHERE fres.request_id = fr.request_id
        )
        GROUP BY u.user_type_id, u.first_name, u.last_name, u.email, u.vertical, u.designation
        ORDER BY u.first_name, u.last_name
    """
    
    result = conn.execute(query, (cycle_id,))
    users = result.fetchall()
    
    return [{
        'user_type_id': user[0],
        'first_name': user[1],
        'last_name': user[2],
        'name': f"{(user[1] or '').strip()} {(user[2] or '').strip()}".strip() or user[3],
        'email': user[3],
        'vertical': user[4],
        'designation': user[5],
        'pending_count': user[6],
    } for user in users]

def get_actual_managers():
    """Get users who are actually managers of other people."""
    conn = get_connection()

    query = """
        SELECT DISTINCT m.user_type_id, m.email, m.first_name, m.last_name, m.vertical
        FROM users m 
        WHERE EXISTS (
            SELECT 1 FROM users u 
            WHERE u.reporting_manager_email = m.email AND u.is_active = 1
        ) AND m.is_active = 1
        ORDER BY m.first_name, m.last_name
    """
    result = conn.execute(query)
    managers = result.fetchall()

    return [{
        'user_type_id': m[0],
        'email': m[1], 
        'name': f"{m[2]} {m[3]}",
        'vertical': m[4]
    } for m in managers]


def normalize_recipient_record(record):
    """Convert mixed recipient formats into a standard dict."""
    if isinstance(record, dict):
        email = record.get("email")
        if not email:
            return None
        first_name = record.get("first_name")
        last_name = record.get("last_name")
        name = record.get("name")
        if not name:
            name_parts = [first_name or "", last_name or ""]
            name = " ".join(part.strip() for part in name_parts if part).strip() or email
        return {
            "user_type_id": record.get("user_type_id"),
            "email": email,
            "name": name,
            "pending_count": record.get("pending_count"),
        }

    if isinstance(record, (list, tuple)) and record:
        user_id = record[0]
        first_name = record[1] if len(record) > 1 else ""
        last_name = record[2] if len(record) > 2 else ""
        email = record[3] if len(record) > 3 else ""
        name = " ".join(part.strip() for part in [first_name, last_name] if part).strip() or email
        return {
            "user_type_id": user_id,
            "email": email,
            "name": name,
            "pending_count": record[6] if len(record) > 6 else None,
        }
    return None


def build_template_context(recipient, notification_type, cycle_data):
    """Build the context dict for template rendering."""
    default_deadline = cycle_data.get("feedback_deadline") or cycle_data.get("nomination_deadline") or "TBD"
    deadline_map = {
        "nomination_reminder": ("nomination completion", cycle_data.get("nomination_deadline", default_deadline)),
        "approval_reminder": ("nomination approval", cycle_data.get("nomination_deadline", default_deadline)),
        "feedback_reminder": ("feedback completion", cycle_data.get("feedback_deadline", default_deadline)),
        "deadline_warning": ("cycle deadline", default_deadline),
    }
    deadline_type, deadline_date = deadline_map.get(notification_type, ("cycle milestone", default_deadline))

    return {
        "name": recipient.get("name") or "there",
        "email": recipient.get("email"),
        "cycle_name": cycle_data.get("cycle_display_name", "current cycle"),
        "nomination_deadline": cycle_data.get("nomination_deadline", "TBD"),
        "feedback_deadline": cycle_data.get("feedback_deadline", "TBD"),
        "pending_count": recipient.get("pending_count") or "1",
        "deadline_type": deadline_type,
        "deadline_date": deadline_date or "TBD",
    }


def text_to_html(body_text: str) -> str:
    """Convert plain text body to simple HTML paragraphs."""
    if not body_text:
        return "<p></p>"
    paragraphs = [para.strip() for para in body_text.split("\n\n")]
    html_parts = []
    for para in paragraphs:
        if not para:
            continue
        html_parts.append(f"<p>{para.replace(chr(10), '<br>')}</p>")
    return "".join(html_parts) or "<p></p>"

st.title("Email Notifications Center")
st.markdown("Configure and send email notifications for feedback deadlines and reminders")

# Get active cycle info (cached for 1 hour - safe, changes infrequently)
active_cycle = get_cached_active_cycle()

if not active_cycle:
    st.warning("No active review cycle found. Email notifications require an active cycle.")
    st.info("Create a new review cycle from the Dashboard to enable email notifications.")
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

# Send targeted notifications only
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
        "nomination_reminder": "Nomination Reminder",
        "approval_reminder": "Manager Approval Reminder",
        "feedback_reminder": "Feedback Completion Reminder",
        "deadline_warning": "Deadline Warning",
        "cycle_completion": "Cycle Completion Notice",
        "custom_message": "Custom Message",
    }[x],
)

# Target audience selection - dynamic based on notification type
col1, col2 = st.columns(2)
with col1:
    # Build audience options dynamically
    audience_options = [
        "all_users",
        "specific_users", 
        "by_vertical",
        "managers_only",
    ]
    
    # Add specific pending option based on notification type
    if notification_type == "nomination_reminder":
        audience_options.append("pending_nominations")
    elif notification_type == "approval_reminder":
        audience_options.append("pending_approvals")
    elif notification_type == "feedback_reminder":
        audience_options.append("pending_reviews")
    
    def get_audience_label(x):
        labels = {
            "all_users": "All Active Users",
            "specific_users": "Specific Users",
            "by_vertical": "By Department", 
            "managers_only": "Managers Only",
            "pending_nominations": "Users with Pending Nomination Approvals",
            "pending_approvals": "Managers with Pending Approvals",
            "pending_reviews": "Users with Pending Reviews",
        }
        return labels.get(x, x)
    
    audience_type = st.radio(
        "Target Audience:",
        audience_options,
        format_func=get_audience_label,
    )

with col2:
    st.info("All notifications are sent immediately when the 'Send Notification' button is clicked.")
    
    # Show specific information for pending nomination types
    if audience_type == "pending_nominations":
        st.info("""
        **Users with Pending Nomination Approvals:**
        - Users who haven't nominated 4 people
        - Users whose managers haven't approved their nominations  
        - Users whose reviewers haven't accepted their invitations
        """)
    elif audience_type == "pending_approvals":
        st.info("""
        **Managers with Pending Approvals:**
        - Managers who have pending nominations awaiting their approval
        """)
    elif audience_type == "pending_reviews":
        st.info("""
        **Users with Pending Reviews:**
        - Users who have accepted feedback requests but haven't completed them
        """)

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
    # Use cached departments (1-hour cache - safe, rarely changes)
    verticals = get_cached_departments()
    selected_vertical = st.selectbox(
        "Select Department:", [v[0] for v in verticals if v[0]]
    )
    
elif audience_type == "managers_only":
    # Get actual managers (users who manage other people)
    selected_users = get_actual_managers()
    st.success(f"Found {len(selected_users)} managers")
    
elif audience_type == "pending_nominations":
    # Get users with pending nomination issues  
    selected_users = get_users_with_pending_nominations()
    st.success(f"Found {len(selected_users)} users with pending nomination approvals")
    
elif audience_type == "pending_approvals":
    # Get managers with pending approval requests
    selected_users = get_managers_with_pending_approvals()  
    st.success(f"Found {len(selected_users)} managers with pending approvals")
    
elif audience_type == "pending_reviews":
    # Get users with pending reviews to complete
    selected_users = get_users_with_pending_reviews()
    st.success(f"Found {len(selected_users)} users with pending reviews")
    
elif audience_type == "all_users":
    selected_users = get_users_for_selection()
    st.success(f"Found {len(selected_users)} active users")

# Message customization
st.subheader("Message Configuration")

# Pre-defined templates based on notification type
templates = {
    "nomination_reminder": {
        "subject": "Action Required: Complete Your Nomination Process",
        "body": """Dear {name},

We notice you have pending items in the nomination process for {cycle_name}.

This could include:
• Nominating up to 4 colleagues for feedback
• Waiting for manager approval of your nominations  
• Waiting for reviewers to accept your feedback invitations

Please log into the system to check your current status and complete any remaining steps. The nomination deadline is {nomination_deadline}.

If you have questions, please contact HR.

Best regards,
Talent Management""",
    },
    "approval_reminder": {
        "subject": "Manager Action Required: Review Team Nominations",
        "body": """Dear {name},

You have pending nomination approvals for your team members in the {cycle_name}.

Please review and approve/reject the nominations at your earliest convenience. The nomination deadline is {nomination_deadline}.

Questions? Contact HR.

Best regards,
Talent Management""",
    },
    "feedback_reminder": {
        "subject": "Reminder: Complete Your Feedback Reviews",
        "body": """Dear {name},

You have {pending_count} feedback review(s) pending completion for the {cycle_name}.

Please complete these reviews by {feedback_deadline} to ensure everyone receives their feedback on time.

Thank you for your participation.

Best regards,
Talent Management""",
    },
    "deadline_warning": {
        "subject": "Urgent: Approaching Deadline",
        "body": """Dear {name},

This is a final reminder that the deadline for {deadline_type} is approaching: {deadline_date}.

Please take action immediately to avoid missing this important deadline.

Contact HR if you need assistance.

Best regards,
Talent Management""",
    },
    "cycle_completion": {
        "subject": "Feedback Cycle Complete - Thank You!",
        "body": """Dear {name},

The {cycle_name} has been successfully completed.

Your feedback results are now available in the system. Thank you for your participation in this important development process.

Best regards,
Talent Management""",
    },
    "custom_message": {
        "subject": "Custom Notification",
        "body": """Dear {name},

[Your custom message here]

Best regards,
Talent Management""",
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
with st.expander("Email Preview"):
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
    st.write("**Delivery:** Send Immediately")

# Resolve recipients for the selected audience
audience_recipients = []
if audience_type == "all_users":
    audience_recipients = get_page_cached_user_data(
        "all_active_users",
        "SELECT user_type_id, first_name, last_name, email FROM users WHERE is_active = 1",
    )
elif audience_type == "by_vertical" and selected_vertical:
    audience_recipients = get_page_cached_user_data(
        f"vertical_users_{selected_vertical}",
        "SELECT user_type_id, first_name, last_name, email FROM users WHERE is_active = 1 AND vertical = ?",
        (selected_vertical,),
    )
elif audience_type == "specific_users":
    audience_recipients = selected_users
else:
    audience_recipients = selected_users

# Normalize and deduplicate recipients by email
normalized_recipients = []
seen_emails = set()
for record in audience_recipients:
    normalized = normalize_recipient_record(record)
    if not normalized or not normalized.get("email"):
        continue
    email_key = normalized["email"].strip().lower()
    if email_key in seen_emails:
        continue
    seen_emails.add(email_key)
    normalized_recipients.append(normalized)

recipient_count = len(normalized_recipients)

with col2:
    st.write(f"**Recipients:** {recipient_count} users")

# Send button
if st.button("Send Notification", type="primary", disabled=recipient_count == 0):
    if recipient_count == 0:
        st.error("No recipients selected.")
    else:
        formatted_messages = []
        template_error = None
        for recipient in normalized_recipients:
            context = build_template_context(recipient, notification_type, active_cycle)
            try:
                subject = custom_subject.format(**context)
                body_text = custom_body.format(**context)
            except KeyError as exc:
                template_error = exc
                break
            html_body = text_to_html(body_text)
            formatted_messages.append((recipient, subject, body_text, html_body))

        if template_error:
            st.error(
                f"Template variable {{{template_error}}} is not available. "
                "Please update the subject/body placeholders and try again."
            )
        else:
            successes = 0
            failures = []
            initiator_id = st.session_state["user_data"]["user_type_id"]

            for recipient, subject, body_text, html_body in formatted_messages:
                queued = send_email(
                    to_email=recipient["email"],
                    subject=subject,
                    html_body=html_body,
                    text_body=body_text,
                    email_type=notification_type,
                    recipient_name=recipient["name"],
                    cycle_id=active_cycle["cycle_id"],
                    initiated_by=initiator_id,
                )
                if queued:
                    successes += 1
                else:
                    failures.append(recipient["email"])

            if successes:
                st.success(
                    f"Queued {successes} email"
                    f"{'s' if successes != 1 else ''} for delivery via the email worker."
                )
            if failures:
                st.error(
                    "Failed to queue the following addresses: "
                    + ", ".join(sorted(failures))
                )

# Notification history moved to separate page
st.markdown("---")
