import streamlit as st
from services.db_helper import get_connection

st.title("System Settings")

st.info("System configuration and maintenance")

# Review cycle configuration
st.subheader("Review Cycle Configuration")

# Get feedback questions
def get_feedback_questions():
    conn = get_connection()
    query = """
        SELECT question_id, question_text, question_type, relationship_type, 
               sort_order, is_active
        FROM feedback_questions 
        ORDER BY relationship_type, sort_order
    """
    try:
        result = conn.execute(query)
        return result.fetchall()
    except Exception as e:
        print(f"Error fetching questions: {e}")
        return []

questions = get_feedback_questions()

# Group questions by relationship type
question_groups = {}
for q in questions:
    rel_type = q[3]
    if rel_type not in question_groups:
        question_groups[rel_type] = []
    question_groups[rel_type].append(q)

# Display questions by type
for rel_type, rel_questions in question_groups.items():
    with st.expander(f"[Questions] Questions for {rel_type.replace('_', ' ').title()}"):
        for q in rel_questions:
            question_id = q[0]
            question_text = q[1]
            question_type = q[2]
            sort_order = q[4]
            is_active = q[5]
            
            col1, col2, col3 = st.columns([4, 1, 1])
            
            with col1:
                status = "[Active]" if is_active else "[Inactive]"
                st.write(f"{status} **{sort_order}.** {question_text}")
                st.write(f"*Type: {question_type}*")
            
            with col2:
                if is_active:
                    if st.button("Disable", key=f"disable_{question_id}"):
                        conn = get_connection()
                        conn.execute("UPDATE feedback_questions SET is_active = 0 WHERE question_id = ?", (question_id,))
                        conn.commit()
                        st.rerun()
                else:
                    if st.button("Enable", key=f"enable_{question_id}"):
                        conn = get_connection()
                        conn.execute("UPDATE feedback_questions SET is_active = 1 WHERE question_id = ?", (question_id,))
                        conn.commit()
                        st.rerun()
            
            with col3:
                if st.button("Edit", key=f"edit_{question_id}"):
                    st.session_state[f'edit_question_{question_id}'] = True
            
            # Edit form
            if st.session_state.get(f'edit_question_{question_id}', False):
                with st.form(f"edit_form_{question_id}"):
                    new_text = st.text_area("Question Text:", value=question_text)
                    new_type = st.selectbox("Type:", ["rating", "text"], index=0 if question_type == "rating" else 1)
                    new_order = st.number_input("Sort Order:", value=sort_order, min_value=1)
                    
                    col_save, col_cancel = st.columns(2)
                    with col_save:
                        save_changes = st.form_submit_button("Save Changes")
                    with col_cancel:
                        cancel_changes = st.form_submit_button("Cancel")
                    
                    if save_changes:
                        conn = get_connection()
                        update_query = """
                            UPDATE feedback_questions 
                            SET question_text = ?, question_type = ?, sort_order = ?
                            WHERE question_id = ?
                        """
                        conn.execute(update_query, (new_text, new_type, new_order, question_id))
                        conn.commit()
                        st.session_state[f'edit_question_{question_id}'] = False
                        st.success("Question updated!")
                        st.rerun()
                    
                    if cancel_changes:
                        st.session_state[f'edit_question_{question_id}'] = False
                        st.rerun()

st.divider()

# Add new question
st.subheader("Add New Question")

with st.form("add_question_form"):
    new_question_text = st.text_area("Question Text:")
    new_question_type = st.selectbox("Question Type:", ["rating", "text"])
    new_relationship_type = st.selectbox("Relationship Type:", [
        "peer", "manager", "direct_reportee", "internal_stakeholder", "external_stakeholder"
    ])
    new_sort_order = st.number_input("Sort Order:", min_value=1, value=1)
    
    add_question = st.form_submit_button("Add Question", type="primary")
    
    if add_question:
        if new_question_text:
            conn = get_connection()
            insert_query = """
                INSERT INTO feedback_questions (question_text, question_type, relationship_type, sort_order)
                VALUES (?, ?, ?, ?)
            """
            conn.execute(insert_query, (new_question_text, new_question_type, new_relationship_type, new_sort_order))
            conn.commit()
            st.success("[Active] Question added successfully!")
        else:
            st.error("[Inactive] Please enter question text")

