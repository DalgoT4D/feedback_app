"""
Email Service Module
Handles all email communications using SendGrid API including notifications and invitations.
If SendGrid SDK is not installed, functions will fail gracefully rather than crash import.

TEMPORARY TESTING NOTE:
  The whitelist below disables sending to any recipient not explicitly allowed.
  Toggle TEMP_EMAIL_WHITELIST_ACTIVE to False to restore normal sending.
"""

import streamlit as st
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

try:
    import sendgrid
    from sendgrid.helpers.mail import Mail, Email, To, Content
except ImportError:  # Allow app to run without SendGrid installed
    sendgrid = None
    Mail = Email = To = Content = None
import logging
from typing import Optional, Dict, Any, List
from datetime import datetime
import sqlite3

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ---------------- TEMPORARY TESTING WHITELIST ----------------
# Only allow real email sends to these recipients while testing.
TEMP_EMAIL_WHITELIST_ACTIVE = True  # Set to False to re-enable normal sending
TEMP_EMAIL_WHITELIST = {
    "pratiksha@projecttech4dev.org",
    "diana@projecttech4dev.org",
    "pratz.rao@gmail.com",
    "rao.pratz@gmail.com",
}
# --------------------------------------------------------------


def get_sendgrid_client():
    """Initialize SendGrid client with API key from secrets."""
    try:
        # Use existing email configuration from secrets.toml
        if "email" in st.secrets:
            api_key = st.secrets["email"].get(
                "email_password"
            )  # SendGrid API key may be stored as email_password
            if not api_key:
                logger.error("SendGrid API key not found in email.email_password")
                return None
            if sendgrid:
                return sendgrid.SendGridAPIClient(api_key=api_key)
            else:
                return None
        else:
            logger.error("Email configuration not found in streamlit secrets")
            return None
    except Exception as e:
        logger.error(f"Failed to initialize SendGrid client: {e}")
        return None


def get_sender_email():
    """Get sender email from secrets."""
    try:
        if "email" in st.secrets:
            return st.secrets["email"].get("from_email", "noreply@tech4dev.com")
        else:
            return "noreply@tech4dev.com"
    except Exception as e:
        logger.warning(f"Failed to get sender email: {e}")
        return "noreply@tech4dev.com"


def log_email_sent(
    to_email: str,
    subject: str,
    email_type: str,
    success: bool,
    error_msg: str = None,
    recipient_name: str = None,
    cycle_id: int = None,
    request_id: int = None,
    initiated_by: int = None,
):
    """Enhanced email logging to the new email_logs structure."""
    try:
        # Use centralized email logging service
        from .email_logging import log_email_enhanced, log_email_recipient_details

        # Determine status based on success
        status = "sent" if success else "failed"

        # Categorize email type - automation emails are system-generated
        if email_type in [
            "external_stakeholder_invite",
            "manager_approval_notification",
            "reviewer_acceptance",
            "feedback_reminder",
        ]:
            email_category = "automation"
        else:
            email_category = "targeted"

        # Log the email using centralized service
        log_id = log_email_enhanced(
            email_type=email_type,
            subject=subject,
            status=status,
            email_category=email_category,
            recipient_email=to_email,
            recipient_name=recipient_name or "Unknown Recipient",
            initiated_by=initiated_by,
            cycle_id=cycle_id,
            request_id=request_id,
        )

        # Log recipient details if we got a log ID back
        if log_id and to_email:
            log_email_recipient_details(
                log_id=log_id,
                user_id=initiated_by or 0,
                email=to_email,
                name=recipient_name or "Unknown Recipient",
                status="delivered" if success else "failed",
            )

    except Exception as e:
        logger.warning(f"Failed to log email with enhanced structure: {e}")

        # Fallback to basic logging using centralized service
        try:
            from .email_logging import log_email_basic

            log_email_basic(
                email_type, subject, "sent" if success else "failed", to_email
            )
        except Exception as fallback_e:
            logger.error(f"Even fallback email logging failed: {fallback_e}")


