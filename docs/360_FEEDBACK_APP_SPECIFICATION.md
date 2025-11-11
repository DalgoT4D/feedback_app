# 360-Degree Feedback App - Complete Technical Specification

## Business Overview & Requirements

### What is 360-Degree Feedback?
This application facilitates a performance review process where employees receive feedback from multiple sources - peers, subordinates, and supervisors - providing a "360-degree" view of their performance. It's a comprehensive evaluation system that helps employees understand how they're perceived by colleagues they work with regularly.

### Core Business Requirements

#### Employee Feedback Request Process
- Each employee can request feedback from **3-5 people** depending on their role
- **Minimum 3 required** (system shows warning if less than 3 selected)
- **Maximum 5 allowed** (system prevents more than 5 selections)
- When selecting reviewers, requesters must declare **relationship type**: peer, manager, direct reportee, external stakeholder, or internal stakeholder
- **Only Manager level and above** can request reviews from external stakeholders
- The system prevents any single employee from being overwhelmed with requests by limiting them to maximum 4 review requests

#### Manager Approval Workflow
- After employee submits their 3-5 reviewer nominations, requests go to their **reporting manager for approval**
- Manager sees nominee list with relationship types (peer/manager/reportee/external/internal)
- Manager can **approve or reject** individual nominees with rejection reason
- If rejected, employee gets notification email and must select **different person** (cannot re-nominate rejected person)
- Only after manager approval are feedback requests sent to reviewers

#### Review Completion Workflow  
- **Different question sets** based on relationship type:
  - **Peers/Internal Stakeholders/Managers**: Collaboration, Communication, Reliability, Ownership + open feedback
  - **Direct Reportees**: Approachability, Openness to feedback, Clarity, Communication + leadership feedback  
  - **External Stakeholders**: Professionalism, Reliability, Responsiveness, Communication, Understanding needs, Quality + collaboration feedback
- Reviews can be saved as drafts and completed later
- All questions mandatory for final submission
- **Reviews are anonymized** when displayed - recipient sees feedback but not who wrote it

#### Privacy & Access Control
- Employees can view **anonymized feedback** they've received 
- Employees can **download their feedback to Excel** for personal records
- Employees can track nomination status: "3/5 responses received" without knowing which specific people responded
- **Send reminders** to non-responders without revealing who hasn't responded yet
- Three user roles: super_admin (full access), hr (dashboard + management), employee (own feedback only)

#### HR Dashboard & Management
- HR can see analytics: how many people haven't completed reviews, total reviews completed, etc.
- HR can send reminder emails to employees with pending reviews via a "nudge" button
- Dashboard shows summary metrics for following up on incomplete reviews
- **HR can initiate new feedback cycles** with specific deadlines for each phase
- **Timeline management**: 4-5 week process with specific deadlines for each phase

#### Process Timeline (4-5 weeks total)
- **Week 1**: Nomination submission period
- **Week 2**: Manager approval + feedback requests sent out
- **Weeks 3-5**: Feedback completion period (3 weeks)
- **Week 5**: Results compilation and sharing

#### Authentication & Security
- **First-time login**: employees with emails in the system can set their initial password
- **Forgot password**: functionality with secure email reset links  
- **Role-based access**: control throughout the application
- **Organizational hierarchy**: management with reporting manager relationships

#### Password Creation Workflow
1. **Initial Setup**: Users are seeded with `password_hash = NULL`
2. **First Visit**: User enters email, system checks if password exists
3. **Password Setup**: If NULL, redirect to password creation page
4. **Security**: Passwords hashed with bcrypt before storage
5. **Subsequent Logins**: Normal email/password authentication

### User Workflow Examples

#### For a Regular Employee (Sarah - Team Lead):
1. **Request Feedback**: Sarah logs in and selects 4 people for feedback. She chooses: 1 peer (Tom), 1 manager (Radhika), 2 direct reportees (Ana, Dev). For each person, she declares the relationship type. System ensures she has minimum 3, max 5.

2. **Manager Approval**: Sarah's manager Radhika reviews the nominations, sees relationship types, and approves all 4. Feedback requests are then sent to Tom, Ana, and Dev.

3. **Track Progress**: Sarah sees "3/4 responses received" without knowing which specific people responded. She can click "Send reminder to 1 person" to nudge the non-responder.

4. **Complete Reviews**: When others request Sarah's feedback, she sees different question sets based on relationship (peer questions for Tom, leadership questions when reviewing her manager).

5. **View My Feedback**: Sarah receives anonymized feedback - she can see the 4 reviews but doesn't know which person wrote which review.

#### For a Manager (Radhika - Associate Director):
1. **Approve Team Nominations**: Radhika reviews feedback requests from her team members, seeing who they want feedback from and the relationship types.

2. **Request External Stakeholder Feedback**: As a Director-level person, Radhika can request feedback from external clients/partners.

3. **Manage Team Timeline**: Track which team members have submitted nominations, completed their reviews, etc.

#### For HR (Mike):
1. **Dashboard Overview**: Mike sees timeline progress: "Week 2 - 23 nominations pending approval, 45 requests sent out, 12 employees haven't submitted nominations"

2. **Send Reminders**: Bulk reminders for different stages (nomination deadline, review completion deadline)

3. **Timeline Management**: Track overall process completion across the 4-5 week cycle

#### For New Employee (First Login):
1. **Password Setup**: Employee receives their email from IT, visits the app, and sets their initial password securely

2. **Forgot Password**: If forgotten, they can request a reset link via email with a secure token

### Technical Architecture
Built using Streamlit + Turso (SQLite) database following the proven patterns from your existing counseling application, including the working connection handling, authentication service, and navigation structure.

## Tech Stack Requirements

### **Core Framework & Database**
- **Frontend**: Streamlit (latest version)
- **Database**: Turso (SQLite-compatible)
- **Database Driver**: `libsql_experimental` (tested and working connection pattern provided)
- **Python Version**: Python 3.8+

### **Required Python Packages**
```txt
streamlit
libsql_experimental
bcrypt
pandas
openpyxl  # For Excel export functionality
python-dotenv  # For environment variables (optional)
smtplib  # Built-in for email functionality
```

### **Authentication & Security**
- **Password Hashing**: `bcrypt` library
- **Session Management**: Streamlit's built-in session state
- **Email Sending**: Python's built-in `smtplib` with Gmail SMTP

