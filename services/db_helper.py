import libsql_experimental as libsql
import streamlit as st
from datetime import datetime, date, timedelta
import logging

logger = logging.getLogger(__name__)

db_url = st.secrets["DB_URL"]
auth_token = st.secrets["AUTH_TOKEN"]

if not db_url or not auth_token:
    raise Exception("Database URL or Auth Token is missing. Check your .streamlit/secrets.toml file.")

_connection = None

def get_connection():
    global _connection
    try:
        if _connection is None:
            _connection = libsql.connect(database=db_url, auth_token=auth_token)
            logger.debug("Established a new database connection.")
        else:
            try:
                _connection.execute("SELECT 1;")
                logger.debug("Connection is healthy.")
            except Exception as conn_error:
                if "STREAM_EXPIRED" in str(conn_error):
                    logger.warning("Connection stream expired. Reinitializing connection.")
                    _connection = libsql.connect(database=db_url, auth_token=auth_token)
                else:
                    raise conn_error
    except Exception as e:
        logger.error(f"Error establishing connection: {e}")
        _connection = libsql.connect(database=db_url, auth_token=auth_token)
    return _connection

def fetch_user_by_email(email):
    """Fetch user by email for authentication."""
    conn = get_connection()
    query = "SELECT * FROM users WHERE email = ? AND is_active = 1;"
    try:
        result = conn.execute(query, (email,))
        user = result.fetchone()
        if user:
            return {
                "user_type_id": user[0],
                "email": user[1],
                "first_name": user[2],
                "last_name": user[3],
                "vertical": user[4],
                "designation": user[5],
                "reporting_manager_email": user[6],
                "password_hash": user[7]
            }
        return None
    except Exception as e:
        print(f"Error fetching user: {e}")
        return None

def fetch_user_roles(user_type_id):
    """Fetch roles for a specific user."""
    conn = get_connection()
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
        print(f"Error fetching user roles: {e}")
        return []

def set_user_password(email, password_hash):
    """Set password for first-time login."""
    conn = get_connection()
    query = "UPDATE users SET password_hash = ? WHERE email = ?"
    try:
        conn.execute(query, (password_hash, email))
        conn.commit()
        return True
    except Exception as e:
        print(f"Error setting password: {e}")
        return False

def get_users_for_selection(exclude_user_id=None, requester_user_id=None):
    """Get list of all active users eligible to give feedback (reviewers)."""
    conn = get_connection()
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
    
    try:
        result = conn.execute(query, tuple(params))
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
        print(f"Error fetching users: {e}")
        return []

def _parse_iso_date(value):
    if not value:
        return None
    if isinstance(value, (date, datetime)):
        return value.date() if isinstance(value, datetime) else value
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except Exception:
        return None

def can_user_request_feedback(user_id):
    """Determine if a user is eligible to request/receive feedback based on date_of_joining.

    Rules:
    - Joined on/before 2025-09-30: eligible to request
    - Else, require at least 3 months tenure to be invited only (not to request)
    - If date is missing, do not block (return True)
    """
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT date_of_joining FROM users WHERE user_type_id = ?",
            (user_id,),
        ).fetchone()
        if not row:
            return True
        doj = _parse_iso_date(row[0])
        if not doj:
            return True
        cutoff = date(2025, 9, 30)
        if doj <= cutoff:
            return True
        # Joined after cutoff: can be invited as reviewer (handled elsewhere), but cannot request
        return False
    except Exception as e:
        print(f"Error checking request eligibility: {e}")
        return True

# NOTE: The real ensure_database_schema is defined later in the file.

def get_manager_level_from_designation(designation):
    """Get numeric manager level from designation text."""
    if not designation:
        return 0
    
    designation_lower = designation.lower()
    
    if 'founder' in designation_lower:
        return 5
    elif 'associate director' in designation_lower:
        return 4  
    elif 'director' in designation_lower:
        return 3
    elif 'manager' in designation_lower or 'sr. manager' in designation_lower:
        return 2
    elif 'lead' in designation_lower:
        return 1
    else:
        return 0

def check_external_stakeholder_permission(user_id):
    """Check if user has manager level or above to request external stakeholder feedback."""
    conn = get_connection()
    query = "SELECT designation FROM users WHERE user_type_id = ?"
    try:
        result = conn.execute(query, (user_id,))
        user = result.fetchone()
        if user:
            manager_level = get_manager_level_from_designation(user[0])
            return manager_level >= 2
        return False
    except Exception as e:
        print(f"Error checking external stakeholder permission: {e}")
        return False

def get_active_review_cycle():
    """Get the currently active review cycle with enhanced metadata."""
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
                'cycle_display_name': cycle[2] or cycle[1],  # Fallback to cycle_name if no display name
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
        print(f"Error fetching active cycle: {e}")
        return None

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
        existing_rows = conn.execute(existing_query, (requester_id, cycle_id))
        for reviewer_id, external_email in existing_rows.fetchall():
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
                name_rows = conn.execute(name_query, tuple(duplicate_internal_ids)).fetchall()
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
                cursor = conn.execute(request_query, (cycle_id, requester_id, reviewer_identifier, relationship_type))
                
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
                cursor = conn.execute(request_query, (cycle_id, requester_id, reviewer_identifier, relationship_type))
                request_id = cursor.lastrowid
                
                # Store for later processing after approval
                external_requests.append({
                    'request_id': request_id,
                    'email': reviewer_identifier,
                    'relationship_type': relationship_type
                })
        
        conn.commit()

        # Informational log retained for debugging
        print(
            f"Created requests successfully. {len(external_requests)} external stakeholders will be processed after manager approval."
        )

        return True, "Requests submitted for manager approval"
        
    except Exception as e:
        print(f"Error creating feedback requests: {e}")
        conn.rollback()
        return False, str(e)

def create_feedback_requests_with_approval_OLD(requester_id, reviewer_data):
    """OLD VERSION - Create feedback requests that require manager approval."""
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
        
        # Create requests for each reviewer
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
                # External reviewer (email address)
                request_query = """
                    INSERT INTO feedback_requests 
                    (cycle_id, requester_id, external_reviewer_email, relationship_type, status, approval_status) 
                    VALUES (?, ?, ?, ?, 'pending_approval', 'pending')
                """
                conn.execute(request_query, (cycle_id, requester_id, reviewer_identifier, relationship_type))
        
        conn.commit()
        return True, "Requests submitted for manager approval"
    except Exception as e:
        print(f"Error creating feedback requests: {e}")
        conn.rollback()
        return False, str(e)