def _send_email_smtp(
    to_email: str, subject: str, html_body: str, text_body: Optional[str] = None
) -> bool:
    """Send email using SMTP settings from secrets (works with SendGrid SMTP relay)."""
    try:
        if "email" not in st.secrets:
            return False
        cfg = st.secrets["email"]
        smtp_server = cfg.get("smtp_server")
        smtp_port = int(cfg.get("smtp_port", 587))
        email_user = cfg.get("email_user")
        email_password = cfg.get("email_password")
        from_email = cfg.get("from_email", email_user)

        if not (smtp_server and email_user and email_password and from_email):
            return False

        msg = MIMEMultipart("alternative")
        msg["From"] = from_email
        msg["To"] = to_email
        msg["Subject"] = subject

        if text_body:
            msg.attach(MIMEText(text_body, "plain"))
        if html_body:
            msg.attach(MIMEText(html_body, "html"))

        server = smtplib.SMTP(smtp_server, smtp_port)
        server.starttls()
        server.login(email_user, email_password)
        server.sendmail(from_email, [to_email], msg.as_string())
        server.quit()
        return True
    except Exception as e:
        logger.error(f"SMTP send failed: {e}")
        return False


def send_email(
    to_email: str,
    subject: str,
    html_body: str,
    text_body: Optional[str] = None,
    email_type: str = "general",
    recipient_name: str = None,
    cycle_id: int = None,
    request_id: int = None,
    initiated_by: int = None,
) -> bool:
    """
    Queue email for background processing to avoid blocking UI.

    Args:
        to_email: Recipient email address
        subject: Email subject line
        html_body: HTML content of email
        text_body: Plain text version (optional)
        email_type: Type of email for logging purposes

    Returns:
        bool: True if email queued successfully, False otherwise
    """
    from services.db_helper import queue_email

    # Queue the email for background processing
    success = queue_email(to_email, subject, html_body, text_body, email_type)

    if success:
        logger.info(f"[EMAIL-QUEUED] Email queued for {to_email} - type: {email_type}")
    else:
        logger.error(f"[EMAIL-QUEUE-FAILED] Failed to queue email for {to_email}")

    return success


def _send_email_sync(
    to_email: str,
    subject: str,
    html_body: str,
    text_body: Optional[str] = None,
    email_type: str = "general",
):
    """
    Synchronously send email - used by background worker only.

    Returns:
        tuple: (success: bool, error_message: str)
    """
    try:
        # TEMPORARY: testing whitelist guard
        recipient = (to_email or "").strip().lower()
        if TEMP_EMAIL_WHITELIST_ACTIVE and recipient not in TEMP_EMAIL_WHITELIST:
            logger.info(
                f"[TEMP-WHITELIST] Skipping email to {to_email} for type '{email_type}'"
            )
            log_email_sent(to_email, subject, email_type, True, "skipped_by_whitelist")
            return True, "skipped_by_whitelist"
    except Exception as e:
        logger.warning(f"Whitelist check failed: {e}")

    # Prefer SMTP if configured (works without installing SendGrid SDK)
    smtp_cfg = st.secrets.get("email", {}) if "email" in st.secrets else {}
    if smtp_cfg.get("smtp_server"):
        ok = _send_email_smtp(to_email, subject, html_body, text_body)
        if ok:
            log_email_sent(to_email, subject, email_type, True)
            return True, "sent_via_smtp"

    sg_client = get_sendgrid_client()
    if not sg_client:
        error_msg = "Email client not available"
        logger.warning(f"{error_msg} - email not sent to {to_email}")
        log_email_sent(to_email, subject, email_type, False, error_msg)
        return False, error_msg

    try:
        from_email = Email(get_sender_email())
        to_email_obj = To(to_email)

        if text_body:
            mail = Mail(
                from_email, to_email_obj, subject, Content("text/plain", text_body)
            )
            mail.add_content(Content("text/html", html_body))
        else:
            mail = Mail(
                from_email, to_email_obj, subject, Content("text/html", html_body)
            )

        response = sg_client.send(mail)
        if response.status_code in [200, 202]:
            logger.info(
                f"Email sent successfully to {to_email} - Status: {response.status_code}"
            )
            log_email_sent(to_email, subject, email_type, True)
            return True, f"sent_via_sendgrid_status_{response.status_code}"
        else:
            error_msg = f"Status: {response.status_code}"
            logger.warning(
                f"Email send failed - Status: {response.status_code}, Response: {response.body}"
            )
            log_email_sent(to_email, subject, email_type, False, error_msg)
            return False, error_msg
    except Exception as e:
        error_msg = f"Exception sending email: {str(e)}"
        logger.error(error_msg)
        log_email_sent(to_email, subject, email_type, False, error_msg)
        return False, error_msg


