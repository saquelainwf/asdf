from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from .db import verify_user_credentials, update_last_login

auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        
        if not email or not password:
            flash('Please enter both email and password.', 'error')
            return render_template('auth/login.html')
        
        # Verify credentials
        user = verify_user_credentials(email, password)
        
        if user:
            # Set session data
            session['logged_in'] = True
            session['user_id'] = user['id']
            session['email'] = user['email']
            session['name'] = user['name']
            session['role'] = user['role']
            session['role_name'] = user['role_name']
            
            # Update last login
            update_last_login(user['id'])
            
            flash(f'Welcome {user["name"]}!', 'success')
            
            # Redirect based on role
            if user['role'] == 1:  # Admin
                return redirect(url_for('dashboard.index'))
            elif user['role'] == 2:  # Agent
                return redirect(url_for('agent.dashboard'))
            else:
                flash('Invalid user role.', 'error')
                return render_template('auth/login.html')
        else:
            flash('Invalid email or password.', 'error')
            return render_template('auth/login.html')
    
    # GET request - show login form
    return render_template('auth/login.html')

@auth_bp.route('/logout')
def logout():
    # Clear session
    session.clear()
    flash('You have been logged out successfully.', 'info')
    return redirect(url_for('auth.login'))