### **File Structure & Patterns**
- **Navigation**: Streamlit's `st.navigation()` with role-based pages
- **Database Pattern**: Global connection with stream expiration handling (proven pattern provided)
- **Error Handling**: Try-catch with connection retry logic
- **State Management**: Streamlit session state for user data and authentication

### **Deployment Environment**
- **Platform**: Streamlit Cloud (recommended)
- **Secrets Management**: `.streamlit/secrets.toml` for database credentials and email config
- **Environment**: Cloud-hosted with Turso database connection

## Database Schema & Setup

### Turso Connection Pattern (Tested & Working)
```python
# services/db_helper.py - Database Connection Setup
import libsql_experimental as libsql
import streamlit as st
from datetime import datetime

# Get database connection details from environment variables
db_url = st.secrets["DB_URL"]
auth_token = st.secrets["AUTH_TOKEN"]

if not db_url or not auth_token:
    raise Exception("Database URL or Auth Token is missing. Check your .env file.")

# Define the global connection variable
_connection = None

def get_connection():
    global _connection  # Declare _connection as global
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
```

### Required SQLite CREATE TABLE Statements

```sql
-- 1. Users table - stores all employee information and authentication (follows your existing pattern)
CREATE TABLE users (
    user_type_id INTEGER PRIMARY KEY AUTOINCREMENT,
    email TEXT UNIQUE NOT NULL,
    first_name TEXT NOT NULL,
    last_name TEXT NOT NULL,
    vertical TEXT, -- Department/Team (Dalgo, Glific, etc.)
    designation TEXT, -- Team Lead, Manager, Director, etc.
    reporting_manager_email TEXT, -- Direct manager's email
    password_hash TEXT NULL, -- NULL until first login
    password_reset_token TEXT NULL,
    password_reset_expires DATETIME NULL,
    is_active BOOLEAN DEFAULT 1,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- 2. Roles table (follows your existing pattern)
CREATE TABLE roles (
    role_id INTEGER PRIMARY KEY AUTOINCREMENT,
    role_name TEXT UNIQUE NOT NULL, -- 'super_admin', 'hr', 'employee'
    description TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- 3. User role assignments (follows your existing pattern)
CREATE TABLE user_roles (
    user_type_id INTEGER,
    role_id INTEGER,
    assigned_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (user_type_id, role_id),
    FOREIGN KEY (user_type_id) REFERENCES users (user_type_id),
    FOREIGN KEY (role_id) REFERENCES roles (role_id)
);

-- 4. Feedback requests - tracks who is requesting feedback from whom
CREATE TABLE feedback_requests (
    request_id INTEGER PRIMARY KEY AUTOINCREMENT,
    cycle_id INTEGER NOT NULL, -- Link to specific review cycle
    requester_id INTEGER NOT NULL, -- User requesting feedback
    reviewer_id INTEGER NOT NULL, -- User being asked to provide feedback
    relationship_type TEXT NOT NULL, -- 'peer', 'manager', 'direct_reportee', 'external_stakeholder', 'internal_stakeholder'
    status TEXT DEFAULT 'pending_approval', -- 'pending_approval', 'approved', 'rejected', 'completed', 'expired'
    approval_status TEXT DEFAULT 'pending', -- 'pending', 'approved', 'rejected'
    approved_by INTEGER NULL, -- Manager who approved/rejected
    rejection_reason TEXT NULL, -- Reason if rejected
    approval_date DATETIME NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    completed_at DATETIME NULL,
    FOREIGN KEY (cycle_id) REFERENCES review_cycles (cycle_id),
    FOREIGN KEY (requester_id) REFERENCES users (user_type_id),
    FOREIGN KEY (reviewer_id) REFERENCES users (user_type_id),
    FOREIGN KEY (approved_by) REFERENCES users (user_type_id)
);

-- 5. Feedback questions - configurable questions for different relationship types
CREATE TABLE feedback_questions (
    question_id INTEGER PRIMARY KEY AUTOINCREMENT,
    question_text TEXT NOT NULL,
    question_type TEXT DEFAULT 'rating', -- 'rating', 'text'
    relationship_type TEXT NOT NULL, -- 'peer', 'manager', 'direct_reportee', 'external_stakeholder', 'internal_stakeholder'
    is_active BOOLEAN DEFAULT 1,
    sort_order INTEGER DEFAULT 0,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- 6. Draft responses - for saving incomplete evaluations
CREATE TABLE draft_responses (
    draft_id INTEGER PRIMARY KEY AUTOINCREMENT,
    request_id INTEGER NOT NULL,
    question_id INTEGER NOT NULL,
    response_value TEXT,
    rating_value INTEGER, -- for rating questions (1-5)
    saved_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (request_id) REFERENCES feedback_requests (request_id),
    FOREIGN KEY (question_id) REFERENCES feedback_questions (question_id),
    UNIQUE(request_id, question_id)
);

-- 7. Final feedback responses - completed evaluations
CREATE TABLE feedback_responses (
    response_id INTEGER PRIMARY KEY AUTOINCREMENT,
    request_id INTEGER NOT NULL,
    question_id INTEGER NOT NULL,
    response_value TEXT,
    rating_value INTEGER, -- for rating questions (1-5)
    submitted_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (request_id) REFERENCES feedback_requests (request_id),
    FOREIGN KEY (question_id) REFERENCES feedback_questions (question_id)
);

-- 8. Reviewer nomination tracking - prevents over-nomination
CREATE TABLE reviewer_nominations (
    nomination_id INTEGER PRIMARY KEY AUTOINCREMENT,
    reviewer_id INTEGER NOT NULL,
    nomination_count INTEGER DEFAULT 0,
    last_updated DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (reviewer_id) REFERENCES users (user_type_id),
    UNIQUE(reviewer_id)
);

-- 9. Rejected nominations - prevent re-nomination of rejected reviewers
CREATE TABLE rejected_nominations (
    rejection_id INTEGER PRIMARY KEY AUTOINCREMENT,
    requester_id INTEGER NOT NULL,
    rejected_reviewer_id INTEGER NOT NULL,
    rejected_by INTEGER NOT NULL, -- Manager who rejected
    rejection_reason TEXT,
    rejected_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (requester_id) REFERENCES users (user_type_id),
    FOREIGN KEY (rejected_reviewer_id) REFERENCES users (user_type_id),
    FOREIGN KEY (rejected_by) REFERENCES users (user_type_id),
    UNIQUE(requester_id, rejected_reviewer_id)
);

-- 10. Review cycles - manage 4-5 week feedback cycles
CREATE TABLE review_cycles (
    cycle_id INTEGER PRIMARY KEY AUTOINCREMENT,
    cycle_name TEXT NOT NULL,
    nomination_start_date DATE NOT NULL,
    nomination_deadline DATE NOT NULL,
    approval_deadline DATE NOT NULL, 
    feedback_deadline DATE NOT NULL,
    results_deadline DATE NOT NULL,
    is_active BOOLEAN DEFAULT 0,
    created_by INTEGER NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (created_by) REFERENCES users (user_type_id)
);

-- 11. Email logs - track email notifications
CREATE TABLE email_logs (
    log_id INTEGER PRIMARY KEY AUTOINCREMENT,
    recipient_email TEXT NOT NULL,
    email_type TEXT NOT NULL, -- 'feedback_request', 'password_reset', 'reminder', 'approval_needed', 'rejection_notice'
    subject TEXT,
    status TEXT DEFAULT 'pending', -- 'pending', 'sent', 'failed'
    sent_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    error_message TEXT NULL
);

-- Insert default roles
INSERT INTO roles (role_name, description) VALUES 
('super_admin', 'Super Administrator with full access'),
('hr', 'HR personnel with dashboard and management access'),
('employee', 'Regular employee with feedback access');

-- Insert feedback questions for different relationship types

-- Questions for Peers/Internal Stakeholders/Managers
INSERT INTO feedback_questions (question_text, question_type, relationship_type, sort_order) VALUES 
('Collaboration', 'rating', 'peer', 1),
('Communication', 'rating', 'peer', 2),
('Reliability', 'rating', 'peer', 3),
('Ownership (Trust)', 'rating', 'peer', 4),
('One or two things you value or appreciate about how this person works — things you'd like them to continue doing.', 'text', 'peer', 5),
('One or two things you feel this person could get even better at, to perform even more effectively in their role.', 'text', 'peer', 6);

-- Same questions for internal stakeholders and managers
INSERT INTO feedback_questions (question_text, question_type, relationship_type, sort_order) VALUES 
('Collaboration', 'rating', 'internal_stakeholder', 1),
('Communication', 'rating', 'internal_stakeholder', 2),
('Reliability', 'rating', 'internal_stakeholder', 3),
('Ownership (Trust)', 'rating', 'internal_stakeholder', 4),
('One or two things you value or appreciate about how this person works — things you'd like them to continue doing.', 'text', 'internal_stakeholder', 5),
('One or two things you feel this person could get even better at, to perform even more effectively in their role.', 'text', 'internal_stakeholder', 6);

INSERT INTO feedback_questions (question_text, question_type, relationship_type, sort_order) VALUES 
('Collaboration', 'rating', 'manager', 1),
('Communication', 'rating', 'manager', 2),
('Reliability', 'rating', 'manager', 3),
('Ownership (Trust)', 'rating', 'manager', 4),
('One or two things you value or appreciate about how this person works — things you'd like them to continue doing.', 'text', 'manager', 5),
('One or two things you feel this person could get even better at, to perform even more effectively in their role.', 'text', 'manager', 6);

-- Questions for Direct Reportees (leadership evaluation)
INSERT INTO feedback_questions (question_text, question_type, relationship_type, sort_order) VALUES 
('Approachability', 'rating', 'direct_reportee', 1),
('Openness to feedback (Openness & Trust)', 'rating', 'direct_reportee', 2),
('Clarity in direction', 'rating', 'direct_reportee', 3),
('Effectiveness in communication', 'rating', 'direct_reportee', 4),
('A short note on what helps or could help you work better under their leadership.', 'text', 'direct_reportee', 5);

-- Questions for External Stakeholders
INSERT INTO feedback_questions (question_text, question_type, relationship_type, sort_order) VALUES 
('Professionalism', 'rating', 'external_stakeholder', 1),
('Reliability (Trust & Excellence)', 'rating', 'external_stakeholder', 2),
('Responsiveness', 'rating', 'external_stakeholder', 3),
('Clarity in communication (Openness & Collaboration)', 'rating', 'external_stakeholder', 4),
('Understanding of your needs', 'rating', 'external_stakeholder', 5),
('Quality of delivery (Social-Sector Focus & Innovation)', 'rating', 'external_stakeholder', 6),
('Share your thoughts on how this person collaborates, communicates, and delivers in your interactions. Any examples of what worked well or areas for growth?', 'text', 'external_stakeholder', 7);

```