def get_pending_approvals_for_manager(manager_id):
    """Get feedback requests pending approval for a manager."""
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
        WHERE mgr.user_type_id = ? AND fr.approval_status = 'pending'
        ORDER BY fr.created_at ASC
    """
    try:
        result = conn.execute(query, (manager_id,))
        return result.fetchall()
    except Exception as e:
        print(f"Error fetching pending approvals: {e}")
        return []

 

def approve_reject_feedback_request_OLD(request_id, manager_id, action, rejection_reason=None):
    """OLD VERSION - Approve or reject a feedback request."""
    conn = get_connection()
    try:
        if action == 'approve':
            update_query = """
                UPDATE feedback_requests 
                SET approval_status = 'approved', status = 'approved', 
                    approved_by = ?, approval_date = CURRENT_TIMESTAMP
                WHERE request_id = ?
            """
            conn.execute(update_query, (manager_id, request_id))
                
        elif action == 'reject':
            update_query = """
                UPDATE feedback_requests 
                SET approval_status = 'rejected', status = 'rejected',
                    approved_by = ?, approval_date = CURRENT_TIMESTAMP,
                    rejection_reason = ?
                WHERE request_id = ?
            """
            conn.execute(update_query, (manager_id, rejection_reason, request_id))
            
            # Add to rejected nominations
            request_details = conn.execute(
                "SELECT requester_id, reviewer_id FROM feedback_requests WHERE request_id = ?", 
                (request_id,)
            ).fetchone()
            if request_details:
                reject_query = """
                    INSERT INTO rejected_nominations 
                    (requester_id, rejected_reviewer_id, rejected_by, rejection_reason)
                    VALUES (?, ?, ?, ?)
                """
                conn.execute(reject_query, (
                    request_details[0], request_details[1], manager_id, rejection_reason
                ))
        
        conn.commit()
        return True
    except Exception as e:
        print(f"Error processing approval/rejection: {e}")
        conn.rollback()
        return False

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
        print(f"Error fetching pending reviews: {e}")
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
        print(f"Error fetching questions: {e}")
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
        print(f"Error fetching draft responses: {e}")
        return {}

def save_draft_response(request_id, question_id, response_value, rating_value=None):
    """Save draft response for partial completion."""
    conn = get_connection()
    query = """
        INSERT INTO draft_responses (request_id, question_id, response_value, rating_value)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(request_id, question_id) DO UPDATE SET
        response_value = excluded.response_value,
        rating_value = excluded.rating_value,
        saved_at = CURRENT_TIMESTAMP
    """
    try:
        conn.execute(query, (request_id, question_id, response_value, rating_value))
        conn.commit()
        return True
    except Exception as e:
        print(f"Error saving draft: {e}")
        return False

def submit_final_feedback(request_id, responses):
    """Submit completed feedback and move from draft to final."""
    from services.email_service import send_feedback_submitted_notification
    
    conn = get_connection()
    try:
        # Insert final responses
        for question_id, response_data in responses.items():
            response_query = """
                INSERT INTO feedback_responses (request_id, question_id, response_value, rating_value)
                VALUES (?, ?, ?, ?)
            """
            conn.execute(response_query, (
                request_id, 
                question_id, 
                response_data.get('response_value'), 
                response_data.get('rating_value')
            ))
        
        # Update request status
        update_query = """
            UPDATE feedback_requests 
            SET status = 'completed', completed_at = CURRENT_TIMESTAMP
            WHERE request_id = ?
        """
        conn.execute(update_query, (request_id,))
        
        # Clear draft responses
        clear_draft_query = "DELETE FROM draft_responses WHERE request_id = ?"
        conn.execute(clear_draft_query, (request_id,))
        
        conn.commit()
        
        # Send feedback completion notification
        try:
            # Get request details for notification
            notification_query = """
                SELECT u_req.email as requester_email,
                       u_req.first_name || ' ' || u_req.last_name as requester_name,
                       u_rev.first_name || ' ' || u_rev.last_name as reviewer_name,
                       c.cycle_name
                FROM feedback_requests fr
                JOIN users u_req ON fr.requester_id = u_req.user_type_id
                JOIN users u_rev ON fr.reviewer_id = u_rev.user_type_id
                LEFT JOIN review_cycles c ON fr.cycle_id = c.cycle_id
                WHERE fr.request_id = ?
            """
            result = conn.execute(notification_query, (request_id,))
            details = result.fetchone()
            
            if details:
                send_feedback_submitted_notification(
                    requester_email=details[0],
                    requester_name=details[1],
                    reviewer_name=details[2],
                    cycle_name=details[3] or "Current Cycle",
                    is_external=False
                )
                
        except Exception as e:
            print(f"Warning: Failed to send feedback completion notification: {e}")
            # Don't fail the submission if email fails
        
        return True
    except Exception as e:
        print(f"Error submitting feedback: {e}")
        conn.rollback()
        return False

def get_anonymized_feedback_for_user(user_id):
    """Get completed feedback received by a user (anonymized - no reviewer names)."""
    conn = get_connection()
    query = """
        SELECT fr.request_id, fr.relationship_type, fr.completed_at,
               fq.question_text, fres.response_value, fres.rating_value, fq.question_type
        FROM feedback_requests fr
        JOIN feedback_responses fres ON fr.request_id = fres.request_id
        JOIN feedback_questions fq ON fres.question_id = fq.question_id
        WHERE fr.requester_id = ? AND fr.status = 'completed'
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
        print(f"Error fetching anonymized feedback: {e}")
        return {}

