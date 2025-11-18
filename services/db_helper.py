"""
Database Helper Functions
Clean implementation using turso-python for ARM compatibility
"""

import streamlit as st
import pandas as pd
import hashlib
import secrets
from datetime import datetime, date, timedelta
from typing import Optional, List, Dict, Any, Union, Tuple
import logging
from .turso_connection import get_connection

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Cache for frequently accessed data
_cache = {}
_cache_timestamps = {}

def get_cached_value(cache_key, cache_duration_seconds=60):
    """Get a cached value if it hasn't expired"""
    if cache_key in _cache and cache_key in _cache_timestamps:
        cache_time = _cache_timestamps[cache_key]
        if (datetime.now() - cache_time).seconds < cache_duration_seconds:
            return _cache[cache_key]
    return None

def set_cached_value(cache_key, data, cache_duration_seconds=60):
    """Set a cached value with timestamp"""
    _cache[cache_key] = data
    _cache_timestamps[cache_key] = datetime.now()

# =====================================================
# EMAIL QUEUE FUNCTIONS
# =====================================================

def create_email_queue_table():
    """Create the email queue table if it doesn't exist"""
    conn = get_connection()
    try:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS email_queue (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                to_email TEXT NOT NULL,
                subject TEXT NOT NULL,
                html_body TEXT NOT NULL,
                text_body TEXT,
                email_type TEXT DEFAULT 'general',
                status TEXT DEFAULT 'pending',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_attempt TIMESTAMP,
                attempt_count INTEGER DEFAULT 0,
                error_message TEXT
            )
        """)
        conn.commit()
    except Exception as e:
        logger.error(f"Error creating email queue table: {e}")

def queue_email(to_email: str, subject: str, html_body: str, text_body: str = None, email_type: str = "general"):
    """Add email to the queue"""
    conn = get_connection()
    try:
        conn.execute("""
            INSERT INTO email_queue (to_email, subject, html_body, text_body, email_type)
            VALUES (?, ?, ?, ?, ?)
        """, (to_email, subject, html_body, text_body, email_type))
        conn.commit()
    except Exception as e:
        logger.error(f"Error queuing email: {e}")

def get_pending_emails():
    """Get pending emails from the queue"""
    conn = get_connection()
    try:
        result = conn.execute("""
            SELECT id, to_email, subject, html_body, text_body, email_type
            FROM email_queue 
            WHERE status = 'pending' 
            ORDER BY created_at ASC
        """)
        return result.fetchall()
    except Exception as e:
        logger.error(f"Error fetching pending emails: {e}")
        return []

def mark_email_sent(email_id: int):
    """Mark email as successfully sent"""
    conn = get_connection()
    try:
        conn.execute("""
            UPDATE email_queue 
            SET status = 'sent', last_attempt = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (email_id,))
        conn.commit()
    except Exception as e:
        logger.error(f"Error marking email as sent: {e}")

def mark_email_failed(email_id: int, error_message: str):
    """Mark email as failed and increment attempts"""
    conn = get_connection()
    try:
        conn.execute("""
            UPDATE email_queue 
            SET status = 'failed', last_attempt = CURRENT_TIMESTAMP,
                attempt_count = attempt_count + 1, error_message = ?
            WHERE id = ?
        """, (error_message, email_id))
        conn.commit()
    except Exception as e:
        logger.error(f"Error marking email as failed: {e}")

# =====================================================
# USER MANAGEMENT FUNCTIONS
# =====================================================

def fetch_user_by_email(email):
    """Fetch user details by email"""
    conn = get_connection()
    try:
        result = conn.execute("""
            SELECT user_type_id, first_name, last_name, email, password_hash, is_active, 
                   vertical, designation, reporting_manager_email, date_of_joining
            FROM users 
            WHERE email = ? AND is_active = 1
        """, (email,))
        
        row = result.fetchone()
        if row:
            return {
                'user_type_id': row[0],
                'first_name': row[1],
                'last_name': row[2],
                'email': row[3],
                'password_hash': row[4],
                'is_active': row[5],
                'vertical': row[6],
                'designation': row[7],
                'reporting_manager_email': row[8],
                'date_of_joining': row[9]
            }
        return None
    except Exception as e:
        logger.error(f"Error fetching user by email {email}: {e}")
        return None

def fetch_user_roles(user_type_id):
    """Fetch roles for a specific user."""
    with get_connection() as conn:
        query = """
            SELECT r.role_id, r.role_name, r.description 
            FROM roles r
            JOIN user_roles ur ON r.role_id = ur.role_id
            WHERE ur.user_type_id = ?;
        """
        try:
            result = conn.execute(query, (user_type_id,))
            roles = result.fetchall()
            return [{"role_id": row[0], "role_name": row[1], "description": row[2]} for row in roles]
        except Exception as e:
            logger.error(f"Error fetching user roles: {e}")
            return []

def set_user_password(email, password_hash):
    """Set user password"""
    conn = get_connection()
    try:
        conn.execute("""
            UPDATE users 
            SET password_hash = ? 
            WHERE email = ?
        """, (password_hash, email))
        conn.commit()
        return True
    except Exception as e:
        logger.error(f"Error setting password for {email}: {e}")
        return False

def get_users_for_selection(exclude_user_id=None, requester_user_id=None):
    """Get list of all active users eligible to give feedback (reviewers)."""
    with get_connection() as conn:
        try:
            # Eligibility to give feedback: joined before cutoff OR at least 90 days tenure
            # If date_of_joining is NULL, include user (cannot validate; do not block)
            query = """
                SELECT user_type_id, first_name, last_name, vertical, designation, email
                FROM users 
                WHERE is_active = 1
                  AND (
                    date_of_joining IS NULL
                    OR DATE(date_of_joining) <= DATE('2025-09-30')
                    OR DATE(date_of_joining) <= DATE('now', '-90 days')
                  )
            """
            params = []
            
            if exclude_user_id:
                query += " AND user_type_id != ?"
                params.append(exclude_user_id)
            
            query += " ORDER BY first_name, last_name"
            
            result = conn.execute(query, tuple(params) if params else ())
            users = []
            for row in result.fetchall():
                users.append({
                    "user_type_id": row[0],
                    "name": f"{row[1]} {row[2]}",
                    "first_name": row[1],
                    "last_name": row[2],
                    "vertical": row[3] or "Unknown",
                    "designation": row[4] or "Unknown",
                    "email": row[5]
                })
            return users
        except Exception as e:
            logger.error(f"Error fetching users: {e}")
            return []

def _parse_iso_date(value):
    """Parse ISO date string to date object"""
    if not value:
        return None
    try:
        if isinstance(value, str):
            return datetime.fromisoformat(value.replace('Z', '+00:00')).date()
        return value
    except:
        return None

def can_user_request_feedback(user_id):
    """Check if user can request feedback based on date of joining policy"""
    conn = get_connection()
    try:
        result = conn.execute("""
            SELECT date_of_joining FROM users WHERE user_type_id = ?
        """, (user_id,))
        
        row = result.fetchone()
        if not row or not row[0]:
            # If no DOJ, allow (configurable policy)
            return True
        
        doj = _parse_iso_date(row[0])
        if not doj:
            return True
        
        # Policy: Must have joined on or before 2025-09-30 to request feedback
        cutoff_date = date(2025, 9, 30)
        return doj <= cutoff_date
        
    except Exception as e:
        logger.error(f"Error checking user feedback eligibility: {e}")
        return True  # Default to allowing if error occurs

def get_manager_level_from_designation(designation):
    """Determine manager level from designation"""
    if not designation:
        return 0
    
    designation = designation.lower()
    
    if any(term in designation for term in ['director', 'head']):
        return 3
    elif any(term in designation for term in ['senior manager', 'senior mgr']):
        return 2
    elif any(term in designation for term in ['manager', 'mgr', 'team lead', 'team leader']):
        return 1
    else:
        return 0

def check_external_stakeholder_permission(user_id):
    """Check if user can nominate external stakeholders"""
    conn = get_connection()
    try:
        result = conn.execute("""
            SELECT designation FROM users WHERE user_type_id = ?
        """, (user_id,))
        
        row = result.fetchone()
        if row and row[0]:
            manager_level = get_manager_level_from_designation(row[0])
            return manager_level >= 1  # Manager level or above
        return False
    except Exception as e:
        logger.error(f"Error checking external stakeholder permission: {e}")
        return False

# =====================================================
# REVIEW CYCLE FUNCTIONS  
# =====================================================

def get_active_review_cycle():
    """Get the currently active review cycle with enhanced metadata"""
    conn = get_connection()
    query = """
        SELECT cycle_id, cycle_name, cycle_display_name, cycle_description,
               cycle_year, cycle_quarter, phase_status,
               nomination_start_date, nomination_deadline, 
               feedback_deadline, created_at
        FROM review_cycles 
        WHERE is_active = 1
        LIMIT 1
    """
    try:
        result = conn.execute(query)
        cycle = result.fetchone()
        if cycle:
            return {
                'cycle_id': cycle[0],
                'cycle_name': cycle[1],
                'cycle_display_name': cycle[2] or cycle[1],
                'cycle_description': cycle[3],
                'cycle_year': cycle[4],
                'cycle_quarter': cycle[5],
                'phase_status': cycle[6],
                'nomination_start_date': cycle[7],
                'nomination_deadline': cycle[8],
                'feedback_deadline': cycle[9],
                'created_at': cycle[10]
            }
        return None
    except Exception as e:
        logger.error(f"Error getting active review cycle: {e}")
        return None

def get_all_cycles():
    """Get all review cycles with enhanced metadata, ordered by most recent first"""
    conn = get_connection()
    query = """
        SELECT cycle_id, cycle_name, cycle_display_name, cycle_description, 
               cycle_year, cycle_quarter, phase_status, is_active,
               nomination_start_date, nomination_deadline, feedback_deadline, created_at
        FROM review_cycles 
        ORDER BY created_at DESC
    """
    try:
        result = conn.execute(query)
        cycles = []
        for row in result.fetchall():
            cycles.append({
                'cycle_id': row[0],
                'cycle_name': row[1],
                'cycle_display_name': row[2],
                'cycle_description': row[3],
                'cycle_year': row[4],
                'cycle_quarter': row[5],
                'phase_status': row[6],
                'is_active': row[7],
                'nomination_start_date': row[8],
                'nomination_deadline': row[9],
                'feedback_deadline': row[10],
                'created_at': row[11]
            })
        return cycles
    except Exception as e:
        logger.error(f"Error fetching all cycles: {e}")
        return []

