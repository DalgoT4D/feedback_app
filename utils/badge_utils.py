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
    action_type: 'nominations', 'approvals', 'reviews'
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
    has_incomplete_reviews = True
    
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
    
    if "reviews" in local_actions:
        has_incomplete_reviews = not local_actions["reviews"]["completed"]
    else:
        # Fallback to DB check only if no local state
        try:
            pending_requests = get_pending_reviewer_requests(user_id)
            pending_reviews = get_pending_reviews_for_user(user_id)
            has_incomplete_reviews = len(pending_requests) > 0 or len(pending_reviews) > 0
        except:
            has_incomplete_reviews = False
    
    return {
        "has_incomplete_nominations": has_incomplete_nominations,
        "has_incomplete_approvals": has_incomplete_approvals,
        "has_incomplete_reviews": has_incomplete_reviews
    }