def get_feedback_progress_for_user(user_id):
    """Get feedback request progress for a user showing anonymized completion status."""
    conn = get_connection()
    query = """
        SELECT 
            COUNT(*) as total_requests,
            COALESCE(SUM(CASE WHEN fr.status = 'completed' THEN 1 ELSE 0 END), 0) as completed_requests,
            COALESCE(SUM(CASE WHEN fr.status = 'approved' THEN 1 ELSE 0 END), 0) as pending_requests,
            COALESCE(SUM(CASE WHEN fr.approval_status = 'pending' THEN 1 ELSE 0 END), 0) as awaiting_approval
        FROM feedback_requests fr
        WHERE fr.requester_id = ? AND fr.status != 'rejected'
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
        print(f"Error fetching feedback progress: {e}")
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

def create_new_review_cycle(cycle_name, nomination_start, nomination_deadline, feedback_deadline, created_by):
    """Create a new review cycle (HR function) - Updated to remove approval and results deadlines."""
    conn = get_connection()
    try:
        # Create new cycle first
        insert_query = """
            INSERT INTO review_cycles 
            (cycle_name, nomination_start_date, nomination_deadline, feedback_deadline, is_active, created_by)
            VALUES (?, ?, ?, ?, 1, ?)
        """
        cursor = conn.execute(insert_query, (
            cycle_name, nomination_start, nomination_deadline, feedback_deadline, created_by
        ))
        
        new_cycle_id = cursor.lastrowid
        
        # Only deactivate other cycles after successfully creating the new one
        deactivate_query = "UPDATE review_cycles SET is_active = 0 WHERE cycle_id != ?"
        conn.execute(deactivate_query, (new_cycle_id,))
        
        conn.commit()
        print(f"Successfully created new cycle with ID {new_cycle_id} and deactivated others")
        return True
    except Exception as e:
        print(f"Error creating review cycle: {e}")
        conn.rollback()
        return False

def get_current_cycle_phase():
    """Determine which phase of the review cycle we're currently in."""
    from datetime import date, datetime
    
    cycle = get_active_review_cycle()
    if not cycle:
        return "No active cycle"
    
    today = date.today()
    
    # Convert string dates to date objects for comparison
    try:
        nomination_deadline = datetime.strptime(cycle['nomination_deadline'], '%Y-%m-%d').date()
        feedback_deadline = datetime.strptime(cycle['feedback_deadline'], '%Y-%m-%d').date()
    except (ValueError, TypeError):
        # If dates are already date objects or invalid, return default
        return "Nomination Phase"
    
    if today <= nomination_deadline:
        return "Nomination Phase"
    elif today <= feedback_deadline:
        return "Feedback Collection Phase"
    else:
        return "Cycle Complete"

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
        print(f"Error updating user details: {e}")
        return False

def update_cycle_deadlines(cycle_id, nomination_deadline, feedback_deadline):
    """Update deadlines for an existing cycle - Updated to remove approval and results deadlines."""
    conn = get_connection()
    try:
        update_query = """
            UPDATE review_cycles 
            SET nomination_deadline = ?, 
                feedback_deadline = ?
            WHERE cycle_id = ? AND is_active = 1
        """
        result = conn.execute(update_query, (
            nomination_deadline, feedback_deadline, cycle_id
        ))
        
        if result.rowcount > 0:
            print(f"Cycle deadlines updated successfully for cycle {cycle_id}")
            return True
        else:
            print(f"No active cycle found with ID {cycle_id}")
            return False
            
    except Exception as e:
        print(f"Error updating cycle deadlines: {e}")
        conn.rollback()
        return False

def mark_cycle_complete(cycle_id, completion_notes=""):
    """Mark a cycle as complete and deactivate it."""
    conn = get_connection()
    try:
        # First check if the cycle exists and is active
        check_query = "SELECT cycle_id, cycle_name, is_active FROM review_cycles WHERE cycle_id = ?"
        result = conn.execute(check_query, (cycle_id,))
        cycle_info = result.fetchone()
        
        if not cycle_info:
            print(f"No cycle found with ID {cycle_id}")
            return False, f"No cycle found with ID {cycle_id}"
        
        if cycle_info[2] == 0:  # is_active is 0
            print(f"Cycle {cycle_id} is already inactive")
            return False, f"Cycle '{cycle_info[1]}' is already inactive"
        
        # Update cycle to completed status - use only guaranteed existing columns
        complete_query = """
            UPDATE review_cycles 
            SET is_active = 0, 
                phase_status = 'completed',
                status = 'completed'
            WHERE cycle_id = ? AND is_active = 1
        """
        result = conn.execute(complete_query, (cycle_id,))
        conn.commit()
        
        if result.rowcount > 0:
            print(f"Cycle {cycle_id} marked as complete")
            return True, f"Cycle '{cycle_info[1]}' marked as complete successfully"
        # If rowcount is 0 here, it means the cycle was active but the update failed for some other reason.
        # The earlier check for cycle_info[2] == 0 already covers the "already inactive" case.
        # So, if we reach here with rowcount 0, it's a genuine failure.
        return False, f"Failed to update cycle '{cycle_info[1]}' for an unknown reason."
            
    except Exception as e:
        print(f"Error marking cycle complete: {e}")
        conn.rollback()
        return False, f"Database error: {str(e)}"

def get_hr_dashboard_metrics():
    """Get comprehensive metrics for HR dashboard."""
    conn = get_connection()
    try:
        metrics = {}
        
        # Total users
        total_users = conn.execute("SELECT COUNT(*) FROM users WHERE is_active = 1").fetchone()[0]
        
        # Check if there's an active cycle
        active_cycle = conn.execute("SELECT cycle_id FROM review_cycles WHERE is_active = 1").fetchone()
        
        if active_cycle:
            cycle_id = active_cycle[0]
            
            # Pending feedback requests (only for active cycle)
            pending_requests = conn.execute(
                "SELECT COUNT(*) FROM feedback_requests WHERE status = 'approved' AND cycle_id = ?"
                , (cycle_id,)).fetchone()[0]
            
            # Completed feedback this month (only for active cycle)
            completed_this_month = conn.execute("""
                SELECT COUNT(*) FROM feedback_requests 
                WHERE status = 'completed' AND cycle_id = ? AND DATE(completed_at) >= DATE('now', 'start of month')
            """, (cycle_id,)).fetchone()[0]
            
            # Users with incomplete reviews (only for active cycle)
            incomplete_reviews = conn.execute("""
                SELECT COUNT(DISTINCT reviewer_id) FROM feedback_requests 
                WHERE status = 'approved' AND cycle_id = ?
            """, (cycle_id,)).fetchone()[0]
        else:
            # No active cycle - all metrics should be 0
            pending_requests = 0
            completed_this_month = 0
            incomplete_reviews = 0
        
        metrics.update({
            'total_users': total_users,
            'pending_requests': pending_requests,
            'completed_this_month': completed_this_month,
            'users_with_incomplete': incomplete_reviews
        })
        
        return metrics
    except Exception as e:
        print(f"Error fetching HR metrics: {e}")
        return {}