def create_named_cycle(display_name, description, year, quarter, cycle_name, nomination_start, nomination_deadline, feedback_deadline, created_by):
    """Create a new named review cycle"""
    conn = get_connection()
    try:
        # Create new cycle with enhanced fields first
        conn.execute("""
            INSERT INTO review_cycles 
            (cycle_name, cycle_display_name, cycle_description, cycle_year, cycle_quarter,
             nomination_start_date, nomination_deadline, feedback_deadline, phase_status, is_active, created_by)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'nomination', 1, ?)
        """, (cycle_name, display_name, description, year, quarter,
              nomination_start, nomination_deadline, feedback_deadline, created_by))
        
        # Get the cycle_id (use a query since lastrowid may not work reliably)
        result = conn.execute("""
            SELECT cycle_id FROM review_cycles 
            WHERE cycle_name = ? AND created_by = ? 
            ORDER BY created_at DESC LIMIT 1
        """, (cycle_name, created_by))
        
        cycle_row = result.fetchone()
        if not cycle_row:
            raise Exception("Failed to retrieve created cycle ID")
        
        cycle_id = cycle_row[0]
        
        # Deactivate other cycles
        conn.execute("UPDATE review_cycles SET is_active = 0 WHERE cycle_id != ?", (cycle_id,))
        
        conn.commit()
        logger.info(f"Successfully created named cycle with ID {cycle_id} and deactivated others")
        return True, cycle_id
        
    except Exception as e:
        logger.error(f"Error creating named cycle: {e}")
        conn.rollback()
        return False, str(e)

def mark_cycle_complete(cycle_id, completion_notes=""):
    """Mark a cycle as complete and deactivate it"""
    conn = get_connection()
    try:
        # First check if the cycle exists and is active
        check_result = conn.execute("""
            SELECT cycle_id, cycle_name, is_active FROM review_cycles WHERE cycle_id = ?
        """, (cycle_id,))
        cycle_info = check_result.fetchone()
        
        if not cycle_info:
            return False, f"No cycle found with ID {cycle_id}"
        
        if cycle_info[2] == 0:  # is_active is 0
            return False, f"Cycle '{cycle_info[1]}' is already inactive"
        
        # Update cycle to completed status
        conn.execute("""
            UPDATE review_cycles 
            SET is_active = 0, 
                phase_status = 'completed'
            WHERE cycle_id = ? AND is_active = 1
        """, (cycle_id,))
        conn.commit()
        
        # Verify the update succeeded by re-querying
        verify_result = conn.execute("""
            SELECT is_active, phase_status FROM review_cycles WHERE cycle_id = ?
        """, (cycle_id,))
        updated_cycle = verify_result.fetchone()
        
        if updated_cycle and updated_cycle[0] == 0 and updated_cycle[1] == 'completed':
            logger.info(f"Cycle {cycle_id} marked as complete")
            return True, f"Cycle '{cycle_info[1]}' marked as complete successfully"
        else:
            return False, f"Failed to update cycle '{cycle_info[1]}' - verification failed."
            
    except Exception as e:
        logger.error(f"Error marking cycle complete: {e}")
        conn.rollback()
        return False, f"Database error: {str(e)}"

def get_current_cycle_phase():
    """Get the current phase of the active cycle"""
    active_cycle = get_active_review_cycle()
    if not active_cycle:
        return None
    
    today = date.today()
    nomination_deadline = active_cycle.get('nomination_deadline')
    
    if nomination_deadline:
        try:
            if isinstance(nomination_deadline, str):
                deadline_date = datetime.fromisoformat(nomination_deadline).date()
            else:
                deadline_date = nomination_deadline
            
            if today <= deadline_date:
                return "nomination"
            else:
                return "feedback"
        except:
            pass
    
    return "nomination"

def update_cycle_status(cycle_id, new_status):
    """Update the phase_status of a specific review cycle"""
    conn = get_connection()
    try:
        conn.execute("UPDATE review_cycles SET phase_status = ? WHERE cycle_id = ?", 
                    (new_status, cycle_id))
        conn.commit()
        logger.info(f"Cycle {cycle_id} phase_status updated to '{new_status}'.")
        return True
    except Exception as e:
        logger.error(f"Error updating cycle phase_status: {e}")
        conn.rollback()
        return False

# =====================================================
# FEEDBACK REQUEST MANAGEMENT FUNCTIONS
# =====================================================

def create_feedback_requests_with_approval(requester_id, reviewer_data):
    """Create feedback requests that require manager approval with external stakeholder support.
    External stakeholder requests go to manager approval first. Invitations are sent after approval.
    """
    conn = get_connection()
    try:
        # Get active cycle
        active_cycle = get_active_review_cycle()
        if not active_cycle:
            return False, "No active review cycle found"
        
        cycle_id = active_cycle['cycle_id']
        
        # Get requester's manager
        manager_query = """
            SELECT m.user_type_id 
            FROM users u 
            JOIN users m ON u.reporting_manager_email = m.email 
            WHERE u.user_type_id = ?
        """
        manager_result = conn.execute(manager_query, (requester_id,))
        manager = manager_result.fetchone()
        
        if not manager:
            return False, "No reporting manager found"
        
        manager_id = manager[0]
        
        # Build lookup of existing nominations for this cycle to prevent duplicates
        existing_internal = set()
        existing_external = set()
        existing_query = """
            SELECT reviewer_id, external_reviewer_email
            FROM feedback_requests
            WHERE requester_id = ? AND cycle_id = ?
        """
        existing_result = conn.execute(existing_query, (requester_id, cycle_id))
        existing_rows = existing_result.fetchall()
        for reviewer_id, external_email in existing_rows:
            if reviewer_id:
                existing_internal.add(reviewer_id)
            if external_email:
                existing_external.add((external_email or "").strip().lower())
        
        duplicate_internal_ids = set()
        duplicate_external_emails = set()
        pending_internal = set()
        pending_external = set()
        external_display_lookup = {}
        
        for reviewer_identifier, _ in reviewer_data:
            if isinstance(reviewer_identifier, int):
                if (
                    reviewer_identifier in existing_internal
                    or reviewer_identifier in pending_internal
                ):
                    duplicate_internal_ids.add(reviewer_identifier)
                else:
                    pending_internal.add(reviewer_identifier)
            else:
                normalized_email = (reviewer_identifier or "").strip().lower()
                external_display_lookup[normalized_email] = (reviewer_identifier or "").strip()
                if (
                    normalized_email in existing_external
                    or normalized_email in pending_external
                ):
                    duplicate_external_emails.add(normalized_email)
                else:
                    pending_external.add(normalized_email)
        
        if duplicate_internal_ids or duplicate_external_emails:
            duplicate_labels = []
            
            if duplicate_internal_ids:
                placeholders = ",".join(["?"] * len(duplicate_internal_ids))
                name_query = f"""
                    SELECT user_type_id, COALESCE(first_name || ' ' || last_name, '') as full_name
                    FROM users
                    WHERE user_type_id IN ({placeholders})
                """
                name_result = conn.execute(name_query, tuple(duplicate_internal_ids))
                name_rows = name_result.fetchall()
                name_map = {row[0]: (row[1].strip() or f"User #{row[0]}") for row in name_rows}
                for reviewer_id in sorted(duplicate_internal_ids):
                    duplicate_labels.append(name_map.get(reviewer_id, f"User #{reviewer_id}"))
            
            if duplicate_external_emails:
                for email_key in sorted(duplicate_external_emails):
                    display_value = external_display_lookup.get(email_key, email_key)
                    duplicate_labels.append(display_value)
            
            duplicate_text = ", ".join(duplicate_labels)
            return False, f"You have already nominated the following reviewers in this cycle: {duplicate_text}"
        
        # Create requests for each reviewer
        external_requests = []  # Track external requests for email sending after approval
        
        for reviewer_identifier, relationship_type in reviewer_data:
            if isinstance(reviewer_identifier, int):
                # Internal reviewer (user ID)
                request_query = """
                    INSERT INTO feedback_requests 
                    (cycle_id, requester_id, reviewer_id, relationship_type, status, approval_status) 
                    VALUES (?, ?, ?, ?, 'pending_approval', 'pending')
                """
                conn.execute(request_query, (cycle_id, requester_id, reviewer_identifier, relationship_type))
                
                # Update nomination count for internal reviewers only
                nomination_query = """
                    INSERT INTO reviewer_nominations (reviewer_id, nomination_count) 
                    VALUES (?, 1)
                    ON CONFLICT(reviewer_id) DO UPDATE SET
                    nomination_count = nomination_count + 1,
                    last_updated = CURRENT_TIMESTAMP
                """
                conn.execute(nomination_query, (reviewer_identifier,))
            else:
                # External reviewer (email address) — goes through manager approval
                request_query = """
                    INSERT INTO feedback_requests 
                    (cycle_id, requester_id, external_reviewer_email, relationship_type, status, approval_status, external_status) 
                    VALUES (?, ?, ?, ?, 'pending_approval', 'pending', 'pending')
                """
                result = conn.execute(request_query, (cycle_id, requester_id, reviewer_identifier, relationship_type))
                # Note: turso-python doesn't support lastrowid directly, so we'll need to get the ID differently
                # For now, we'll proceed without storing the request_id
                
                # Store for later processing after approval
                external_requests.append({
                    'email': reviewer_identifier,
                    'relationship_type': relationship_type
                })
        
        conn.commit()

        # Informational log retained for debugging
        logger.info(
            f"Created requests successfully. {len(external_requests)} external stakeholders will be processed after manager approval."
        )

        return True, "Requests submitted for manager approval"
        
    except Exception as e:
        logger.error(f"Error creating feedback requests: {e}")
        conn.rollback()
        return False, str(e)