## Project Structure

```
360_feedback_app/
├── main.py                          # Main Streamlit app with navigation
├── login.py                         # Authentication page  
├── password_setup.py                # First-time password setup
├── forgot_password.py               # Password reset functionality
├── services/
│   ├── db_helper.py                # Database operations (50+ functions)
│   ├── auth_service.py             # Authentication logic
│   └── email_service.py            # Email sending functionality
├── screens/
│   ├── employee/                   # Employee-facing screens
│   │   ├── request_feedback.py     # Request 3-5 reviewers with relationship types
│   │   ├── my_feedback.py          # View anonymized feedback + Excel download
│   │   ├── my_reviews.py           # Track reviews to complete for others
│   │   └── provide_feedback.py     # Complete feedback forms (different Q sets)
│   ├── manager/                    # Manager-specific screens  
│   │   └── approve_nominations.py  # Approve/reject team member nominations
│   ├── hr/                         # HR management screens
│   │   ├── dashboard.py            # Analytics + create new cycles + phase tracking
│   │   ├── manage_employees.py     # Employee management
│   │   └── send_reminders.py       # Send reminder emails
│   └── admin/                      # Super admin screens
│       ├── user_management.py      # User management functions
│       └── system_settings.py     # App configuration
└── .streamlit/
    └── secrets.toml                # Database credentials + email config
```

## Core Database Helper Functions

