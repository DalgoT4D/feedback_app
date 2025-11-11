import streamlit as st
from services.db_helper import get_connection

st.title("User Management")

st.info("Advanced user management functionality")

# Add new user functionality
st.subheader("Add New User")

with st.form("add_user_form"):
    col1, col2 = st.columns(2)

    with col1:
        first_name = st.text_input("First Name*")
        last_name = st.text_input("Last Name*")
        email = st.text_input("Email Address*")

    with col2:
        vertical = st.text_input("Department/Vertical")
        designation = st.text_input("Designation")
        reporting_manager_email = st.text_input("Reporting Manager Email")

    submit_new_user = st.form_submit_button("Add User", type="primary")

    if submit_new_user:
        if first_name and last_name and email:
            conn = get_connection()
            try:
                # Check if email already exists
                check_query = "SELECT COUNT(*) FROM users WHERE email = ?"
                result = conn.execute(check_query, (email,))
                if result.fetchone()[0] > 0:
                    st.error("[Error] Email already exists in the system")
                else:
                    # Insert new user
                    insert_query = """
                        INSERT INTO users (first_name, last_name, email, vertical, designation, reporting_manager_email)
                        VALUES (?, ?, ?, ?, ?, ?)
                    """
                    cursor = conn.cursor()
                    cursor.execute(
                        insert_query,
                        (
                            first_name,
                            last_name,
                            email,
                            vertical,
                            designation,
                            reporting_manager_email,
                        ),
                    )

                    # Get the new user ID
                    user_id = cursor.lastrowid

                    # Assign default employee role
                    role_query = (
                        "INSERT INTO user_roles (user_type_id, role_id) VALUES (?, 3)"
                    )
                    conn.execute(role_query, (user_id,))

                    conn.commit()
                    st.success(f"[Success] User added successfully!")
                    st.info("User will need to set up their password on first login.")
            except Exception as e:
                st.error(f"[Error] Error adding user: {e}")
                conn.rollback()
        else:
            st.error("[Error] Please fill in all required fields (marked with *)")

st.divider()



# System statistics
st.subheader("System Statistics")


def get_system_stats():
    conn = get_connection()
    try:
        stats = {}

        # User counts
        user_count = conn.execute(
            "SELECT COUNT(*) FROM users WHERE is_active = 1"
        ).fetchone()[0]
        stats["active_users"] = user_count

        # Role distribution
        role_dist = conn.execute(
            """
            SELECT r.role_name, COUNT(ur.user_type_id) as count
            FROM roles r
            LEFT JOIN user_roles ur ON r.role_id = ur.role_id
            GROUP BY r.role_name
        """
        ).fetchall()
        stats["role_distribution"] = role_dist

        # Feedback activity
        total_requests = conn.execute(
            "SELECT COUNT(*) FROM feedback_requests"
        ).fetchone()[0]
        completed_requests = conn.execute(
            "SELECT COUNT(*) FROM feedback_requests WHERE status = 'completed'"
        ).fetchone()[0]
        stats["total_requests"] = total_requests
        stats["completed_requests"] = completed_requests

        return stats
    except Exception as e:
        print(f"Error fetching stats: {e}")
        return {}


stats = get_system_stats()

if stats:
    col1, col2, col3 = st.columns(3)

    with col1:
        st.metric("Active Users", stats.get("active_users", 0))

    with col2:
        st.metric("Total Feedback Requests", stats.get("total_requests", 0))

    with col3:
        completion_rate = 0
        if stats.get("total_requests", 0) > 0:
            completion_rate = (
                stats.get("completed_requests", 0) / stats.get("total_requests", 0)
            ) * 100
        st.metric("Completion Rate", f"{completion_rate:.1f}%")

    # Role distribution
    st.write("**Role Distribution:**")
    if "role_distribution" in stats:
        for role, count in stats["role_distribution"]:
            st.write(f"• **{role}:** {count} users")

st.divider()

# Database maintenance
st.subheader("Database Maintenance")

with st.expander("[Caution] Advanced Operations (Use with Caution)"):
    col1, col2 = st.columns(2)

    with col1:
        st.write("**Data Cleanup**")
        if st.button("[Clean] Clean Old Data"):
            st.info("This would clean up old/expired data")

    with col2:
        st.write("**Database Health**")
        if st.button("[Check] Check Database"):
            conn = get_connection()
            try:
                # Simple health check
                conn.execute("SELECT 1")
                st.success("[Success] Database connection healthy")

                # Check table integrity
                tables = [
                    "users",
                    "roles",
                    "user_roles",
                    "feedback_requests",
                    "feedback_responses",
                ]
                for table in tables:
                    count = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
                    st.write(f"• {table}: {count} records")

            except Exception as e:
                st.error(f"[Error] Database issue: {e}")

# Quick Actions removed - use navigation menu

# Help documentation
with st.expander("[Help] Admin Help"):
    st.write(
        """
    **User Management Tasks:**
    - Add new employees to the system
    - Assign roles (employee, hr, super_admin)
    - Export user data for reporting
    - Monitor system usage and performance
    
    **Best Practices:**
    - Always assign the 'employee' role as a minimum
    - Use 'hr' role for HR personnel
    - Limit 'super_admin' role to system administrators
    - Regularly export data for backup purposes
    
    **Troubleshooting:**
    - If users can't log in, check their active status
    - Password issues require manual reset by admin
    - Role changes take effect immediately
    """
    )

st.info(
    "[Remember] **Remember:** Changes to user data and roles are immediately effective. Always double-check before making modifications."
)