def get_pending_approvals_for_manager(manager_id):
    """Get feedback requests pending approval for a manager for the current active cycle only."""
    conn = get_connection()
    query = """
        SELECT 
            fr.request_id,
            fr.requester_id,
            fr.reviewer_id,
            fr.relationship_type,
            req.first_name AS requester_name,
            req.last_name AS requester_surname,
            COALESCE(rev.first_name, '') AS reviewer_name,
            COALESCE(rev.last_name, '') AS reviewer_surname,
            COALESCE(rev.vertical, 'External') AS reviewer_vertical,
            COALESCE(rev.designation, 'External Stakeholder') AS reviewer_designation,
            fr.created_at,
            fr.external_reviewer_email
        FROM feedback_requests fr
        JOIN users req ON fr.requester_id = req.user_type_id
        LEFT JOIN users rev ON fr.reviewer_id = rev.user_type_id
        JOIN users mgr ON req.reporting_manager_email = mgr.email
        JOIN review_cycles rc ON fr.cycle_id = rc.cycle_id
        WHERE mgr.user_type_id = ? 
            AND fr.approval_status = 'pending' 
            AND rc.is_active = 1
        ORDER BY fr.created_at ASC
    """
    try:
        result = conn.execute(query, (manager_id,))
        return result.fetchall()
    except Exception as e:
        logger.error(f"Error fetching pending approvals: {e}")
        return []

def approve_reject_feedback_request(request_id, manager_id, action, rejection_reason=None):
    """Manager approval/rejection with external invitation processing."""
    conn = get_connection()
    try:
        if action == "approve":
            conn.execute(
                """
                UPDATE feedback_requests
                SET approval_status='approved', workflow_state='pending_reviewer_acceptance',
                    approved_by=?, approval_date=CURRENT_TIMESTAMP, counts_toward_limit=1
                WHERE request_id = ?
                """,
                (manager_id, request_id),
            )
            # Process external stakeholder invitations immediately (emails are now queued)
            try:
                process_external_stakeholder_invitations(request_id)
            except Exception as e:
                logger.error(f"Error processing external invitations: {e}")
            
        elif action == "reject":
            # Add tracking ID for rejection monitoring
            tracking_id = f"rejection_{request_id}_{datetime.now().isoformat()}"
            
            # Get request details first
            request_details = conn.execute(
                "SELECT requester_id, reviewer_id, external_reviewer_email FROM feedback_requests WHERE request_id = ?", 
                (request_id,)
            ).fetchone()
            
            if request_details:
                # Update the feedback request
                conn.execute(
                    """
                    UPDATE feedback_requests
                    SET approval_status='rejected', status='rejected', workflow_state='manager_rejected',
                        approved_by=?, approval_date=CURRENT_TIMESTAMP, rejection_reason=?,
                        tracking_id=?, counts_toward_limit=0
                    WHERE request_id = ?
                    """,
                    (manager_id, rejection_reason, tracking_id, request_id)
                )
                
                # Insert into rejection tracking for HR monitoring
                try:
                    conn.execute(
                        """
                        INSERT INTO rejection_tracking 
                        (tracking_id, request_id, rejection_type, requester_id, rejected_reviewer_id, 
                         external_reviewer_email, rejected_by, rejection_reason, rejected_at, viewed_by_hr)
                        VALUES (?, ?, 'manager_rejection', ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, 0)
                        """,
                        (tracking_id, request_id, request_details[0], request_details[1], 
                         request_details[2], manager_id, rejection_reason)
                    )
                except Exception as e:
                    logger.error(f"Error adding rejection tracking: {e}")
                
                # Send rejection email
                try:
                    from services.email_service import send_nomination_rejected
                    # Get requester details for email
                    requester_result = conn.execute(
                        "SELECT first_name, last_name, email FROM users WHERE user_type_id = ?",
                        (request_details[0],)
                    ).fetchone()
                    
                    if requester_result:
                        requester_name = f"{requester_result[0]} {requester_result[1]}"
                        requester_email = requester_result[2]
                        
                        # Get reviewer name
                        if request_details[1]:  # Internal reviewer
                            reviewer_result = conn.execute(
                                "SELECT first_name, last_name FROM users WHERE user_type_id = ?",
                                (request_details[1],)
                            ).fetchone()
                            reviewer_name = f"{reviewer_result[0]} {reviewer_result[1]}" if reviewer_result else "Unknown"
                        else:  # External reviewer
                            reviewer_name = request_details[2]
                        
                        send_nomination_rejected(
                            requester_email=requester_email,
                            requester_name=requester_name,
                            reviewer_name=reviewer_name,
                            rejection_reason=rejection_reason
                        )
                except Exception as e:
                    logger.error(f"Error sending rejection email: {e}")
        
        conn.commit()
        return True
    except Exception as e:
        logger.error(f"Error processing approval/rejection: {e}")
        conn.rollback()
        return False

def reviewer_accept_reject_request(request_id, reviewer_id, action, rejection_reason=None):
    """Allow reviewer to accept or reject a feedback request."""
    conn = get_connection()
    try:
        if action == "accept":
            query = """
                UPDATE feedback_requests
                SET reviewer_status='accepted',
                    workflow_state='in_progress',
                    reviewer_response_date=CURRENT_TIMESTAMP,
                    counts_toward_limit=1
                WHERE request_id = ? AND (reviewer_id = ? OR external_reviewer_email = ?)
            """
            conn.execute(query, (request_id, reviewer_id, reviewer_id))
        elif action == "reject":
            # Add tracking for reviewer rejections
            tracking_id = f"reviewer_rejection_{request_id}_{datetime.now().isoformat()}"
            
            # Get request details for tracking
            request_details = conn.execute(
                "SELECT requester_id, reviewer_id, external_reviewer_email FROM feedback_requests WHERE request_id = ?",
                (request_id,)
            ).fetchone()
            
            if request_details:
                query = """
                    UPDATE feedback_requests
                    SET reviewer_status='rejected',
                        workflow_state='reviewer_rejected',
                        reviewer_rejection_reason=?,
                        reviewer_response_date=CURRENT_TIMESTAMP,
                        counts_toward_limit=0,
                        tracking_id=?
                    WHERE request_id = ? AND (reviewer_id = ? OR external_reviewer_email = ?)
                """
                conn.execute(query, (rejection_reason or "", tracking_id, request_id, reviewer_id, reviewer_id))
                
                # Insert into rejection tracking
                try:
                    conn.execute(
                        """
                        INSERT INTO rejection_tracking 
                        (tracking_id, request_id, rejection_type, requester_id, rejected_reviewer_id, 
                         external_reviewer_email, rejected_by, rejection_reason, rejected_at, viewed_by_hr)
                        VALUES (?, ?, 'reviewer_rejection', ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, 0)
                        """,
                        (tracking_id, request_id, request_details[0], request_details[1], 
                         request_details[2], reviewer_id, rejection_reason or "")
                    )
                except Exception as e:
                    logger.error(f"Error adding rejection tracking: {e}")
        
        conn.commit()
        return True, f"Request {action}ed successfully"
    except Exception as e:
        logger.error(f"Error processing reviewer response: {e}")
        conn.rollback()
        return False, f"Error processing reviewer response: {e}"

def get_user_nominations_status(user_id):
    """Get current user's nomination status and existing nominations (includes externals)."""
    conn = get_connection()
    try:
        active_cycle = get_active_review_cycle()
        if not active_cycle:
            return {
                "existing_nominations": [],
                "rejected_nominations": [],
                "total_count": 0,
                "can_nominate_more": True,
                "remaining_slots": 4,
            }
        cycle_id = active_cycle["cycle_id"]
        query = """
            SELECT fr.request_id, fr.reviewer_id, fr.external_reviewer_email,
                   fr.relationship_type, fr.workflow_state, fr.approval_status,
                   fr.reviewer_status, fr.created_at, fr.rejection_reason,
                   fr.reviewer_rejection_reason, fr.counts_toward_limit,
                   u.first_name, u.last_name, u.designation, u.vertical
            FROM feedback_requests fr
            LEFT JOIN users u ON fr.reviewer_id = u.user_type_id
            WHERE fr.requester_id = ? AND fr.cycle_id = ? AND COALESCE(fr.is_active,1) = 1
            ORDER BY fr.created_at ASC
        """
        result = conn.execute(query, (user_id, cycle_id))
        active_nominations = []
        rejected_nominations = []
        
        for row in result.fetchall():
            if row[2]:  # external
                reviewer_name = row[2]
                designation = "External Stakeholder"
                vertical = "External"
                reviewer_identifier = row[2]
            else:
                reviewer_name = f"{row[11]} {row[12]}".strip() if row[11] else "Unknown"
                designation = row[13] or "Unknown"
                vertical = row[14] or "Unknown"
                reviewer_identifier = row[1]
            
            data = {
                "request_id": row[0],
                "reviewer_id": row[1],
                "external_email": row[2],
                "reviewer_name": reviewer_name,
                "designation": designation,
                "vertical": vertical,
                "relationship_type": row[3],
                "workflow_state": row[4],
                "approval_status": row[5],
                "reviewer_status": row[6],
                "created_at": row[7],
                "rejection_reason": row[8],
                "reviewer_rejection_reason": row[9],
                "counts_toward_limit": row[10] or 0,
                "reviewer_identifier": reviewer_identifier,
            }
            
            if row[5] == "rejected" or row[6] == "rejected":  # approval_status or reviewer_status
                rejected_nominations.append(data)
            else:
                active_nominations.append(data)
        
        total_count = len(active_nominations)
        can_nominate_more = total_count < 4
        remaining_slots = max(0, 4 - total_count)
        
        return {
            "existing_nominations": active_nominations,
            "rejected_nominations": rejected_nominations,
            "total_count": total_count,
            "can_nominate_more": can_nominate_more,
            "remaining_slots": remaining_slots,
        }
    except Exception as e:
        logger.error(f"Error getting nomination status: {e}")
        return {
            "existing_nominations": [],
            "rejected_nominations": [],
            "total_count": 0,
            "can_nominate_more": True,
            "remaining_slots": 4,
        }

# =====================================================
# REVIEW MANAGEMENT FUNCTIONS
# =====================================================

