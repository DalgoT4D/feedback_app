import streamlit as st
import base64  # Import base64
from services.db_helper import get_manager_level_from_designation, has_direct_reports

st.set_page_config(
    page_title="360° Feedback Application",
    page_icon="assets/favicon.png",
    layout="wide",
)

# Custom CSS for styling
st.markdown(
    """
<style>
@import url('https://fonts.googleapis.com/css2?family=Lato:wght@300;400&display=swap');

/* Adjust sidebar styling */
[data-testid="stSidebar"] { /* Targets sidebar container */
    background-color: #f0f2f6; /* Lighter background for sidebar */
    margin-top: 60px; /* Adjust sidebar to start below the fixed header */
}

/* Hide Streamlit's default header/toolbar */
[data-testid="stHeader"] {
    visibility: hidden;
    height: 0px;
}

/* Adjust sidebar collapse button position */
[data-testid="stSidebarCollapseButton"] {
    top: 60px !important; /* Push it down below the fixed header */
}

/* Main title styling */
h1 {
    color: #1E4796; /* Blue for page titles */
}

/* Subheader styling */
h2, h3, h4 {
    color: #E55325; /* Orange for subheadings */
}

/* Button primary color */
[data-testid="stForm"] button[kind="primary"] { /* Primary button class */
    background-color: #1E4796;
    color: white;
    border-color: #1E4796;
}
[data-testid="stForm"] button[kind="primary"]:hover {
    background-color: #E55325; /* Orange on hover */
    border-color: #E55325;
}

/* Links/secondary buttons */
a, [data-testid="baseButton-secondary"] {
    color: #E55325; /* Orange specified by user */
}
[data-testid="baseButton-secondary"]:hover {
    background-color: #FFFAF8 !important; /* Light background to make orange pop */
}


/* Info and Warning boxes */
[data-testid="stAlert"] [data-testid="stMarkdownContainer"] p {
    color: #333333; /* Darker text for readability in alerts */
}
[data-testid="stAlert"].st-emotion-cache-fk9g0f.e1aec7752 { /* Target st.info block */
    background-color: rgba(30, 71, 150, 0.1); /* Light blue background */
    border-left: 5px solid #1E4796;
}
[data-testid="stAlert"].st-emotion-cache-fk9g0f.e1aec7751 { /* Target st.warning block */
    background-color: rgba(229, 83, 37, 0.1); /* Light orange background */
    border-left: 5px solid #E55325;
}


/* Website-wide header */
.main-header {
    background-color: #1E4796; /* Dark blue background for header */
    padding: 10px 20px;
    display: flex;
    align-items: center;
    gap: 15px; /* Space between logo and title */
    color: white;
    box-shadow: 0 2px 4px rgba(0,0,0,0.1);
    position: fixed; /* Fix header at the top */
    top: 0;
    left: 0;
    width: 100%;
    z-index: 1000; /* Ensure it's above other content */
}

.main-header img {
    height: 40px; /* Adjust logo size */
    width: auto;
}

/* Add CSS for the new spacer */
.header-spacer {
    flex-grow: 1;
}

.main-header h2 {
    color: white;
    margin: 0;
    font-size: 2.2em; /* Larger font for the title */
    font-family: 'Lato', sans-serif; /* Elegant font */
    font-weight: 300; /* Thinner font weight */
}

/* Adjust main content area to prevent overlap with fixed header */
[data-testid="stAppViewContainer"] {
    padding-top: 60px; /* Adjust based on header height (10px + 40px + 10px) */
}

/* Add a subtle shadow for depth to entire app */
.st-emotion-cache-bm2z6j { /* Targets main app container */
    box-shadow: 0 4px 8px rgba(0, 0, 0, 0.1);
}

</style>
""",
    unsafe_allow_html=True,
)

# Website-wide header
if st.session_state.get("authenticated"):  # Only show header if authenticated
    st.markdown(
        f"""
        <div class="main-header">
            <img src="data:image/png;base64,{base64.b64encode(open("assets/logo.png", "rb").read()).decode("utf-8")}" alt="Logo">
            <div class="header-spacer"></div> <!-- Spacer for centering -->
            <h2>360° Feedback Application</h2>
            <div class="header-spacer"></div> <!-- Spacer for centering -->
        </div>
        """,
        unsafe_allow_html=True,
    )


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
    "Logout": st.Page(logout, title="Log out", icon=":material/logout:"),
}

