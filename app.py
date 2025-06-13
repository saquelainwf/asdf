from flask import Flask
import os
from config import Config

# Import blueprints
from dashboard.routes import dashboard_bp
from upload.routes import upload_bp
from data.routes import data_bp

def create_app():
    app = Flask(__name__)
    
    # Load configuration
    app.config.from_object(Config)
    
    # Ensure upload directory exists
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    
    # Register blueprints
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(upload_bp)
    app.register_blueprint(data_bp)
    
    return app

app = create_app()

if __name__ == '__main__':
    app.run(debug=app.config['DEBUG'])