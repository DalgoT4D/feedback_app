import streamlit as st
from services.db_helper import get_connection, update_user_details

st.title("Manage Employees")


# Get all users
def get_all_users():
    conn = get_connection()
    query = """
        SELECT u.user_type_id, u.first_name, u.last_name, u.email, 
               u.vertical, u.designation, u.reporting_manager_email, u.is_active,
               GROUP_CONCAT(r.role_name) as roles
        FROM users u
        LEFT JOIN user_roles ur ON u.user_type_id = ur.user_type_id
        LEFT JOIN roles r ON ur.role_id = r.role_id
        GROUP BY u.user_type_id
        ORDER BY u.first_name, u.last_name
    """
    try:
        result = conn.execute(query)
        return result.fetchall()
    except Exception as e:
        print(f"Error fetching users: {e}")
        return []


# Get roles
def get_all_roles():
    conn = get_connection()
    query = "SELECT role_id, role_name, description FROM roles ORDER BY role_name"
    try:
        result = conn.execute(query)
        return result.fetchall()
    except Exception as e:
        print(f"Error fetching roles: {e}")
        return []


# Assign role to user
def assign_role_to_user(user_id, role_id):
    conn = get_connection()
    query = """
        INSERT INTO user_roles (user_type_id, role_id) 
        VALUES (?, ?)
        ON CONFLICT DO NOTHING
    """
    try:
        conn.execute(query, (user_id, role_id))
        conn.commit()
        return True
    except Exception as e:
        print(f"Error assigning role: {e}")
        return False


# Remove role from user
def remove_role_from_user(user_id, role_id):
    conn = get_connection()
    query = "DELETE FROM user_roles WHERE user_type_id = ? AND role_id = ?"
    try:
        conn.execute(query, (user_id, role_id))
        conn.commit()
        return True
    except Exception as e:
        print(f"Error removing role: {e}")
        return False


# Update user status
def update_user_status(user_id, is_active):
    conn = get_connection()
    query = "UPDATE users SET is_active = ? WHERE user_type_id = ?"
    try:
        conn.execute(query, (is_active, user_id))
        conn.commit()
        return True
    except Exception as e:
        print(f"Error updating user status: {e}")
        return False


# Main interface
users = get_all_users()
roles = get_all_roles()

if not users:
    st.error("No users found in the system.")
    st.stop()

# Search and filter
st.subheader("Search & Filter")
col1, col2, col3 = st.columns(3)

with col1:
    search_term = st.text_input("Search by name or email:")

with col2:
    vertical_filter = st.selectbox(
        "Filter by department:",
        ["All"] + list(set([user[4] for user in users if user[4]])),
    )

with col3:
    status_filter = st.selectbox("Filter by status:", ["All", "Active", "Inactive"])

# Filter users
filtered_users = users

if search_term:
    filtered_users = [
        user
        for user in filtered_users
        if search_term.lower() in f"{user[1]} {user[2]} {user[3]}".lower()
    ]

if vertical_filter != "All":
    filtered_users = [user for user in filtered_users if user[4] == vertical_filter]

if status_filter == "Active":
    filtered_users = [user for user in filtered_users if user[7] == 1]
elif status_filter == "Inactive":
    filtered_users = [user for user in filtered_users if user[7] == 0]

# Display users
st.subheader(f"Employees ({len(filtered_users)} found)")

