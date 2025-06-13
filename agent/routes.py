from flask import Blueprint, render_template, session
from auth.decorators import agent_required
from .db import get_agent_stats, get_agent_recent_activity

agent_bp = Blueprint('agent', __name__)

@agent_bp.route('/agent/dashboard')
@agent_required
def dashboard():
    """Agent dashboard page"""
    agent_id = session.get('user_id')
    
    # Get agent statistics
    stats = get_agent_stats(agent_id)
    recent_activity = get_agent_recent_activity(agent_id)
    
    return render_template('agent/dashboard.html', 
                         stats=stats,
                         recent_activity=recent_activity,
                         agent_name=session.get('name'))