def get_users_with_pending_reviews():
    """Get users who have pending reviews to complete."""
    conn = get_connection()
    
    # Check if there's an active cycle
    active_cycle = conn.execute("SELECT cycle_id FROM review_cycles WHERE is_active = 1").fetchone()
    
    if not active_cycle:
        return []  # No active cycle, no pending reviews
    
    cycle_id = active_cycle[0]
    
    query = """
        SELECT u.user_type_id, u.first_name, u.last_name, u.vertical, u.email,
               COUNT(fr.request_id) as pending_count
        FROM users u
        JOIN feedback_requests fr ON u.user_type_id = fr.reviewer_id
        WHERE fr.status = 'approved' AND u.is_active = 1 AND fr.cycle_id = ?
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
        print(f"Error fetching users with pending reviews: {e}")
        return []

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
        print(f"Error fetching users by vertical: {e}")
        return []


# Enhanced Multi-Cycle Management Functions

def create_named_cycle(display_name, description, year, quarter, cycle_name, nomination_start, nomination_deadline, feedback_deadline, created_by):
    """Create a new review cycle with enhanced naming and metadata - Updated to remove approval and results deadlines."""
    conn = get_connection()
    try:
        # Create new cycle with enhanced fields first
        insert_query = """
            INSERT INTO review_cycles 
            (cycle_name, cycle_display_name, cycle_description, cycle_year, cycle_quarter,
             nomination_start_date, nomination_deadline, feedback_deadline, phase_status, is_active, created_by)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'nomination', 1, ?)
        """
        cursor = conn.execute(insert_query, (
            cycle_name, display_name, description, year, quarter,
            nomination_start, nomination_deadline, feedback_deadline, created_by
        ))
        
        # Some libsql builds always return 0 for cursor.lastrowid.
        # Re-query the just inserted row (cycle_name is UNIQUE) to get the real ID.
        cycle_row = conn.execute(
            """
            SELECT cycle_id 
            FROM review_cycles 
            WHERE cycle_name = ?
            ORDER BY cycle_id DESC
            LIMIT 1
            """,
            (cycle_name,)
        ).fetchone()
        
        if not cycle_row:
            conn.rollback()
            return False, "Unable to retrieve newly created cycle ID"
        
        cycle_id = cycle_row[0]
        
        # Create cycle phases - simplified to just nomination and feedback
        phases = [
            ('nomination', nomination_start, nomination_deadline),
            ('feedback', nomination_deadline, feedback_deadline)
        ]
        
        for i, (phase_name, start_date, end_date) in enumerate(phases):
            is_current = (i == 0)  # First phase is current
            conn.execute("""
                INSERT INTO cycle_phases (cycle_id, phase_name, start_date, end_date, is_current_phase)
                VALUES (?, ?, ?, ?, ?)
            """, (cycle_id, phase_name, start_date, end_date, is_current))
        
        # Only deactivate other cycles after successfully creating the new one
        deactivate_query = "UPDATE review_cycles SET is_active = 0 WHERE cycle_id != ?"
        conn.execute(deactivate_query, (cycle_id,))
        
        conn.commit()
        print(f"Successfully created named cycle with ID {cycle_id} and deactivated others")
        return True, cycle_id
    except Exception as e:
        print(f"Error creating named cycle: {e}")
        conn.rollback()
        return False, str(e)

def get_all_cycles():
    """Get all review cycles with enhanced metadata, ordered by most recent first."""
    conn = get_connection()
    query = """
        SELECT cycle_id, cycle_name, cycle_display_name, cycle_description, 
               cycle_year, cycle_quarter, phase_status, is_active,
               nomination_start_date, nomination_deadline, feedback_deadline, created_at, status
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
                'created_at': row[11],
                'status': row[12]
            })
        return cycles
    except Exception as e:
        print(f"Error fetching all cycles: {e}")
        return []

def get_cycle_by_id(cycle_id):
    """Get a specific cycle by ID with all metadata."""
    conn = get_connection()
    query = """
        SELECT cycle_id, cycle_name, cycle_display_name, cycle_description, 
               cycle_year, cycle_quarter, phase_status, is_active,
               nomination_start_date, nomination_deadline, feedback_deadline, created_at
        FROM review_cycles 
        WHERE cycle_id = ?
    """
    try:
        result = conn.execute(query, (cycle_id,))
        row = result.fetchone()
        if row:
            return {
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
            }
        return None
    except Exception as e:
        print(f"Error fetching cycle by ID: {e}")
        return None

def get_current_cycle_context():
    """Get detailed current cycle context for smart messaging."""
    conn = get_connection()
    try:
        # Get active cycle
        active_cycle = get_active_review_cycle()
        
        # Get recent cycles for context
        recent_cycles = conn.execute("""
            SELECT cycle_id, cycle_display_name, cycle_year, cycle_quarter, created_at
            FROM review_cycles 
            ORDER BY created_at DESC LIMIT 3
        """).fetchall()
        
        # Get total participation stats
        if active_cycle:
            total_users = conn.execute("SELECT COUNT(*) FROM users WHERE is_active = 1").fetchone()[0]
            participating_users = conn.execute("""
                SELECT COUNT(DISTINCT requester_id) FROM feedback_requests 
                WHERE cycle_id = (SELECT cycle_id FROM review_cycles WHERE is_active = 1)
            """).fetchone()[0]
        else:
            total_users = participating_users = 0
        
        return {
            'active_cycle': active_cycle,
            'recent_cycles': [{'cycle_id': r[0], 'display_name': r[1], 'year': r[2], 'quarter': r[3], 'created_at': r[4]} for r in recent_cycles],
            'participation_stats': {
                'total_users': total_users,
                'participating_users': participating_users,
                'participation_rate': (participating_users / total_users * 100) if total_users > 0 else 0
            }
        }
    except Exception as e:
        print(f"Error getting cycle context: {e}")
        return {'active_cycle': None, 'recent_cycles': [], 'participation_stats': {}}

def get_user_cycle_history(user_id):
    """Get a user's participation history across cycles."""
    conn = get_connection()
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
        print(f"Error fetching user cycle history: {e}")
        return []