# Role-based sections
if st.session_state["authenticated"]:
    st.sidebar.write(
        f"Logged in as: {st.session_state['user_data']['first_name']} {st.session_state['user_data']['last_name']}"
    )

    if has_role("hr"):
        # HR - Clean organized sections for HR professional
        nav_sections = {
            "Cycle Management": [
                st.Page(
                    "pages/hr_dashboard.py",
                    title="Cycle Management",
                    icon=":material/dashboard:",
                ),
            ],
            "Activity Tracking": [
                st.Page(
                    "pages/overview_dashboard.py",
                    title="Overview Dashboard",
                    icon=":material/analytics:",
                ),
                st.Page(
                    "pages/user_activity.py",
                    title="User Activity",
                    icon=":material/people_alt:",
                ),
                st.Page(
                    "pages/completed_feedback.py",
                    title="Completed Feedback",
                    icon=":material/feedback:",
                ),
            ],
            "Feedback Management": [
                st.Page(
                    "pages/admin_overview.py",
                    title="All Reviews & Requests",
                    icon=":material/view_list:",
                ),
                st.Page(
                    "pages/reviewer_rejections.py",
                    title="Reviewer Rejections",
                    icon=":material/block:",
                ),
            ],
            "Communication": [
                st.Page(
                    "pages/email_notifications.py",
                    title="Email Notifications",
                    icon=":material/mail:",
                ),
                st.Page(
                    "pages/send_reminders.py",
                    title="Send Reminders",
                    icon=":material/notification_important:",
                ),
            ],
            "Employee Management": [
                st.Page(
                    "pages/manage_employees.py",
                    title="Manage Employees",
                    icon=":material/people:",
                ),
            ],
            "Admin Tools": [  # New section for admin pages
                st.Page(
                    "pages/system_overview.py",
                    title="System Overview",
                    icon=":material/monitor_heart:",
                ),
                st.Page(
                    "pages/system_settings.py",
                    title="System Settings",
                    icon=":material/settings:",
                ),
                st.Page(
                    "pages/user_management.py",
                    title="User Management",
                    icon=":material/manage_accounts:",
                ),
            ],
            "Provide Feedback": [
                st.Page(
                    "pages/review_requests.py",
                    title="Review Requests",
                    icon=":material/how_to_reg:",
                ),
                st.Page(
                    "pages/my_reviews.py",
                    title="Complete Reviews",
                    icon=":material/assignment:",
                ),
            ],
            "Get Feedback": [
                st.Page(
                    "pages/request_feedback.py",
                    title="Request Feedback",
                    icon=":material/rate_review:",
                ),
                st.Page(
                    "pages/current_feedback.py",
                    title="Current Feedback",
                    icon=":material/feedback:",
                ),
                st.Page(
                    "pages/previous_feedback.py",
                    title="Previous Feedback",
                    icon=":material/history:",
                ),
            ],
            "Account": [pages["Logout"]],
        }
        user_data = st.session_state.get("user_data", {})
        manager_level = get_manager_level_from_designation(
            user_data.get("designation", "")
        )
        # Only show "Approve Nominations" if user is a manager AND has direct reports
        if manager_level >= 1 and has_direct_reports(user_data.get("email")):
            nav_sections["Cycle Management"].append(
                st.Page(
                    "pages/approve_nominations.py",
                    title="Approve Nominations",
                    icon=":material/approval:",
                )
            )

        pg = st.navigation(nav_sections)
    else:
        # Regular employee + managers (for approval functions)
        nav_sections = {
            "Provide Feedback": [
                st.Page(
                    "pages/review_requests.py",
                    title="Review Requests",
                    icon=":material/how_to_reg:",
                ),
                st.Page(
                    "pages/my_reviews.py",
                    title="Complete Reviews",
                    icon=":material/assignment:",
                ),
            ],
            "Get Feedback": [
                st.Page(
                    "pages/request_feedback.py",
                    title="Request Feedback",
                    icon=":material/rate_review:",
                ),
                st.Page(
                    "pages/current_feedback.py",
                    title="Current Feedback",
                    icon=":material/feedback:",
                ),
                st.Page(
                    "pages/previous_feedback.py",
                    title="Previous Feedback",
                    icon=":material/history:",
                ),
            ],
            "Account": [pages["Logout"]],
        }

        # Add manager approval for team leads and above
        user_data = st.session_state.get("user_data", {})
        manager_level = get_manager_level_from_designation(
            user_data.get("designation", "")
        )
        # Only show "Approve Team Nominations" if user is a manager AND has direct reports
        if manager_level >= 1 and has_direct_reports(user_data.get("email")):  # Team Lead or above
            nav_sections["Team Management"] = [
                st.Page(
                    "pages/approve_nominations.py",
                    title="Approve Team Nominations",
                    icon=":material/approval:",
                ),
            ]

        pg = st.navigation(nav_sections)
else:
    # Not authenticated - login only
    pg = st.navigation([pages["Login"]])

pg.run()
