# 360-Degree Feedback Application

A comprehensive enterprise-grade feedback management system built with Streamlit and Turso database.

## Overview

This application facilitates a performance review process where employees receive feedback from multiple sources - peers, subordinates, and supervisors - providing a "360-degree" view of their performance.

## Features

### Authentication System
- **First-time password setup** for new users
- **Secure password hashing** with bcrypt
- **Role-based access control** (employee, hr)

### Employee Features
- **Request Feedback** from up to 4 colleagues with automatic relationship assignment
- **Smart Restrictions** - cannot nominate direct manager, previously nominated reviewers, or overloaded reviewers
- **Flexible Nomination** - add reviewers one at a time, no need to nominate all at once
- **Automatic Relationship Detection** - system determines peer/stakeholder/reportee relationships
- **Nomination Status Tracking** - see approval status and completion progress for each nomination
- **Rejection Handling** - clear messaging for rejected nominations with ability to nominate replacements
- **Review Requests** - accept or decline feedback requests from colleagues with mandatory rejection reasons
- **View Anonymized Feedback** received from others
- **Complete Reviews** for colleagues with different question sets (only after accepting requests)
- **Excel Export** of personal feedback data
- **Draft Saving** for incomplete reviews

### Manager Features
- **Approve/Reject Nominations** from team members
- **Review Relationship Types** declared by requesters
- **Provide Rejection Reasons** when declining nominations
- **Reportees' Feedback (Anonymized)** — New: View anonymized feedback received by your direct reports, select a reportee to see their progress and responses, and export to Excel. Reviewer identities are hidden from managers.

### HR Dashboard
- **Create and Manage Review Cycles** with streamlined 2-phase timeline (nomination and feedback)
- **Advanced Deadline Management** - set overall cycle deadlines and extend deadlines for individual users
- **Deadline Enforcement** - auto-acceptance of pending nominations when deadline passes
- **Monitor Progress** with detailed user progress tracking across nomination and feedback phases
- **Send Reminder Emails** to users with pending reviews
- **View Analytics** and completion metrics
- **Bulk Reminder Management**
- **Reviewer Rejections** - monitor and review declined feedback requests with reasons

### Communication (Email Notifications) — New
- **Email Notifications Center**: Targeted emails with templates and preview
  - Notification types: nomination reminders, manager approvals, feedback reminders, deadline warnings, cycle completion, and custom messages
  - Audience targeting: all users, specific users, or by department
  - Templating: use variables like {name}, {email}, {cycle_name}, {nomination_deadline}, {feedback_deadline}, {pending_count}
  - Preview: live subject/body preview before sending
  - History: view previously sent notifications with basic details
- **Send Reminders**: One‑click bulk or individual reminders to users with pending reviews
- **SMTP Integration**: Uses `.streamlit/secrets.toml` for SMTP
- Note: Scheduling UI is present for selecting future date/time, but background scheduling/automation is not yet enabled; sends occur immediately when triggered from the app

### HR Admin Features
- **User Management** - add, activate/deactivate users
- **Role Assignment** - manage hr roles
- **Question Management** - customize feedback questions
- **System Configuration** - manage settings and preferences

## Installation & Setup

### Prerequisites
- Python 3.8+
- Turso database account

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Database Setup
The application connects to your Turso database using credentials in `.streamlit/secrets.toml`:

```toml
DB_URL = "libsql://your-database-url.turso.io"
AUTH_TOKEN = "your-turso-auth-token"

# Optional: Email configuration
[email]
smtp_server = "smtp.gmail.com"
smtp_port = 587
email_user = "your-email@company.com"
email_password = "your-app-password"
from_email = "hr@company.com"  # optional; defaults to email_user
```

### 3. Initialize Database
```bash
# Create database schema
python setup/create_schema.py

# Insert initial data (roles, questions, users)
python setup/simple_insert.py
```

### 4. Run Application
```bash
streamlit run main.py
```

 

## Role Structure

The system uses a simplified 2-role structure:

### HR Personnel (hr role)
- **Diana Gomes** (diana@projecttech4dev.org) - Full HR dashboard and administrative access
- **Additional HR Staff** - Can be assigned hr role for management capabilities
- **Access**: Organized into clear sections: Cycle Management, Activity Tracking, Feedback Management, Communication, Employee Management
- **Capabilities**: User management, cycle creation, system settings, analytics, all in professionally organized interface