def get_feedback_by_cycle(user_id, cycle_id=None):
    """Get user's feedback results filtered by cycle."""
    conn = get_connection()
    if cycle_id:
        cycle_filter = "AND fr.cycle_id = ?"
        params = [user_id, cycle_id]
    else:
        cycle_filter = ""
        params = [user_id]
    
    query = f"""
        SELECT fr.request_id, fr.reviewer_id, fr.relationship_type, fr.status,
               fr.submitted_at, fr.cycle_id, rc.cycle_display_name,
               u.first_name, u.last_name
        FROM feedback_requests fr
        JOIN users u ON fr.reviewer_id = u.user_type_id
        LEFT JOIN review_cycles rc ON fr.cycle_id = rc.cycle_id
        WHERE fr.requester_id = ? AND fr.status = 'completed' {cycle_filter}
        ORDER BY fr.submitted_at DESC
    """
    
    try:
        result = conn.execute(query, params)
        feedback_list = []
        for row in result.fetchall():
            feedback_list.append({
                'request_id': row[0],
                'reviewer_id': row[1],
                'relationship_type': row[2],
                'status': row[3],
                'submitted_at': row[4],
                'cycle_id': row[5],
                'cycle_name': row[6],
                'reviewer_name': f"{row[7]} {row[8]}"
            })
        return feedback_list
    except Exception as e:
        print(f"Error fetching feedback by cycle: {e}")
        return []

def update_cycle_status(cycle_id, new_status):
    """Update the status of a specific review cycle."""
    conn = get_connection()
    try:
        update_query = "UPDATE review_cycles SET status = ? WHERE cycle_id = ?"
        conn.execute(update_query, (new_status, cycle_id))
        conn.commit()
        print(f"Cycle {cycle_id} status updated to '{new_status}'.")
        return True
    except Exception as e:
        print(f"Error updating cycle status: {e}")
        conn.rollback()
        return False

def archive_cycle(cycle_id):
    """Archive a completed cycle."""
    conn = get_connection()
    try:
        conn.execute("""
            UPDATE review_cycles 
            SET is_active = 0, phase_status = 'completed'
            WHERE cycle_id = ?
        """, (cycle_id,))
        
        # Update all phases to mark as completed
        conn.execute("""
            UPDATE cycle_phases 
            SET is_current_phase = 0
            WHERE cycle_id = ?
        """, (cycle_id,))
        
        conn.commit()
        return True
    except Exception as e:
        print(f"Error archiving cycle: {e}")
        return False


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
                "status": _wf_get_display_status(row[4]),
                "reviewer_identifier": reviewer_identifier,
            }

            if row[4] in ("manager_rejected", "reviewer_rejected"):
                rejected_nominations.append(data)
            else:
                active_nominations.append(data)

        limit_count = sum(1 for nom in active_nominations if _wf_should_count(nom["workflow_state"]))
        return {
            "existing_nominations": active_nominations,
            "rejected_nominations": rejected_nominations,
            "total_count": limit_count,
            "can_nominate_more": limit_count < 4,
            "remaining_slots": max(0, 4 - limit_count),
        }

    except Exception as e:
        print(f"Error getting user nominations status: {e}")
        return {
            "existing_nominations": [],
            "rejected_nominations": [],
            "total_count": 0,
            "can_nominate_more": True,
            "remaining_slots": 4,
        }

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
            query = """
                UPDATE feedback_requests
                SET reviewer_status='rejected',
                    workflow_state='reviewer_rejected',
                    reviewer_rejection_reason=?,
                    reviewer_response_date=CURRENT_TIMESTAMP,
                    counts_toward_limit=0
                WHERE request_id = ? AND (reviewer_id = ? OR external_reviewer_email = ?)
            """
            conn.execute(query, (rejection_reason or "", request_id, reviewer_id, reviewer_id))
        conn.commit()
        return True, f"Request {action}ed successfully"
    except Exception as e:
        print(f"Error processing reviewer response: {e}")
        conn.rollback()
        return False, f"Error processing reviewer response: {e}"

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
        return [
            {
                "tracking_id": row[0],
                "rejection_type": row[1],
                "rejected_at": row[2],
                "rejection_reason": row[3],
                "viewed_by_hr": row[4],
                "requester_name": row[5],
                "requester_email": row[6],
                "reviewer_name": row[7],
                "rejected_by_name": row[8],
                "relationship_type": row[9],
            }
            for row in result.fetchall()
        ]
    except Exception as e:
        print(f"Error getting HR rejection dashboard: {e}")
        return []

def create_feedback_request_fixed(requester_id, reviewer_data):
    """Create feedback requests (internal & external) pending manager approval and email manager."""
    from services.email_service import send_manager_approval_request
    conn = get_connection()
    try:
        active_cycle = get_active_review_cycle()
        if not active_cycle:
            return False, "No active review cycle found"
        cycle_id = active_cycle["cycle_id"]

        # current status to enforce limit
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
                # External email; also guard against nominating manager email
                if reviewer_id.strip().lower() == manager_email.strip().lower():
                    return False, f"You cannot nominate your direct manager ({reviewer_id}) as an external stakeholder."
                conn.execute(
                    """
                    INSERT INTO feedback_requests
                    (cycle_id, requester_id, external_reviewer_email, relationship_type,
                     workflow_state, approval_status, reviewer_status,
                     counts_toward_limit, is_active)
                    VALUES (?, ?, ?, ?, 'pending_manager_approval', 'pending', 'pending_acceptance', 1, 1)
                    """,
                    (cycle_id, requester_id, reviewer_id, relationship_type),
                )

        conn.commit()

        # Email manager with summary
        try:
            mgr_row = conn.execute(
                """
                SELECT m.email, m.first_name, m.last_name
                FROM users u JOIN users m ON u.reporting_manager_email = m.email
                WHERE u.user_type_id = ?
                """,
                (requester_id,),
            ).fetchone()
            req_row = conn.execute(
                "SELECT first_name, last_name FROM users WHERE user_type_id = ?",
                (requester_id,),
            ).fetchone()
            if mgr_row and req_row:
                manager_email_send = mgr_row[0]
                manager_name = f"{mgr_row[1]} {mgr_row[2]}"
                requester_name = f"{req_row[0]} {req_row[1]}"
                nominees = []
                for reviewer_id, relationship_type in reviewer_data:
                    if isinstance(reviewer_id, int):
                        nm = conn.execute(
                            "SELECT first_name, last_name FROM users WHERE user_type_id = ?",
                            (reviewer_id,),
                        ).fetchone()
                        if nm:
                            nominees.append({"reviewer_name": f"{nm[0]} {nm[1]}", "relationship_type": relationship_type})
                    else:
                        nominees.append({"reviewer_name": reviewer_id, "relationship_type": relationship_type})
                send_manager_approval_request(manager_email_send, manager_name, requester_name, nominees, active_cycle["cycle_name"])
        except Exception as e:
            print(f"Warning: Failed to send manager approval email: {e}")

        return True, "Feedback requests created successfully"
    except Exception as e:
        print(f"Error creating feedback requests: {e}")
        conn.rollback()
        return False, f"Error creating feedback requests: {e}"