for user in filtered_users:
    user_id = user[0]
    name = f"{user[1]} {user[2]}"
    email = user[3]
    vertical = user[4]
    designation = user[5]
    manager_email = user[6]
    is_active = user[7]
    current_roles = user[8] if user[8] else ""

    with st.container():
        col1, col2, col3 = st.columns([3, 2, 1])

        with col1:
            st.write(f"**{name}**")
            st.write(f"📧 {email}")
            st.write(f"🏢 {vertical} - {designation}")
            if manager_email:
                st.write(f"👤 Manager: {manager_email}")

        with col2:
            # Display current roles with badges
            if current_roles:
                st.write("**Current Roles:**")
                role_list = current_roles.split(",")
                for role in role_list:
                    role_cleaned = role.strip()
                    if role_cleaned == "employee":
                        st.markdown(
                            f"<span style='background-color:#e8f4fd; color:#1f77b4; padding:2px 8px; border-radius:12px; font-size:0.8em; margin:2px;'>👤 {role_cleaned}</span>",
                            unsafe_allow_html=True,
                        )
                    elif role_cleaned == "hr":
                        st.markdown(
                            f"<span style='background-color:#e8f5e8; color:#2d7d2d; padding:2px 8px; border-radius:12px; font-size:0.8em; margin:2px;'>👥 {role_cleaned}</span>",
                            unsafe_allow_html=True,
                        )
                    elif role_cleaned == "super_admin":
                        st.markdown(
                            f"<span style='background-color:#fff0e6; color:#d4691d; padding:2px 8px; border-radius:12px; font-size:0.8em; margin:2px;'>⚡ {role_cleaned}</span>",
                            unsafe_allow_html=True,
                        )
                    else:
                        st.markdown(
                            f"<span style='background-color:#f0f0f0; color:#333; padding:2px 8px; border-radius:12px; font-size:0.8em; margin:2px;'>🔧 {role_cleaned}</span>",
                            unsafe_allow_html=True,
                        )
            else:
                st.write("**Current Roles:** None assigned")

            st.write("")  # Add some spacing

            # Role management button
            if st.button(
                "Manage Roles", key=f"manage_roles_{user_id}", type="secondary"
            ):
                st.session_state[f"show_role_form_{user_id}"] = True

            if st.button("Edit User", key=f"edit_user_{user_id}"):
                st.session_state[f"show_edit_form_{user_id}"] = True

            # Role management modal/form
            if st.session_state.get(f"show_role_form_{user_id}", False):
                with st.container():
                    st.markdown("---")
                    st.markdown(f"### Role Management for {name}")

                    # Get user's current roles
                    user_role_ids = []
                    if current_roles:
                        user_roles_query = """
                            SELECT r.role_id FROM roles r
                            JOIN user_roles ur ON r.role_id = ur.role_id
                            WHERE ur.user_type_id = ?
                        """
                        conn = get_connection()
                        result = conn.execute(user_roles_query, (user_id,))
                        user_role_ids = [row[0] for row in result.fetchall()]

                    # Create a clean role management interface
                    st.write("**Available Roles:**")

                    for role in roles:
                        role_id = role[0]
                        role_name = role[1]
                        role_desc = role[2]

                        has_role = role_id in user_role_ids

                        # Create a card-like container for each role
                        with st.container():
                            role_col1, role_col2 = st.columns([4, 3])

                            with role_col1:
                                st.write(f"**{role_name.title()}**")
                                if role_desc:
                                    st.caption(role_desc)
                                else:
                                    st.caption("Standard role permissions")

                            with role_col2:
                                if has_role:
                                    if st.button(
                                        "Remove",
                                        key=f"remove_{user_id}_{role_id}",
                                        type="secondary",
                                    ):
                                        if remove_role_from_user(user_id, role_id):
                                            st.success(f"✅ Removed {role_name}")
                                            st.rerun()
                                        else:
                                            st.error("❌ Failed to remove role")
                                else:
                                    if st.button(
                                        "Assign",
                                        key=f"add_{user_id}_{role_id}",
                                        type="primary",
                                    ):
                                        if assign_role_to_user(user_id, role_id):
                                            st.success(f"✅ Assigned {role_name}")
                                            st.rerun()
                                        else:
                                            st.error("❌ Failed to assign role")

                            st.markdown(
                                "<div style='height: 10px;'></div>",
                                unsafe_allow_html=True,
                            )

                    # Close button
                    col_close1, col_close2, col_close3 = st.columns([2, 1, 2])
                    with col_close1:
                        if st.button(
                            "Done", key=f"close_roles_{user_id}", type="primary"
                        ):
                            st.session_state[f"show_role_form_{user_id}"] = False
                            st.rerun()

            # Edit user form
            if st.session_state.get(f"show_edit_form_{user_id}", False):
                with st.form(f"edit_user_form_{user_id}"):
                    st.markdown(f"### Edit User: {name}")
                    new_first_name = st.text_input("First Name", value=user[1])
                    new_last_name = st.text_input("Last Name", value=user[2])
                    new_vertical = st.text_input("Department/Vertical", value=vertical)
                    new_designation = st.text_input("Designation", value=designation)
                    new_manager_email = st.text_input(
                        "Reporting Manager Email", value=manager_email
                    )

                    submitted = st.form_submit_button("Save Changes")
                    if submitted:
                        if update_user_details(
                            user_id,
                            new_first_name,
                            new_last_name,
                            new_vertical,
                            new_designation,
                            new_manager_email,
                        ):
                            st.success("User details updated successfully!")
                            st.session_state[f"show_edit_form_{user_id}"] = False
                            st.rerun()
                        else:
                            st.error("Failed to update user details.")

        with col3:
            # Status toggle
            if is_active:
                if st.button("Deactivate", key=f"deactivate_{user_id}"):
                    if update_user_status(user_id, 0):
                        st.success("User deactivated")
                        st.rerun()
                    else:
                        st.error("Failed to deactivate")
            else:
                if st.button("Activate", key=f"activate_{user_id}"):
                    if update_user_status(user_id, 1):
                        st.success("User activated")
                        st.rerun()
                    else:
                        st.error("Failed to activate")

        st.divider()

# Summary statistics
st.subheader("Summary")
total_users = len(users)
active_users = len([u for u in users if u[7] == 1])
inactive_users = total_users - active_users

col1, col2, col3 = st.columns(3)
with col1:
    st.metric("Total Users", total_users)
with col2:
    st.metric("Active Users", active_users)
with col3:
    st.metric("Inactive Users", inactive_users)

# Quick Actions removed - use navigation menu
with st.expander("📋 Role Descriptions"):
    for role in roles:
        st.write(f"**{role[1]}:** {role[2]}")

st.info(
    "💡 **Tip:** Use role assignments to control access to different parts of the application. HR personnel should have the 'hr' role, and super admins should have the 'super_admin' role."
)
