from flask import Flask, session, request
from datetime import datetime, timedelta
import os
from config import Config

# Import blueprints
from dashboard.routes import dashboard_bp
from upload.routes import upload_bp
from data.routes import data_bp
from auth.routes import auth_bp
from agent.routes import agent_bp
from case_claims.routes import case_claims_bp
from admin.routes import admin_bp
from subconnectors.routes import subconnectors_bp
from invoices.routes import invoices_bp
from payouts.routes import payouts_bp

def create_app():
    app = Flask(__name__)
    
    # Load configuration
    app.config.from_object(Config)
    
    # Ensure upload directory exists
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    
    # Security headers
    @app.after_request
    def add_security_headers(response):
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['X-Frame-Options'] = 'DENY'
        response.headers['X-XSS-Protection'] = '1; mode=block'
        response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
        response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
        response.headers['Pragma'] = 'no-cache'
        response.headers['Expires'] = '0'
        return response
    
    # Session timeout check
    @app.before_request
    def check_session_timeout():
        # Skip timeout check for login/logout routes
        if request.endpoint in ['auth.login', 'auth.logout', 'static']:
            return
        
        if 'logged_in' in session and session['logged_in']:
            # Check if session has expired
            if 'last_activity' in session:
                last_activity = datetime.fromisoformat(session['last_activity'])
                if datetime.now() - last_activity > timedelta(seconds=app.config['PERMANENT_SESSION_LIFETIME']):
                    session.clear()
                    from flask import flash, redirect, url_for
                    flash('Your session has expired. Please log in again.', 'warning')
                    return redirect(url_for('auth.login'))
            
            # Update last activity
            session['last_activity'] = datetime.now().isoformat()
            session.permanent = True
    
    # Register blueprints
    app.register_blueprint(auth_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(upload_bp)
    app.register_blueprint(data_bp)
    app.register_blueprint(agent_bp)
    app.register_blueprint(case_claims_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(subconnectors_bp)
    app.register_blueprint(invoices_bp)
    app.register_blueprint(payouts_bp)
    
    return app

app = create_app()

if __name__ == '__main__':
    app.run(debug=app.config['DEBUG'])