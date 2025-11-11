import streamlit as st
from services.db_helper import get_users_with_pending_reviews, get_connection
from services.email_service import send_reminder_email

st.title("Send Reminders")

# Get users with pending reviews
pending_users = get_users_with_pending_reviews()

if not pending_users:
    st.success("🎉 No users have pending reviews!")
    st.info("All feedback requests have been completed.")
else:
    st.write(f"**{len(pending_users)} users** have pending feedback reviews:")
    
    # Bulk actions
    st.subheader("Bulk Actions")
    col1, col2 = st.columns(2)
    
    with col1:
        if st.button("📨 Send Reminders to All", type="primary"):
            success_count = 0
            for user in pending_users:
                if send_reminder_email(user['email'], user['pending_count']):
                    success_count += 1
            
            if success_count > 0:
                st.success(f"✅ Reminders sent to {success_count} users!")
            else:
                st.error("❌ Failed to send reminders.")
    
    with col2:
        # Filter options
        min_pending = st.number_input("Minimum pending reviews:", min_value=1, value=1)
        filtered_users = [user for user in pending_users if user['pending_count'] >= min_pending]
        
        if len(filtered_users) != len(pending_users):
            st.write(f"Filtered to {len(filtered_users)} users with {min_pending}+ pending reviews")
    
    st.divider()
    
    # Individual user management
    st.subheader("Individual Reminders")
    
    # Show pending users
    for user in filtered_users:
        col1, col2, col3, col4 = st.columns([3, 2, 1, 1])
        
        with col1:
            st.write(f"**{user['name']}**")
            st.write(f"📧 {user['email']}")
        
        with col2:
            st.write(f"🏢 {user['vertical']}")
        
        with col3:
            if user['pending_count'] == 1:
                st.write(f"**{user['pending_count']}** review")
            else:
                st.write(f"**{user['pending_count']}** reviews")
        
        with col4:
            if st.button("📨 Send Reminder", key=f"remind_{user['user_type_id']}"):
                if send_reminder_email(user['email'], user['pending_count']):
                    st.success("✅ Sent!")
                else:
                    st.error("❌ Failed")
        
        st.divider()

# Email history and analytics
st.subheader("Email Analytics")

def get_email_stats():
    conn = get_connection()
    try:
        # Recent email stats
        stats_query = """
            SELECT 
                email_type,
                COUNT(*) as count,
                SUM(CASE WHEN status = 'sent' THEN 1 ELSE 0 END) as sent,
                SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) as failed
            FROM email_logs 
            WHERE DATE(sent_at) >= DATE('now', '-7 days')
            GROUP BY email_type
        """
        result = conn.execute(stats_query)
        return result.fetchall()
    except Exception as e:
        print(f"Error fetching email stats: {e}")
        return []

email_stats = get_email_stats()

if email_stats:
    st.write("**Email activity (last 7 days):**")
    for stat in email_stats:
        email_type = stat[0]
        total = stat[1]
        sent = stat[2]
        failed = stat[3]
        
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.write(f"**{email_type.replace('_', ' ').title()}**")
        with col2:
            st.write(f"Total: {total}")
        with col3:
            st.write(f"✅ Sent: {sent}")
        with col4:
            st.write(f"❌ Failed: {failed}")
else:
    st.info("No email activity in the last 7 days")

# Template customization
st.subheader("Reminder Settings")

with st.expander("📝 Email Template Preview"):
    st.write("**Subject:** Reminder: Pending Feedback Reviews")
    st.write("""
    **Email Body:**
    
    Hello,
    
    You have [X] pending feedback review(s) waiting for completion.
    
    Please log in to the system to complete your reviews at your earliest convenience.
    
    Thank you!
    """)



# Tips and best practices
with st.expander("💡 Best Practices for Reminders"):
    st.write("""
    **Timing:**
    - Send initial reminders 1 week before deadline
    - Send final reminders 2-3 days before deadline
    - Avoid sending daily reminders (can be counterproductive)
    
    **Frequency:**
    - Maximum 2-3 reminders per cycle
    - Space reminders at least 3-4 days apart
    - Consider individual follow-up for persistent non-responders
    
    **Communication:**
    - Be clear about deadlines
    - Explain the importance of feedback
    - Offer support for technical issues
    - Consider escalating to managers for chronic non-responders
    """)

if pending_users:
    # Show urgency indicators
    high_priority = [u for u in pending_users if u['pending_count'] >= 3]
    if high_priority:
        st.warning(f"⚠️ **High Priority:** {len(high_priority)} users have 3+ pending reviews")