### Employees (default role)
- **All other users** including Erica Arya, Donald Lobo, Vinod, and all staff members
- **Standard Features**: Request feedback, complete reviews, view results
- **Manager Functions**: Team leads and managers get additional "Approve Team Nominations" access based on designation
- **Automatic**: No special role assignment needed - default for all users

## Deadline Management System

### Streamlined Timeline
The feedback cycle now operates on a simplified 2-phase timeline:

1. **Nomination Phase**: Employees submit feedback requests and managers approve/reject them
2. **Feedback Phase**: Approved reviewers complete their feedback forms

**Removed phases**: Approval deadline and results deadline have been eliminated for simplicity.

### Deadline Enforcement
- **Nomination Deadline**: Once passed, employees cannot submit new requests
  - All pending manager approvals are automatically approved
  - All pending reviewer acceptances are automatically accepted
- **Feedback Deadline**: Once passed, reviewers cannot complete feedback forms
  - Results become available immediately after all feedback is collected

### Per-User Extensions
HR can extend deadlines for individual users when needed:
- **Individual Extensions**: Extend nomination or feedback deadlines for specific users
- **Reason Tracking**: All extensions require documentation
- **Override Capability**: Users with extensions can continue working past general deadlines

### Auto-Acceptance Logic
When the nomination deadline passes:
- Pending manager approvals → Automatically approved
- Pending reviewer responses → Automatically accepted as "yes"
- System logs all auto-accepted items for transparency

## First-Time Login

1. **Set Password**: New users should use "Set Password" to create their account
2. **Login**: Use email and password to access the system
3. **Navigation**: Role-based menu appears based on user permissions

## Nomination System Design

### Core Principles

**Flexible Nomination Process**: Unlike traditional systems that require all nominations at once, this application supports incremental nominations:

- **No Minimum Requirement**: Users can start with 1 reviewer if they choose
- **Maximum of 4**: Hard limit to prevent reviewer overload
- **Incremental Addition**: Add reviewers one at a time or in small groups
- **Status Visibility**: Clear tracking of each nomination's approval and completion status
- **Manager Approval**: Each nomination requires manager approval regardless of when submitted

### Automatic Relationship Mapping

The system automatically determines relationships based on organizational data:

**Mapping Rules**:
- **Same team + no reporting relationship** → **Peer**
- **Different teams** → **Internal Collaborator** 
- **Person reports to you** → **Direct Reportee**
- **Your direct manager** → **Blocked** (cannot nominate)

**No Manual Selection**: Users simply choose reviewers; the system handles relationship classification automatically.

### Nomination Workflow

1. **Employee selects reviewers** from available colleagues (1-4 total)
2. **System automatically maps relationships** based on organizational structure
3. **System validates** reviewer availability and prevents invalid selections
4. **Manager reviews and approves/rejects** each nomination
5. **Approved reviewers receive notification** to complete feedback
6. **Employee tracks progress** in real-time dashboard
7. **Results compiled** once feedback collection phase ends

### Benefits of This Approach

- **Reduces Pressure**: Employees don't need to identify all reviewers immediately
- **Improves Quality**: Thoughtful selection over time vs rushed decisions
- **Flexibility**: Adapt based on availability and workload changes
- **Better Tracking**: Clear visibility into each nomination's status
- **Manager Oversight**: Approval required for each nomination maintains quality control

## How to Use

### For Employees

1. **Request Feedback**
   - Select up to 4 colleagues total (can nominate one at a time)
   - System automatically determines relationships (peer/stakeholder/reportee) based on organizational structure
   - Cannot nominate direct manager or previously nominated reviewers  
   - View existing nominations with clear approval and completion status
   - Handle rejected nominations with clear messaging and replacement options
   - Submit individual or groups for manager approval
   - Track remaining nomination slots

2. **Complete Reviews**
   - View pending requests in "Reviews to Complete"
   - Answer relationship-specific questions
   - Save drafts or submit final responses

3. **View Results**
   - Access anonymized feedback in "My Feedback"
   - Download Excel reports
   - Track completion progress

### For Managers (Employee Role + Designation-based Access)

1. **Approve Team Nominations**
   - Automatically available to team leads and managers based on designation
   - Review direct reports' nomination requests
   - Approve or reject with clear reasons
   - Consider reviewer workload and automatically assigned relationships

### For HR (hr role)

1. **Cycle Management**
   - Create and manage review cycles with streamlined 2-phase deadlines
   - Access advanced deadline management page for per-user extensions
   - Monitor cycle progress and completion status
   - Complete cycles when ready