```python
# services/db_helper.py - Key Functions

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
                "department": user[4],
                "position": user[5],
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

def get_users_for_selection(exclude_user_id=None, requester_user_id=None):
    """Get list of users for reviewer selection with nomination tracking and rejection filtering."""
    conn = get_connection()
    query = """
        SELECT u.user_type_id, u.first_name, u.last_name, u.vertical, u.designation,
               COALESCE(rn.nomination_count, 0) as nomination_count,
               CASE WHEN rej.rejected_reviewer_id IS NOT NULL THEN 1 ELSE 0 END as is_rejected
        FROM users u
        LEFT JOIN reviewer_nominations rn ON u.user_type_id = rn.reviewer_id
        LEFT JOIN rejected_nominations rej ON u.user_type_id = rej.rejected_reviewer_id 
            AND rej.requester_id = ?
        WHERE u.is_active = 1
    """
    params = [requester_user_id or 0]
    
    if exclude_user_id:
        query += " AND u.user_type_id != ?"
        params.append(exclude_user_id)
    
    query += " ORDER BY u.first_name, u.last_name"
    
    try:
        result = conn.execute(query, params)
        users = []
        for row in result.fetchall():
            is_over_limit = row[5] >= 4  # nomination_count >= 4
            is_rejected = row[6] == 1  # previously rejected
            users.append({
                "user_type_id": row[0],
                "name": f"{row[1]} {row[2]}",
                "vertical": row[3],
                "designation": row[4],
                "nomination_count": row[5],
                "is_over_limit": is_over_limit,
                "is_rejected": is_rejected,
                "is_selectable": not (is_over_limit or is_rejected)
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
    elif 'manager' in designation_lower:
        return 2
    elif 'lead' in designation_lower:
        return 1
    else:
        return 0  # Associate/Analyst/Consultant

def check_external_stakeholder_permission(user_id):
    """Check if user has manager level or above to request external stakeholder feedback."""
    conn = get_connection()
    query = "SELECT designation FROM users WHERE user_type_id = ?"
    try:
        result = conn.execute(query, (user_id,))
        user = result.fetchone()
        if user:
            manager_level = get_manager_level_from_designation(user[0])
            return manager_level >= 2  # Manager level (2) or above
        return False
    except Exception as e:
        print(f"Error checking external stakeholder permission: {e}")
        return False

def create_feedback_requests_with_approval(requester_id, reviewer_data):
    """Create feedback requests that require manager approval."""
    conn = get_connection()
    try:
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
        for reviewer_id, relationship_type in reviewer_data:
            request_query = """
                INSERT INTO feedback_requests 
                (requester_id, reviewer_id, relationship_type, status, approval_status) 
                VALUES (?, ?, ?, 'pending_approval', 'pending')
            """
            conn.execute(request_query, (requester_id, reviewer_id, relationship_type))
            
            # Update nomination count
            nomination_query = """
                INSERT INTO reviewer_nominations (reviewer_id, nomination_count) 
                VALUES (?, 1)
                ON CONFLICT(reviewer_id) DO UPDATE SET
                nomination_count = nomination_count + 1,
                last_updated = CURRENT_TIMESTAMP
            """
            conn.execute(nomination_query, (reviewer_id,))
        
        conn.commit()
        
        # Send email to manager for approval
        send_approval_needed_email(manager_id, requester_id)
        
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
            # Update request status
            update_query = """
                UPDATE feedback_requests 
                SET approval_status = 'approved', status = 'approved', 
                    approved_by = ?, approval_date = CURRENT_TIMESTAMP
                WHERE request_id = ?
            """
            conn.execute(update_query, (manager_id, request_id))
            
            # Send feedback request to reviewer
            # Get request details for email
            request_details = conn.execute(
                "SELECT reviewer_id, requester_id FROM feedback_requests WHERE request_id = ?", 
                (request_id,)
            ).fetchone()
            if request_details:
                send_feedback_request_email(request_details[0], request_details[1])
                
        elif action == 'reject':
            # Update request status
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
                
                # Send rejection notice to requester
                send_rejection_notice_email(request_details[0], request_details[1], rejection_reason)
        
        conn.commit()
        return True
    except Exception as e:
        print(f"Error processing approval/rejection: {e}")
        conn.rollback()
        return False

def create_feedback_requests(requester_id, reviewer_ids):
    """Create feedback requests and update nomination counts."""
    conn = get_connection()
    try:
        for reviewer_id in reviewer_ids:
            # Create feedback request
            request_query = """
                INSERT INTO feedback_requests (requester_id, reviewer_id) 
                VALUES (?, ?)
            """
            conn.execute(request_query, (requester_id, reviewer_id))
            
            # Update nomination count
            nomination_query = """
                INSERT INTO reviewer_nominations (reviewer_id, nomination_count) 
                VALUES (?, 1)
                ON CONFLICT(reviewer_id) DO UPDATE SET
                nomination_count = nomination_count + 1,
                last_updated = CURRENT_TIMESTAMP
            """
            conn.execute(nomination_query, (reviewer_id,))
        
        conn.commit()
        return True
    except Exception as e:
        print(f"Error creating feedback requests: {e}")
        conn.rollback()
        return False

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

def get_pending_reviews_for_employee(employee_id):
    """Get feedback requests pending for an employee to complete."""
    conn = get_connection()
    query = """
        SELECT fr.request_id, e.first_name, e.last_name, e.department, 
               fr.created_at, COUNT(dr.draft_id) as draft_count
        FROM feedback_requests fr
        JOIN employees e ON fr.requester_id = e.employee_id
        LEFT JOIN draft_responses dr ON fr.request_id = dr.request_id
        WHERE fr.reviewer_id = ? AND fr.status = 'pending'
        GROUP BY fr.request_id, e.first_name, e.last_name, e.department, fr.created_at
        ORDER BY fr.created_at ASC
    """
    try:
        result = conn.execute(query, (employee_id,))
        return result.fetchall()
    except Exception as e:
        print(f"Error fetching pending reviews: {e}")
        return []

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
        # Group by request_id for anonymized display
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
            SUM(CASE WHEN fr.status = 'completed' THEN 1 ELSE 0 END) as completed_requests,
            SUM(CASE WHEN fr.status = 'approved' THEN 1 ELSE 0 END) as pending_requests,
            SUM(CASE WHEN fr.approval_status = 'pending' THEN 1 ELSE 0 END) as awaiting_approval
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

def get_non_responders_for_user(user_id):
    """Get count of non-responders for sending anonymous reminders."""
    conn = get_connection()
    query = """
        SELECT COUNT(*) as non_responder_count
        FROM feedback_requests fr
        WHERE fr.requester_id = ? AND fr.status = 'approved'
    """
    try:
        result = conn.execute(query, (user_id,))
        count = result.fetchone()
        return count[0] if count else 0
    except Exception as e:
        print(f"Error fetching non-responder count: {e}")
        return 0

def send_anonymous_reminders_for_user(user_id):
    """Send reminder emails to non-responders without revealing who they are."""
    conn = get_connection()
    query = """
        SELECT fr.reviewer_id, u.email, u.first_name
        FROM feedback_requests fr
        JOIN users u ON fr.reviewer_id = u.user_type_id
        WHERE fr.requester_id = ? AND fr.status = 'approved'
    """
    try:
        result = conn.execute(query, (user_id,))
        non_responders = result.fetchall()
        
        # Send reminder emails to each non-responder
        for reviewer_id, email, first_name in non_responders:
            send_feedback_reminder_email(reviewer_id, user_id)
        
        return len(non_responders)
    except Exception as e:
        print(f"Error sending anonymous reminders: {e}")
        return 0

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

def create_new_review_cycle(cycle_name, nomination_start, nomination_deadline, approval_deadline, feedback_deadline, results_deadline, created_by):
    """Create a new review cycle (HR function)."""
    conn = get_connection()
    try:
        # Deactivate any existing active cycles
        deactivate_query = "UPDATE review_cycles SET is_active = 0"
        conn.execute(deactivate_query)
        
        # Create new cycle
        insert_query = """
            INSERT INTO review_cycles 
            (cycle_name, nomination_start_date, nomination_deadline, approval_deadline, 
             feedback_deadline, results_deadline, is_active, created_by)
            VALUES (?, ?, ?, ?, ?, ?, 1, ?)
        """
        conn.execute(insert_query, (
            cycle_name, nomination_start, nomination_deadline, approval_deadline,
            feedback_deadline, results_deadline, created_by
        ))
        
        conn.commit()
        return True
    except Exception as e:
        print(f"Error creating review cycle: {e}")
        conn.rollback()
        return False

def get_active_review_cycle():
    """Get the currently active review cycle."""
    conn = get_connection()
    query = """
        SELECT cycle_id, cycle_name, nomination_start_date, nomination_deadline, 
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
                'nomination_start_date': cycle[2],
                'nomination_deadline': cycle[3],
                'approval_deadline': cycle[4],
                'feedback_deadline': cycle[5],
                'results_deadline': cycle[6],
                'created_at': cycle[7]
            }
        return None
    except Exception as e:
        print(f"Error fetching active cycle: {e}")
        return None

def generate_feedback_excel_data(user_id):
    """Generate Excel-ready data for a user's feedback."""
    feedback_data = get_anonymized_feedback_for_user(user_id)
    
    # Prepare data for Excel export
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

def get_current_cycle_phase():
    """Determine which phase of the review cycle we're currently in."""
    from datetime import datetime, date
    
    cycle = get_active_review_cycle()
    if not cycle:
        return "No active cycle"
    
    today = date.today()
    
    if today <= cycle['nomination_deadline']:
        return "Nomination Phase"
    elif today <= cycle['approval_deadline']:
        return "Manager Approval Phase"
    elif today <= cycle['feedback_deadline']:
        return "Feedback Collection Phase"
    elif today <= cycle['results_deadline']:
        return "Results Processing Phase"
    else:
        return "Cycle Complete"

def get_hr_dashboard_metrics():
    """Get comprehensive metrics for HR dashboard."""
    conn = get_connection()
    try:
        metrics = {}
        
        # Total employees
        total_employees = conn.execute("SELECT COUNT(*) FROM employees WHERE is_active = 1").fetchone()[0]
        
        # Pending feedback requests
        pending_requests = conn.execute(
            "SELECT COUNT(*) FROM feedback_requests WHERE status = 'pending'"
        ).fetchone()[0]
        
        # Completed feedback this month
        completed_this_month = conn.execute("""
            SELECT COUNT(*) FROM feedback_requests 
            WHERE status = 'completed' AND DATE(completed_at) >= DATE('now', 'start of month')
        """).fetchone()[0]
        
        # Employees with incomplete reviews
        incomplete_reviews = conn.execute("""
            SELECT COUNT(DISTINCT reviewer_id) FROM feedback_requests 
            WHERE status = 'pending'
        """).fetchone()[0]
        
        metrics.update({
            'total_employees': total_employees,
            'pending_requests': pending_requests,
            'completed_this_month': completed_this_month,
            'employees_with_incomplete': incomplete_reviews
        })
        
        return metrics
    except Exception as e:
        print(f"Error fetching HR metrics: {e}")
        return {}

def send_reminder_email(employee_id):
    """Log reminder email to be sent."""
    conn = get_connection()
    try:
        # Get employee email
        employee = conn.execute(
            "SELECT email, first_name FROM employees WHERE employee_id = ?", 
            (employee_id,)
        ).fetchone()
        
        if employee:
            # Log email for sending
            log_query = """
                INSERT INTO email_logs (recipient_email, email_type, subject)
                VALUES (?, 'reminder', 'Pending Feedback Reviews - Action Required')
            """
            conn.execute(log_query, (employee[0],))
            conn.commit()
            return True
        return False
    except Exception as e:
        print(f"Error logging reminder email: {e}")
        return False
```