st.divider()

# Email configuration
st.subheader("Email Configuration")

email_config_exists = "email" in st.secrets

if email_config_exists:
    st.success("[Active] Email configuration found in secrets")
    st.write("**SMTP Server:** smtp.gmail.com")
    st.write("**Port:** 587")
    st.write("**Authentication:** Configured")
else:
    st.warning("[Warning] Email configuration not found")
    st.write("Add email configuration to `.streamlit/secrets.toml`:")
    st.code("""
[email]
smtp_server = "smtp.gmail.com"
smtp_port = 587
email_user = "your-email@company.com"
email_password = "your-app-password"
    """)

# Test email functionality
if email_config_exists:
    st.subheader("Test Email")
    with st.form("test_email_form"):
        test_email = st.text_input("Send test email to:")
        send_test = st.form_submit_button("[Send] Send Test Email")
        
        if send_test and test_email:
            from services.email_service import send_email
            if send_email(test_email, "Test Email", "This is a test email from the 360 Feedback System."):
                st.success("[Active] Test email sent successfully!")
            else:
                st.error("[Inactive] Failed to send test email")

st.divider()

# System maintenance
st.subheader("System Maintenance")

col1, col2 = st.columns(2)

with col1:
    st.write("**Database Statistics**")
    conn = get_connection()
    try:
        # Get table counts
        tables = {
            'Users': 'users',
            'Feedback Requests': 'feedback_requests', 
            'Completed Reviews': 'feedback_responses',
            'Active Cycles': 'review_cycles'
        }
        
        for display_name, table_name in tables.items():
            count = conn.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()[0]
            st.write(f"• {display_name}: **{count}**")
            
    except Exception as e:
        st.error(f"Error fetching statistics: {e}")

with col2:
    # Quick Actions removed - use navigation menu
st.divider()

# Application settings
st.subheader("Application Settings")

with st.expander("[Advanced] Advanced Settings"):
    st.write("**Nomination Limits:**")
    st.write("• Maximum nominations per person: 4")
    st.write("• Minimum reviewers required: 3")
    st.write("• Maximum reviewers allowed: 5")
    
    st.write("**Review Cycle Phases:**")
    st.write("• Week 1: Nomination submission")
    st.write("• Week 2: Manager approval")
    st.write("• Weeks 3-5: Feedback collection")
    st.write("• Week 5: Results compilation")
    
    st.write("**Security Settings:**")
    st.write("• Password minimum length: 6 characters")
    st.write("• Session timeout: Browser session")
    st.write("• Role-based access control: Enabled")

# Version and support info
st.subheader("System Information")

col1, col2 = st.columns(2)

with col1:
    st.write("**Application Version**")
    st.write("360° Feedback System v1.0")
    st.write("Built with Streamlit")
    st.write("Database: Turso (SQLite)")

with col2:
    st.write("**Support**")
    st.write("For technical support, contact your system administrator.")
    st.write("Documentation available in the help sections.")

# Export system configuration
st.subheader("System Backup")

if st.button("[Export] Export Configuration"):
    # Export key configuration data
    config_data = {
        "questions": questions,
        "active_cycle": "See HR Dashboard",
        "user_count": conn.execute("SELECT COUNT(*) FROM users WHERE is_active = 1").fetchone()[0]
    }
    
    st.json(config_data)
    st.info("[Config] Configuration data displayed above. Copy for backup purposes.")

st.info("[Note] **Note:** System settings changes may require administrator privileges and application restart.")