def get_pending_reviews_for_user(user_id):
    """Get feedback requests pending for a user to complete (only for active cycles)."""
    conn = get_connection()
    query = """
        SELECT fr.request_id, req.first_name, req.last_name, req.vertical, 
               fr.created_at, fr.relationship_type,
               COUNT(dr.draft_id) as draft_count
        FROM feedback_requests fr
        JOIN users req ON fr.requester_id = req.user_type_id
        JOIN review_cycles rc ON fr.cycle_id = rc.cycle_id
        LEFT JOIN draft_responses dr ON fr.request_id = dr.request_id
        WHERE fr.reviewer_id = ? 
          AND fr.approval_status = 'approved' 
          AND fr.reviewer_status = 'accepted'
          AND rc.is_active = 1
        GROUP BY fr.request_id, req.first_name, req.last_name, req.vertical, fr.created_at, fr.relationship_type
        ORDER BY fr.created_at ASC
    """
    try:
        result = conn.execute(query, (user_id,))
        return result.fetchall()
    except Exception as e:
        logger.error(f"Error fetching pending reviews: {e}")
        return []

def get_questions_by_relationship_type(relationship_type):
    """Get questions for a specific relationship type."""
    conn = get_connection()
    query = """
        SELECT question_id, question_text, question_type, sort_order
        FROM feedback_questions 
        WHERE relationship_type = ? AND is_active = 1
        ORDER BY sort_order ASC
    """
    try:
        result = conn.execute(query, (relationship_type,))
        return result.fetchall()
    except Exception as e:
        logger.error(f"Error fetching questions: {e}")
        return []

def get_draft_responses(request_id):
    """Get draft responses for a request."""
    conn = get_connection()
    query = """
        SELECT question_id, response_value, rating_value
        FROM draft_responses 
        WHERE request_id = ?
    """
    try:
        result = conn.execute(query, (request_id,))
        drafts = {}
        for row in result.fetchall():
            drafts[row[0]] = {
                'response_value': row[1],
                'rating_value': row[2]
            }
        return drafts
    except Exception as e:
        logger.error(f"Error fetching draft responses: {e}")
        return {}

def save_draft_response(request_id, question_id, response_value, rating_value=None):
    """Save draft response for partial completion."""
    conn = get_connection()
    try:
        query = """
            INSERT INTO draft_responses (request_id, question_id, response_value, rating_value)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(request_id, question_id) DO UPDATE SET
            response_value = excluded.response_value,
            rating_value = excluded.rating_value,
            saved_at = CURRENT_TIMESTAMP
        """
        conn.execute(query, (request_id, question_id, response_value, rating_value))
        conn.commit()
        return True
    except Exception as e:
        logger.error(f"Error saving draft: {e}")
        return False

def submit_final_feedback(request_id, responses):
    """Submit completed feedback and move from draft to final."""
    conn = get_connection()
    try:
        # Insert final responses
        for question_id, response_data in responses.items():
            response_val = response_data.get('response_value')
            rating_val = response_data.get('rating_value')
            
            response_query = """
                INSERT INTO feedback_responses (request_id, question_id, response_value, rating_value)
                VALUES (?, ?, ?, ?)
            """
            conn.execute(response_query, (request_id, question_id, response_val, rating_val))
        
        # Update request status
        update_query = """
            UPDATE feedback_requests 
            SET reviewer_status = 'completed', completed_at = CURRENT_TIMESTAMP,
                workflow_state = 'completed'
            WHERE request_id = ?
        """
        conn.execute(update_query, (request_id,))
        
        # Delete draft responses
        delete_query = "DELETE FROM draft_responses WHERE request_id = ?"
        conn.execute(delete_query, (request_id,))
        
        conn.commit()
        
        # Send notification email
        try:
            from services.email_service import send_feedback_submitted_notification
            # Get request details
            details_query = """
                SELECT req_user.first_name || ' ' || req_user.last_name as requester_name,
                       req_user.email as requester_email,
                       rev_user.first_name || ' ' || rev_user.last_name as reviewer_name,
                       cycle.cycle_name
                FROM feedback_requests fr
                JOIN users req_user ON fr.requester_id = req_user.user_type_id
                LEFT JOIN users rev_user ON fr.reviewer_id = rev_user.user_type_id
                LEFT JOIN review_cycles cycle ON fr.cycle_id = cycle.cycle_id
                WHERE fr.request_id = ?
            """
            details_result = conn.execute(details_query, (request_id,))
            details = details_result.fetchone()
            
            if details:
                send_feedback_submitted_notification(
                    requester_email=details[1],
                    requester_name=details[0],
                    reviewer_name=details[2] or "External Reviewer",
                    cycle_name=details[3]
                )
        except Exception as e:
            logger.error(f"Error sending notification email: {e}")
        
        return True, "Feedback submitted successfully"
    except Exception as e:
        logger.error(f"Error submitting feedback: {e}")
        conn.rollback()
        return False, str(e)

def get_anonymized_feedback_for_user(user_id):
    """Get completed feedback received by a user (anonymized - no reviewer names) for the current active cycle only."""
    conn = get_connection()
    query = """
        SELECT fr.request_id, fr.relationship_type, fr.completed_at,
               fq.question_text, fres.response_value, fres.rating_value, fq.question_type
        FROM feedback_requests fr
        JOIN feedback_responses fres ON fr.request_id = fres.request_id
        JOIN feedback_questions fq ON fres.question_id = fq.question_id
        JOIN review_cycles rc ON fr.cycle_id = rc.cycle_id
        WHERE fr.requester_id = ? 
            AND fr.workflow_state = 'completed'
            AND rc.is_active = 1
        ORDER BY fr.request_id, fq.sort_order ASC
    """
    try:
        result = conn.execute(query, (user_id,))
        feedback_groups = {}
        for row in result.fetchall():
            request_id = row[0]
            if request_id not in feedback_groups:
                feedback_groups[request_id] = {
                    'relationship_type': row[1],
                    'completed_at': row[2],
                    'responses': []
                }
            feedback_groups[request_id]['responses'].append({
                'question_text': row[3],
                'response_value': row[4],
                'rating_value': row[5],
                'question_type': row[6]
            })
        return feedback_groups
    except Exception as e:
        logger.error(f"Error fetching anonymized feedback: {e}")
        return {}

def get_feedback_progress_for_user(user_id):
    """Get feedback request progress for a user showing anonymized completion status for the current active cycle only."""
    conn = get_connection()
    query = """
        SELECT 
            COUNT(*) as total_requests,
            COALESCE(SUM(CASE WHEN fr.workflow_state = 'completed' THEN 1 ELSE 0 END), 0) as completed_requests,
            COALESCE(SUM(CASE WHEN fr.approval_status = 'approved' THEN 1 ELSE 0 END), 0) as pending_requests,
            COALESCE(SUM(CASE WHEN fr.approval_status = 'pending' THEN 1 ELSE 0 END), 0) as awaiting_approval
        FROM feedback_requests fr
        JOIN review_cycles rc ON fr.cycle_id = rc.cycle_id
        WHERE fr.requester_id = ? 
            AND fr.approval_status != 'rejected'
            AND rc.is_active = 1
    """
    try:
        result = conn.execute(query, (user_id,))
        progress = result.fetchone()
        if progress:
            return {
                'total_requests': progress[0],
                'completed_requests': progress[1], 
                'pending_requests': progress[2],
                'awaiting_approval': progress[3]
            }
        return {'total_requests': 0, 'completed_requests': 0, 'pending_requests': 0, 'awaiting_approval': 0}
    except Exception as e:
        logger.error(f"Error fetching feedback progress: {e}")
        return {'total_requests': 0, 'completed_requests': 0, 'pending_requests': 0, 'awaiting_approval': 0}

def generate_feedback_excel_data(user_id):
    """Generate Excel-ready data for a user's feedback."""
    feedback_data = get_anonymized_feedback_for_user(user_id)
    
    excel_rows = []
    
    for request_id, feedback in feedback_data.items():
        relationship_type = feedback['relationship_type']
        completed_at = feedback['completed_at']
        
        for response in feedback['responses']:
            excel_rows.append({
                'Review_Number': f"Review_{request_id}",
                'Relationship_Type': relationship_type.replace('_', ' ').title(),
                'Question': response['question_text'],
                'Question_Type': response['question_type'],
                'Rating': response['rating_value'] if response['rating_value'] else '',
                'Text_Response': response['response_value'] if response['response_value'] else '',
                'Completed_Date': completed_at
            })
    
    return excel_rows

# =====================================================
# USER MANAGEMENT AND RELATIONSHIP FUNCTIONS
# =====================================================

def get_direct_reports(manager_email):
    """Return a list of direct reports for a manager email."""
    conn = get_connection()
    try:
        query = """
            SELECT user_type_id, first_name, last_name, email, vertical, designation
            FROM users
            WHERE reporting_manager_email = ? AND is_active = 1
            ORDER BY first_name, last_name
        """
        result = conn.execute(query, (manager_email,))
        rows = result.fetchall()
        return [
            {
                'user_type_id': r[0],
                'name': f"{r[1]} {r[2]}",
                'email': r[3],
                'vertical': r[4],
                'designation': r[5],
            }
            for r in rows
        ]
    except Exception as e:
        logger.error(f"Error fetching direct reports for {manager_email}: {e}")
        return []

def has_direct_reports(user_email):
    """Check if a user has any direct reports."""
    conn = get_connection()
    try:
        query = "SELECT COUNT(*) FROM users WHERE reporting_manager_email = ? AND is_active = 1;"
        result = conn.execute(query, (user_email,))
        count = result.fetchone()[0]
        return count > 0
    except Exception as e:
        logger.error(f"Error checking for direct reports for {user_email}: {e}")
        return False

def get_user_direct_manager(user_id):
    """Get the user's direct manager information."""
    conn = get_connection()
    try:
        query = """
            SELECT m.user_type_id, m.first_name, m.last_name, m.email, m.designation
            FROM users u 
            JOIN users m ON u.reporting_manager_email = m.email 
            WHERE u.user_type_id = ? AND u.is_active = 1 AND m.is_active = 1
        """
        result = conn.execute(query, (user_id,))
        manager = result.fetchone()
        
        if manager:
            return {
                'user_type_id': manager[0],
                'name': f"{manager[1]} {manager[2]}",
                'first_name': manager[1],
                'last_name': manager[2],
                'email': manager[3],
                'designation': manager[4]
            }
        return None
    except Exception as e:
        logger.error(f"Error getting user's direct manager: {e}")
        return None