2. **Advanced Deadline Management** (New Feature)
   - **Manage Cycle Deadlines** - dedicated page for comprehensive deadline control
   - **Modify Overall Deadlines** - update nomination and feedback deadlines for entire cycle
   - **Extend Individual User Deadlines** - grant extensions to specific users with reason tracking
   - **Progress Overview** - detailed user progress tracking with accordions for nomination and feedback phases
   - **Auto-Acceptance Controls** - manually trigger auto-acceptance of expired nominations
   - **Color-Coded Status** - green for complete, yellow for pending, visual progress indicators

3. **Activity Tracking**
   - Overview dashboard with key performance indicators
   - User activity monitoring across all cycles
   - Comprehensive analytics and completion metrics

4. **Feedback Management**
   - View completed feedback and results
   - Monitor reviewer rejections with reasons
   - Track feedback quality and participation

5. **Communication**
   - Send email notifications and reminders
   - Configure deadline-specific messaging (updated for new deadline structure)
   - Bulk communication management

6. **Employee Management**
   - Manage user accounts and roles
   - Update employee information and assignments
   - System administration tasks

### For Employees (New Feature)

**Employee Dashboard** - New landing page showing:
- **Welcome Section** with personalized greeting
- **Current Cycle Information** with cycle name and description
- **Deadline Status** - visual indicators for nomination and feedback deadlines
- **Personal Progress Metrics** - requests submitted, awaiting approval, pending, completed
- **Quick Actions** - direct access to request feedback, provide feedback, view results
- **Pending Actions Required** - notifications for requests needing response or feedback to complete
- **Deadline Enforcement Notices** - clear messaging when deadlines have passed

## Nomination Status Tracking

The application provides comprehensive status tracking for each nomination with automatic relationship assignment:

### Status Types

