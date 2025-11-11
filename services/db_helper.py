import libsql_experimental as libsql
import streamlit as st
from datetime import datetime

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
            print("Established a new database connection.")
        else:
            try:
                _connection.execute("SELECT 1;")
                print("Connection is healthy.")
            except Exception as conn_error:
                if "STREAM_EXPIRED" in str(conn_error):
                    print("Connection stream expired. Reinitializing connection.")
                    _connection = libsql.connect(database=db_url, auth_token=auth_token)
                else:
                    raise conn_error
    except Exception as e:
        print(f"Error establishing connection: {e}")
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
    """Get list of all active users for reviewer selection (simplified version)."""
    conn = get_connection()
    query = """
        SELECT user_type_id, first_name, last_name, vertical, designation, email
        FROM users 
        WHERE is_active = 1
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
               approval_deadline, feedback_deadline, results_deadline, created_at
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
                'approval_deadline': cycle[9],
                'feedback_deadline': cycle[10],
                'results_deadline': cycle[11],
                'created_at': cycle[12]
            }
        return None
    except Exception as e:
        print(f"Error fetching active cycle: {e}")
        return None

def create_feedback_requests_with_approval(requester_id, reviewer_data):
    """Create feedback requests that require manager approval."""
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
        SELECT fr.request_id, fr.requester_id, fr.reviewer_id, fr.relationship_type,
               req.first_name as requester_name, req.last_name as requester_surname,
               rev.first_name as reviewer_name, rev.last_name as reviewer_surname,
               rev.vertical, rev.designation, fr.created_at
        FROM feedback_requests fr
        JOIN users req ON fr.requester_id = req.user_type_id
        JOIN users rev ON fr.reviewer_id = rev.user_type_id
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

def approve_reject_feedback_request(request_id, manager_id, action, rejection_reason=None):
    """Approve or reject a feedback request."""
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

def create_new_review_cycle(cycle_name, nomination_start, nomination_deadline, approval_deadline, feedback_deadline, results_deadline, created_by):
    """Create a new review cycle (HR function)."""
    conn = get_connection()
    try:
        # Create new cycle first
        insert_query = """
            INSERT INTO review_cycles 
            (cycle_name, nomination_start_date, nomination_deadline, approval_deadline, 
             feedback_deadline, results_deadline, is_active, created_by)
            VALUES (?, ?, ?, ?, ?, ?, 1, ?)
        """
        cursor = conn.execute(insert_query, (
            cycle_name, nomination_start, nomination_deadline, approval_deadline,
            feedback_deadline, results_deadline, created_by
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
        approval_deadline = datetime.strptime(cycle['approval_deadline'], '%Y-%m-%d').date()
        feedback_deadline = datetime.strptime(cycle['feedback_deadline'], '%Y-%m-%d').date()
        results_deadline = datetime.strptime(cycle['results_deadline'], '%Y-%m-%d').date()
    except (ValueError, TypeError):
        # If dates are already date objects or invalid, return default
        return "Nomination Phase"
    
    if today <= nomination_deadline:
        return "Nomination Phase"
    elif today <= approval_deadline:
        return "Manager Approval Phase"
    elif today <= feedback_deadline:
        return "Feedback Collection Phase"
    elif today <= results_deadline:
        return "Results Processing Phase"
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

def update_cycle_deadlines(cycle_id, nomination_deadline, approval_deadline, feedback_deadline, results_deadline):
    """Update deadlines for an existing cycle."""
    conn = get_connection()
    try:
        update_query = """
            UPDATE review_cycles 
            SET nomination_deadline = ?, 
                approval_deadline = ?, 
                feedback_deadline = ?, 
                results_deadline = ?
            WHERE cycle_id = ? AND is_active = 1
        """
        result = conn.execute(update_query, (
            nomination_deadline, approval_deadline, feedback_deadline, 
            results_deadline, cycle_id
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

def create_named_cycle(display_name, description, year, quarter, cycle_name, nomination_start, nomination_deadline, approval_deadline, feedback_deadline, results_deadline, created_by):
    """Create a new review cycle with enhanced naming and metadata."""
    conn = get_connection()
    try:
        # Create new cycle with enhanced fields first
        insert_query = """
            INSERT INTO review_cycles 
            (cycle_name, cycle_display_name, cycle_description, cycle_year, cycle_quarter,
             nomination_start_date, nomination_deadline, approval_deadline, 
             feedback_deadline, results_deadline, phase_status, is_active, created_by)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'nomination', 1, ?)
        """
        cursor = conn.execute(insert_query, (
            cycle_name, display_name, description, year, quarter,
            nomination_start, nomination_deadline, approval_deadline,
            feedback_deadline, results_deadline, created_by
        ))
        
        cycle_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        
        # Create cycle phases
        phases = [
            ('nomination', nomination_start, nomination_deadline),
            ('approval', nomination_deadline, approval_deadline),
            ('feedback', approval_deadline, feedback_deadline),
            ('review', feedback_deadline, results_deadline)
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
        return False, None

def get_all_cycles():
    """Get all review cycles with enhanced metadata, ordered by most recent first."""
    conn = get_connection()
    query = """
        SELECT cycle_id, cycle_name, cycle_display_name, cycle_description, 
               cycle_year, cycle_quarter, phase_status, is_active,
               nomination_start_date, nomination_deadline, approval_deadline, 
               feedback_deadline, results_deadline, created_at, status
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
                'approval_deadline': row[10],
                'feedback_deadline': row[11],
                'results_deadline': row[12],
                'created_at': row[13],
                'status': row[14]
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
               nomination_start_date, nomination_deadline, approval_deadline, 
               feedback_deadline, results_deadline, created_at
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
                'approval_deadline': row[10],
                'feedback_deadline': row[11],
                'results_deadline': row[12],
                'created_at': row[13]
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
    """Get current user's nomination status and existing nominations."""
    conn = get_connection()
    try:
        # Get active cycle
        active_cycle = get_active_review_cycle()
        if not active_cycle:
            return {'existing_nominations': [], 'rejected_nominations': [], 'total_count': 0, 'can_nominate_more': False}
        
        cycle_id = active_cycle['cycle_id']
        
        # Get existing nominations for this cycle (including rejected ones)
        query = """
            SELECT fr.request_id, fr.reviewer_id, fr.external_reviewer_email, 
                   fr.relationship_type, fr.status, fr.approval_status, fr.created_at,
                   fr.rejection_reason, u.first_name, u.last_name, u.designation, u.vertical
            FROM feedback_requests fr
            LEFT JOIN users u ON fr.reviewer_id = u.user_type_id
            WHERE fr.requester_id = ? AND fr.cycle_id = ?
            ORDER BY fr.created_at ASC
        """
        result = conn.execute(query, (user_id, cycle_id))
        
        nominations = []
        rejected_nominations = []
        
        for row in result.fetchall():
            if row[2]:  # External reviewer
                reviewer_name = row[2]  # Email address
                designation = "External Stakeholder"
                vertical = "External"
                reviewer_identifier = row[2]  # Email for external
            else:  # Internal reviewer
                reviewer_name = f"{row[8]} {row[9]}" if row[8] else "Unknown"
                designation = row[10] or "Unknown"
                vertical = row[11] or "Unknown"
                reviewer_identifier = row[1]  # User ID for internal
            
            nomination_data = {
                'request_id': row[0],
                'reviewer_id': row[1],
                'external_email': row[2],
                'reviewer_name': reviewer_name,
                'designation': designation,
                'vertical': vertical,
                'relationship_type': row[3],
                'status': row[4],
                'approval_status': row[5],
                'created_at': row[6],
                'rejection_reason': row[7],
                'reviewer_identifier': reviewer_identifier
            }
            
            if row[5] == 'rejected':  # approval_status
                rejected_nominations.append(nomination_data)
            else:
                nominations.append(nomination_data)
        
        # Count only non-rejected nominations towards the limit
        active_count = len(nominations)
        can_nominate_more = active_count < 4
        
        return {
            'existing_nominations': nominations,
            'rejected_nominations': rejected_nominations,
            'total_count': active_count,
            'can_nominate_more': can_nominate_more,
            'remaining_slots': max(0, 4 - active_count)
        }
    except Exception as e:
        print(f"Error getting user nominations status: {e}")
        return {'existing_nominations': [], 'rejected_nominations': [], 'total_count': 0, 'can_nominate_more': True, 'remaining_slots': 4}

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