def determine_relationship_type(requester_id, reviewer_id):
    """
    Automatically determine relationship type based on organizational structure.
    
    Rules:
    1) Same team, neither is manager of other -> peer
    2) Different teams -> internal_collaborator  
    3) Reviewer reports to requester -> direct_reportee
    4) Cannot request feedback from your own manager (should be blocked at UI level)
    """
    conn = get_connection()
    try:
        # Get both users' information
        query = """
            SELECT 
                r.vertical as requester_vertical, r.email as requester_email,
                r.reporting_manager_email as requester_manager_email,
                rv.vertical as reviewer_vertical, rv.reporting_manager_email as reviewer_manager_email,
                rv.email as reviewer_email
            FROM users r, users rv
            WHERE r.user_type_id = ? AND rv.user_type_id = ?
            AND r.is_active = 1 AND rv.is_active = 1
        """
        result = conn.execute(query, (requester_id, reviewer_id))
        data = result.fetchone()
        
        if not data:
            raise ValueError("User data not found")
        
        requester_vertical = data[0]
        requester_email = data[1]
        requester_manager_email = data[2]
        reviewer_vertical = data[3]
        reviewer_manager_email = data[4]
        reviewer_email = data[5]
        
        # Check if reviewer is the requester's manager
        if reviewer_email == requester_manager_email:
            raise ValueError("Cannot request feedback from your direct manager")
        
        # Check if reviewer reports to requester
        if reviewer_manager_email == requester_email:
            return "direct_reportee"
        
        # Check if same team/vertical
        if requester_vertical == reviewer_vertical:
            return "peer"
        else:
            return "internal_collaborator"
            
    except Exception as e:
        logger.error(f"Error determining relationship type: {e}")
        raise ValueError(str(e))

def get_relationship_with_preview(requester_id, reviewer_list):
    """
    Get relationship types for multiple reviewers with automatic mapping.
    Returns list of tuples: (reviewer_identifier, relationship_type)
    
    Args:
        requester_id: ID of the user requesting feedback
        reviewer_list: List of reviewer identifiers (user IDs or emails)
    """
    relationships = []
    for reviewer_identifier in reviewer_list:
        if isinstance(reviewer_identifier, int):
            # Internal reviewer
            try:
                relationship_type = determine_relationship_type(requester_id, reviewer_identifier)
                relationships.append((reviewer_identifier, relationship_type))
            except ValueError as e:
                # Skip invalid relationships (like requesting from direct manager)
                logger.warning(f"Skipping invalid relationship: {e}")
                continue
        else:
            # External reviewer - always external_stakeholder
            relationships.append((reviewer_identifier, "external_stakeholder"))
    
    return relationships

def update_user_details(user_id, first_name, last_name, vertical, designation, reporting_manager_email):
    """Update user details in the database."""
    conn = get_connection()
    query = """
        UPDATE users
        SET first_name = ?,
            last_name = ?,
            vertical = ?,
            designation = ?,
            reporting_manager_email = ?
        WHERE user_type_id = ?
    """
    try:
        conn.execute(query, (first_name, last_name, vertical, designation, reporting_manager_email, user_id))
        conn.commit()
        return True
    except Exception as e:
        logger.error(f"Error updating user details: {e}")
        return False

def get_all_users_by_vertical(vertical):
    """Get all users from a specific vertical."""
    conn = get_connection()
    query = """
        SELECT u.user_type_id, u.first_name, u.last_name, u.vertical, u.designation
        FROM users u
        WHERE u.vertical = ? AND u.is_active = 1
        ORDER BY u.first_name, u.last_name
    """
    try:
        result = conn.execute(query, (vertical,))
        users = []
        for row in result.fetchall():
            users.append({
                "user_type_id": row[0],
                "name": f"{row[1]} {row[2]}",
                "vertical": row[3],
                "designation": row[4],
            })
        return users
    except Exception as e:
        logger.error(f"Error fetching users by vertical: {e}")
        return []

def get_all_users():
    """Get all users for email reminder purposes."""
    conn = get_connection()
    try:
        query = """
            SELECT user_type_id, email, first_name, last_name, designation, vertical, is_active
            FROM users 
            ORDER BY first_name, last_name
        """
        result = conn.execute(query)
        
        users = []
        for row in result.fetchall():
            users.append({
                'user_type_id': row[0],
                'email': row[1],
                'name': f"{row[2]} {row[3]}",
                'first_name': row[2],
                'last_name': row[3],
                'designation': row[4],
                'vertical': row[5],
                'is_active': bool(row[6])
            })
        
        return users
    except Exception as e:
        logger.error(f"Error fetching all users: {e}")
        return []

# =====================================================
# ANALYTICS AND REPORTING FUNCTIONS
# =====================================================

def get_hr_dashboard_metrics():
    """Get comprehensive metrics for HR dashboard."""
    conn = get_connection()
    try:
        metrics = {}
        
        # Total users
        total_users_result = conn.execute("SELECT COUNT(*) FROM users WHERE is_active = 1")
        total_users = total_users_result.fetchone()[0]
        
        # Check if there's an active cycle
        active_cycle_result = conn.execute("SELECT cycle_id FROM review_cycles WHERE is_active = 1")
        active_cycle = active_cycle_result.fetchone()
        
        if active_cycle:
            cycle_id = active_cycle[0]
            
            # Pending feedback requests (only for active cycle)
            pending_result = conn.execute(
                "SELECT COUNT(*) FROM feedback_requests WHERE approval_status = 'approved' AND cycle_id = ?"
                , (cycle_id,))
            pending_requests = pending_result.fetchone()[0]
            
            # Completed feedback this month (only for active cycle)
            completed_result = conn.execute("""
                SELECT COUNT(*) FROM feedback_requests 
                WHERE status = 'completed' AND cycle_id = ? AND DATE(completed_at) >= DATE('now', 'start of month')
            """, (cycle_id,))
            completed_this_month = completed_result.fetchone()[0]
            
            # Users with incomplete reviews (only for active cycle)
            incomplete_result = conn.execute("""
                SELECT COUNT(DISTINCT reviewer_id) FROM feedback_requests 
                WHERE approval_status = 'approved' AND cycle_id = ?
            """, (cycle_id,))
            incomplete_reviews = incomplete_result.fetchone()[0]
            
        else:
            pending_requests = 0
            completed_this_month = 0
            incomplete_reviews = 0
            
        metrics = {
            'total_users': total_users,
            'pending_requests': pending_requests,
            'completed_this_month': completed_this_month,
            'incomplete_reviews': incomplete_reviews
        }
        
        return metrics
    except Exception as e:
        logger.error(f"Error fetching HR dashboard metrics: {e}")
        return {}

def get_users_with_pending_reviews():
    """Get users who have pending reviews to complete."""
    conn = get_connection()
    
    # Check if there's an active cycle
    active_cycle_result = conn.execute("SELECT cycle_id FROM review_cycles WHERE is_active = 1")
    active_cycle = active_cycle_result.fetchone()
    
    if not active_cycle:
        return []  # No active cycle, no pending reviews
    
    cycle_id = active_cycle[0]
    
    query = """
        SELECT u.user_type_id, u.first_name, u.last_name, u.vertical, u.email,
               COUNT(fr.request_id) as pending_count
        FROM users u
        JOIN feedback_requests fr ON u.user_type_id = fr.reviewer_id
        WHERE fr.approval_status = 'approved' AND u.is_active = 1 AND fr.cycle_id = ?
        GROUP BY u.user_type_id, u.first_name, u.last_name, u.vertical, u.email
        ORDER BY pending_count DESC, u.first_name
    """
    try:
        result = conn.execute(query, (cycle_id,))
        users = []
        for row in result.fetchall():
            users.append({
                'user_type_id': row[0],
                'name': f"{row[1]} {row[2]}",
                'vertical': row[3],
                'email': row[4],
                'pending_count': row[5]
            })
        return users
    except Exception as e:
        logger.error(f"Error fetching users with pending reviews: {e}")
        return []

def get_hr_rejections_dashboard():
    """Get all rejections for HR monitoring (manager + reviewer)."""
    conn = get_connection()
    try:
        active_cycle = get_active_review_cycle()
        if not active_cycle:
            return []
        query = """
            SELECT rt.tracking_id, rt.rejection_type, rt.rejected_at,
                   rt.rejection_reason, rt.viewed_by_hr,
                   u1.first_name || ' ' || u1.last_name as requester_name,
                   u1.email as requester_email,
                   COALESCE(u2.first_name || ' ' || u2.last_name, fr.external_reviewer_email) as reviewer_name,
                   u3.first_name || ' ' || u3.last_name as rejected_by_name,
                   fr.relationship_type
            FROM rejection_tracking rt
            JOIN users u1 ON rt.requester_id = u1.user_type_id
            LEFT JOIN users u2 ON rt.rejected_reviewer_id = u2.user_type_id
            LEFT JOIN users u3 ON rt.rejected_by = u3.user_type_id
            JOIN feedback_requests fr ON rt.request_id = fr.request_id
            WHERE rt.cycle_id = ?
            ORDER BY rt.rejected_at DESC
        """
        result = conn.execute(query, (active_cycle["cycle_id"],))
        rejections = []
        for row in result.fetchall():
            rejections.append({
                "tracking_id": row[0],
                "rejection_type": row[1],
                "rejected_at": row[2],
                "rejection_reason": row[3],
                "viewed_by_hr": row[4],
                "requester_name": row[5],
                "requester_email": row[6],
                "reviewer_name": row[7],
                "rejected_by_name": row[8],
                "relationship_type": row[9]
            })
        return rejections
    except Exception as e:
        logger.error(f"Error fetching HR rejections dashboard: {e}")
        return []

