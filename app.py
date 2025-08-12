import os
import logging

from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from sqlalchemy.orm import DeclarativeBase
from werkzeug.middleware.proxy_fix import ProxyFix

# Configure logging
logging.basicConfig(level=logging.DEBUG)

class Base(DeclarativeBase):
    pass

db = SQLAlchemy(model_class=Base)
login_manager = LoginManager()

# create the app
app = Flask(__name__)
app.secret_key = os.environ.get("SESSION_SECRET", "wauu_lms_secret_key_2025")
app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)

# Platform-specific configurations
port = int(os.environ.get('PORT', 5000))
app.config['PORT'] = port

# Configure file uploads
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size

# Handle upload folder for different platforms
upload_folder = os.environ.get('UPLOAD_FOLDER', 'uploads')
app.config['UPLOAD_FOLDER'] = upload_folder

# Configure the database with better platform support
database_url = os.environ.get("DATABASE_URL")

# Handle different database URL formats (Heroku, Railway, etc.)
if database_url:
    if database_url.startswith("postgres://"):
        database_url = database_url.replace("postgres://", "postgresql://", 1)
    app.config["SQLALCHEMY_DATABASE_URI"] = database_url
else:
    # Use SQLite for development/platforms without database URL
    # Ensure instance directory exists with proper path
    instance_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'instance')
    os.makedirs(instance_dir, exist_ok=True)
    
    # Use absolute path for SQLite database
    db_path = os.environ.get('DB_PATH', os.path.join(instance_dir, 'wauu_lms.db'))
    app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{db_path}"
app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
    "pool_recycle": 300,
    "pool_pre_ping": True,
}

# Initialize extensions
db.init_app(app)
login_manager.init_app(app)
login_manager.login_view = 'login'
login_manager.login_message = 'Please log in to access this page.'

# Create upload directory
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

with app.app_context():
    # Import models to ensure tables are created
    from models import User, Course, Enrollment, Assignment, Submission, Discussion, Post, Grade
    from routes import *
    
    db.create_all()
    
    # Initialize sample data
    from init_data import init_sample_data
    init_sample_data()

@login_manager.user_loader
def load_user(user_id):
    from models import User
    return User.query.get(int(user_id))