def determine_relationship_type(requester_id, reviewer_id):
    """
    Automatically determine relationship type based on organizational structure.
    
    Rules:
    1) Same team, neither is manager of other -> peer
    2) Different team, neither is manager of other -> internal_stakeholder  
    3) Reviewer reports to requester -> direct_reportee
    """
    conn = get_connection()
    try:
        # Get both users' information
        query = """
            SELECT 
                r.vertical as requester_vertical, r.email as requester_email,
                rv.vertical as reviewer_vertical, rv.reporting_manager_email as reviewer_manager_email
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
        reviewer_vertical = data[2]
        reviewer_manager_email = data[3]
        
        # Rule 3: Check if reviewer reports to requester (direct reportee)
        if reviewer_manager_email and reviewer_manager_email.lower() == requester_email.lower():
            return "direct_reportee"
        
        # Rule 1: Same team/vertical and not manager relationship -> peer
        if requester_vertical and reviewer_vertical and requester_vertical == reviewer_vertical:
            return "peer"
        
        # Rule 2: Different team/vertical and not manager relationship -> internal stakeholder
        return "internal_stakeholder"
        
    except Exception as e:
        print(f"Error determining relationship type: {e}")
        # Default fallback
        return "peer"

def get_relationship_with_preview(requester_id, reviewer_data):
    """
    Get relationship types for multiple reviewers with preview.
    Returns list of tuples: (reviewer_identifier, relationship_type)
    """
    relationships = []
    for reviewer_identifier, _ in reviewer_data:  # Ignore the old relationship parameter
        if isinstance(reviewer_identifier, int):
            # Internal reviewer
            relationship_type = determine_relationship_type(requester_id, reviewer_identifier)
            relationships.append((reviewer_identifier, relationship_type))
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
    """Handle reviewer acceptance or rejection of feedback request."""
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