def approve_reject_feedback_request(request_id, manager_id, action, rejection_reason=None):
    """Manager approval/rejection with external invitation processing."""
    from services.email_service import send_nomination_rejected, send_nominee_invite
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
            # If external, process token+invite via existing pipeline
            try:
                from services.db_helper import process_external_stakeholder_invitations
                process_external_stakeholder_invitations(request_id)
            except Exception:
                pass
        elif action == "reject":
            conn.execute(
                """
                UPDATE feedback_requests
                SET approval_status='rejected', workflow_state='manager_rejected',
                    approved_by=?, approval_date=CURRENT_TIMESTAMP, counts_toward_limit=0,
                    rejection_reason=?
                WHERE request_id = ?
                """,
                (manager_id, rejection_reason or "", request_id),
            )
        conn.commit()
        return True
    except Exception as e:
        print(f"Error processing approval/rejection: {e}")
        conn.rollback()
        return False

# Helpers (scoped here to avoid import cycle)
def _wf_get_display_status(workflow_state: str) -> str:
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
    return (workflow_state or "") in {
        "pending_manager_approval",
        "pending_reviewer_acceptance",
        "in_progress",
        "completed",
    }

def get_user_nominated_reviewers(user_id):
    """Get list of reviewer IDs that user has already nominated (including rejected)."""
    conn = get_connection()
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
        print(f"Error getting nominated reviewers: {e}")
        return []

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
        print(f"Error getting user's direct manager: {e}")
        return None

def has_direct_reports(user_email):
    """Check if a user has any direct reports."""
    conn = get_connection()
    try:
        query = "SELECT COUNT(*) FROM users WHERE reporting_manager_email = ? AND is_active = 1;"
        result = conn.execute(query, (user_email,)).fetchone()
        return result[0] > 0
    except Exception as e:
        print(f"Error checking for direct reports for {user_email}: {e}")
        return False

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
        rows = conn.execute(query, (manager_email,)).fetchall()
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
        print(f"Error fetching direct reports for {manager_email}: {e}")
        return []

