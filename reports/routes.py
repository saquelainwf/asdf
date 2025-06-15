from flask import Blueprint, render_template, request, redirect, url_for, flash
from auth.decorators import admin_required
from datetime import datetime, timedelta
from .db import (
    get_reports_overview, get_monthly_payout_report, 
    get_agent_performance_report, get_tax_summary_report,
    get_entity_analysis_report
)

reports_bp = Blueprint('reports', __name__)

@reports_bp.route('/admin/reports')
@admin_required
def dashboard():
    """Reports dashboard"""
    overview = get_reports_overview()
    
    # Date helpers
    today = datetime.now().date()
    current_month = today.strftime('%Y-%m')
    current_year = today.year
    three_months_ago = (today - timedelta(days=90)).strftime('%Y-%m-%d')
    
    # Available years for tax reports
    available_years = list(range(current_year - 2, current_year + 2))
    
    return render_template('admin/reports_dashboard.html',
                         overview=overview,
                         current_month=current_month,
                         current_year=current_year,
                         today=today.strftime('%Y-%m-%d'),
                         three_months_ago=three_months_ago,
                         available_years=available_years)

@reports_bp.route('/admin/reports/monthly')
@admin_required
def monthly_report():
    """Monthly payout report"""
    month = request.args.get('month', datetime.now().strftime('%Y-%m'))
    
    try:
        report_data = get_monthly_payout_report(month)
        return render_template('admin/monthly_report.html',
                             report_data=report_data,
                             selected_month=month)
    except Exception as e:
        flash(f'Error generating monthly report: {str(e)}', 'error')
        return redirect(url_for('reports.dashboard'))

@reports_bp.route('/admin/reports/agent-performance')
@admin_required
def agent_performance():
    """Agent performance report"""
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    
    if not start_date or not end_date:
        # Default to last 3 months
        end_date = datetime.now().date()
        start_date = end_date - timedelta(days=90)
    
    try:
        report_data = get_agent_performance_report(start_date, end_date)
        return render_template('admin/agent_performance_report.html',
                             report_data=report_data,
                             start_date=start_date,
                             end_date=end_date)
    except Exception as e:
        flash(f'Error generating performance report: {str(e)}', 'error')
        return redirect(url_for('reports.dashboard'))

@reports_bp.route('/admin/reports/tax-summary')
@admin_required
def tax_summary():
    """Tax summary report"""
    year = request.args.get('year', datetime.now().year, type=int)
    
    try:
        report_data = get_tax_summary_report(year)
        return render_template('admin/tax_summary_report.html',
                             report_data=report_data,
                             selected_year=year)
    except Exception as e:
        flash(f'Error generating tax report: {str(e)}', 'error')
        return redirect(url_for('reports.dashboard'))

@reports_bp.route('/admin/reports/entity-analysis')
@admin_required
def entity_analysis():
    """Entity analysis report"""
    period = request.args.get('period', 'last_12_months')
    
    try:
        report_data = get_entity_analysis_report(period)
        return render_template('admin/entity_analysis_report.html',
                             report_data=report_data,
                             selected_period=period)
    except Exception as e:
        flash(f'Error generating entity analysis: {str(e)}', 'error')
        return redirect(url_for('reports.dashboard'))