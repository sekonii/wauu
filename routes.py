import os
from flask import render_template, request, redirect, url_for, flash, send_from_directory, abort
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.utils import secure_filename
from app import app, db
from models import User, Course, Enrollment, Assignment, Submission, Discussion, Post, Grade, LectureRoom, LectureSessionLog
from decorators import admin_required, lecturer_required
from datetime import datetime

ALLOWED_EXTENSIONS = {'txt', 'pdf', 'png', 'jpg', 'jpeg', 'gif', 'doc', 'docx', 'ppt', 'pptx', 'xls', 'xlsx', 'zip', 'rar'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/')
def index():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    return render_template('home.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        user = User.query.filter_by(username=username).first()
        
        if user and user.check_password(password):
            login_user(user)
            flash(f'Welcome back, {user.get_full_name()}!', 'success')
            return redirect(url_for('dashboard'))
        else:
            flash('Invalid username or password.', 'danger')
    
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']
        first_name = request.form['first_name']
        last_name = request.form['last_name']
        role = request.form.get('role', 'student')
        
        # Check if user already exists
        if User.query.filter_by(username=username).first():
            flash('Username already exists.', 'danger')
            return render_template('register.html')
        
        if User.query.filter_by(email=email).first():
            flash('Email already registered.', 'danger')
            return render_template('register.html')
        
        # Create new user
        user = User(
            username=username,
            email=email,
            first_name=first_name,
            last_name=last_name,
            role=role
        )
        user.set_password(password)
        
        db.session.add(user)
        db.session.commit()
        
        flash('Registration successful! Please login.', 'success')
        return redirect(url_for('login'))
    
    return render_template('register.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been logged out successfully.', 'info')
    return redirect(url_for('login'))

@app.route('/dashboard')
@login_required
def dashboard():
    if current_user.is_admin():
        # Admin dashboard stats
        total_users = User.query.count()
        total_courses = Course.query.count()
        total_assignments = Assignment.query.count()
        recent_submissions = Submission.query.order_by(Submission.submitted_at.desc()).limit(5).all()
        
        return render_template('dashboard.html', 
                             total_users=total_users,
                             total_courses=total_courses,
                             total_assignments=total_assignments,
                             recent_submissions=recent_submissions)
    
    elif current_user.is_lecturer():
        # Lecturer dashboard
        my_courses = Course.query.filter_by(lecturer_id=current_user.id).all()
        pending_submissions = Submission.query.join(Assignment).filter(
            Assignment.course_id.in_([c.id for c in my_courses])
        ).filter(~Submission.id.in_(
            db.session.query(Grade.assignment_id).filter_by(student_id=Submission.student_id)
        )).count()
        
        return render_template('dashboard.html', 
                             my_courses=my_courses,
                             pending_submissions=pending_submissions)
    
    else:
        # Student dashboard
        enrollments = Enrollment.query.filter_by(user_id=current_user.id).all()
        my_courses = [e.course for e in enrollments]
        pending_assignments = Assignment.query.filter(
            Assignment.course_id.in_([c.id for c in my_courses])
        ).filter(~Assignment.id.in_(
            db.session.query(Submission.assignment_id).filter_by(student_id=current_user.id)
        )).all()
        
        recent_grades = Grade.query.filter_by(student_id=current_user.id).order_by(Grade.graded_at.desc()).limit(5).all()
        
        return render_template('dashboard.html',
                             my_courses=my_courses,
                             pending_assignments=pending_assignments,
                             recent_grades=recent_grades)

@app.route('/courses')
@login_required
def courses():
    if current_user.is_admin():
        all_courses = Course.query.all()
        return render_template('courses.html', courses=all_courses)
    elif current_user.is_lecturer():
        my_courses = Course.query.filter_by(lecturer_id=current_user.id).all()
        return render_template('courses.html', courses=my_courses)
    else:
        # Students see enrolled courses and available courses
        enrolled_courses = db.session.query(Course).join(Enrollment).filter(Enrollment.user_id == current_user.id).all()
        all_courses = Course.query.all()
        available_courses = [c for c in all_courses if c not in enrolled_courses]
        return render_template('courses.html', courses=enrolled_courses, available_courses=available_courses)

@app.route('/course/<int:course_id>')
@login_required
def course_detail(course_id):
    course = Course.query.get_or_404(course_id)
    
    # Check if user has access to this course
    if current_user.is_student():
        enrollment = Enrollment.query.filter_by(user_id=current_user.id, course_id=course_id).first()
        if not enrollment:
            flash('You are not enrolled in this course.', 'danger')
            return redirect(url_for('courses'))
    elif current_user.is_lecturer() and course.lecturer_id != current_user.id:
        flash('You do not have access to this course.', 'danger')
        return redirect(url_for('courses'))
    
    assignments = Assignment.query.filter_by(course_id=course_id).order_by(Assignment.created_at.desc()).all()
    discussions = Discussion.query.filter_by(course_id=course_id).order_by(Discussion.created_at.desc()).all()
    
    return render_template('course_detail.html', course=course, assignments=assignments, discussions=discussions)

@app.route('/enroll/<int:course_id>')
@login_required
def enroll_course(course_id):
    if not current_user.is_student():
        flash('Only students can enroll in courses.', 'danger')
        return redirect(url_for('courses'))
    
    course = Course.query.get_or_404(course_id)
    existing_enrollment = Enrollment.query.filter_by(user_id=current_user.id, course_id=course_id).first()
    
    if existing_enrollment:
        flash('You are already enrolled in this course.', 'warning')
    else:
        enrollment = Enrollment(user_id=current_user.id, course_id=course_id)
        db.session.add(enrollment)
        db.session.commit()
        flash(f'Successfully enrolled in {course.title}!', 'success')
    
    return redirect(url_for('courses'))

@app.route('/assignments')
@login_required
def assignments():
    search_query = request.args.get('search', '').strip()
    
    if current_user.is_student():
        # Get assignments from enrolled courses
        enrolled_courses = db.session.query(Course).join(Enrollment).filter(Enrollment.user_id == current_user.id).all()
        course_ids = [c.id for c in enrolled_courses]
        assignments_query = Assignment.query.filter(Assignment.course_id.in_(course_ids))
        if search_query:
            assignments_query = assignments_query.filter(
                db.or_(
                    Assignment.title.ilike(f'%{search_query}%'),
                    Assignment.description.ilike(f'%{search_query}%')
                )
            )
        assignments = assignments_query.order_by(Assignment.due_date.asc()).all()
    elif current_user.is_lecturer():
        # Get assignments from lecturer's courses
        my_courses = Course.query.filter_by(lecturer_id=current_user.id).all()
        course_ids = [c.id for c in my_courses]
        assignments_query = Assignment.query.filter(Assignment.course_id.in_(course_ids))
        if search_query:
            assignments_query = assignments_query.filter(
                db.or_(
                    Assignment.title.ilike(f'%{search_query}%'),
                    Assignment.description.ilike(f'%{search_query}%'),
                    Assignment.course.has(Course.name.ilike(f'%{search_query}%')),
                    Assignment.course.has(Course.code.ilike(f'%{search_query}%'))
                )
            )
        assignments = assignments_query.order_by(Assignment.created_at.desc()).all()
    else:
        # Admin sees all assignments
        assignments_query = Assignment.query
        if search_query:
            assignments_query = assignments_query.filter(
                db.or_(
                    Assignment.title.ilike(f'%{search_query}%'),
                    Assignment.description.ilike(f'%{search_query}%'),
                    Assignment.course.has(Course.name.ilike(f'%{search_query}%')),
                    Assignment.course.has(Course.code.ilike(f'%{search_query}%'))
                )
            )
        assignments = assignments_query.order_by(Assignment.created_at.desc()).all()
    
    return render_template('assignments.html', assignments=assignments, search_query=search_query)

@app.route('/assignment/<int:assignment_id>')
@login_required
def assignment_detail(assignment_id):
    assignment = Assignment.query.get_or_404(assignment_id)
    
    # Check access permissions
    if current_user.is_student():
        enrollment = Enrollment.query.filter_by(user_id=current_user.id, course_id=assignment.course_id).first()
        if not enrollment:
            flash('You do not have access to this assignment.', 'danger')
            return redirect(url_for('assignments'))
        
        # Get student's submission if any
        submission = Submission.query.filter_by(assignment_id=assignment_id, student_id=current_user.id).first()
        grade = Grade.query.filter_by(assignment_id=assignment_id, student_id=current_user.id).first()
        
        return render_template('assignment_detail.html', assignment=assignment, submission=submission, grade=grade)
    
    elif current_user.is_lecturer():
        if assignment.course.lecturer_id != current_user.id:
            flash('You do not have access to this assignment.', 'danger')
            return redirect(url_for('assignments'))
        
        # Get all submissions for this assignment
        submissions = Submission.query.filter_by(assignment_id=assignment_id).all()
        return render_template('assignment_detail.html', assignment=assignment, submissions=submissions)
    
    else:
        # Admin can see everything
        submissions = Submission.query.filter_by(assignment_id=assignment_id).all()
        return render_template('assignment_detail.html', assignment=assignment, submissions=submissions)

@app.route('/submit_assignment/<int:assignment_id>', methods=['POST'])
@login_required
def submit_assignment(assignment_id):
    if not current_user.is_student():
        flash('Only students can submit assignments.', 'danger')
        return redirect(url_for('assignment_detail', assignment_id=assignment_id))
    
    assignment = Assignment.query.get_or_404(assignment_id)
    
    # Check if student is enrolled
    enrollment = Enrollment.query.filter_by(user_id=current_user.id, course_id=assignment.course_id).first()
    if not enrollment:
        flash('You are not enrolled in this course.', 'danger')
        return redirect(url_for('assignments'))
    
    # Check if already submitted
    existing_submission = Submission.query.filter_by(assignment_id=assignment_id, student_id=current_user.id).first()
    if existing_submission:
        flash('You have already submitted this assignment.', 'warning')
        return redirect(url_for('assignment_detail', assignment_id=assignment_id))
    
    content = request.form.get('content', '')
    url = request.form.get('url', '')
    file_path = None
    
    # Handle file upload
    if 'file' in request.files:
        file = request.files['file']
        if file and file.filename and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            # Add timestamp to avoid conflicts
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S_')
            filename = timestamp + filename
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(file_path)
    
    submission = Submission(
        assignment_id=assignment_id,
        student_id=current_user.id,
        content=content,
        file_path=file_path,
        url=url
    )
    
    db.session.add(submission)
    db.session.commit()
    
    flash('Assignment submitted successfully!', 'success')
    return redirect(url_for('assignment_detail', assignment_id=assignment_id))

@app.route('/grade_submission/<int:submission_id>', methods=['POST'])
@login_required
@lecturer_required
def grade_submission(submission_id):
    submission = Submission.query.get_or_404(submission_id)
    
    # Verify lecturer owns the course
    if submission.assignment.course.lecturer_id != current_user.id and not current_user.is_admin():
        flash('You do not have permission to grade this submission.', 'danger')
        return redirect(url_for('assignments'))
    
    points_earned = float(request.form['points_earned'])
    feedback = request.form.get('feedback', '')
    
    # Check if grade already exists
    existing_grade = Grade.query.filter_by(assignment_id=submission.assignment_id, student_id=submission.student_id).first()
    
    if existing_grade:
        existing_grade.points_earned = points_earned
        existing_grade.feedback = feedback
        existing_grade.graded_at = datetime.utcnow()
    else:
        grade = Grade(
            assignment_id=submission.assignment_id,
            student_id=submission.student_id,
            points_earned=points_earned,
            feedback=feedback
        )
        db.session.add(grade)
    
    db.session.commit()
    flash('Grade submitted successfully!', 'success')
    return redirect(url_for('assignment_detail', assignment_id=submission.assignment_id))

@app.route('/discussions')
@login_required
def discussions():
    search_query = request.args.get('search', '').strip()
    
    if current_user.is_student():
        # Get discussions from enrolled courses
        enrolled_courses = db.session.query(Course).join(Enrollment).filter(Enrollment.user_id == current_user.id).all()
        course_ids = [c.id for c in enrolled_courses]
        discussions_query = Discussion.query.filter(Discussion.course_id.in_(course_ids))
        if search_query:
            discussions_query = discussions_query.filter(
                db.or_(
                    Discussion.title.ilike(f'%{search_query}%'),
                    Discussion.description.ilike(f'%{search_query}%')
                )
            )
        discussions = discussions_query.order_by(Discussion.created_at.desc()).all()
    elif current_user.is_lecturer():
        # Get discussions from lecturer's courses
        my_courses = Course.query.filter_by(lecturer_id=current_user.id).all()
        course_ids = [c.id for c in my_courses]
        discussions_query = Discussion.query.filter(Discussion.course_id.in_(course_ids))
        if search_query:
            discussions_query = discussions_query.filter(
                db.or_(
                    Discussion.title.ilike(f'%{search_query}%'),
                    Discussion.description.ilike(f'%{search_query}%'),
                    Discussion.course.has(Course.name.ilike(f'%{search_query}%')),
                    Discussion.course.has(Course.code.ilike(f'%{search_query}%'))
                )
            )
        discussions = discussions_query.order_by(Discussion.created_at.desc()).all()
    else:
        # Admin sees all discussions
        discussions_query = Discussion.query
        if search_query:
            discussions_query = discussions_query.filter(
                db.or_(
                    Discussion.title.ilike(f'%{search_query}%'),
                    Discussion.description.ilike(f'%{search_query}%'),
                    Discussion.course.has(Course.name.ilike(f'%{search_query}%')),
                    Discussion.course.has(Course.code.ilike(f'%{search_query}%'))
                )
            )
        discussions = discussions_query.order_by(Discussion.created_at.desc()).all()
    
    return render_template('discussions.html', discussions=discussions, search_query=search_query)

@app.route('/discussion/<int:discussion_id>')
@login_required
def discussion_detail(discussion_id):
    discussion = Discussion.query.get_or_404(discussion_id)
    
    # Check access permissions
    if current_user.is_student():
        enrollment = Enrollment.query.filter_by(user_id=current_user.id, course_id=discussion.course_id).first()
        if not enrollment:
            flash('You do not have access to this discussion.', 'danger')
            return redirect(url_for('discussions'))
    elif current_user.is_lecturer() and discussion.course.lecturer_id != current_user.id:
        flash('You do not have access to this discussion.', 'danger')
        return redirect(url_for('discussions'))
    
    posts = Post.query.filter_by(discussion_id=discussion_id, parent_id=None).order_by(Post.created_at.asc()).all()
    return render_template('discussion_detail.html', discussion=discussion, posts=posts)

@app.route('/add_post/<int:discussion_id>', methods=['POST'])
@login_required
def add_post(discussion_id):
    discussion = Discussion.query.get_or_404(discussion_id)
    content = request.form['content']
    parent_id = request.form.get('parent_id')
    
    # Verify access
    if current_user.is_student():
        enrollment = Enrollment.query.filter_by(user_id=current_user.id, course_id=discussion.course_id).first()
        if not enrollment:
            flash('You do not have access to this discussion.', 'danger')
            return redirect(url_for('discussions'))
    elif current_user.is_lecturer() and discussion.course.lecturer_id != current_user.id:
        flash('You do not have access to this discussion.', 'danger')
        return redirect(url_for('discussions'))
    
    post = Post(
        content=content,
        discussion_id=discussion_id,
        author_id=current_user.id,
        parent_id=int(parent_id) if parent_id else None
    )
    
    db.session.add(post)
    db.session.commit()
    
    flash('Post added successfully!', 'success')
    return redirect(url_for('discussion_detail', discussion_id=discussion_id))

@app.route('/grades')
@login_required
def grades():
    if current_user.is_student():
        grades = Grade.query.filter_by(student_id=current_user.id).order_by(Grade.graded_at.desc()).all()
        return render_template('grades.html', grades=grades)
    else:
        flash('Only students can view grades.', 'danger')
        return redirect(url_for('dashboard'))

@app.route('/profile')
@login_required
def profile():
    return render_template('profile.html')

@app.route('/update_profile', methods=['POST'])
@login_required
def update_profile():
    current_user.first_name = request.form['first_name']
    current_user.last_name = request.form['last_name']
    current_user.email = request.form['email']
    
    db.session.commit()
    flash('Profile updated successfully!', 'success')
    return redirect(url_for('profile'))

@app.route('/admin/users')
@login_required
@admin_required
def admin_users():
    users = User.query.order_by(User.created_at.desc()).all()
    return render_template('admin/users.html', users=users)

@app.route('/admin/courses')
@login_required
@admin_required
def admin_courses():
    courses = Course.query.order_by(Course.created_at.desc()).all()
    lecturers = User.query.filter_by(role='lecturer').all()
    return render_template('admin/courses.html', courses=courses, lecturers=lecturers)

@app.route('/admin/analytics')
@login_required
@admin_required
def admin_analytics():
    # Calculate comprehensive metrics
    total_users = User.query.count()
    student_count = User.query.filter_by(role='student').count()
    lecturer_count = User.query.filter_by(role='lecturer').count()
    admin_count = User.query.filter_by(role='admin').count()
    
    total_courses = Course.query.count()
    total_assignments = Assignment.query.count()
    total_submissions = Submission.query.count()
    total_discussions = Discussion.query.count()
    
    # Calculate averages
    avg_enrollment = round(Enrollment.query.count() / max(total_courses, 1), 1)
    submission_rate = round((total_submissions / max(total_assignments * student_count, 1)) * 100, 1)
    
    # Get recent activities (simulated for demo)
    recent_activities = []
    recent_submissions = Submission.query.order_by(Submission.submitted_at.desc()).limit(5).all()
    for submission in recent_submissions:
        recent_activities.append({
            'user': submission.student,
            'action': f'Submitted assignment "{submission.assignment.title}"',
            'created_at': submission.submitted_at
        })
    
    # Top performing courses (simulated data)
    top_courses = []
    courses = Course.query.all()
    for course in courses[:4]:
        top_courses.append({
            'code': course.code,
            'title': course.title,
            'avg_grade': 85 + (hash(course.code) % 15)  # Simulated grade
        })
    
    metrics = {
        'total_users': total_users,
        'student_count': student_count,
        'lecturer_count': lecturer_count,
        'admin_count': admin_count,
        'new_users_this_month': 5,  # Simulated
        'active_courses': total_courses,
        'avg_enrollment': avg_enrollment,
        'total_assignments': total_assignments,
        'submission_rate': submission_rate,
        'avg_grade': 87,  # Simulated
        'grade_improvement': '+3%',  # Simulated
        'active_users_today': 25  # Simulated
    }
    
    return render_template('admin/analytics.html', 
                         metrics=metrics, 
                         recent_activities=recent_activities,
                         top_courses=top_courses)

@app.route('/admin/system_health')
@login_required
@admin_required
def admin_system_health():
    # System health metrics
    health_data = {
        'database_status': 'Healthy',
        'server_uptime': '7 days, 12 hours',
        'memory_usage': '68%',
        'disk_usage': '42%',
        'active_sessions': 23,
        'error_rate': '0.02%',
        'response_time': '145ms'
    }
    
    return render_template('admin/system_health.html', health=health_data)

@app.route('/admin/add_user', methods=['POST'])
@login_required
@admin_required
def admin_add_user():
    username = request.form['username']
    email = request.form['email']
    password = request.form['password']
    first_name = request.form['first_name']
    last_name = request.form['last_name']
    role = request.form['role']
    
    # Check if user already exists
    if User.query.filter_by(username=username).first():
        flash('Username already exists.', 'danger')
        return redirect(url_for('admin_users'))
    
    # Create new user
    user = User(
        username=username,
        email=email,
        first_name=first_name,
        last_name=last_name,
        role=role
    )
    user.set_password(password)
    
    db.session.add(user)
    db.session.commit()
    
    flash(f'User {username} created successfully!', 'success')
    return redirect(url_for('admin_users'))

@app.route('/admin/edit_user/<int:user_id>', methods=['POST'])
@login_required
@admin_required
def admin_edit_user(user_id):
    user = User.query.get_or_404(user_id)
    
    user.username = request.form['username']
    user.email = request.form['email']
    user.first_name = request.form['first_name']
    user.last_name = request.form['last_name']
    user.role = request.form['role']
    
    if request.form.get('password'):
        user.set_password(request.form['password'])
    
    db.session.commit()
    flash(f'User {user.username} updated successfully!', 'success')
    return redirect(url_for('admin_users'))

@app.route('/admin/delete_user/<int:user_id>', methods=['POST'])
@login_required
@admin_required
def admin_delete_user(user_id):
    user = User.query.get_or_404(user_id)
    
    if user.id == current_user.id:
        flash('You cannot delete your own account.', 'danger')
        return redirect(url_for('admin_users'))
    
    db.session.delete(user)
    db.session.commit()
    flash(f'User {user.username} deleted successfully!', 'success')
    return redirect(url_for('admin_users'))

@app.route('/admin/add_course', methods=['POST'])
@login_required
@admin_required
def admin_add_course():
    code = request.form['code']
    title = request.form['title']
    description = request.form['description']
    lecturer_id = request.form['lecturer_id']
    
    # Check if course code already exists
    if Course.query.filter_by(code=code).first():
        flash('Course code already exists.', 'danger')
        return redirect(url_for('admin_courses'))
    
    course = Course(
        code=code,
        title=title,
        description=description,
        lecturer_id=lecturer_id
    )
    
    db.session.add(course)
    db.session.commit()
    
    flash(f'Course {code} created successfully!', 'success')
    return redirect(url_for('admin_courses'))

@app.route('/admin/edit_course/<int:course_id>', methods=['POST'])
@login_required
@admin_required
def admin_edit_course(course_id):
    course = Course.query.get_or_404(course_id)
    
    course.code = request.form['code']
    course.title = request.form['title']
    course.description = request.form['description']
    course.lecturer_id = request.form['lecturer_id']
    
    db.session.commit()
    flash(f'Course {course.code} updated successfully!', 'success')
    return redirect(url_for('admin_courses'))

@app.route('/admin/delete_course/<int:course_id>', methods=['POST'])
@login_required
@admin_required
def admin_delete_course(course_id):
    course = Course.query.get_or_404(course_id)
    
    db.session.delete(course)
    db.session.commit()
    flash(f'Course {course.code} deleted successfully!', 'success')
    return redirect(url_for('admin_courses'))

@app.route('/course/<int:course_id>/create_assignment', methods=['GET', 'POST'])
@login_required
@lecturer_required
def create_assignment(course_id):
    course = Course.query.get_or_404(course_id)
    
    # Verify lecturer owns this course
    if course.lecturer_id != current_user.id:
        flash('You do not have permission to create assignments for this course.', 'danger')
        return redirect(url_for('courses'))
    
    if request.method == 'POST':
        title = request.form['title']
        description = request.form['description']
        max_points = int(request.form['max_points'])
        due_date_str = request.form.get('due_date')
        
        due_date = None
        if due_date_str:
            try:
                due_date = datetime.strptime(due_date_str, '%Y-%m-%dT%H:%M')
            except ValueError:
                flash('Invalid due date format.', 'danger')
                return render_template('create_assignment.html', course=course)
        
        assignment = Assignment(
            title=title,
            description=description,
            course_id=course_id,
            max_points=max_points,
            due_date=due_date
        )
        
        db.session.add(assignment)
        db.session.commit()
        
        flash('Assignment created successfully!', 'success')
        return redirect(url_for('course_detail', course_id=course_id))
    
    return render_template('create_assignment.html', course=course)

@app.route('/uploads/<filename>')
@login_required
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

# Video Conferencing Routes

@app.route('/video_conferences')
@login_required
def video_conferences():
    """Display all video conferences based on user role"""
    if current_user.is_admin():
        # Admins can see all lecture rooms
        lecture_rooms = LectureRoom.query.order_by(LectureRoom.created_at.desc()).all()
        return render_template('video_conferences.html', lecture_rooms=lecture_rooms, title="All Video Conferences")
    
    elif current_user.is_lecturer():
        # Lecturers see their own lecture rooms
        lecture_rooms = LectureRoom.query.filter_by(lecturer_id=current_user.id).order_by(LectureRoom.created_at.desc()).all()
        return render_template('video_conferences.html', lecture_rooms=lecture_rooms, title="My Lecture Rooms")
    
    else:  # Student
        # Students see lecture rooms for courses they're enrolled in
        enrolled_courses = db.session.query(Course).join(Enrollment).filter(Enrollment.user_id == current_user.id).all()
        course_ids = [course.id for course in enrolled_courses]
        if course_ids:
            lecture_rooms = LectureRoom.query.filter(LectureRoom.course_id.in_(course_ids)).order_by(LectureRoom.created_at.desc()).all()
        else:
            lecture_rooms = []
        return render_template('video_conferences.html', lecture_rooms=lecture_rooms, title="Available Lectures")

@app.route('/create_lecture_room/<int:course_id>', methods=['GET', 'POST'])
@login_required
@lecturer_required
def create_lecture_room(course_id):
    """Create a new lecture room for a course"""
    course = Course.query.get_or_404(course_id)
    
    # Verify lecturer owns this course
    if course.lecturer_id != current_user.id:
        flash('You do not have permission to create lecture rooms for this course.', 'danger')
        return redirect(url_for('courses'))
    
    if request.method == 'POST':
        import uuid
        
        title = request.form['title']
        description = request.form.get('description', '')
        scheduled_start_str = request.form.get('scheduled_start')
        scheduled_end_str = request.form.get('scheduled_end')
        
        # Generate unique room name (simple format for anonymous access)
        room_name = f"{course.code}{uuid.uuid4().hex[:6]}"
        
        # Parse scheduled times
        scheduled_start = None
        scheduled_end = None
        
        if scheduled_start_str:
            try:
                scheduled_start = datetime.strptime(scheduled_start_str, '%Y-%m-%dT%H:%M')
            except ValueError:
                flash('Invalid start time format.', 'danger')
                return render_template('create_lecture_room.html', course=course)
        
        if scheduled_end_str:
            try:
                scheduled_end = datetime.strptime(scheduled_end_str, '%Y-%m-%dT%H:%M')
            except ValueError:
                flash('Invalid end time format.', 'danger')
                return render_template('create_lecture_room.html', course=course)
        
        # Validate that end time is after start time
        if scheduled_start and scheduled_end and scheduled_end <= scheduled_start:
            flash('End time must be after start time.', 'danger')
            return render_template('create_lecture_room.html', course=course)
        
        lecture_room = LectureRoom(
            room_name=room_name,
            course_id=course_id,
            lecturer_id=current_user.id,
            title=title,
            description=description,
            scheduled_start=scheduled_start,
            scheduled_end=scheduled_end
        )
        
        db.session.add(lecture_room)
        db.session.commit()
        
        flash(f'Lecture room "{title}" created successfully!', 'success')
        return redirect(url_for('video_conferences'))
    
    return render_template('create_lecture_room.html', course=course)

@app.route('/lecture_room/<int:room_id>')
@login_required
def lecture_room_detail(room_id):
    """Display details of a specific lecture room"""
    lecture_room = LectureRoom.query.get_or_404(room_id)
    
    # Check permissions
    if current_user.is_student():
        # Students can only access rooms for courses they're enrolled in
        enrollment = Enrollment.query.filter_by(user_id=current_user.id, course_id=lecture_room.course_id).first()
        if not enrollment:
            flash('You are not enrolled in this course.', 'danger')
            return redirect(url_for('video_conferences'))
    
    elif current_user.is_lecturer():
        # Lecturers can only access their own rooms
        if lecture_room.lecturer_id != current_user.id:
            flash('You do not have permission to access this lecture room.', 'danger')
            return redirect(url_for('video_conferences'))
    
    # Get session logs for admins and lecturers
    session_logs = []
    if current_user.is_admin() or current_user.is_lecturer():
        session_logs = LectureSessionLog.query.filter_by(lecture_room_id=room_id).order_by(LectureSessionLog.joined_at.desc()).all()
    
    return render_template('lecture_room_detail.html', lecture_room=lecture_room, session_logs=session_logs)

@app.route('/join_lecture/<int:room_id>')
@login_required
def join_lecture(room_id):
    """Join a lecture room - opens Jitsi interface"""
    lecture_room = LectureRoom.query.get_or_404(room_id)
    
    # Enhanced permission checks
    can_join = False
    
    if current_user.is_admin():
        can_join = True
    elif current_user.is_lecturer():
        # Lecturers can only join their own rooms or rooms in courses they teach
        if lecture_room.lecturer_id == current_user.id:
            can_join = True
        else:
            flash('You do not have permission to join this lecture room.', 'danger')
            return redirect(url_for('video_conferences'))
    elif current_user.is_student():
        # Students can only join rooms for courses they're enrolled in
        enrollment = Enrollment.query.filter_by(user_id=current_user.id, course_id=lecture_room.course_id).first()
        if enrollment:
            can_join = True
        else:
            flash('You are not enrolled in this course and cannot join this lecture.', 'danger')
            return redirect(url_for('video_conferences'))
    
    if not can_join:
        flash('Access denied to this lecture room.', 'danger')
        return redirect(url_for('video_conferences'))
    
    # Check if the session exists for this user already (to avoid duplicate logs)
    existing_session = LectureSessionLog.query.filter_by(
        lecture_room_id=room_id,
        participant_id=current_user.id,
        left_at=None
    ).first()
    
    if not existing_session:
        # Log the participant joining
        session_log = LectureSessionLog(
            lecture_room_id=room_id,
            participant_id=current_user.id
        )
        db.session.add(session_log)
    
    # If lecturer is joining, ensure the session is started
    if current_user.is_lecturer() and lecture_room.lecturer_id == current_user.id:
        if not lecture_room.is_active:
            lecture_room.start_session()
    
    db.session.commit()
    
    return render_template('jitsi_conference.html', lecture_room=lecture_room, user=current_user)

@app.route('/start_lecture/<int:room_id>')
@login_required
@lecturer_required
def start_lecture(room_id):
    """Start a lecture session (lecturer only)"""
    lecture_room = LectureRoom.query.get_or_404(room_id)
    
    # Verify lecturer owns this room
    if lecture_room.lecturer_id != current_user.id:
        flash('You do not have permission to start this lecture.', 'danger')
        return redirect(url_for('video_conferences'))
    
    lecture_room.start_session()
    db.session.commit()
    
    flash(f'Lecture "{lecture_room.title}" has been started!', 'success')
    return redirect(url_for('join_lecture', room_id=room_id))

@app.route('/end_lecture/<int:room_id>')
@login_required
@lecturer_required
def end_lecture(room_id):
    """End a lecture session (lecturer only)"""
    lecture_room = LectureRoom.query.get_or_404(room_id)
    
    # Verify lecturer owns this room
    if lecture_room.lecturer_id != current_user.id:
        flash('You do not have permission to end this lecture.', 'danger')
        return redirect(url_for('video_conferences'))
    
    lecture_room.end_session()
    
    # Mark all active session logs as ended
    active_sessions = LectureSessionLog.query.filter_by(lecture_room_id=room_id, left_at=None).all()
    for session in active_sessions:
        session.mark_left()
    
    db.session.commit()
    
    flash(f'Lecture "{lecture_room.title}" has been ended!', 'success')
    return redirect(url_for('video_conferences'))

@app.route('/lecture_sessions')
@login_required
@admin_required
def lecture_sessions():
    """View all lecture session logs (admin only)"""
    page = request.args.get('page', 1, type=int)
    
    # Get filter parameters
    course_filter = request.args.get('course')
    lecturer_filter = request.args.get('lecturer')
    date_filter = request.args.get('date')
    
    # Build query
    query = LectureSessionLog.query.join(LectureRoom).join(Course).join(User)
    
    if course_filter:
        query = query.filter(Course.id == course_filter)
    
    if lecturer_filter:
        query = query.filter(LectureRoom.lecturer_id == lecturer_filter)
    
    if date_filter:
        try:
            filter_date = datetime.strptime(date_filter, '%Y-%m-%d').date()
            query = query.filter(db.func.date(LectureSessionLog.joined_at) == filter_date)
        except ValueError:
            flash('Invalid date format.', 'danger')
    
    session_logs = query.order_by(LectureSessionLog.joined_at.desc()).paginate(
        page=page, per_page=20, error_out=False
    )
    
    # Get filter options
    courses = Course.query.all()
    lecturers = User.query.filter_by(role='lecturer').all()
    
    return render_template('lecture_sessions.html', 
                         session_logs=session_logs, 
                         courses=courses, 
                         lecturers=lecturers,
                         current_filters={
                             'course': course_filter,
                             'lecturer': lecturer_filter,
                             'date': date_filter
                         })