def get_users_progress_summary():
    """Get progress summary for all users in the current cycle for HR dashboard."""
    conn = get_connection()
    try:
        active_cycle = get_active_review_cycle()
        if not active_cycle:
            return []
        
        cycle_id = active_cycle['cycle_id']
        
        # Get all users and their progress
        query = """
            SELECT 
                u.user_type_id,
                u.first_name,
                u.last_name,
                u.email,
                u.vertical,
                u.designation,
                COUNT(DISTINCT fr_requested.request_id) as requested_count,
                COUNT(DISTINCT CASE WHEN fr_requested.approval_status = 'approved' 
                                  AND m.user_type_id IS NOT NULL THEN fr_requested.request_id END) as manager_approved_count,
                COUNT(DISTINCT CASE WHEN fr_requested.reviewer_status = 'accepted' THEN fr_requested.request_id END) as respondent_approved_count,
                COUNT(DISTINCT fr_assigned.request_id) as assigned_feedback_count,
                COUNT(DISTINCT CASE WHEN fr_assigned.workflow_state = 'completed' THEN fr_assigned.request_id END) as completed_feedback_count
            FROM users u
            LEFT JOIN feedback_requests fr_requested ON u.user_type_id = fr_requested.requester_id 
                AND fr_requested.cycle_id = ?
            LEFT JOIN users m ON fr_requested.approval_status = 'approved' 
                AND u.reporting_manager_email = m.email
            LEFT JOIN feedback_requests fr_assigned ON u.user_type_id = fr_assigned.reviewer_id 
                AND fr_assigned.cycle_id = ?
            WHERE u.is_active = 1
            GROUP BY u.user_type_id, u.first_name, u.last_name, u.email, u.vertical, u.designation
            ORDER BY u.first_name, u.last_name
        """
        result = conn.execute(query, (cycle_id, cycle_id))
        
        users_progress = []
        for row in result.fetchall():
            users_progress.append({
                'user_type_id': row[0],
                'name': f"{row[1]} {row[2]}",
                'email': row[3],
                'vertical': row[4],
                'designation': row[5],
                'requested_count': row[6],
                'manager_approved_count': row[7],
                'respondent_approved_count': row[8],
                'assigned_feedback_count': row[9],
                'completed_feedback_count': row[10]
            })
        
        return users_progress
    except Exception as e:
        logger.error(f"Error getting users progress summary: {e}")
        return []

def get_reviewer_nomination_counts():
    """Get current nomination counts for all reviewers in the active cycle."""
    conn = get_connection()
    try:
        active_cycle = get_active_review_cycle()
        if not active_cycle:
            return {}
        
        cycle_id = active_cycle['cycle_id']
        
        # Count active nominations (approved, pending approval) for each reviewer
        query = """
            SELECT reviewer_id, COUNT(*) as nomination_count
            FROM feedback_requests 
            WHERE cycle_id = ? AND approval_status IN ('pending', 'approved')
            GROUP BY reviewer_id
        """
        result = conn.execute(query, (cycle_id,))
        
        nomination_counts = {}
        for row in result.fetchall():
            nomination_counts[row[0]] = row[1]
        
        return nomination_counts
    except Exception as e:
        logger.error(f"Error getting reviewer nomination counts: {e}")
        return {}

def is_reviewer_at_limit(reviewer_id):
    """Check if a reviewer has reached the nomination limit of 4."""
    nomination_counts = get_reviewer_nomination_counts()
    return nomination_counts.get(reviewer_id, 0) >= 4

def get_users_for_selection_with_limits(exclude_user_id=None, requester_user_id=None):
    """Get list of users for selection with nomination limit information."""
    # Get base user list
    users = get_users_for_selection(exclude_user_id, requester_user_id)
    
    # Get nomination counts
    nomination_counts = get_reviewer_nomination_counts()
    
    # Add nomination count and limit status to each user
    for user in users:
        user_id = user['user_type_id']
        user['nomination_count'] = nomination_counts.get(user_id, 0)
        user['at_limit'] = user['nomination_count'] >= 4
    
    return users

def get_pending_reviewer_requests(user_id):
    """Get feedback requests where user is the reviewer and needs to accept/reject for the current active cycle only."""
    conn = get_connection()
    try:
        query = """
            SELECT fr.request_id, fr.requester_id, fr.relationship_type, fr.created_at,
                   req.first_name, req.last_name, req.vertical, req.designation,
                   rc.cycle_display_name, rc.nomination_deadline
            FROM feedback_requests fr
            JOIN users req ON fr.requester_id = req.user_type_id
            JOIN review_cycles rc ON fr.cycle_id = rc.cycle_id
            WHERE fr.reviewer_id = ? 
                AND fr.approval_status = 'approved' 
                AND fr.reviewer_status = 'pending_acceptance'
                AND rc.is_active = 1
            ORDER BY fr.created_at ASC
        """
        result = conn.execute(query, (user_id,))
        
        requests = []
        for row in result.fetchall():
            requests.append({
                'request_id': row[0],
                'requester_id': row[1],
                'relationship_type': row[2],
                'created_at': row[3],
                'requester_name': f"{row[4]} {row[5]}",
                'vertical': row[6],
                'designation': row[7],
                'cycle_name': row[8],
                'deadline': row[9]
            })
        
        return requests
    except Exception as e:
        logger.error(f"Error fetching pending reviewer requests: {e}")
        return []

# =====================================================
# EXTERNAL STAKEHOLDER FUNCTIONS
# =====================================================

def generate_external_token():
    """Generate a secure token for external stakeholders."""
    import secrets
    import string
    alphabet = string.ascii_letters + string.digits
    return ''.join(secrets.choice(alphabet) for _ in range(16))

def create_external_stakeholder_token(email, request_id, cycle_id):
    """Create a new token for external stakeholder."""
    conn = get_connection()
    try:
        token = generate_external_token()
        
        # Insert token
        insert_query = """
            INSERT INTO external_stakeholder_tokens (email, token, request_id, cycle_id)
            VALUES (?, ?, ?, ?)
        """
        conn.execute(insert_query, (email, token, request_id, cycle_id))
        
        # Update feedback request with token
        update_query = """
            UPDATE feedback_requests 
            SET external_token = ?, external_status = 'invitation_sent'
            WHERE request_id = ?
        """
        conn.execute(update_query, (token, request_id))
        
        conn.commit()
        return token
    except Exception as e:
        logger.error(f"Error creating external stakeholder token: {e}")
        conn.rollback()
        return None

def validate_external_token(email, token):
    """Validate external stakeholder token and return request info."""
    conn = get_connection()
    try:
        query = """
            SELECT est.request_id, est.cycle_id, est.status, est.token_id,
                   fr.requester_id, req.first_name, req.last_name, req.vertical,
                   fr.relationship_type, rc.cycle_display_name
            FROM external_stakeholder_tokens est
            JOIN feedback_requests fr ON est.request_id = fr.request_id
            JOIN users req ON fr.requester_id = req.user_type_id
            JOIN review_cycles rc ON est.cycle_id = rc.cycle_id
            WHERE est.email = ? AND est.token = ? AND est.is_active = 1
        """
        result = conn.execute(query, (email.lower().strip(), token.strip()))
        token_data = result.fetchone()
        
        if token_data:
            return {
                'request_id': token_data[0],
                'cycle_id': token_data[1],
                'status': token_data[2],
                'token_id': token_data[3],
                'requester_id': token_data[4],
                'requester_name': f"{token_data[5]} {token_data[6]}",
                'requester_vertical': token_data[7],
                'relationship_type': token_data[8],
                'cycle_name': token_data[9]
            }
        return None
    except Exception as e:
        logger.error(f"Error validating external token: {e}")
        return None

def accept_external_stakeholder_request(token_data):
    """Mark external stakeholder request as accepted."""
    conn = get_connection()
    try:
        # Update token status
        conn.execute("""
            UPDATE external_stakeholder_tokens 
            SET status = 'accepted', used_at = CURRENT_TIMESTAMP
            WHERE token_id = ?
        """, (token_data['token_id'],))
        
        # Update request status
        conn.execute("""
            UPDATE feedback_requests 
            SET external_status = 'accepted', reviewer_status = 'accepted',
                reviewer_response_date = CURRENT_TIMESTAMP
            WHERE request_id = ?
        """, (token_data['request_id'],))
        
        conn.commit()
        return True
    except Exception as e:
        logger.error(f"Error accepting external stakeholder request: {e}")
        conn.rollback()
        return False

def reject_external_stakeholder_request(token_data, rejection_reason):
    """Mark external stakeholder request as rejected."""
    conn = get_connection()
    try:
        # Update token status
        conn.execute("""
            UPDATE external_stakeholder_tokens 
            SET status = 'rejected', rejection_reason = ?, used_at = CURRENT_TIMESTAMP
            WHERE token_id = ?
        """, (rejection_reason, token_data['token_id']))
        
        # Update request status
        conn.execute("""
            UPDATE feedback_requests 
            SET external_status = 'rejected', reviewer_status = 'rejected',
                reviewer_rejection_reason = ?, reviewer_response_date = CURRENT_TIMESTAMP
            WHERE request_id = ?
        """, (rejection_reason, token_data['request_id']))
        
        conn.commit()
        return True
    except Exception as e:
        logger.error(f"Error rejecting external stakeholder request: {e}")
        conn.rollback()
        return False

def complete_external_stakeholder_feedback(request_id, responses):
    """Submit completed feedback from external stakeholder."""
    conn = get_connection()
    try:
        # Insert final responses
        for question_id, response_data in responses.items():
            response_value = response_data.get('response_value')
            rating_value = response_data.get('rating_value')
            
            response_query = """
                INSERT INTO feedback_responses (request_id, question_id, response_value, rating_value)
                VALUES (?, ?, ?, ?)
            """
            conn.execute(response_query, (request_id, question_id, response_value, rating_value))
        
        # Update request status
        update_query = """
            UPDATE feedback_requests 
            SET reviewer_status = 'completed', completed_at = CURRENT_TIMESTAMP,
                workflow_state = 'completed', external_status = 'completed'
            WHERE request_id = ?
        """
        conn.execute(update_query, (request_id,))
        
        # Update token status
        token_update = """
            UPDATE external_stakeholder_tokens 
            SET status = 'completed'
            WHERE request_id = ?
        """
        conn.execute(token_update, (request_id,))
        
        conn.commit()
        
        # Send notification email
        try:
            from services.email_service import send_feedback_submitted_notification
            # Get request details
            details_query = """
                SELECT req_user.first_name || ' ' || req_user.last_name as requester_name,
                       req_user.email as requester_email,
                       fr.external_reviewer_email as reviewer_email,
                       cycle.cycle_name
                FROM feedback_requests fr
                JOIN users req_user ON fr.requester_id = req_user.user_type_id
                LEFT JOIN review_cycles cycle ON fr.cycle_id = cycle.cycle_id
                WHERE fr.request_id = ?
            """
            details_result = conn.execute(details_query, (request_id,))
            details = details_result.fetchone()
            
            if details:
                send_feedback_submitted_notification(
                    requester_email=details[1],
                    requester_name=details[0],
                    reviewer_name=details[2] or "External Stakeholder",
                    cycle_name=details[3]
                )
        except Exception as e:
            logger.error(f"Error sending notification email: {e}")
        
        return True, "Feedback submitted successfully"
    except Exception as e:
        logger.error(f"Error completing external stakeholder feedback: {e}")
        conn.rollback()
        return False, str(e)