def send_external_stakeholder_invite(
    external_email: str,
    requester_name: str,
    requester_designation: str,
    cycle_name: str,
    token: str,
    feedback_deadline: str,
    requester_vertical: str = "",
    external_stakeholder_name: str = "",
    cycle_id: int = None,
    request_id: int = None,
    initiated_by: int = None,
) -> bool:
    """Send invitation email to external stakeholder with token-based access."""

    # Use production domain
    app_url = "https://360feedback.projecttech4dev.org"

    subject = f"Feedback Request from {requester_name} at Tech4Dev"

    html_body = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
            .header {{ background-color: #1E4796; color: white; padding: 20px; text-align: center; }}
            .header h1 {{ margin: 0; font-size: 24px; }}
            .header h2 {{ margin: 5px 0 0 0; font-size: 18px; opacity: 0.9; }}
            .content {{ padding: 20px; }}
            .token-box {{ background-color: #f0f0f0; padding: 15px; border-left: 4px solid #1E4796; margin: 20px 0; }}
            .steps {{ background-color: #f9f9f9; padding: 15px; border-radius: 5px; margin: 20px 0; }}
            .footer {{ background-color: #f0f0f0; padding: 10px; text-align: center; font-size: 12px; }}
        </style>
    </head>
    <body>
        <div class="header">
            <h1>Insight 360°</h1>
            <h2>Feedback Request</h2>
        </div>
        
        <div class="content">
            <h2>Hi {external_stakeholder_name if external_stakeholder_name else "there"},</h2>
            
            <p><strong>{requester_name}</strong> ({requester_designation}{f", {requester_vertical}" if requester_vertical else ""}) 
            has requested your feedback as part of their 360° review at Tech4Dev.</p>
            
            <p>Your insights and perspective are valuable for their professional development. 
            The feedback process is anonymous and should take about 10-15 minutes to complete.</p>
            
            <div class="token-box">
                <h3>Your Access Information:</h3>
                <p><strong>Email:</strong> {external_email}</p>
                <p><strong>Access Token:</strong> <code style="background-color: #e0e0e0; padding: 2px 5px;">{token}</code></p>
            </div>
            
            <div class="steps">
                <h3>How to Provide Feedback:</h3>
                <ol>
                    <li>Visit the feedback portal: <a href="{app_url}">{app_url}</a></li>
                    <li>Click "External Stakeholder Login"</li>
                    <li>Enter your email address: <strong>{external_email}</strong></li>
                    <li>Enter your access token: <strong>{token}</strong></li>
                    <li>Complete the feedback questions</li>
                </ol>
            </div>
            
            <p><strong>Important Details:</strong></p>
            <ul>
                <li><strong>Feedback Deadline:</strong> {feedback_deadline}</li>
                <li><strong>Review Cycle:</strong> {cycle_name}</li>
                <li>Your feedback will remain completely anonymous</li>
                <li>You can save your progress and return later using the same token</li>
                <li>You can decline to participate if you don't have sufficient working relationship</li>
            </ul>
            
            <p>If you have any questions or need assistance, please contact diana@projecttech4dev.org.</p>
            
            <p>Thank you for taking the time to provide valuable feedback!</p>
            
            <p>Best regards,<br>
            The Tech4Dev Team</p>
        </div>
        
        <div class="footer">
            <p>This is an automated message from the Tech4Dev Insight 360°.</p>
        </div>
    </body>
    </html>
    """

    text_body = f"""
    Feedback Request from {requester_name}

    Hi {external_stakeholder_name if external_stakeholder_name else "there"},

    {requester_name} ({requester_designation}{f", {requester_vertical}" if requester_vertical else ""}) has requested your feedback as part of their 360° review at Tech4Dev.

    Your Access Information:
    Email: {external_email}
    Access Token: {token}

    To provide feedback:
    1. Visit: {app_url}
    2. Click "External Stakeholder Login"
    3. Enter your email: {external_email}
    4. Enter your token: {token}
    5. Complete the feedback questions

    Feedback Deadline: {feedback_deadline}
    Review Cycle: {cycle_name}

    Your feedback will remain anonymous. You can save progress and return later using the same token.

    Thank you for your time!

    The Tech4Dev Team
    """

    return send_email(
        external_email,
        subject,
        html_body,
        text_body,
        "external_stakeholder_invite",
        recipient_name=external_stakeholder_name,
        cycle_id=cycle_id,
        request_id=request_id,
        initiated_by=initiated_by,
    )


def send_nominee_invite(
    reviewer_email: str,
    reviewer_name: str,
    requester_name: str,
    cycle_name: str,
    feedback_deadline: str,
    relationship_type: str,
) -> bool:
    """Send invitation email to internal reviewer after nomination is approved."""

    # Use production app URL
    app_url = "https://360feedback.projecttech4dev.org"
    relationship_display = relationship_type.replace("_", " ").title()

    subject = "📌 360° Feedback – Your Input Requested"

    html_body = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
            .header {{ background-color: #1E4796; color: white; padding: 20px; text-align: center; }}
            .header h1 {{ margin: 0; font-size: 24px; }}
            .header h2 {{ margin: 5px 0 0 0; font-size: 18px; opacity: 0.9; }}
            .content {{ padding: 20px; }}
            .info-box {{ background-color: #f0f8ff; padding: 15px; border-left: 4px solid #1E4796; margin: 20px 0; }}
            .footer {{ background-color: #f0f0f0; padding: 10px; text-align: center; font-size: 12px; }}
        </style>
    </head>
    <body>
        <div class="header">
            <h1>Insight 360°</h1>
            <h2>Feedback Request</h2>
        </div>
        
        <div class="content">
            <p>Hi {reviewer_name},</p>
            
            <p>You have been nominated by <strong>{requester_name}</strong> to provide feedback as part of the 360-degree feedback process. This is an opportunity for you to share your valuable feedback on the individual's strengths and areas for improvement which can help the person grow and excel. Request you to take out the time and fill the form in earnest.</p>
            
            <p>🔹 <strong>How to Submit Your Feedback?</strong></p>
            <p>Please complete the following form by <strong>{feedback_deadline}</strong>:</p>
            <p>📝 <a href="{app_url}">{app_url}</a></p>
            
            <p><strong>Approve the nomination and fill out the form!</strong></p>
            
            <p>Your feedback will remain confidential and will be used to support professional development. If you have any questions, feel free to reach out to diana@projecttech4dev.org.</p>
            
            <p>Thanks for your time and input!</p>
            
            <p>Best regards,<br>
            Talent Management</p>
        </div>
        
        <div class="footer">
            <p>This is an automated message from the Tech4Dev Insight 360°.</p>
        </div>
    </body>
    </html>
    """

    text_body = f"""
    Feedback Request

    Hi {reviewer_name},

    You have been selected to provide feedback for {requester_name} as part of their 360-degree review process.

    Feedback Details:
    - For: {requester_name}
    - Your Relationship: {relationship_display}
    - Review Cycle: {cycle_name}
    - Deadline: {feedback_deadline}

    Next Steps:
    1. Login to: {app_url}
    2. Go to "Review Requests"
    3. Accept or decline this request
    4. Complete the feedback questionnaire

    Your feedback will remain anonymous. Please provide honest, constructive feedback.

    Thank you!
    Talent Management
    """

    return send_email(reviewer_email, subject, html_body, text_body, "nominee_invite")


def send_manager_approval_request(
    manager_email: str,
    manager_name: str,
    requester_name: str,
    nominees: List[Dict],
    cycle_name: str,
) -> bool:
    """Send notification to manager about pending nomination approvals."""

    # Use production domain
    app_url = "https://360feedback.projecttech4dev.org"

    subject = f"Nomination Approval Required: {requester_name}'s feedback requests"

    nominees_list = ""
    for i, nominee in enumerate(nominees, 1):
        relationship = nominee.get("relationship_type", "").replace("_", " ").title()
        nominees_list += (
            f"{i}. {nominee.get('reviewer_name', 'Unknown')} ({relationship})\n"
        )

    html_body = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
            .header {{ background-color: #1E4796; color: white; padding: 20px; text-align: center; }}
            .header h1 {{ margin: 0; font-size: 24px; }}
            .header h2 {{ margin: 5px 0 0 0; font-size: 18px; opacity: 0.9; }}
            .content {{ padding: 20px; }}
            .nominees-box {{ background-color: #fff8f0; padding: 15px; border-left: 4px solid #E55325; margin: 20px 0; }}
            .footer {{ background-color: #f0f0f0; padding: 10px; text-align: center; font-size: 12px; }}
        </style>
    </head>
    <body>
        <div class="header">
            <h1>Insight 360°</h1>
            <h2>Nomination Approval Required</h2>
        </div>
        
        <div class="content">
            <h2>Hi {manager_name},</h2>
            
            <p><strong>{requester_name}</strong> has submitted 360° feedback nominations that require your approval.</p>
            
            <div class="nominees-box">
                <h3>Pending Nominations:</h3>
                <pre>{nominees_list}</pre>
            </div>
            
            <p><strong>Action Required:</strong></p>
            <ol>
                <li>Login to the feedback portal: <a href="{app_url}">{app_url}</a></li>
                <li>Navigate to "Approve Nominations" (check for notification badge)</li>
                <li>Review each nomination for appropriateness</li>
                <li>Approve or reject with reasons</li>
            </ol>
            
            <p><strong>Review Guidelines:</strong></p>
            <ul>
                <li>Ensure nominees have sufficient working relationship with the requester</li>
                <li>Check that the relationship type is appropriate</li>
                <li>Consider nominee's current workload and availability</li>
                <li>Provide clear reasons if rejecting nominations</li>
            </ul>
            
            <p>Please review and approve/reject these nominations promptly to keep the feedback process on track.</p>
            
            <p>Best regards,<br>
            Talent Management</p>
        </div>
        
        <div class="footer">
            <p>This is an automated message from the Tech4Dev Insight 360°.</p>
        </div>
    </body>
    </html>
    """

    text_body = f"""
    Nomination Approval Required

    Hi {manager_name},

    {requester_name} has submitted new feedback nominations that require your approval.

    Pending Nominations:
    {nominees_list}

    Action Required:
    1. Login to: {app_url}
    2. Navigate to "Approve Nominations"
    3. Review each nomination
    4. Approve or reject with reasons

    Please review promptly to keep the feedback process on track.

    Talent Management
    """

    return send_email(
        manager_email, subject, html_body, text_body, "manager_approval_request"
    )


def send_nomination_approved(
    requester_email: str,
    requester_name: str,
    approved_nominees: List[str],
    cycle_name: str,
) -> bool:
    """Send notification when nominations are approved by manager."""

    subject = "Feedback nominations approved"

    nominees_list = "\n".join([f"• {nominee}" for nominee in approved_nominees])

    html_body = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
            .header {{ background-color: #1E4796; color: white; padding: 20px; text-align: center; }}
            .header h1 {{ margin: 0; font-size: 24px; }}
            .header h2 {{ margin: 5px 0 0 0; font-size: 18px; opacity: 0.9; }}
            .content {{ padding: 20px; }}
            .success-box {{ background-color: #f0fff0; padding: 15px; border-left: 4px solid #28a745; margin: 20px 0; }}
            .footer {{ background-color: #f0f0f0; padding: 10px; text-align: center; font-size: 12px; }}
        </style>
    </head>
    <body>
        <div class="header">
            <h1>Insight 360°</h1>
            <h2>Nominations Approved ✅</h2>
        </div>
        
        <div class="content">
            <h2>Hi {requester_name},</h2>
            
            <p>Great news! Your manager has approved the following feedback nominations.</p>
            
            <div class="success-box">
                <h3>Approved Reviewers:</h3>
                <pre>{nominees_list}</pre>
            </div>
            
            <p><strong>What happens next:</strong></p>
            <ul>
                <li>Approved reviewers will receive invitation emails to provide feedback</li>
                <li>You can track the progress in your "Current Cycle Feedback" dashboard</li>
                <li>You'll be notified by email when feedback is provided</li>
                <li>You will be able to view your anonymized feedback on the app.</li>
            </ul>
            
            <p><strong>Portal:</strong> <a href="https://360feedback.projecttech4dev.org">https://360feedback.projecttech4dev.org</a></p>
            
            <p>The feedback collection process is now underway!</p>
            
            <p>Best regards,<br>
            Talent Management</p>
        </div>
        
        <div class="footer">
            <p>This is an automated message from the Tech4Dev Insight 360°.</p>
        </div>
    </body>
    </html>
    """

    return send_email(requester_email, subject, html_body, None, "nomination_approved")


def send_nomination_rejected(
    requester_email: str,
    requester_name: str,
    rejected_nominees: List[Dict],
    cycle_name: str,
) -> bool:
    """Send notification when nominations are rejected by manager."""

    subject = "Feedback nominations require revision"

    rejections_list = ""
    for nominee in rejected_nominees:
        reason = nominee.get("rejection_reason", "No reason provided")
        rejections_list += f"• {nominee.get('reviewer_name', 'Unknown')}: {reason}\n"

    html_body = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
            .header {{ background-color: #1E4796; color: white; padding: 20px; text-align: center; }}
            .header h1 {{ margin: 0; font-size: 24px; }}
            .header h2 {{ margin: 5px 0 0 0; font-size: 18px; opacity: 0.9; }}
            .content {{ padding: 20px; }}
            .rejection-box {{ background-color: #fff5f5; padding: 15px; border-left: 4px solid #dc3545; margin: 20px 0; }}
            .footer {{ background-color: #f0f0f0; padding: 10px; text-align: center; font-size: 12px; }}
        </style>
    </head>
    <body>
        <div class="header">
            <h1>Insight 360°</h1>
            <h2>360° Feedback Nominations Require Revision</h2>
        </div>
        
        <div class="content">
            <h2>Hi {requester_name},</h2>
            
            <p>Your manager has reviewed your feedback nominations and has rejected the following:</p>
            
            <div class="rejection-box">
                <h3>Rejected Nominations:</h3>
                <pre>{rejections_list}</pre>
            </div>
            
            <p><strong>Next Steps:</strong></p>
            <ul>
                <li>Review the rejection reasons carefully</li>
                <li>Submit new nominations for different reviewers</li>
                <li>Ensure nominees have sufficient working relationship with you</li>
                <li>You can still nominate up to your remaining allocation</li>
            </ul>
            
            <p><strong>Portal:</strong> <a href="https://360feedback.projecttech4dev.org">https://360feedback.projecttech4dev.org</a></p>
            
            <p>Please submit replacement nominations promptly to stay on track for the feedback deadline.</p>
            
            <p>Best regards,<br>
            Talent Management</p>
        </div>
        
        <div class="footer">
            <p>This is an automated message from the Tech4Dev Insight 360°.</p>
        </div>
    </body>
    </html>
    """

    return send_email(requester_email, subject, html_body, None, "nomination_rejected")


def send_feedback_submitted_notification(
    requester_email: str,
    requester_name: str,
    reviewer_name: str,
    cycle_name: str,
    is_external: bool = False,
) -> bool:
    """Send notification when feedback is submitted by a reviewer."""

    # Use generic subject since feedback is anonymized
    subject = "Feedback received"

    html_body = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
            .header {{ background-color: #1E4796; color: white; padding: 20px; text-align: center; }}
            .header h1 {{ margin: 0; font-size: 24px; }}
            .header h2 {{ margin: 5px 0 0 0; font-size: 18px; opacity: 0.9; }}
            .content {{ padding: 20px; }}
            .info-box {{ background-color: #f0f8ff; padding: 15px; border-left: 4px solid #1E4796; margin: 20px 0; }}
            .footer {{ background-color: #f0f0f0; padding: 10px; text-align: center; font-size: 12px; }}
        </style>
    </head>
    <body>
        <div class="header">
            <h1>Insight 360°</h1>
            <h2>360° Feedback Received</h2>
        </div>
        
        <div class="content">
            <h2>Hi {requester_name},</h2>
            
            <p>Good news! You have received feedback!</p>
            
            <div class="info-box">
                <h3>Progress Update:</h3>
                <p>A reviewer has completed their feedback for you. You can view your anonymized feedback in the "Current Cycle Feedback" dashboard.</p>
                <p><strong>Portal:</strong> <a href="https://360feedback.projecttech4dev.org">https://360feedback.projecttech4dev.org</a></p>
            </div>
            
            <p><strong>What's Next:</strong></p>
            <ul>
                <li>Continue to encourage any remaining reviewers to complete their feedback</li>
                <li>Your anonymized feedback is available for you to review</li>
            </ul>
            
            <p>Thank you for participating in the 360° feedback process!</p>
            
            <p>Best regards,<br>
            Talent Management</p>
        </div>
        
        <div class="footer">
            <p>This is an automated message from the Tech4Dev Insight 360°.</p>
        </div>
    </body>
    </html>
    """

    return send_email(
        requester_email, subject, html_body, None, "feedback_submitted_notification"
    )


def send_cycle_deadline_reminder(
    user_email: str,
    user_name: str,
    deadline_type: str,
    deadline_date: str,
    days_remaining: int,
) -> bool:
    """Send reminder email about approaching deadlines."""

    if deadline_type == "nomination":
        subject = f"Reminder: {days_remaining} days left to submit feedback nominations"
        action = "submit your feedback nominations"
        page = "Request Feedback"
    elif deadline_type == "feedback":
        subject = f"Reminder: {days_remaining} days left to complete feedback reviews"
        action = "complete your pending feedback reviews"
        page = "Provide Feedback"
    else:
        subject = f"Reminder: {days_remaining} days left for feedback cycle"
        action = "complete your pending tasks"
        page = "dashboard"

    # Use production domain
    app_url = "https://360feedback.projecttech4dev.org"

    html_body = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
            .header {{ background-color: #1E4796; color: white; padding: 20px; text-align: center; }}
            .header h1 {{ margin: 0; font-size: 24px; }}
            .header h2 {{ margin: 5px 0 0 0; font-size: 18px; opacity: 0.9; }}
            .content {{ padding: 20px; }}
            .warning-box {{ background-color: #fff8e1; padding: 15px; border-left: 4px solid #ffc107; margin: 20px 0; }}
            .footer {{ background-color: #f0f0f0; padding: 10px; text-align: center; font-size: 12px; }}
        </style>
    </head>
    <body>
        <div class="header">
            <h1>Insight 360°</h1>
            <h2>⏰ Deadline Reminder</h2>
        </div>
        
        <div class="content">
            <h2>Hi {user_name},</h2>
            
            <p>This is a friendly reminder that you have <strong>{days_remaining} days</strong> 
            remaining to {action}.</p>
            
            <div class="warning-box">
                <h3>Important Details:</h3>
                <p><strong>Deadline:</strong> {deadline_date}</p>
                <p><strong>Days Remaining:</strong> {days_remaining}</p>
                <p><strong>Action Required:</strong> {action.title()}</p>
            </div>
            
            <p><strong>To complete this task:</strong></p>
            <ol>
                <li>Login to the feedback portal: <a href="{app_url}">{app_url}</a></li>
                <li>Navigate to "{page}"</li>
                <li>Complete your pending items</li>
            </ol>
            
            <p>Don't miss the deadline! Please complete your tasks promptly.</p>
            
            <p>Best regards,<br>
            Talent Management</p>
        </div>
        
        <div class="footer">
            <p>This is an automated reminder from the Tech4Dev Insight 360°.</p>
        </div>
    </body>
    </html>
    """

    return send_email(user_email, subject, html_body, None, "deadline_reminder")


def send_manual_reminder(
    to_emails: List[str], subject: str, html_body: str, text_body: Optional[str] = None
) -> Dict[str, bool]:
    """
    Send manual reminder emails to multiple recipients.

    Args:
        to_emails: List of recipient email addresses
        subject: Email subject line
        html_body: HTML content of email
        text_body: Plain text version (optional)

    Returns:
        Dict mapping email addresses to success status
    """
    results = {}

    for email in to_emails:
        success = send_email(
            email.strip(), subject, html_body, text_body, "manual_reminder"
        )
        results[email.strip()] = success

    return results


def get_email_log(limit: int = 100) -> List[Dict[str, Any]]:
    """Retrieve recent email log entries for debugging and tracking."""
    try:
        conn = sqlite3.connect("feedback_app.db")
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT id, to_email, subject, email_type, sent_at, success, error_message, sender_email
            FROM sent_emails_log
            ORDER BY sent_at DESC
            LIMIT ?
        """,
            (limit,),
        )

        rows = cursor.fetchall()
        conn.close()

        return [
            {
                "id": row[0],
                "to_email": row[1],
                "subject": row[2],
                "email_type": row[3],
                "sent_at": row[4],
                "success": bool(row[5]),
                "error_message": row[6],
                "sender_email": row[7],
            }
            for row in rows
        ]
    except Exception as e:
        logger.error(f"Failed to retrieve email log: {e}")
        return []


# Legacy compatibility functions (keeping existing function signatures)
def send_external_stakeholder_invitation(
    to_email,
    requester_name,
    requester_vertical,
    cycle_name,
    token,
    app_url="https://360feedbacktool.streamlit.app/",
    external_stakeholder_name="",
):
    """Legacy function - redirects to new send_external_stakeholder_invite."""
    return send_external_stakeholder_invite(
        external_email=to_email,
        requester_name=requester_name,
        requester_designation="",
        cycle_name=cycle_name,
        token=token,
        feedback_deadline="",
        requester_vertical=requester_vertical,
        external_stakeholder_name=external_stakeholder_name,
    )


def send_feedback_request_email(to_email, requester_name, app_url=""):
    """Legacy function - redirects to new send_nominee_invite."""
    return send_nominee_invite(
        reviewer_email=to_email,
        reviewer_name="",
        requester_name=requester_name,
        cycle_name="",
        feedback_deadline="",
        relationship_type="",
    )


def send_reminder_email(to_email, pending_count, app_url=""):
    """Legacy function for sending reminder emails."""
    return send_cycle_deadline_reminder(
        user_email=to_email,
        user_name="",
        deadline_type="feedback",
        deadline_date="",
        days_remaining=pending_count,
    )


def send_approval_needed_email(manager_email, requester_name):
    """Legacy function - redirects to new send_manager_approval_request."""
    return send_manager_approval_request(
        manager_email=manager_email,
        manager_name="",
        requester_name=requester_name,
        nominees=[],
        cycle_name="",
    )


def send_rejection_notice_email(requester_email, reviewer_name, rejection_reason):
    """Legacy function - redirects to new send_nomination_rejected."""
    return send_nomination_rejected(
        requester_email=requester_email,
        requester_name="",
        rejected_nominees=[
            {"reviewer_name": reviewer_name, "rejection_reason": rejection_reason}
        ],
        cycle_name="",
    )


def send_password_reset_email(email, first_name, reset_token):
    """Send password reset email with token."""
    subject = "Password Reset - Insight 360°"
    html_body = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
            .header {{ background-color: #1E4796; color: white; padding: 20px; text-align: center; }}
            .header h1 {{ margin: 0; font-size: 24px; }}
            .header h2 {{ margin: 5px 0 0 0; font-size: 18px; opacity: 0.9; }}
            .content {{ padding: 20px; }}
            .token-box {{ background-color: #f0f0f0; padding: 15px; border-left: 4px solid #1E4796; margin: 20px 0; }}
            .footer {{ background-color: #f0f0f0; padding: 10px; text-align: center; font-size: 12px; }}
        </style>
    </head>
    <body>
        <div class="header">
            <h1>Insight 360°</h1>
            <h2>Password Reset Request</h2>
        </div>
        
        <div class="content">
            <h2>Hello {first_name},</h2>
            <p>You have requested to reset your password for Insight 360°.</p>
            
            <div class="token-box">
                <h3>Your Reset Token:</h3>
                <p style="font-family: monospace; font-size: 16px; font-weight: bold; color: #333;">
                    {reset_token}
                </p>
            </div>
            
            <p><strong>Instructions:</strong></p>
            <ol>
                <li>Copy the reset token above</li>
                <li>Return to the login page</li>
                <li>Click "Forgot Password?" again</li>
                <li>Select "I have a reset token"</li>
                <li>Paste the token and create your new password</li>
            </ol>
            
            <p><strong>Important:</strong></p>
            <ul>
                <li>This token expires in 24 hours</li>
                <li>Use this token only once</li>
                <li>If you didn't request this reset, please contact your administrator</li>
            </ul>
            
            <p>If you have any issues, please contact your system administrator.</p>
            
            <p>Best regards,<br>Insight 360°</p>
        </div>
        
        <div class="footer">
            <p>This is an automated message from the Tech4Dev Insight 360°.</p>
        </div>
    </body>
    </html>
    """
    return send_email(email, subject, html_body, None, "password_reset")