## Authentication Service

```python
# services/auth_service.py
import bcrypt
from services.db_helper import fetch_user_by_email, fetch_user_roles

def authenticate_user(email, password):
    """Authenticate user by email and password."""
    user = fetch_user_by_email(email)
    
    if not user:
        return False, "User not found.", None
    
    if not user["password_hash"]:
        return False, "Please set up your password first.", None
    
    # Verify password
    if not bcrypt.checkpw(password.encode('utf-8'), user["password_hash"].encode('utf-8')):
        return False, "Incorrect password.", None
    
    # Get roles
    roles = fetch_user_roles(user["user_type_id"])
    user["roles"] = roles
    
    return True, None, user

def check_user_needs_password_setup(email):
    """Check if user exists but needs password setup."""
    user = fetch_user_by_email(email)
    if user and not user["password_hash"]:
        return True, user
    return False, None

def set_user_password(email, password):
    """Set password for first-time login."""
    conn = get_connection()
    password_hash = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
    
    query = "UPDATE users SET password_hash = ? WHERE email = ?"
    try:
        conn.execute(query, (password_hash, email))
        conn.commit()
        return True
    except Exception as e:
        print(f"Error setting password: {e}")
        return False
```

## Main Application Structure

```python
# main.py
import streamlit as st

def logout():
    """Logs the user out and redirects to the login page."""
    st.session_state["authenticated"] = False
    st.session_state["email"] = None
    st.session_state["user_data"] = None
    st.session_state["user_roles"] = []
    st.rerun()

def has_role(role_name):
    """Check if current user has a specific role."""
    user_roles = st.session_state.get("user_roles", [])
    return any(role["role_name"] == role_name for role in user_roles)

# Initialize session state
if "authenticated" not in st.session_state:
    st.session_state["authenticated"] = False
if "user_roles" not in st.session_state:
    st.session_state["user_roles"] = []

# Pages
pages = {
    "Login": st.Page("login.py", title="Log in", icon=":material/login:", default=True),
    "Password Setup": st.Page("password_setup.py", title="Set Password", icon=":material/key:"),
    "Forgot Password": st.Page("forgot_password.py", title="Reset Password", icon=":material/lock_reset:"),
    "Logout": st.Page(logout, title="Log out", icon=":material/logout:"),
}

# Role-based sections
if st.session_state["authenticated"]:
    st.sidebar.write(f"Logged in as: {st.session_state['user_data']['first_name']} {st.session_state['user_data']['last_name']}")
    
    if has_role("super_admin"):
        # Super admin - full access
        pg = st.navigation({
            "Dashboard": [
                st.Page("screens/hr/dashboard.py", title="Analytics Dashboard", icon=":material/dashboard:"),
            ],
            "Management": [
                st.Page("screens/manager/approve_nominations.py", title="Approve Nominations", icon=":material/approval:"),
                st.Page("screens/hr/manage_employees.py", title="Manage Employees", icon=":material/people:"),
                st.Page("screens/hr/send_reminders.py", title="Send Reminders", icon=":material/mail:"),
            ],
            "My Feedback": [
                st.Page("screens/employee/request_feedback.py", title="Request Feedback", icon=":material/rate_review:"),
                st.Page("screens/employee/my_feedback.py", title="My Feedback", icon=":material/feedback:"),
                st.Page("screens/employee/my_reviews.py", title="Reviews to Complete", icon=":material/assignment:"),
                st.Page("screens/employee/provide_feedback.py", title="Provide Feedback", icon=":material/edit:"),
            ],
            "Admin": [
                st.Page("screens/admin/user_management.py", title="User Management", icon=":material/admin_panel_settings:"),
                st.Page("screens/admin/system_settings.py", title="System Settings", icon=":material/settings:"),
            ],
            "Account": [pages["Logout"]],
        })
    elif has_role("hr"):
        # HR - dashboard and management + own feedback
        pg = st.navigation({
            "Dashboard": [
                st.Page("screens/hr/dashboard.py", title="Analytics Dashboard", icon=":material/dashboard:"),
            ],
            "Management": [
                st.Page("screens/manager/approve_nominations.py", title="Approve Nominations", icon=":material/approval:"),
                st.Page("screens/hr/manage_employees.py", title="Manage Employees", icon=":material/people:"),
                st.Page("screens/hr/send_reminders.py", title="Send Reminders", icon=":material/mail:"),
            ],
            "My Feedback": [
                st.Page("screens/employee/request_feedback.py", title="Request Feedback", icon=":material/rate_review:"),
                st.Page("screens/employee/my_feedback.py", title="My Feedback", icon=":material/feedback:"),
                st.Page("screens/employee/my_reviews.py", title="Reviews to Complete", icon=":material/assignment:"),
                st.Page("screens/employee/provide_feedback.py", title="Provide Feedback", icon=":material/edit:"),
            ],
            "Account": [pages["Logout"]],
        })
    else:
        # Regular employee + managers (for approval functions)
        nav_sections = {
            "My Feedback": [
                st.Page("screens/employee/request_feedback.py", title="Request Feedback", icon=":material/rate_review:"),
                st.Page("screens/employee/my_feedback.py", title="My Feedback", icon=":material/feedback:"),
                st.Page("screens/employee/my_reviews.py", title="Reviews to Complete", icon=":material/assignment:"),
                st.Page("screens/employee/provide_feedback.py", title="Provide Feedback", icon=":material/edit:"),
            ],
            "Account": [pages["Logout"]],
        }
        
        # Add manager approval for team leads and above
        user_data = st.session_state.get("user_data", {})
        from services.db_helper import get_manager_level_from_designation
        manager_level = get_manager_level_from_designation(user_data.get("designation", ""))
        if manager_level >= 1:  # Team Lead or above
            nav_sections["Team Management"] = [
                st.Page("screens/manager/approve_nominations.py", title="Approve Team Nominations", icon=":material/approval:"),
            ]
        
        pg = st.navigation(nav_sections)
else:
    # Not authenticated - login options only
    pg = st.navigation([pages["Login"], pages["Password Setup"], pages["Forgot Password"]])

pg.run()
```