**Approval Status**:
- **[Pending]** Awaiting manager approval
- **[Approved]** Manager has approved the nomination
- **[Rejected]** Manager rejected with reason provided (doesn't count toward 4-person limit)

**Completion Status**:
- **[Pending]** Waiting for reviewer to start
- **[In Progress]** Reviewer has started but not completed
- **[Completed]** Feedback submitted and final

**Relationship Types** (Automatically Assigned):
- **[Peer]** Same team, no reporting relationship
- **[Internal]** Cross-team collaborator, different teams
- **[Reportee]** Direct reports, people who report to you
- **[External]** External stakeholder outside organization
- **[Manager]** Direct manager, cannot be nominated (blocked)
- **[Nominated]** Already nominated, cannot nominate again (greyed out)

### Dashboard Features

- **Real-time Updates**: Status changes immediately when manager approves or reviewer submits
- **Detailed Information**: See reviewer name, designation, relationship type, and nomination date
- **Progress Tracking**: Visual indicators for approval and completion status
- **Remaining Slots**: Clear indication of how many more reviewers can be nominated
- **Flexible Timing**: Add new nominations throughout the nomination phase

## Question Sets by Relationship Type

### Peers/Internal Stakeholders/Managers
- Collaboration, Communication, Reliability, Ownership ratings
- Open feedback on strengths and improvement areas

### Direct Reportees (Leadership Evaluation)
- Approachability, Openness to feedback, Clarity, Communication ratings
- Leadership effectiveness feedback

### External Stakeholders

External stakeholders can be nominated by employees (subject to manager approval), receive a secure email token, and provide feedback without needing to “accept” the request in-app.

- Manager Approval: External nominations go through the normal manager approval workflow.
- Invitations: After approval, the system emails a secure token to the external stakeholder.
- External Login: They authenticate via email + token on the External Stakeholder Login page.
- Minimal UI: They only see the feedback deadline and a “Provide Feedback” action; they do not see any “Request Feedback” features.
- No Acceptance Step: Their request is considered accepted upon token login so they can go straight to the form.
- Anonymity: Their identity is not shown to the requester or the requester’s manager in results.

### Eligibility Rules — New
- Date of Joining (DOJ) policy drives who can request or give feedback:
  - Joined on/before 2025-09-30: Eligible to request feedback and be invited to give feedback
  - Joined after 2025-09-30: Can be invited to give feedback once tenure >= 3 months; cannot request feedback
  - Missing DOJ: Not blocked by default (configurable policy)
- Reviewer selection lists only include users eligible to give feedback per the above rules.
- The “Request Feedback” page is only available to users eligible to request per the above rules.
- Professionalism, Reliability, Responsiveness, Understanding ratings
- Quality of delivery and collaboration examples

## Security Features

- **Password Hashing**: Secure bcrypt encryption
- **Role-Based Access**: Granular permission control
- **Anonymized Feedback**: Reviewers remain anonymous to requesters and their managers; HR can access named views for auditing
- **Nomination Limits**: Prevents reviewer overload (max 4 requests per person)
- **Rejection Tracking**: Prevents re-nomination of rejected reviewers

## Workflow Timeline

### Phase 1: Nomination Phase (Week 1)
- **Flexible Nomination Window**: Employees can nominate reviewers throughout the phase
- **Progressive Submission**: Add 1-4 reviewers individually or in groups as desired
- **Real-time Validation**: System immediately validates reviewer availability and relationship appropriateness
- **Status Dashboard**: Live tracking of nomination progress and remaining slots
- **No Pressure Approach**: Quality over speed - thoughtful selection encouraged

### Phase 2: Manager Approval Phase (Week 2)  
- **Rolling Approval**: Managers can approve nominations as they come in
- **Detailed Review**: Each nomination includes context and relationship justification
- **Rejection Handling**: Clear reasons provided for rejected nominations
- **Bulk Operations**: Managers can approve multiple nominations efficiently
- **Immediate Notifications**: Approved nominations immediately activate for reviewers

### Phase 3: Feedback Collection Phase (Weeks 3-5)
- **Reviewer Notifications**: Approved reviewers receive immediate feedback requests
- **Progressive Collection**: Early nominations can begin feedback while others are still being approved
- **Draft System**: Reviewers can save partial responses and complete later
- **Reminder System**: Automated reminders for pending reviews
- **Status Tracking**: Real-time completion progress visible to all stakeholders

### Phase 4: Results Processing Phase (Week 5)
- **Continuous Compilation**: Completed feedback processed as soon as submitted
- **Early Access**: Results available for completed reviewers immediately
- **Final Reports**: Comprehensive feedback compilation at phase end
- **Export Capabilities**: Individual and administrative reports available
- **Cycle Analytics**: Performance metrics and completion analysis

## Advanced Features

### Nomination Management

**Smart Validation**:
- **Automatic Relationship Detection**: System determines relationships based on organizational structure
  - **[Peer]** Same team, no direct reporting relationship
  - **[Internal]** Different teams, no direct reporting relationship  
  - **[Reportee]** People who report directly to you
  - **[External]** People outside the organization
- Prevents duplicate nominations within the same cycle
- Blocks nomination of direct manager (shown with [Manager] indicator)
- Validates reviewer availability and workload limits
- Checks external stakeholder permissions based on user level
- Handles rejected nominations with clear messaging and replacement options

**Manager Approval Workflow**:
- Centralized approval interface for managers
- Detailed nomination context and reasoning
- Bulk approval capabilities for efficiency
- Rejection reasons logged for feedback

**Real-time Status Updates**:
- Live dashboard showing all nomination statuses
- Email notifications for status changes
- Progress tracking across entire review cycle
- Automated reminders for pending actions

### Data Management

**Nomination History**:
- Complete audit trail of all nominations
- Rejection tracking to prevent re-nomination
- Cycle-by-cycle historical view
- Performance analytics across cycles

**Export Capabilities**:
- Excel export of individual feedback results
- Admin reports on nomination patterns
- Cycle completion analytics
- Manager approval efficiency metrics

## Technical Architecture

- **Frontend**: Streamlit with role-based navigation
- **Database**: Turso (SQLite-compatible) with connection pooling
- **Authentication**: bcrypt password hashing + session management
- **Email**: SMTP integration for notifications
- **Export**: Excel generation with openpyxl

## Developer Guide

- App entry: `main.py` defines role-based navigation and sidebar menu.
- Authentication: `login.py` sets `st.session_state['authenticated']`, `user_data`, and roles (via `services/auth_service.py`).
- Database: Turso (SQLite) via `libsql_experimental`. All DB helpers live in `services/db_helper.py`.
- Key data model tables:
  - `users`: includes `date_of_joining` (DATE), `vertical`, `designation`, `reporting_manager_email`.
  - `review_cycles`: active cycle with `nomination_deadline`, `feedback_deadline`.
  - `feedback_requests`: one per nomination; tracks `approval_status`, `reviewer_status`, `status` and external fields.
  - `feedback_responses`: final submitted answers.
  - `draft_responses`: in-progress saves.
  - `external_stakeholder_tokens`: token + status for external reviewers.
  - `email_logs`: minimal history of notifications.
- Eligibility logic:
  - Requesters: `services/db_helper.can_user_request_feedback(user_id)` controls visibility/access to the Request page.
  - Reviewers: `services/db_helper.get_users_for_selection` filters eligible reviewers based on DOJ and tenure.
- External stakeholders:
  - Token is generated and emailed only after manager approval.
  - Token login auto-accepts and routes to feedback form.
- Manager tools:
  - Approve team nominations.
  - View reportees’ anonymized feedback (`pages/reportees_feedback.py`).
- HR tools:
  - `pages/completed_feedback.py` provides named views of completed feedback.
  - Notifications center + reminders under Communication.

Known considerations
- Align `email_logs` schema with runtime fields (this repo’s `setup/create_schema.py` is already aligned).
- Missing DOJ is treated as “not blocked” for now; set it in DB to enforce strict eligibility.
- Excel export requires `openpyxl` (included in requirements).

## File Structure

```
feedback_app/
├── main.py                          # Main app with professional navigation
├── login.py                         # Authentication page
├── requirements.txt                 # Python dependencies
├── services/
│   ├── db_helper.py                # Database operations
│   ├── auth_service.py             # Authentication logic
│   └── email_service.py            # Email notifications
├── screens/
│   ├── employee/                   # Employee interface
│   │   ├── request_feedback.py     # Nomination system
│   │   ├── my_reviews.py           # Complete reviews (merged section)
│   │   ├── review_requests.py      # Accept/decline requests
│   │   └── my_feedback.py          # View received feedback
│   ├── hr/                         # HR interface (professionally organized)
│   │   ├── dashboard.py            # Cycle management (clean interface)
│   │   ├── overview_dashboard.py   # Activity tracking metrics
│   │   ├── user_activity.py        # User activity monitoring
│   │   ├── completed_feedback.py   # Feedback management
│   │   ├── reviewer_rejections.py  # Rejection tracking
│   │   └── manage_employees.py     # Employee management
├── pages/
│   ├── email_notifications.py      # Email Notifications Center (HR > Communication)
│   ├── send_reminders.py           # Bulk/individual reminders (HR > Communication)
│   ├── reportees_feedback.py       # Managers: view reportees' anonymized feedback
│   └── external_auth.py            # External stakeholder login (email + token)
├── setup/                          # Database setup & utilities
├── testing/                        # Automated testing with MCP
├── docs/                           # Documentation
└── .streamlit/
    └── secrets.toml                # Database & email config

## Email Notifications Details

- Navigation: HR role → Communication → Email Notifications / Send Reminders
- SMTP Setup: configure `[email]` in `.streamlit/secrets.toml` (SendGrid, Gmail, etc.)
  
- Email Logs: The app maintains a lightweight `email_logs` table for history. If you initialized your DB before this feature, run `python setup/create_schema.py` to add it.
- Limitations: The "schedule for later" controls are UI-only for now; background scheduling/cron is not yet wired up.
```

## Deployment

### Streamlit Cloud
1. Push code to GitHub repository
2. Connect Streamlit Cloud to repository
3. Add secrets in Streamlit Cloud dashboard
4. Deploy application

### Environment Variables
Required secrets:
- `DB_URL`: Turso database URL
- `AUTH_TOKEN`: Turso authentication token
- `email.*`: SMTP configuration (optional)

## Testing

### Automated Testing with Claude + MCP

This project includes comprehensive automated testing using Claude with MCP browser automation:

```bash
# Ensure Claude Desktop has Playwright MCP configured
# Then tell Claude: "Read and execute testing/AUTOMATED_TESTING_PLAN.md"
```

The automated testing covers:
- **Authentication** for all user roles
- **Complete workflows** (feedback requests, approvals, reviews)
- **HR dashboard** and management features
- **Super admin** functionality
- **Error handling** and edge cases
- **Email integration** (with human coordination)

See `testing/README.md` for detailed testing instructions.

## Support & Troubleshooting

### Common Issues

1. **Database Connection Errors**
   - Verify Turso credentials in secrets.toml
   - Check network connectivity

2. **Login Problems**
   - Use "Set Password" for first-time users
   - Verify email exists in users table

3. **Email Issues**
   - Configure SMTP settings in secrets.toml
   - Use app-specific passwords for Gmail

### Admin Tasks

- **Add New Users**: Use Administration > User Management (HR only)
- **Assign HR Roles**: Use Management > Manage Employees (HR only)
- **Create Cycles**: Use Dashboard > Create New Review Cycle (HR only)
  

## License

Internal use only - ProjectTech4Dev Organization

---

For technical support, contact your system administrator.
