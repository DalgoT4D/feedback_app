import streamlit as st
import base64  # Import base64
from pathlib import Path
from services.db_helper import (
    get_manager_level_from_designation,
    has_direct_reports,
    get_active_review_cycle,
    can_user_request_feedback,
)
from datetime import datetime, date

st.set_page_config(
    page_title="Insight 360°",
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

/* Main title styling - more specific selectors for Streamlit Cloud */
.main h1, [data-testid="stMarkdownContainer"] h1, .stMarkdown h1 {
    color: #1E4796 !important; /* Blue for page titles */
}

/* Subheader styling - more specific selectors for Streamlit Cloud */
.main h2, [data-testid="stMarkdownContainer"] h2, .stMarkdown h2,
.main h3, [data-testid="stMarkdownContainer"] h3, .stMarkdown h3,
.main h4, [data-testid="stMarkdownContainer"] h4, .stMarkdown h4 {
    color: #E55325 !important; /* Orange for subheadings */
}

/* Also target streamlit's title element */
[data-testid="element-container"] h1 {
    color: #1E4796 !important;
}

[data-testid="element-container"] h2,
[data-testid="element-container"] h3, 
[data-testid="element-container"] h4 {
    color: #E55325 !important;
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

/* Create orange dot using CSS background on navigation items with bullets */
/* This uses a more direct approach - target all sidebar navigation and use regex-like CSS */

/* Method 1: Use attribute selectors to target links containing bullet character */
[data-testid="stSidebar"] a[href][title*="•"] {
    position: relative;
}

[data-testid="stSidebar"] a[href][title*="•"]::after {
    content: '';
    position: absolute;
    right: 8px;
    top: 50%;
    transform: translateY(-50%);
    width: 6px;
    height: 6px;
    background-color: #E55325;
    border-radius: 50%;
    z-index: 10;
}

/* Method 2: Global text replacement using CSS */
/* Replace bullets with orange ones using text-shadow */
[data-testid="stSidebar"] {
    --badge-color: #E55325;
}

/* Method 3: Use text-decoration and pseudo-elements to overlay orange dots */
[data-testid="stSidebar"] a[href*="bullet-indicator"] {
    color: #E55325 !important;
}

/* Force orange color on bullet spans with maximum specificity */
[data-testid="stSidebar"] span[style*="color: #E55325"] {
    color: #E55325 !important;
    font-weight: bold !important;
}

/* Override all navigation text color specifically for bullets */
[data-testid="stSidebar"] [data-testid="stSidebarNavLink"] span[style*="#E55325"] {
    color: #E55325 !important;
}

/* Nuclear option - target any span containing bullet character */
span:has-text("•") {
    color: #E55325 !important;
}

/* Most specific selector for Streamlit navigation bullets */
[data-testid="stSidebar"] [data-testid="stSidebarNavLink"] span {
    color: inherit;
}

[data-testid="stSidebar"] [data-testid="stSidebarNavLink"] span[style] {
    color: #E55325 !important;
}

/* Class-based approach for maximum compatibility */
.orange-bullet {
    color: #E55325 !important;
    font-weight: bold !important;
}

/* Ultra-specific selector for orange bullets */
[data-testid="stSidebar"] .orange-bullet {
    color: #E55325 !important;
    font-weight: bold !important;
}

/* Override any inherited colors */
[data-testid="stSidebar"] span.orange-bullet {
    color: #E55325 !important;
    font-weight: bold !important;
}

/* Try to target the special bracket characters */
[data-testid="stSidebar"] a[href*="⟨"] {
    color: inherit;
    position: relative;
}

[data-testid="stSidebar"] a[href*="⟨"]::after {
    content: attr(title);
    position: absolute;
    color: #E55325;
    font-weight: bold;
}

/* Alternative - try CSS text replacement */
[data-testid="stSidebar"] {
    --badge-color: #E55325;
    color: var(--badge-color);
}

/* Use advanced CSS selectors to target badge text */
[data-testid="stSidebar"] [data-testid="stSidebarNavLink"]:contains("⟨") {
    color: #E55325 !important;
}

/* Clean badge styling - no special formatting needed */

</style>
""",
    unsafe_allow_html=True,
)

# Website-wide header
if st.session_state.get("authenticated"):  # Only show header if authenticated
    # Safe logo loading with error handling
    try:
        with open("assets/logo.png", "rb") as f:
            logo_b64 = base64.b64encode(f.read()).decode("utf-8")
        logo_html = f'<img src="data:image/png;base64,{logo_b64}" alt="Logo">'
    except FileNotFoundError:
        logo_html = '<div style="width: 40px; height: 40px; background-color: #1E4796; border-radius: 5px;"></div>'

    st.markdown(
        f"""
        <div class="main-header">
            {logo_html}
            <div class="header-spacer"></div> <!-- Spacer for centering -->
            <h2>Insight 360°</h2>
            <div class="header-spacer"></div> <!-- Spacer for centering -->
        </div>
        """,
        unsafe_allow_html=True,
    )


# Logout functionality moved to logout.py


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
    "External_Feedback": st.Page(
        "app_pages/external_feedback.py",
        title="External Feedback",
        icon=":material/rate_review:",
    ),
    "Logout": st.Page("logout.py", title="Log out", icon=":material/logout:"),
}


# Role-based sections
def _parse_date(date_value):
    """Normalize date strings/objects into date."""
    if isinstance(date_value, date):
        return date_value
    if isinstance(date_value, str):
        try:
            return datetime.strptime(date_value, "%Y-%m-%d").date()
        except ValueError:
            return None
    return None


BADGES_ENABLED = False  # Temporarily disable badges to isolate navigation issues

BADGES_ENABLED = True  # Re-enable lightweight badges in native sidebar


def _badge_title(title: str, has_incomplete_actions: bool) -> str:
    """Append badge using simple binary system - diamond for incomplete actions."""
    if not BADGES_ENABLED:
        return title
    if has_incomplete_actions:
        return f"{title} 🔸"
    return title


# Badge utility functions moved to utils/badge_utils.py to avoid circular imports
from utils.badge_utils import get_smart_badge_status


if st.session_state["authenticated"]:
    user_data = st.session_state.get("user_data", {})
    user_id = user_data.get("user_type_id")

    # Use smart badge status with local state overrides - extended cache for performance
    cache_key = f"badge_status_{user_id}"
    if cache_key not in st.session_state or st.session_state.get(
        "badge_cache_time", 0
    ) < (datetime.now().timestamp() - 120):
        # Get smart badge status (uses local state + fallback to DB)
        smart_status = get_smart_badge_status(user_id)

        # Convert to page-specific badge status
        badge_status = {}

        # Request Feedback badge - check if nominations are incomplete
        active_cycle = get_active_review_cycle()
        if user_id and active_cycle:
            nomination_deadline = _parse_date(active_cycle.get("nomination_deadline"))
            today = date.today()
            if nomination_deadline and today <= nomination_deadline:
                badge_status["Request Feedback"] = smart_status[
                    "has_incomplete_nominations"
                ]
            else:
                badge_status["Request Feedback"] = False
        else:
            badge_status["Request Feedback"] = False

        # Review-related badges
        badge_status["Review Requests"] = smart_status["has_pending_reviewer_requests"]
        badge_status["Provide Feedback"] = smart_status["has_pending_feedback_forms"]

        # Approval badges for managers
        user_manager_level = get_manager_level_from_designation(
            user_data.get("designation", "")
        )
        user_has_reports = has_direct_reports(user_data.get("email"))
        if user_manager_level >= 1 and user_has_reports:
            badge_status["Approve Nominations"] = smart_status[
                "has_incomplete_approvals"
            ]
            badge_status["Approve Team Nominations"] = smart_status[
                "has_incomplete_approvals"
            ]
        else:
            badge_status["Approve Nominations"] = False
            badge_status["Approve Team Nominations"] = False

        # Cache the smart binary status
        st.session_state[cache_key] = badge_status
        st.session_state["badge_cache_time"] = datetime.now().timestamp()
        st.session_state["user_manager_level"] = user_manager_level
        st.session_state["user_has_reports"] = user_has_reports
        st.session_state["active_cycle"] = active_cycle
    else:
        # Use cached smart status
        badge_status = st.session_state[cache_key]
        user_manager_level = st.session_state.get("user_manager_level", 0)
        user_has_reports = st.session_state.get("user_has_reports", False)
        active_cycle = st.session_state.get("active_cycle")

    if has_role("hr"):
        nav_sections = {
            "Cycle Management": [
                st.Page(
                    "app_pages/hr_dashboard.py",
                    title=_badge_title(
                        "Cycle Management", False
                    ),  # No badges for HR admin pages
                    icon=":material/dashboard:",
                ),
                st.Page(
                    "app_pages/manage_cycle_deadlines.py",
                    title=_badge_title("Manage Cycle Deadlines", False),
                    icon=":material/schedule:",
                ),
            ],
            "Activity Tracking": [
                st.Page(
                    "app_pages/overview_dashboard.py",
                    title=_badge_title("Overview Dashboard", False),
                    icon=":material/analytics:",
                ),
                st.Page(
                    "app_pages/user_activity.py",
                    title=_badge_title("User Activity", False),
                    icon=":material/people_alt:",
                ),
                st.Page(
                    "app_pages/completed_feedback.py",
                    title=_badge_title("Completed Feedback", False),
                    icon=":material/feedback:",
                ),
                st.Page(
                    "app_pages/reviewer_rejections.py",
                    title=_badge_title("Reviewer Rejections", False),
                    icon=":material/block:",
                ),
                st.Page(
                    "app_pages/data_exports.py",
                    title=_badge_title("Data Exports", False),
                    icon=":material/download:",
                ),
            ],
            "Communication": [
                st.Page(
                    "app_pages/email_notifications.py",
                    title=_badge_title("Email Notifications", False),
                    icon=":material/mail:",
                ),
                st.Page(
                    "app_pages/notification_history.py",
                    title=_badge_title("Notification History", False),
                    icon=":material/history:",
                ),
            ],
            "Employee Management": [
                st.Page(
                    "app_pages/manage_employees.py",
                    title=_badge_title("Manage Employees", False),
                    icon=":material/people:",
                ),
            ],
            "Provide Feedback": [
                st.Page(
                    "app_pages/review_requests.py",
                    title=_badge_title(
                        "Review Requests", badge_status.get("Review Requests", False)
                    ),
                    icon=":material/how_to_reg:",
                ),
                st.Page(
                    "app_pages/my_reviews.py",
                    title=_badge_title(
                        "Provide Feedback", badge_status.get("Provide Feedback", False)
                    ),
                    icon=":material/assignment:",
                ),
            ],
            "Get Feedback": [
                *(
                    [
                        st.Page(
                            "app_pages/request_feedback.py",
                            title=_badge_title(
                                "Request Feedback",
                                badge_status.get("Request Feedback", False),
                            ),
                            icon=":material/rate_review:",
                        )
                    ]
                    if can_user_request_feedback(user_id)
                    else []
                ),
                st.Page(
                    "app_pages/current_nominations.py",
                    title=_badge_title("Current Nominations", False),
                    icon=":material/playlist_add_check:",
                ),
                st.Page(
                    "app_pages/current_feedback.py",
                    title=_badge_title(
                        "Current Cycle Feedback", False
                    ),  # No action needed on this page
                    icon=":material/feedback:",
                ),
                st.Page(
                    "app_pages/previous_feedback.py",
                    title=_badge_title(
                        "Previous Cycle Feedback", False
                    ),  # No action needed on this page
                    icon=":material/history:",
                ),
            ],
            "Account": [pages["Logout"]],
        }
        if user_manager_level >= 1 and user_has_reports:
            nav_sections["Cycle Management"].append(
                st.Page(
                    "app_pages/approve_nominations.py",
                    title=_badge_title(
                        "Approve Nominations",
                        badge_status.get("Approve Nominations", False),
                    ),
                    icon=":material/approval:",
                )
            )
            nav_sections.setdefault("Team Management", [])
            nav_sections["Team Management"].append(
                st.Page(
                    "app_pages/reportees_feedback.py",
                    title=_badge_title(
                        "Reportees' Feedback", False
                    ),  # No action needed on this page
                    icon=":material/people:",
                )
            )
    else:
        # Build sections in order; place Team Management before Account
        nav_sections = {
            "Provide Feedback": [
                st.Page(
                    "app_pages/review_requests.py",
                    title=_badge_title(
                        "Review Requests", badge_status.get("Review Requests", False)
                    ),
                    icon=":material/how_to_reg:",
                ),
                st.Page(
                    "app_pages/my_reviews.py",
                    title=_badge_title(
                        "Provide Feedback", badge_status.get("Provide Feedback", False)
                    ),
                    icon=":material/assignment:",
                ),
            ],
            "Get Feedback": [
                *(
                    [
                        st.Page(
                            "app_pages/request_feedback.py",
                            title=_badge_title(
                                "Request Feedback",
                                badge_status.get("Request Feedback", False),
                            ),
                            icon=":material/rate_review:",
                        )
                    ]
                    if can_user_request_feedback(user_id)
                    else []
                ),
                st.Page(
                    "app_pages/current_nominations.py",
                    title=_badge_title("Current Nominations", False),
                    icon=":material/playlist_add_check:",
                ),
                st.Page(
                    "app_pages/current_feedback.py",
                    title=_badge_title(
                        "Current Cycle Feedback", False
                    ),  # No action needed on this page
                    icon=":material/feedback:",
                ),
                st.Page(
                    "app_pages/previous_feedback.py",
                    title=_badge_title(
                        "Previous Cycle Feedback", False
                    ),  # No action needed on this page
                    icon=":material/history:",
                ),
            ],
        }
        if user_manager_level >= 1 and user_has_reports:
            nav_sections["Team Management"] = [
                st.Page(
                    "app_pages/approve_nominations.py",
                    title=_badge_title(
                        "Approve Team Nominations",
                        badge_status.get("Approve Team Nominations", False),
                    ),
                    icon=":material/approval:",
                ),
                st.Page(
                    "app_pages/reportees_feedback.py",
                    title=_badge_title(
                        "Reportees' Feedback", False
                    ),  # No action needed on this page
                    icon=":material/people:",
                ),
            ]
        # Append Account last so logout stays at bottom
        nav_sections["Account"] = [pages["Logout"]]

    # Render built-in sidebar navigation for stability
    pg = st.navigation(nav_sections, position="sidebar")
    current_page_title = pg.title
else:
    # Not authenticated - login and external feedback access
    # Hide sidebar for unauthenticated users
    st.markdown(
        """
        <style>
        [data-testid="stSidebar"] {
            display: none;
        }
        [data-testid="stSidebarCollapseButton"] {
            display: none;
        }
        </style>
    """,
        unsafe_allow_html=True,
    )
    pg = st.navigation([pages["Login"], pages["External_Feedback"]], position="sidebar")

pg.run()