def create_user_deadline_extension_table():
    """Create the user deadline extensions table if it doesn't exist."""
    conn = get_connection()
    try:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS user_deadline_extensions (
                extension_id INTEGER PRIMARY KEY AUTOINCREMENT,
                cycle_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                deadline_type TEXT NOT NULL CHECK (deadline_type IN ('nomination', 'feedback')),
                original_deadline DATE NOT NULL,
                extended_deadline DATE NOT NULL,
                reason TEXT,
                extended_by INTEGER NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (cycle_id) REFERENCES review_cycles(cycle_id),
                FOREIGN KEY (user_id) REFERENCES users(user_type_id),
                FOREIGN KEY (extended_by) REFERENCES users(user_type_id),
                UNIQUE(cycle_id, user_id, deadline_type)
            )
        """)
        conn.commit()
        return True
    except Exception as e:
        print(f"Error creating user deadline extensions table: {e}")
        return False

def extend_user_deadline(cycle_id, user_id, deadline_type, new_deadline, reason, extended_by):
    """Extend deadline for a specific user."""
    conn = get_connection()
    try:
        # First ensure the table exists
        create_user_deadline_extension_table()
        
        # Get original deadline from cycle
        cycle = get_cycle_by_id(cycle_id)
        if not cycle:
            return False, "Cycle not found"
        
        original_deadline = cycle.get(f'{deadline_type}_deadline')
        if not original_deadline:
            return False, f"Invalid deadline type: {deadline_type}"
        
        # Insert or update extension
        query = """
            INSERT INTO user_deadline_extensions 
            (cycle_id, user_id, deadline_type, original_deadline, extended_deadline, reason, extended_by)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(cycle_id, user_id, deadline_type) DO UPDATE SET
            extended_deadline = excluded.extended_deadline,
            reason = excluded.reason,
            extended_by = excluded.extended_by,
            created_at = CURRENT_TIMESTAMP
        """
        
        conn.execute(query, (cycle_id, user_id, deadline_type, original_deadline, new_deadline, reason, extended_by))
        conn.commit()
        return True, "Deadline extended successfully"
        
    except Exception as e:
        print(f"Error extending user deadline: {e}")
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
        result = conn.execute(extension_query, (cycle_id, user_id, deadline_type)).fetchone()
        
        if result:
            return result[0]  # Return extended deadline
        
        # Return original deadline from cycle
        cycle = get_cycle_by_id(cycle_id)
        if cycle:
            return cycle.get(f'{deadline_type}_deadline')
        
        return None
    except Exception as e:
        print(f"Error getting user deadline: {e}")
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
        print(f"Error getting deadline extensions: {e}")
        return []

def is_deadline_passed(deadline_date):
    """Check if a deadline has passed."""
    from datetime import datetime, date
    
    try:
        if isinstance(deadline_date, str):
            deadline = datetime.strptime(deadline_date, '%Y-%m-%d').date()
        elif isinstance(deadline_date, date):
            deadline = deadline_date
        else:
            return False
        
        return date.today() > deadline
    except Exception as e:
        print(f"Error checking deadline: {e}")
        return False

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
        manager_approval_query = """
            UPDATE feedback_requests 
            SET approval_status = 'approved', 
                status = 'approved',
                approval_date = CURRENT_TIMESTAMP,
                approved_by = -1
            WHERE cycle_id = ? AND approval_status = 'pending'
        """
        manager_result = conn.execute(manager_approval_query, (cycle_id,))
        manager_auto_approved = manager_result.rowcount
        
        # Auto-accept all pending reviewer responses
        reviewer_acceptance_query = """
            UPDATE feedback_requests 
            SET reviewer_status = 'accepted',
                reviewer_response_date = CURRENT_TIMESTAMP
            WHERE cycle_id = ? AND approval_status = 'approved' AND reviewer_status IS NULL
        """
        reviewer_result = conn.execute(reviewer_acceptance_query, (cycle_id,))
        reviewer_auto_accepted = reviewer_result.rowcount
        
        conn.commit()
        
        message = f"Auto-accepted {manager_auto_approved} manager approvals and {reviewer_auto_accepted} reviewer acceptances due to passed nomination deadline"
        print(message)
        return True, message
        
    except Exception as e:
        print(f"Error in auto-acceptance: {e}")
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
        
        # Get user's effective deadline (considering extensions)
        user_deadline = get_user_deadline(cycle_id, user_id, action_type)
        
        if not user_deadline:
            return False, f"No {action_type} deadline found"
        
        if is_deadline_passed(user_deadline):
            return False, f"The {action_type} deadline has passed for you"
        
        return True, f"{action_type.title()} deadline has not passed"
        
    except Exception as e:
        print(f"Error checking deadline enforcement: {e}")
        return False, str(e)

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
                COUNT(DISTINCT CASE WHEN fr_assigned.status = 'completed' THEN fr_assigned.request_id END) as completed_feedback_count
            FROM users u
            LEFT JOIN feedback_requests fr_requested ON u.user_type_id = fr_requested.requester_id 
                AND fr_requested.cycle_id = ?
            LEFT JOIN users m ON fr_requested.approval_status = 'approved' 
                AND u.reporting_manager_email = m.email
            LEFT JOIN feedback_requests fr_assigned ON u.user_type_id = fr_assigned.reviewer_id 
                AND fr_assigned.cycle_id = ? 
                AND fr_assigned.reviewer_status = 'accepted'
            WHERE u.is_active = 1
            GROUP BY u.user_type_id, u.first_name, u.last_name, u.email, u.vertical, u.designation
            ORDER BY u.first_name, u.last_name
        """
        
        result = conn.execute(query, (cycle_id, cycle_id))
        users_progress = []
        
        for row in result.fetchall():
            user_data = {
                'user_id': row[0],
                'name': f"{row[1]} {row[2]}",
                'email': row[3],
                'vertical': row[4] or 'N/A',
                'designation': row[5] or 'N/A',
                'nomination_progress': {
                    'requested': row[6],
                    'manager_approved': row[7],
                    'respondent_approved': row[8],
                    'is_complete': row[8] >= 4  # 4 or more approved respondents
                },
                'feedback_progress': {
                    'assigned': row[9],
                    'completed': row[10],
                    'is_complete': row[9] > 0 and row[9] == row[10]  # All assigned feedback completed
                }
            }
            users_progress.append(user_data)
        
        return users_progress
        
    except Exception as e:
        print(f"Error getting users progress summary: {e}")
        return []

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
            # Default fallback if users not found
            return "peer"
        
        requester_vertical = data[0]
        requester_email = data[1] 
        requester_manager_email = data[2]
        reviewer_vertical = data[3]
        reviewer_manager_email = data[4]
        reviewer_email = data[5]
        
        # Safety check: Don't allow requesting feedback from your own manager
        if (requester_manager_email and reviewer_email and 
            requester_manager_email.lower() == reviewer_email.lower()):
            raise ValueError("Cannot request feedback from your direct manager")
        
        # Rule 3: Check if reviewer reports to requester (direct reportee)
        if reviewer_manager_email and reviewer_manager_email.lower() == requester_email.lower():
            return "direct_reportee"
        
        # Rule 1: Same team/vertical and not manager relationship -> peer
        if requester_vertical and reviewer_vertical and requester_vertical == reviewer_vertical:
            return "peer"
        
        # Rule 2: Different teams -> internal_collaborator
        return "internal_collaborator"
        
    except Exception as e:
        print(f"Error determining relationship type: {e}")
        # Default fallback
        return "peer"

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
                print(f"Skipping invalid relationship: {e}")
                continue
        else:
            # External reviewer - always external_stakeholder
            relationships.append((reviewer_identifier, "external_stakeholder"))
    
    return relationships

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
        print(f"Error getting reviewer nomination counts: {e}")
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
    """Get feedback requests where user is the reviewer and needs to accept/reject."""
    conn = get_connection()
    try:
        query = """
            SELECT fr.request_id, fr.requester_id, fr.relationship_type, fr.created_at,
                   req.first_name, req.last_name, req.vertical, req.designation,
                   rc.cycle_display_name, rc.nomination_deadline
            FROM feedback_requests fr
            JOIN users req ON fr.requester_id = req.user_type_id
            JOIN review_cycles rc ON fr.cycle_id = rc.cycle_id
            WHERE fr.reviewer_id = ? AND fr.approval_status = 'approved' AND fr.reviewer_status IS NULL
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
                'requester_vertical': row[6],
                'requester_designation': row[7],
                'cycle_name': row[8],
                'nomination_deadline': row[9]
            })
        
        return requests
    except Exception as e:
        print(f"Error fetching pending reviewer requests: {e}")
        return []

def handle_reviewer_response(request_id, reviewer_id, action, rejection_reason=None):
    """Handle reviewer acceptance or rejection of feedback request - FIXED VERSION."""
    return reviewer_accept_reject_request(request_id, reviewer_id, action, rejection_reason)

def handle_reviewer_response_OLD(request_id, reviewer_id, action, rejection_reason=None):
    """OLD VERSION - Handle reviewer acceptance or rejection of feedback request."""
    conn = get_connection()
    try:
        if action == 'accept':
            # Update request to accepted by reviewer
            update_query = """
                UPDATE feedback_requests 
                SET reviewer_status = 'accepted', reviewer_response_date = CURRENT_TIMESTAMP
                WHERE request_id = ? AND reviewer_id = ?
            """
            conn.execute(update_query, (request_id, reviewer_id))
        
        elif action == 'reject':
            if not rejection_reason or not rejection_reason.strip():
                return False, "Rejection reason is required"
            
            # Update request to rejected by reviewer
            update_query = """
                UPDATE feedback_requests 
                SET reviewer_status = 'rejected', reviewer_response_date = CURRENT_TIMESTAMP,
                    reviewer_rejection_reason = ?
                WHERE request_id = ? AND reviewer_id = ?
            """
            conn.execute(update_query, (rejection_reason.strip(), request_id, reviewer_id))
            
            # Update nomination count (reduce by 1 since reviewer rejected)
            count_update_query = """
                UPDATE reviewer_nominations 
                SET nomination_count = GREATEST(0, nomination_count - 1),
                    last_updated = CURRENT_TIMESTAMP
                WHERE reviewer_id = ?
            """
            conn.execute(count_update_query, (reviewer_id,))
        
        conn.commit()
        return True, "Response recorded successfully"
    
    except Exception as e:
        print(f"Error handling reviewer response: {e}")
        conn.rollback()
        return False, str(e)

def ensure_database_schema():
    """Ensure all required tables and columns exist for the feedback system."""
    conn = get_connection()
    try:
        # Check and add email_logs table
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
        
        # Check if reviewer_status column exists in feedback_requests
        try:
            conn.execute("SELECT reviewer_status FROM feedback_requests LIMIT 1")
        except:
            # Add reviewer_status and related columns
            conn.execute("ALTER TABLE feedback_requests ADD COLUMN reviewer_status TEXT")
            conn.execute("ALTER TABLE feedback_requests ADD COLUMN reviewer_response_date TIMESTAMP")
            conn.execute("ALTER TABLE feedback_requests ADD COLUMN reviewer_rejection_reason TEXT")

        # Add date_of_joining to users if missing
        try:
            conn.execute("SELECT date_of_joining FROM users LIMIT 1")
        except Exception:
            try:
                conn.execute("ALTER TABLE users ADD COLUMN date_of_joining DATE NULL")
                print("Added date_of_joining column to users")
            except Exception as e:
                print(f"Could not add date_of_joining column: {e}")

        # Add external stakeholder columns if not exists
        try:
            conn.execute("SELECT external_token FROM feedback_requests LIMIT 1")
        except:
            conn.execute("ALTER TABLE feedback_requests ADD COLUMN external_token TEXT")
            conn.execute("ALTER TABLE feedback_requests ADD COLUMN external_status TEXT DEFAULT 'pending'")
        
        # Create external stakeholder tokens table
        conn.execute("""
            CREATE TABLE IF NOT EXISTS external_stakeholder_tokens (
                token_id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT NOT NULL,
                token TEXT UNIQUE NOT NULL,
                request_id INTEGER NOT NULL,
                cycle_id INTEGER NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                used_at TIMESTAMP NULL,
                is_active BOOLEAN DEFAULT 1,
                status TEXT DEFAULT 'pending' CHECK (status IN ('pending', 'accepted', 'rejected', 'completed')),
                rejection_reason TEXT NULL,
                FOREIGN KEY (request_id) REFERENCES feedback_requests(request_id),
                FOREIGN KEY (cycle_id) REFERENCES review_cycles(cycle_id),
                UNIQUE(email, request_id)
            )
        """)
        
        conn.commit()
        print("Database schema updated successfully")
        return True
    except Exception as e:
        print(f"Error updating database schema: {e}")
        return False

def get_reviewer_rejections_for_hr():
    """Get all reviewer rejections for HR review."""
    conn = get_connection()
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
        print(f"Error fetching reviewer rejections: {e}")
        return []

# External Stakeholder Functions

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
        print(f"Error creating external stakeholder token: {e}")
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
                'cycle_name': token_data[9],
                'email': email
            }
        return None
        
    except Exception as e:
        print(f"Error validating external token: {e}")
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
        print(f"Error accepting external request: {e}")
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
        print(f"Error rejecting external request: {e}")
        conn.rollback()
        return False

def complete_external_stakeholder_feedback(request_id, responses):
    """Submit completed feedback from external stakeholder."""
    from services.email_service import send_feedback_submitted_notification
    
    conn = get_connection()
    try:
        # Insert final responses
        for question_id, response_data in responses.items():
            response_query = """
                INSERT INTO feedback_responses (request_id, question_id, response_value, rating_value)
                VALUES (?, ?, ?, ?)
            """
            conn.execute(response_query, (
                request_id, 
                question_id, 
                response_data.get('response_value'), 
                response_data.get('rating_value')
            ))
        
        # Update request status
        update_query = """
            UPDATE feedback_requests 
            SET status = 'completed', completed_at = CURRENT_TIMESTAMP
            WHERE request_id = ?
        """
        conn.execute(update_query, (request_id,))
        
        # Update token status
        conn.execute("""
            UPDATE external_stakeholder_tokens 
            SET status = 'completed'
            WHERE request_id = ?
        """, (request_id,))
        
        conn.commit()
        
        # Send feedback completion notification
        try:
            # Get request details for notification
            notification_query = """
                SELECT fr.external_reviewer_email, u.email as requester_email,
                       u.first_name || ' ' || u.last_name as requester_name,
                       c.cycle_name
                FROM feedback_requests fr
                JOIN users u ON fr.requester_id = u.user_type_id
                LEFT JOIN review_cycles c ON fr.cycle_id = c.cycle_id
                WHERE fr.request_id = ?
            """
            result = conn.execute(notification_query, (request_id,))
            details = result.fetchone()
            
            if details:
                send_feedback_submitted_notification(
                    requester_email=details[1],
                    requester_name=details[2],
                    reviewer_name=details[0],  # External email as reviewer name
                    cycle_name=details[3] or "Current Cycle",
                    is_external=True
                )
                
        except Exception as e:
            print(f"Warning: Failed to send feedback completion notification: {e}")
            # Don't fail the submission if email fails
        
        return True
        
    except Exception as e:
        print(f"Error submitting external feedback: {e}")
        conn.rollback()
        return False

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
        print(f"Error getting external requests for email: {e}")
        return []

def process_external_stakeholder_invitations(request_id):
    """Process external stakeholder invitation after manager approval."""
    from services.email_service import send_external_stakeholder_invitation
    
    conn = get_connection()
    try:
        # Get request details
        query = """
            SELECT fr.external_reviewer_email, fr.relationship_type, fr.cycle_id,
                   req.first_name, req.last_name, req.vertical,
                   rc.cycle_display_name
            FROM feedback_requests fr
            JOIN users req ON fr.requester_id = req.user_type_id
            JOIN review_cycles rc ON fr.cycle_id = rc.cycle_id
            WHERE fr.request_id = ? AND fr.external_reviewer_email IS NOT NULL
        """
        result = conn.execute(query, (request_id,))
        request_data = result.fetchone()
        
        if not request_data:
            return False, "External request not found"
        
        external_email, relationship_type, cycle_id, req_first, req_last, req_vertical, cycle_name = request_data
        requester_name = f"{req_first} {req_last}"
        
        # Generate token
        token = create_external_stakeholder_token(external_email, request_id, cycle_id)
        if not token:
            return False, "Failed to create authentication token"
        
        # Send email invitation
        email_sent = send_external_stakeholder_invitation(
            external_email, requester_name, req_vertical, cycle_name, token
        )
        
        if email_sent:
            # Update status to invitation_sent
            conn.execute("""
                UPDATE feedback_requests 
                SET external_status = 'invitation_sent' 
                WHERE request_id = ?
            """, (request_id,))
            conn.commit()
            return True, "Invitation sent successfully"
        else:
            return False, "Failed to send email invitation"
        
    except Exception as e:
        print(f"Error processing external invitation: {e}")
        return False, str(e)

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
        print(f"Error getting all users: {e}")
        return []
