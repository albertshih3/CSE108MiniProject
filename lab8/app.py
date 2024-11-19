## Import statements
from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from flask_admin import Admin 
from flask_admin.contrib.sqla import ModelView
from flask_admin.form import Select2Widget
from wtforms import SelectField, PasswordField, StringField
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///enrollment.db'
db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

## End of import statements ##

## Database Models ##
    
# User database model
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(120), nullable=False)
    role = db.Column(db.String(20), nullable=False)
    display_name = db.Column(db.String(100))

    def __str__(self):
        return self.username

# Course database model
class Course(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    teacher_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    time = db.Column(db.String(50), nullable=False)
    capacity = db.Column(db.Integer, nullable=False)
    teacher = db.relationship('User', backref='courses')

# Enrollment database model
class Enrollment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    course_id = db.Column(db.Integer, db.ForeignKey('course.id'), nullable=False)
    grade = db.Column(db.Integer, nullable=True)
    student = db.relationship('User', backref='enrollments')
    course = db.relationship('Course', backref='enrollments')
    
## End of database models ##

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# Routes
@app.route('/')
def index():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        user = User.query.filter_by(username=request.form['username']).first()
        if user and check_password_hash(user.password_hash, request.form['password']):
            login_user(user)
            return redirect(url_for('dashboard'))
        flash('Invalid username or password')
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

@app.route('/dashboard')
@login_required
def dashboard():
    if current_user.role == 'student':
        enrollments = Enrollment.query.filter_by(student_id=current_user.id).all()
        courses = Course.query.all()
        return render_template('student_dashboard.html', enrollments=enrollments, courses=courses)
    elif current_user.role == 'teacher':
        courses = Course.query.filter_by(teacher_id=current_user.id).all()
        return render_template('teacher_dashboard.html', courses=courses)
    return redirect(url_for('admin.index'))

@app.route('/enroll/<int:course_id>', methods=['POST'])
@login_required
def enroll(course_id):
    if current_user.role != 'student':
        return redirect(url_for('dashboard'))
    
    course = Course.query.get_or_404(course_id)
    current_enrollment = Enrollment.query.filter_by(course_id=course_id).count()
    
    if current_enrollment >= course.capacity:
        flash('Course is full')
        return redirect(url_for('dashboard'))
    
    enrollment = Enrollment(student_id=current_user.id, course_id=course_id)
    db.session.add(enrollment)
    db.session.commit()
    return redirect(url_for('dashboard'))

@app.route('/update_grade/<int:enrollment_id>', methods=['POST'])
@login_required
def update_grade(enrollment_id):
    if current_user.role != 'teacher':
        return redirect(url_for('dashboard'))
    
    enrollment = Enrollment.query.get_or_404(enrollment_id)
    course = Course.query.get(enrollment.course_id)
    
    if course.teacher_id != current_user.id:
        return redirect(url_for('dashboard'))
    
    grade = request.form.get('grade')
    if grade and grade.isdigit():
        enrollment.grade = int(grade)
        db.session.commit()
    
    return redirect(url_for('dashboard'))

@app.route('/drop_class/<int:enrollment_id>', methods=['POST'])
@login_required
def drop_class(enrollment_id):
    if current_user.role != 'student':
        return redirect(url_for('dashboard'))
    
    enrollment = Enrollment.query.get_or_404(enrollment_id)
    
    if enrollment.student_id != current_user.id:
        return redirect(url_for('dashboard'))
    
    db.session.delete(enrollment)
    db.session.commit()
    
    return redirect(url_for('dashboard'))

# Admin views
class AdminModelView(ModelView):
    def is_accessible(self):
        return current_user.is_authenticated and current_user.role == 'admin'
    
# ChildView class for displaying child models in Flask-Admin
class ChildView(ModelView):
    column_display_pk = True
    column_hide_backrefs = False
    column_list = ('course_id', 'course_name', 'student_id', 'student_name', 'grade')
    column_labels = {
        'course_name': 'Course Name',
        'student_name': 'Student Name',
        'grade': 'Grade'
    }
    form_columns = ('course_id', 'student_id', 'grade')

    def _course_name_formatter(view, context, model, name):
        return model.course.name

    def _student_name_formatter(view, context, model, name):
        return model.student.display_name

    column_formatters = {
        'course_name': _course_name_formatter,
        'student_name': _student_name_formatter
    }
    
    def is_accessible(self):
        return current_user.is_authenticated and current_user.role == 'admin'
    
class UserView(ModelView):
    column_display_pk = True
    column_list = ('id', 'username', 'password_hash', 'role', 'display_name')
    
    # Explicitly define the form
    
    def is_accessible(self):
        return current_user.is_authenticated and current_user.role == 'admin'

admin = Admin(app, name='ACME University Admin', template_mode='bootstrap4')
admin.add_view(UserView(User, db.session))
admin.add_view(AdminModelView(Course, db.session))
admin.add_view(ChildView(Enrollment, db.session))

def init_db():
    # Create users if they don't exist
    users = [
        # Teachers
        {
            'username': 'ahepworth',
            'password': 'password123',
            'role': 'teacher',
            'display_name': 'Dr. Hepworth'
        },
        {
            'username': 'swalker',
            'password': 'password123',
            'role': 'teacher',
            'display_name': 'Susan Walker'
        },
        {
            'username': 'rjenkins',
            'password': 'password123',
            'role': 'teacher',
            'display_name': 'Ralph Jenkins'
        },
        # Students
        {
            'username': 'cnorris',
            'password': 'password123',
            'role': 'student',
            'display_name': 'Chuck Norris'
        },
        {
            'username': 'mnorris',
            'password': 'password123',
            'role': 'student',
            'display_name': 'Mindy Norris'
        },
        {
            'username': 'nlittle',
            'password': 'password123',
            'role': 'student',
            'display_name': 'Nancy Little'
        },
        {
            'username': 'jstuart',
            'password': 'password123',
            'role': 'student',
            'display_name': 'John Stuart'
        },
        # Admin
        {
            'username': 'admin',
            'password': 'admin123',
            'role': 'admin',
            'display_name': 'Admin'
        }
    ]

    # Create users
    created_users = {}
    for user_data in users:
        if not User.query.filter_by(username=user_data['username']).first():
            user = User(
                username=user_data['username'],
                password_hash=generate_password_hash(user_data['password']),
                role=user_data['role'],
                display_name=user_data['display_name']
            )
            db.session.add(user)
            db.session.flush()
            created_users[user_data['username']] = user

    # Create courses if they don't exist
    courses = [
        {
            'name': 'Math 101',
            'teacher': 'rjenkins',
            'time': 'MWF 10:00-10:50 AM',
            'capacity': 8
        },
        {
            'name': 'Physics 121',
            'teacher': 'swalker',
            'time': 'TR 11:00-11:50 AM',
            'capacity': 10
        },
        {
            'name': 'CS 106',
            'teacher': 'ahepworth',
            'time': 'MWF 2:00-2:50 PM',
            'capacity': 10
        },
        {
            'name': 'CS 162',
            'teacher': 'ahepworth',
            'time': 'TR 3:00-3:50 PM',
            'capacity': 4
        }
    ]

    created_courses = {}
    for course_data in courses:
        if not Course.query.filter_by(name=course_data['name']).first():
            teacher = created_users.get(course_data['teacher'])
            if teacher:
                course = Course(
                    name=course_data['name'],
                    teacher_id=teacher.id,
                    time=course_data['time'],
                    capacity=course_data['capacity']
                )
                db.session.add(course)
                db.session.flush()
                created_courses[course_data['name']] = course

    # Create initial enrollments and grades
    enrollments_data = [
        {'course': 'Math 101', 'students': [
            ('jstuart', 86),
            ('nlittle', 53),
        ]},
        {'course': 'Physics 121', 'students': [
            ('mnorris', 94),
            ('jstuart', 91),
        ]},
        {'course': 'CS 106', 'students': [
            ('nlittle', 57),
            ('mnorris', 68),
        ]},
        {'course': 'CS 162', 'students': [
            ('jstuart', 67),
            ('nlittle', 87),
        ]}
    ]

    for enrollment_data in enrollments_data:
        course = Course.query.filter_by(name=enrollment_data['course']).first()
        if course:
            for username, grade in enrollment_data['students']:
                student = User.query.filter_by(username=username).first()
                if student and not Enrollment.query.filter_by(student_id=student.id, course_id=course.id).first():
                    enrollment = Enrollment(
                        student_id=student.id,
                        course_id=course.id,
                        grade=grade
                    )
                    db.session.add(enrollment)

    db.session.commit()

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        init_db()
    app.run(debug=True)