from flask import Blueprint, render_template
from .db import get_dashboard_stats
from auth.decorators import admin_required

dashboard_bp = Blueprint('dashboard', __name__)

@dashboard_bp.route('/')
@admin_required
def index():
    stats = get_dashboard_stats()
    return render_template('dashboard.html', 
                         total_records=stats['total_records'],
                         bank_stats=stats['bank_stats'],
                         recent_uploads=stats['recent_uploads'])