## Key Screen Implementation Guidelines

### Employee Request Feedback Screen
```python
# screens/employee/request_feedback.py
import streamlit as st
from services.db_helper import get_users_for_selection, create_feedback_requests

st.title("Request 360° Feedback")

# Get current user
current_user_id = st.session_state["user_data"]["user_type_id"]

# Get available reviewers
users = get_users_for_selection(exclude_user_id=current_user_id)

# Display selection interface
st.write("Select up to 3 colleagues to provide feedback:")

selected_reviewers = []
for user in users:
    col1, col2 = st.columns([3, 1])
    
    with col1:
        if user["is_over_limit"]:
            # Greyed out with tooltip
            st.write(f"~~{user['name']} - {user['department']}~~ *(Already nominated 4 times)*")
        else:
            if st.checkbox(f"{user['name']} - {user['department']}", key=f"user_{user['user_type_id']}"):
                selected_reviewers.append(user["user_type_id"])
    
    with col2:
        st.write(f"Nominations: {user['nomination_count']}/4")

# Validate selection
if len(selected_reviewers) > 3:
    st.error("Please select maximum 3 reviewers.")
elif len(selected_reviewers) == 0:
    st.warning("Please select at least one reviewer.")
else:
    if st.button("Send Feedback Requests"):
        if create_feedback_requests(current_user_id, selected_reviewers):
            st.success("Feedback requests sent successfully!")
            st.rerun()
        else:
            st.error("Error sending requests. Please try again.")
```

