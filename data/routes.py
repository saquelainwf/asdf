from flask import Blueprint, render_template, Response, request, flash, redirect, url_for
import csv
import json
from io import StringIO
from auth.decorators import admin_required
from .db import get_mis_data, get_duplicates_for_session

data_bp = Blueprint('data', __name__)

@data_bp.route('/view-data')
@admin_required
def view_data():
    """View all MIS data for verification"""
    data = get_mis_data()
    return render_template('view_data.html', data=data)

@data_bp.route('/download-duplicates/<session_id>')
@admin_required
def download_duplicates(session_id):
    duplicates = get_duplicates_for_session(session_id)
    
    if not duplicates:
        flash('No duplicates found for this session', 'info')
        return redirect(url_for('upload.upload_page'))
    
    # Create CSV
    output = StringIO()
    writer = csv.writer(output)
    
    # Headers
    sample_data = json.loads(duplicates[0]['row_data'])
    headers = list(sample_data.keys()) + ['duplicate_type', 'duplicate_reason']
    writer.writerow(headers)
    
    # Data rows
    for dup in duplicates:
        row_data = json.loads(dup['row_data'])
        reason = 'Already exists in database' if dup['duplicate_type'] == 'in_database' else 'Duplicate within uploaded file'
        row = list(row_data.values()) + [dup['duplicate_type'], reason]
        writer.writerow(row)
    
    output.seek(0)
    return Response(
        output.getvalue(),
        mimetype='text/csv',
        headers={'Content-Disposition': f'attachment; filename=duplicates_{session_id}.csv'}
    )