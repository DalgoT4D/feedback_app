"""
Badge utility functions for smart local badge management.
"""
import streamlit as st
from datetime import datetime

def clear_badge_cache():
    """Clear badge cache to force recalculation on next page load."""
    user_data = st.session_state.get("user_data", {})
    user_id = user_data.get("user_type_id")
    if user_id:
        cache_key = f"badge_status_{user_id}"
        if cache_key in st.session_state:
            del st.session_state[cache_key]
        if "badge_cache_time" in st.session_state:
            del st.session_state["badge_cache_time"]

def update_local_badge(action_type: str, completed: bool = True):
    """Update local badge state immediately without DB calls.
    action_type: 'nominations', 'approvals', 'review_requests', 'feedback_forms'
    completed: True if action is complete (removes badge), False if action needed (adds badge)
    """
    user_data = st.session_state.get("user_data", {})
    user_id = user_data.get("user_type_id")
    if not user_id:
        return
    
    # Initialize local action tracking
    if "local_actions" not in st.session_state:
        st.session_state["local_actions"] = {}
    
    local_actions = st.session_state["local_actions"]
    
    if action_type not in local_actions:
        local_actions[action_type] = {"completed": completed}
    else:
        local_actions[action_type]["completed"] = completed
    
    # Clear badge cache to trigger immediate recalculation
    clear_badge_cache()

def get_smart_badge_status(user_id):
    """Get badge status using local state first, then fallback to DB.
    This provides instant updates for user actions.
    """
    # Avoid circular import by importing here
    from services.db_helper import (
        get_user_nominations_status,
        get_pending_approvals_for_manager,
        get_pending_reviewer_requests,
        get_pending_reviews_for_user,
    )
    
    # Performance optimization: cache local actions lookup
    if "local_actions" not in st.session_state:
        st.session_state["local_actions"] = {}
    local_actions = st.session_state["local_actions"]
    
    # Check local state for immediate feedback
    has_incomplete_nominations = True
    has_incomplete_approvals = True 
    has_pending_reviewer_requests = True
    has_pending_feedback_forms = True
    
    pending_requests = None
    pending_reviews = None
    
    # Override with local state if available
    if "nominations" in local_actions:
        has_incomplete_nominations = not local_actions["nominations"]["completed"]
    else:
        # Fallback to DB check only if no local state
        try:
            nominations_status = get_user_nominations_status(user_id)
            has_incomplete_nominations = nominations_status["can_nominate_more"]
        except:
            has_incomplete_nominations = False
    
    if "approvals" in local_actions:
        has_incomplete_approvals = not local_actions["approvals"]["completed"]
    else:
        # Fallback to DB check only if no local state
        try:
            approvals = get_pending_approvals_for_manager(user_id)
            has_incomplete_approvals = len(approvals) > 0
        except:
            has_incomplete_approvals = False
    
    if "review_requests" in local_actions:
        has_pending_reviewer_requests = not local_actions["review_requests"]["completed"]
    else:
        # Fallback to DB check only if no local state
        try:
            pending_requests = get_pending_reviewer_requests(user_id)
            has_pending_reviewer_requests = len(pending_requests) > 0
        except:
            has_pending_reviewer_requests = False
    
    if "feedback_forms" in local_actions:
        has_pending_feedback_forms = not local_actions["feedback_forms"]["completed"]
    elif "reviews" in local_actions:
        # Backward compatibility with previous key name
        has_pending_feedback_forms = not local_actions["reviews"]["completed"]
    else:
        try:
            pending_reviews = get_pending_reviews_for_user(user_id)
            has_pending_feedback_forms = len(pending_reviews) > 0
        except:
            has_pending_feedback_forms = False
    
    return {
        "has_incomplete_nominations": has_incomplete_nominations,
        "has_incomplete_approvals": has_incomplete_approvals,
        "has_pending_reviewer_requests": has_pending_reviewer_requests,
        "has_pending_feedback_forms": has_pending_feedback_forms,
        # Legacy key kept for compatibility
        "has_incomplete_reviews": has_pending_reviewer_requests or has_pending_feedback_forms,
    }
