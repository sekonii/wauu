from app import db
from flask_login import UserMixin
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(256))
    first_name = db.Column(db.String(64), nullable=False)
    last_name = db.Column(db.String(64), nullable=False)
    role = db.Column(db.String(20), nullable=False, default='student')  # student, lecturer, admin
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    enrollments = db.relationship('Enrollment', backref='user', lazy='dynamic')
    taught_courses = db.relationship('Course', backref='lecturer', lazy='dynamic')
    submissions = db.relationship('Submission', backref='student', lazy='dynamic')
    posts = db.relationship('Post', backref='author', lazy='dynamic')
    grades = db.relationship('Grade', backref='student', lazy='dynamic')
    
    def set_password(self, password):
        # For this application, we store passwords as plain text as requested
        self.password_hash = password
    
    def check_password(self, password):
        return self.password_hash == password
    
    def get_full_name(self):
        return f"{self.first_name} {self.last_name}"
    
    def is_admin(self):
        return self.role == 'admin'
    
    def is_lecturer(self):
        return self.role == 'lecturer'
    
    def is_student(self):
        return self.role == 'student'

class Course(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(20), unique=True, nullable=False)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    lecturer_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    enrollments = db.relationship('Enrollment', backref='course', lazy='dynamic', cascade='all, delete-orphan')
    assignments = db.relationship('Assignment', backref='course', lazy='dynamic', cascade='all, delete-orphan')
    discussions = db.relationship('Discussion', backref='course', lazy='dynamic', cascade='all, delete-orphan')

class Enrollment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    course_id = db.Column(db.Integer, db.ForeignKey('course.id'), nullable=False)
    enrolled_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    __table_args__ = (db.UniqueConstraint('user_id', 'course_id'),)

class Assignment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    course_id = db.Column(db.Integer, db.ForeignKey('course.id'), nullable=False)
    max_points = db.Column(db.Integer, default=100)
    due_date = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    submissions = db.relationship('Submission', backref='assignment', lazy='dynamic', cascade='all, delete-orphan')
    grades = db.relationship('Grade', backref='assignment', lazy='dynamic', cascade='all, delete-orphan')

class Submission(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    assignment_id = db.Column(db.Integer, db.ForeignKey('assignment.id'), nullable=False)
    student_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    content = db.Column(db.Text)
    file_path = db.Column(db.String(255))
    url = db.Column(db.String(255))
    submitted_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def is_late(self):
        if self.assignment.due_date:
            return self.submitted_at > self.assignment.due_date
        return False

class Grade(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    assignment_id = db.Column(db.Integer, db.ForeignKey('assignment.id'), nullable=False)
    student_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    points_earned = db.Column(db.Float, default=0)
    feedback = db.Column(db.Text)
    graded_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    __table_args__ = (db.UniqueConstraint('assignment_id', 'student_id'),)
    
    def get_percentage(self):
        if self.assignment.max_points > 0:
            return (self.points_earned / self.assignment.max_points) * 100
        return 0

class Discussion(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    course_id = db.Column(db.Integer, db.ForeignKey('course.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    posts = db.relationship('Post', backref='discussion', lazy='dynamic', cascade='all, delete-orphan')

class Post(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.Text, nullable=False)
    discussion_id = db.Column(db.Integer, db.ForeignKey('discussion.id'), nullable=False)
    author_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    parent_id = db.Column(db.Integer, db.ForeignKey('post.id'))  # For replies
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Self-referential relationship for replies
    replies = db.relationship('Post', backref=db.backref('parent', remote_side=[id]), lazy='dynamic')

class LectureRoom(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    room_name = db.Column(db.String(100), unique=True, nullable=False)
    course_id = db.Column(db.Integer, db.ForeignKey('course.id'), nullable=False)
    lecturer_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    scheduled_start = db.Column(db.DateTime)
    scheduled_end = db.Column(db.DateTime)
    actual_start = db.Column(db.DateTime)
    actual_end = db.Column(db.DateTime)
    is_active = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    course = db.relationship('Course', backref='lecture_rooms')
    lecturer = db.relationship('User', backref='hosted_rooms')
    session_logs = db.relationship('LectureSessionLog', backref='lecture_room', lazy='dynamic', cascade='all, delete-orphan')
    
    def generate_room_name(self):
        """Generate a unique room name based on course and timestamp"""
        import uuid
        # Use an even simpler format to ensure anonymous access
        return f"{self.course.code}{uuid.uuid4().hex[:6]}"
    
    def get_jitsi_url(self):
        """Get the full Jitsi Meet URL for this room"""
        return f"https://meet.jit.si/{self.room_name}"
    
    def start_session(self):
        """Mark the session as started"""
        self.is_active = True
        self.actual_start = datetime.utcnow()
        
    def end_session(self):
        """Mark the session as ended"""
        self.is_active = False
        self.actual_end = datetime.utcnow()

class LectureSessionLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    lecture_room_id = db.Column(db.Integer, db.ForeignKey('lecture_room.id'), nullable=False)
    participant_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    joined_at = db.Column(db.DateTime, default=datetime.utcnow)
    left_at = db.Column(db.DateTime)
    duration_minutes = db.Column(db.Integer)  # Calculated when participant leaves
    
    # Relationships
    participant = db.relationship('User', backref='lecture_sessions')
    
    def calculate_duration(self):
        """Calculate session duration when participant leaves"""
        if self.left_at and self.joined_at:
            duration = self.left_at - self.joined_at
            self.duration_minutes = int(duration.total_seconds() / 60)
        
    def mark_left(self):
        """Mark participant as left and calculate duration"""
        self.left_at = datetime.utcnow()
        self.calculate_duration()