def get_external_stakeholder_requests_for_email():
    """Get external stakeholder requests that need email invitations."""
    conn = get_connection()
    try:
        query = """
            SELECT fr.request_id, fr.external_reviewer_email, fr.relationship_type,
                   req.first_name, req.last_name, req.email as requester_email,
                   req.vertical, rc.cycle_display_name, rc.cycle_id
            FROM feedback_requests fr
            JOIN users req ON fr.requester_id = req.user_type_id
            JOIN review_cycles rc ON fr.cycle_id = rc.cycle_id
            WHERE fr.external_reviewer_email IS NOT NULL 
              AND fr.external_status = 'pending'
              AND fr.approval_status = 'approved'
              AND rc.is_active = 1
        """
        result = conn.execute(query)
        
        requests = []
        for row in result.fetchall():
            requests.append({
                'request_id': row[0],
                'external_email': row[1],
                'relationship_type': row[2],
                'requester_name': f"{row[3]} {row[4]}",
                'requester_email': row[5],
                'requester_vertical': row[6],
                'cycle_name': row[7],
                'cycle_id': row[8]
            })
        
        return requests
    except Exception as e:
        logger.error(f"Error fetching external stakeholder requests: {e}")
        return []

def process_external_stakeholder_invitations(request_id):
    """Process external stakeholder invitation after manager approval."""
    conn = get_connection()
    try:
        # Get request details including external stakeholder names
        query = """
            SELECT fr.external_reviewer_email, fr.relationship_type, fr.cycle_id,
                   req.first_name, req.last_name, req.vertical,
                   rc.cycle_display_name, fr.external_stakeholder_first_name, fr.external_stakeholder_last_name
            FROM feedback_requests fr
            JOIN users req ON fr.requester_id = req.user_type_id
            JOIN review_cycles rc ON fr.cycle_id = rc.cycle_id
            WHERE fr.request_id = ? AND fr.external_reviewer_email IS NOT NULL
        """
        result = conn.execute(query, (request_id,))
        request_data = result.fetchone()
        
        if not request_data:
            return False, "External request not found"
        
        # Create token for this external stakeholder
        token = create_external_stakeholder_token(
            request_data[0],  # external_reviewer_email
            request_id,
            request_data[2]   # cycle_id
        )
        
        if token:
            # Send invitation email
            try:
                from services.email_service import send_external_stakeholder_invitation
                send_external_stakeholder_invitation(
                    external_email=request_data[0],
                    external_name=f"{request_data[7] or ''} {request_data[8] or ''}".strip() or request_data[0],
                    requester_name=f"{request_data[3]} {request_data[4]}",
                    cycle_name=request_data[6],
                    token=token
                )
                return True, "Invitation sent successfully"
            except Exception as e:
                logger.error(f"Error sending external invitation: {e}")
                return False, f"Failed to send invitation: {str(e)}"
        else:
            return False, "Failed to create external token"
            
    except Exception as e:
        logger.error(f"Error processing external stakeholder invitations: {e}")
        return False, str(e)

# =====================================================
# DEADLINE AND WORKFLOW MANAGEMENT FUNCTIONS
# =====================================================

def _wf_get_display_status(workflow_state: str) -> str:
    """Get display status from workflow state"""
    status_map = {
        "pending_manager_approval": "pending",
        "manager_rejected": "rejected",
        "pending_reviewer_acceptance": "approved",
        "reviewer_rejected": "rejected",
        "in_progress": "approved",
        "completed": "completed",
        "expired": "expired",
    }
    return status_map.get(workflow_state or "", "unknown")

def _wf_should_count(workflow_state: str) -> bool:
    """Check if workflow state should count toward limits"""
    return (workflow_state or "") in {
        "pending_manager_approval",
        "pending_reviewer_acceptance",
        "in_progress",
        "completed",
    }

def is_deadline_passed(deadline_date):
    """Check if a deadline has passed."""
    try:
        if isinstance(deadline_date, str):
            deadline = datetime.strptime(deadline_date, '%Y-%m-%d').date()
        elif isinstance(deadline_date, date):
            deadline = deadline_date
        else:
            return False
        
        return date.today() > deadline
    except Exception as e:
        logger.error(f"Error checking deadline: {e}")
        return False

def extend_user_deadline(cycle_id, user_id, deadline_type, new_deadline, reason, extended_by):
    """Extend deadline for a specific user."""
    conn = get_connection()
    try:
        # Get original deadline from cycle
        cycle_result = conn.execute("SELECT nomination_deadline, feedback_deadline FROM review_cycles WHERE cycle_id = ?", (cycle_id,))
        cycle = cycle_result.fetchone()
        if not cycle:
            return False, "Cycle not found"
        
        original_deadline = cycle[0] if deadline_type == 'nomination' else cycle[1]
        if not original_deadline:
            return False, f"Invalid deadline type: {deadline_type}"
        
        # Insert extension
        insert_query = """
            INSERT INTO user_deadline_extensions 
            (cycle_id, user_id, deadline_type, original_deadline, extended_deadline, reason, extended_by)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """
        conn.execute(insert_query, (cycle_id, user_id, deadline_type, original_deadline, new_deadline, reason, extended_by))
        conn.commit()
        
        return True, "Deadline extended successfully"
    except Exception as e:
        logger.error(f"Error extending user deadline: {e}")
        conn.rollback()
        return False, str(e)

def get_user_deadline(cycle_id, user_id, deadline_type):
    """Get the effective deadline for a user (considering extensions)."""
    conn = get_connection()
    try:
        # Check if user has an extension
        extension_query = """
            SELECT extended_deadline 
            FROM user_deadline_extensions 
            WHERE cycle_id = ? AND user_id = ? AND deadline_type = ?
        """
        result = conn.execute(extension_query, (cycle_id, user_id, deadline_type))
        extension = result.fetchone()
        
        if extension:
            return extension[0]  # Return extended deadline
        
        # Return original deadline from cycle
        cycle_query = """
            SELECT nomination_deadline, feedback_deadline 
            FROM review_cycles 
            WHERE cycle_id = ?
        """
        cycle_result = conn.execute(cycle_query, (cycle_id,))
        cycle = cycle_result.fetchone()
        
        if cycle:
            return cycle[0] if deadline_type == 'nomination' else cycle[1]
        
        return None
    except Exception as e:
        logger.error(f"Error getting user deadline: {e}")
        return None

def get_user_deadline_extensions(cycle_id):
    """Get all deadline extensions for a cycle."""
    conn = get_connection()
    try:
        query = """
            SELECT ude.user_id, ude.deadline_type, ude.original_deadline, ude.extended_deadline,
                   ude.reason, ude.created_at, u.first_name, u.last_name, u.email,
                   extender.first_name as extended_by_first, extender.last_name as extended_by_last
            FROM user_deadline_extensions ude
            JOIN users u ON ude.user_id = u.user_type_id
            JOIN users extender ON ude.extended_by = extender.user_type_id
            WHERE ude.cycle_id = ?
            ORDER BY ude.created_at DESC
        """
        result = conn.execute(query, (cycle_id,))
        
        extensions = []
        for row in result.fetchall():
            extensions.append({
                'user_id': row[0],
                'deadline_type': row[1],
                'original_deadline': row[2],
                'extended_deadline': row[3],
                'reason': row[4],
                'created_at': row[5],
                'user_name': f"{row[6]} {row[7]}",
                'user_email': row[8],
                'extended_by': f"{row[9]} {row[10]}"
            })
        
        return extensions
    except Exception as e:
        logger.error(f"Error getting deadline extensions: {e}")
        return []

def auto_accept_expired_nominations():
    """Auto-accept all pending nominations and approvals when deadline has passed."""
    conn = get_connection()
    try:
        active_cycle = get_active_review_cycle()
        if not active_cycle:
            return False, "No active cycle found"
        
        cycle_id = active_cycle['cycle_id']
        nomination_deadline = active_cycle['nomination_deadline']
        
        # Check if nomination deadline has passed
        if not is_deadline_passed(nomination_deadline):
            return False, "Nomination deadline has not passed yet"
        
        # Auto-approve all pending manager approvals
        manager_approvals = conn.execute("""
            UPDATE feedback_requests 
            SET approval_status = 'approved', workflow_state = 'pending_reviewer_acceptance'
            WHERE cycle_id = ? AND approval_status = 'pending'
        """, (cycle_id,))
        
        # Auto-accept all pending reviewer acceptances
        reviewer_acceptances = conn.execute("""
            UPDATE feedback_requests 
            SET reviewer_status = 'accepted', workflow_state = 'in_progress'
            WHERE cycle_id = ? AND reviewer_status = 'pending_acceptance'
        """, (cycle_id,))
        
        conn.commit()
        
        return True, "Expired nominations auto-accepted successfully"
    except Exception as e:
        logger.error(f"Error auto-accepting expired nominations: {e}")
        conn.rollback()
        return False, str(e)

def check_user_deadline_enforcement(user_id, action_type):
    """Check if user can perform an action based on deadline enforcement.
    
    Args:
        user_id: The user attempting the action
        action_type: 'nomination' or 'feedback'
    
    Returns:
        (can_perform, message)
    """
    try:
        active_cycle = get_active_review_cycle()
        if not active_cycle:
            return False, "No active cycle found"
        
        cycle_id = active_cycle['cycle_id']
        
        # Get effective deadline for this user
        deadline = get_user_deadline(cycle_id, user_id, action_type)
        
        if not deadline:
            return True, ""  # No deadline set, allow action
        
        if is_deadline_passed(deadline):
            return False, f"The {action_type} deadline has passed"
        
        return True, ""
    except Exception as e:
        logger.error(f"Error checking deadline enforcement: {e}")
        return True, ""  # Default to allowing action if error