### Provide Feedback Screen with Draft Saving
```python
# screens/employee/provide_feedback.py
import streamlit as st
from services.db_helper import get_pending_reviews_for_employee, get_feedback_questions, save_draft_response, submit_final_feedback

st.title("Provide Feedback")

# Get pending reviews
user_id = st.session_state["user_data"]["user_type_id"]
pending_reviews = get_pending_reviews_for_user(user_id)

if not pending_reviews:
    st.info("No pending feedback requests.")
else:
    # Select review to complete
    review_options = [f"{row[1]} {row[2]} - {row[3]} (Requested: {row[4][:10]})" for row in pending_reviews]
    selected_idx = st.selectbox("Select feedback request to complete:", range(len(review_options)), format_func=lambda x: review_options[x])
    
    if selected_idx is not None:
        request_id = pending_reviews[selected_idx][0]
        
        # Get feedback questions
        questions = get_feedback_questions()
        
        # Load existing draft responses
        draft_responses = get_draft_responses(request_id)
        
        responses = {}
        
        for question in questions:
            st.subheader(question["question_text"])
            
            existing_draft = draft_responses.get(question["question_id"], {})
            
            if question["question_type"] == "rating":
                rating = st.slider(
                    "Rating (1-5)", 1, 5, 
                    value=existing_draft.get("rating_value", 3),
                    key=f"rating_{question['question_id']}"
                )
                responses[question["question_id"]] = {"rating_value": rating}
                
            elif question["question_type"] == "text":
                text_response = st.text_area(
                    "Your response:", 
                    value=existing_draft.get("response_value", ""),
                    key=f"text_{question['question_id']}"
                )
                responses[question["question_id"]] = {"response_value": text_response}
        
        # Action buttons
        col1, col2 = st.columns(2)
        
        with col1:
            if st.button("Save Draft"):
                success = True
                for q_id, response_data in responses.items():
                    if not save_draft_response(request_id, q_id, 
                                             response_data.get("response_value"), 
                                             response_data.get("rating_value")):
                        success = False
                        break
                
                if success:
                    st.success("Draft saved successfully!")
                else:
                    st.error("Error saving draft.")
        
        with col2:
            if st.button("Submit Final Feedback"):
                # Validate all questions answered
                all_complete = all(
                    response_data.get("rating_value") or response_data.get("response_value")
                    for response_data in responses.values()
                )
                
                if all_complete:
                    if submit_final_feedback(request_id, responses):
                        st.success("Feedback submitted successfully!")
                        st.rerun()
                    else:
                        st.error("Error submitting feedback.")
                else:
                    st.error("Please complete all questions before submitting.")
```

### HR Dashboard with Cycle Management and Nudge Functionality
```python
# screens/hr/dashboard.py
import streamlit as st
from datetime import datetime, timedelta
from services.db_helper import (
    get_hr_dashboard_metrics, get_employees_with_pending_reviews, 
    send_reminder_email, create_new_review_cycle, get_active_review_cycle,
    get_current_cycle_phase
)

st.title("HR Analytics Dashboard")

# Current cycle status
st.subheader("Current Review Cycle")
active_cycle = get_active_review_cycle()
current_phase = get_current_cycle_phase()

if active_cycle:
    col1, col2 = st.columns(2)
    with col1:
        st.info(f"**{active_cycle['cycle_name']}**")
        st.write(f"Current Phase: **{current_phase}**")
    with col2:
        st.write(f"Nomination Deadline: {active_cycle['nomination_deadline']}")
        st.write(f"Feedback Deadline: {active_cycle['feedback_deadline']}")
else:
    st.warning("No active review cycle")

# Create new cycle section
if st.button("Create New Review Cycle"):
    st.session_state.show_cycle_form = True

if st.session_state.get('show_cycle_form', False):
    st.subheader("Create New Review Cycle")
    
    cycle_name = st.text_input("Cycle Name", value=f"Review Cycle {datetime.now().strftime('%Y-%m')}")
    
    col1, col2 = st.columns(2)
    with col1:
        nomination_start = st.date_input("Nomination Start Date", datetime.now().date())
        nomination_deadline = st.date_input("Nomination Deadline", nomination_start + timedelta(weeks=1))
        approval_deadline = st.date_input("Approval Deadline", nomination_deadline + timedelta(weeks=1))
    
    with col2:
        feedback_deadline = st.date_input("Feedback Deadline", approval_deadline + timedelta(weeks=3))
        results_deadline = st.date_input("Results Deadline", feedback_deadline + timedelta(weeks=1))
    
    col1, col2 = st.columns(2)
    with col1:
        if st.button("Create Cycle"):
            user_id = st.session_state["user_data"]["user_type_id"]
            if create_new_review_cycle(
                cycle_name, nomination_start, nomination_deadline, 
                approval_deadline, feedback_deadline, results_deadline, user_id
            ):
                st.success("Review cycle created successfully!")
                st.session_state.show_cycle_form = False
                st.rerun()
            else:
                st.error("Error creating cycle")
    
    with col2:
        if st.button("Cancel"):
            st.session_state.show_cycle_form = False
            st.rerun()

# Get metrics
metrics = get_hr_dashboard_metrics()

# Display key metrics
st.subheader("Dashboard Metrics")
col1, col2, col3, col4 = st.columns(4)

with col1:
    st.metric("Total Employees", metrics.get('total_employees', 0))

with col2:
    st.metric("Pending Requests", metrics.get('pending_requests', 0))

with col3:
    st.metric("Completed This Month", metrics.get('completed_this_month', 0))

with col4:
    st.metric("Employees with Incomplete", metrics.get('employees_with_incomplete', 0))

# Employees with pending reviews
st.subheader("Employees with Pending Reviews")

pending_employees = get_employees_with_pending_reviews()

if pending_employees:
    for emp in pending_employees:
        col1, col2, col3 = st.columns([3, 1, 1])
        
        with col1:
            st.write(f"{emp['name']} - {emp['pending_count']} pending")
        
        with col2:
            st.write(f"Dept: {emp['vertical']}")
        
        with col3:
            if st.button("Send Reminder", key=f"remind_{emp['user_type_id']}"):
                if send_reminder_email(emp['user_type_id']):
                    st.success("Reminder sent!")
                else:
                    st.error("Failed to send.")
```

### Employee Feedback Download Screen
```python
# screens/employee/my_feedback.py
import streamlit as st
import pandas as pd
from datetime import datetime
from io import BytesIO
from services.db_helper import (
    get_anonymized_feedback_for_user, get_feedback_progress_for_user,
    generate_feedback_excel_data
)

st.title("My Feedback Results")

user_id = st.session_state["user_data"]["user_type_id"]

# Progress tracking
progress = get_feedback_progress_for_user(user_id)
st.subheader("Feedback Progress")

col1, col2, col3 = st.columns(3)
with col1:
    st.metric("Responses Received", f"{progress['completed_requests']}/{progress['total_requests']}")
with col2:
    st.metric("Pending Responses", progress['pending_requests'])
with col3:
    st.metric("Awaiting Approval", progress['awaiting_approval'])

# Download Excel
if progress['completed_requests'] > 0:
    if st.button("Download My Feedback (Excel)"):
        excel_data = generate_feedback_excel_data(user_id)
        
        if excel_data:
            df = pd.DataFrame(excel_data)
            
            # Create Excel file in memory
            output = BytesIO()
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                df.to_excel(writer, sheet_name='My_Feedback', index=False)
            
            output.seek(0)
            
            st.download_button(
                label="📥 Download Excel File",
                data=output.getvalue(),
                file_name=f"my_feedback_{user_id}_{datetime.now().strftime('%Y%m%d')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )

# Display anonymized feedback
feedback_data = get_anonymized_feedback_for_user(user_id)

if feedback_data:
    st.subheader("Feedback Results (Anonymized)")
    
    for i, (request_id, feedback) in enumerate(feedback_data.items(), 1):
        with st.expander(f"Review #{i} - {feedback['relationship_type'].replace('_', ' ').title()}"):
            st.write(f"**Completed:** {feedback['completed_at']}")
            
            for response in feedback['responses']:
                st.write(f"**{response['question_text']}**")
                
                if response['question_type'] == 'rating':
                    st.write(f"Rating: {'⭐' * response['rating_value']} ({response['rating_value']}/5)")
                else:
                    st.write(response['response_value'])
                
                st.write("---")
else:
    st.info("No completed feedback available yet.")
```

## Security Features

### Password Reset Implementation
```python
# forgot_password.py
import streamlit as st
import secrets
from datetime import datetime, timedelta
from services.db_helper import get_connection
from services.email_service import send_password_reset_email

st.title("Reset Password")

email = st.text_input("Enter your email address:")

if st.button("Send Reset Link"):
    if email:
        # Generate secure token
        reset_token = secrets.token_urlsafe(32)
        expires_at = datetime.now() + timedelta(hours=24)
        
        # Store token in database
        conn = get_connection()
        query = """
            UPDATE employees 
            SET password_reset_token = ?, password_reset_expires = ?
            WHERE email = ?
        """
        
        try:
            conn.execute(query, (reset_token, expires_at, email))
            conn.commit()
            
            # Send email with reset link
            reset_url = f"{st.secrets['APP_URL']}/password_reset?token={reset_token}"
            if send_password_reset_email(email, reset_url):
                st.success("Password reset link sent to your email!")
            else:
                st.error("Error sending email. Please try again.")
                
        except Exception as e:
            st.error("Error processing request.")
    else:
        st.error("Please enter your email address.")
```

## Configuration Requirements

### .streamlit/secrets.toml
```toml
# Database Configuration (Turso)
DB_URL = "libsql://your-database-url.turso.io"
AUTH_TOKEN = "your-turso-auth-token"

# App Configuration  
APP_URL = "https://your-app-url.streamlit.app"

# Email Configuration (Gmail SMTP)
[email]
smtp_server = "smtp.gmail.com"
smtp_port = 587
email_user = "your-email@company.com"
email_password = "your-app-password"  # Use App Password, not regular password
```

### Requirements.txt
```txt
streamlit>=1.28.0
libsql_experimental>=0.10.0
bcrypt>=4.0.0
pandas>=2.0.0
openpyxl>=3.1.0
```

## Email Service
```python
# services/email_service.py
import smtplib
from email.mime.text import MimeText
from email.mime.multipart import MimeMultipart
import streamlit as st

def send_email(to_email, subject, body):
    """Send email using SMTP."""
    try:
        # Email configuration
        smtp_server = st.secrets["email"]["smtp_server"]
        smtp_port = st.secrets["email"]["smtp_port"]
        email_user = st.secrets["email"]["email_user"]
        email_password = st.secrets["email"]["email_password"]
        
        # Create message
        msg = MimeMultipart()
        msg['From'] = email_user
        msg['To'] = to_email
        msg['Subject'] = subject
        
        msg.attach(MimeText(body, 'html'))
        
        # Send email
        server = smtplib.SMTP(smtp_server, smtp_port)
        server.starttls()
        server.login(email_user, email_password)
        text = msg.as_string()
        server.sendmail(email_user, to_email, text)
        server.quit()
        
        return True
    except Exception as e:
        print(f"Error sending email: {e}")
        return False

def send_feedback_request_email(to_email, requester_name, app_url):
    """Send feedback request notification."""
    subject = "360° Feedback Request"
    body = f"""
    <h2>Feedback Request</h2>
    <p>Hello,</p>
    <p>{requester_name} has requested your feedback as part of their 360° performance review.</p>
    <p><a href="{app_url}">Click here to access the feedback form</a></p>
    <p>Thank you for your participation!</p>
    """
    return send_email(to_email, subject, body)

def send_reminder_email(to_email, pending_count, app_url):
    """Send reminder for pending reviews."""
    subject = "Reminder: Pending Feedback Reviews"
    body = f"""
    <h2>Pending Reviews Reminder</h2>
    <p>Hello,</p>
    <p>You have {pending_count} pending feedback review(s) waiting for completion.</p>
    <p><a href="{app_url}">Click here to complete your reviews</a></p>
    <p>Please complete them at your earliest convenience.</p>
    """
    return send_email(to_email, subject, body)
```

## Deployment Notes

1. **Turso Database Setup**: Create database with provided schema
2. **Employee Data Import**: Populate employees table with company data
3. **Role Assignment**: Assign appropriate roles to employees
4. **Email Configuration**: Set up SMTP credentials
5. **App Deployment**: Deploy to Streamlit Cloud with secrets configured

## Additional Features to Implement

1. **Anonymous Feedback Option**: Toggle for anonymous reviews
2. **Feedback Cycles**: Scheduled review periods
3. **Custom Questions**: Admin ability to modify questions
4. **Reporting**: PDF export of completed feedback
5. **Notifications**: In-app notification system
6. **Mobile Optimization**: Responsive design improvements

This specification provides a complete foundation for building a robust enterprise-grade 360-degree feedback application using the proven Streamlit + Turso architecture pattern.