def ensure_database_schema():
    """Ensure all required tables and columns exist for the feedback system."""
    conn = get_connection()
    try:
        # Create email_logs table if not exists
        conn.execute("""
            CREATE TABLE IF NOT EXISTS email_logs (
                log_id INTEGER PRIMARY KEY AUTOINCREMENT,
                email_type TEXT NOT NULL,
                recipients_count INTEGER DEFAULT 0,
                subject TEXT,
                body TEXT,
                sent_by INTEGER,
                status TEXT DEFAULT 'pending',
                sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (sent_by) REFERENCES users(user_type_id)
            )
        """)
        
        # Create user_deadline_extensions table if not exists
        conn.execute("""
            CREATE TABLE IF NOT EXISTS user_deadline_extensions (
                extension_id INTEGER PRIMARY KEY AUTOINCREMENT,
                cycle_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                deadline_type TEXT NOT NULL,
                original_deadline DATE,
                extended_deadline DATE NOT NULL,
                reason TEXT,
                extended_by INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (cycle_id) REFERENCES review_cycles(cycle_id),
                FOREIGN KEY (user_id) REFERENCES users(user_type_id),
                FOREIGN KEY (extended_by) REFERENCES users(user_type_id)
            )
        """)
        
        conn.commit()
        logger.info("Database schema ensured successfully")
        return True
    except Exception as e:
        logger.error(f"Error ensuring database schema: {e}")
        conn.rollback()
        return False

if __name__ == "__main__":
    # Test the new db_helper functions
    print("Testing new db_helper functions...")
    
    # Test connection
    try:
        conn = get_connection()
        result = conn.execute("SELECT COUNT(*) FROM users")
        user_count = result.fetchone()[0]
        print(f"✅ Found {user_count} users in database")
        
        # Test active cycle
        cycle = get_active_review_cycle()
        if cycle:
            print(f"✅ Active cycle: {cycle['cycle_display_name']}")
        else:
            print("ℹ️ No active cycle found")
            
    except Exception as e:
        print(f"❌ Test failed: {e}")


def get_user_nominated_reviewers(user_id):
    """Get list of reviewer IDs that user has already nominated (including rejected)."""
    with get_connection() as conn:
        try:
            active_cycle = get_active_review_cycle()
            if not active_cycle:
                return []
            
            cycle_id = active_cycle['cycle_id']
            
            # Get all nominated reviewers (both internal and external)
            query = """
                SELECT reviewer_id, external_reviewer_email
                FROM feedback_requests
                WHERE requester_id = ? AND cycle_id = ?
            """
            result = conn.execute(query, (user_id, cycle_id))
            
            nominated_reviewers = []
            for row in result.fetchall():
                if row[0]:  # Internal reviewer
                    nominated_reviewers.append(row[0])
                elif row[1]:  # External reviewer
                    nominated_reviewers.append(row[1])
            
            return nominated_reviewers
        except Exception as e:
            logger.error(f"Error getting nominated reviewers: {e}")
            return []


def create_feedback_request_fixed(requester_id, reviewer_data):
    """Create feedback requests (internal & external) pending manager approval and email manager."""
    with get_connection() as conn:
        try:
            active_cycle = get_active_review_cycle()
            if not active_cycle:
                return False, "No active review cycle found"
            cycle_id = active_cycle["cycle_id"]
            
            # Current status to enforce limit
            current_status = get_user_nominations_status(requester_id)
            if current_status["total_count"] + len(reviewer_data) > 4:
                return False, f"Cannot nominate {len(reviewer_data)} more reviewers. You have {current_status['remaining_slots']} slots remaining."
            
            # Prevent nominating direct manager
            direct_manager = get_user_direct_manager(requester_id)
            manager_id = direct_manager["user_type_id"] if direct_manager else None
            manager_email = (direct_manager.get("email") if direct_manager else "") or ""
            
            # Insert rows
            for reviewer_id, relationship_type in reviewer_data:
                if isinstance(reviewer_id, int):
                    if reviewer_id == manager_id:
                        return False, f"Note: Your Direct manager ({direct_manager['name']}) should not be nominated — their feedback is shared through ongoing discussions and review touchpoints like check-ins or H1 assessments."
                    conn.execute(
                        """
                        INSERT INTO feedback_requests
                        (cycle_id, requester_id, reviewer_id, relationship_type,
                         workflow_state, approval_status, reviewer_status,
                         counts_toward_limit, is_active)
                        VALUES (?, ?, ?, ?, 'pending_manager_approval', 'pending', 'pending_acceptance', 1, 1)
                        """,
                        (cycle_id, requester_id, reviewer_id, relationship_type),
                    )
                else:
                    # External stakeholder data (email + names) or just email (legacy)
                    if isinstance(reviewer_id, dict):
                        # New format with names
                        external_email = reviewer_id['email']
                        external_first_name = reviewer_id['first_name']
                        external_last_name = reviewer_id['last_name']
                    else:
                        # Legacy format (just email)
                        external_email = reviewer_id
                        external_first_name = None
                        external_last_name = None
                    
                    # Guard against nominating manager email
                    if external_email.strip().lower() == manager_email.strip().lower():
                        return False, f"You cannot nominate your direct manager ({external_email}) as an external stakeholder."
                    
                    conn.execute(
                        """
                        INSERT INTO feedback_requests
                        (cycle_id, requester_id, external_reviewer_email, external_stakeholder_first_name, 
                         external_stakeholder_last_name, relationship_type, workflow_state, approval_status, 
                         reviewer_status, counts_toward_limit, is_active)
                        VALUES (?, ?, ?, ?, ?, ?, 'pending_manager_approval', 'pending', 'pending_acceptance', 1, 1)
                        """,
                        (cycle_id, requester_id, external_email, external_first_name, external_last_name, relationship_type),
                    )
            
            conn.commit()
            return True, "Feedback requests created successfully"
            
        except Exception as e:
            logger.error(f"Error creating feedback requests: {e}")
            return False, f"Error creating feedback requests: {e}"


def get_reviewer_rejections_for_hr():
    """Get all reviewer rejections for HR review."""
    with get_connection() as conn:
        try:
            query = """
                SELECT fr.request_id, fr.reviewer_rejection_reason, fr.reviewer_response_date,
                       req.first_name as requester_first, req.last_name as requester_last,
                       req.email as requester_email, req.vertical as requester_vertical,
                       rev.first_name as reviewer_first, rev.last_name as reviewer_last,
                       rev.email as reviewer_email, rev.vertical as reviewer_vertical,
                       fr.relationship_type, rc.cycle_display_name
                FROM feedback_requests fr
                JOIN users req ON fr.requester_id = req.user_type_id
                JOIN users rev ON fr.reviewer_id = rev.user_type_id
                JOIN review_cycles rc ON fr.cycle_id = rc.cycle_id
                WHERE fr.reviewer_status = 'rejected'
                ORDER BY fr.reviewer_response_date DESC
            """
            result = conn.execute(query)
            
            rejections = []
            for row in result.fetchall():
                rejections.append({
                    'request_id': row[0],
                    'rejection_reason': row[1],
                    'rejection_date': row[2],
                    'requester_name': f"{row[3]} {row[4]}",
                    'requester_email': row[5],
                    'requester_vertical': row[6],
                    'reviewer_name': f"{row[7]} {row[8]}",
                    'reviewer_email': row[9],
                    'reviewer_vertical': row[10],
                    'relationship_type': row[11],
                    'cycle_name': row[12]
                })
            
            return rejections
        except Exception as e:
            logger.error(f"Error fetching reviewer rejections: {e}")
            return []


def get_user_cycle_history(user_id):
    """Get a user's participation history across cycles."""
    with get_connection() as conn:
        query = """
            SELECT DISTINCT rc.cycle_id, rc.cycle_display_name, rc.cycle_year, rc.cycle_quarter,
                   COUNT(DISTINCT fr_as_requester.request_id) as requested_reviews,
                   COUNT(DISTINCT fr_as_reviewer.request_id) as completed_reviews,
                   rc.created_at
            FROM review_cycles rc
            LEFT JOIN feedback_requests fr_as_requester ON rc.cycle_id = fr_as_requester.cycle_id 
                AND fr_as_requester.requester_id = ?
            LEFT JOIN feedback_requests fr_as_reviewer ON rc.cycle_id = fr_as_reviewer.cycle_id 
                AND fr_as_reviewer.reviewer_id = ? AND fr_as_reviewer.status = 'completed'
            WHERE (fr_as_requester.request_id IS NOT NULL OR fr_as_reviewer.request_id IS NOT NULL)
            GROUP BY rc.cycle_id, rc.cycle_display_name, rc.cycle_year, rc.cycle_quarter, rc.created_at
            ORDER BY rc.created_at DESC
        """
        try:
            result = conn.execute(query, (user_id, user_id))
            history = []
            for row in result.fetchall():
                history.append({
                    'cycle_id': row[0],
                    'display_name': row[1],
                    'year': row[2],
                    'quarter': row[3],
                    'requested_reviews': row[4],
                    'completed_reviews': row[5],
                    'created_at': row[6]
                })
            return history
        except Exception as e:
            logger.error(f"Error getting user cycle history: {e}")
            return []


def create_new_review_cycle(cycle_name, nomination_start, nomination_deadline, feedback_deadline, created_by):
    """Create a new review cycle (HR function) - Updated to remove approval and results deadlines."""
    with get_connection() as conn:
        try:
            # Create new cycle first
            insert_query = """
                INSERT INTO review_cycles 
                (cycle_name, nomination_start_date, nomination_deadline, feedback_deadline, is_active, created_by)
                VALUES (?, ?, ?, ?, 1, ?)
            """
            result = conn.execute(insert_query, (
                cycle_name, nomination_start, nomination_deadline, feedback_deadline, created_by
            ))
            
            new_cycle_id = result.lastrowid
            
            # Only deactivate other cycles after successfully creating the new one
            deactivate_query = "UPDATE review_cycles SET is_active = 0 WHERE cycle_id != ?"
            conn.execute(deactivate_query, (new_cycle_id,))
            
            conn.commit()
            logger.info(f"Successfully created new cycle with ID {new_cycle_id} and deactivated others")
            return True
        except Exception as e:
            logger.error(f"Error creating review cycle: {e}")
            return False


def handle_reviewer_response(request_id, reviewer_id, action, rejection_reason=None):
    """
    Handle reviewer response - wrapper for reviewer_accept_reject_request for compatibility
    """
    return reviewer_accept_reject_request(request_id, reviewer_id, action, rejection_reason)