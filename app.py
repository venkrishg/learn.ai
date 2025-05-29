import os
from flask import Flask, render_template, redirect, url_for, flash, send_from_directory, session, request, abort
from flask_sqlalchemy import SQLAlchemy
from flask_wtf import FlaskForm
from flask_wtf.file import FileField, FileAllowed
from wtforms import StringField, SubmitField, TextAreaField, SelectField, PasswordField 
from wtforms.validators import DataRequired, Optional, Length 
from werkzeug.utils import secure_filename
from datetime import datetime 
from functools import wraps 
import uuid # For unique filenames
# import os # Already imported at the top

UPLOAD_FOLDER = 'uploads/videos'
MATERIALS_UPLOAD_FOLDER = 'uploads/materials' 
EDITOR_PASSWORD = 'Scrolls@2021' 

app = Flask(__name__)
app.config['SECRET_KEY'] = os.urandom(24) 
app.config['EDITOR_PASSWORD'] = EDITOR_PASSWORD
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///site.db'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MATERIALS_UPLOAD_FOLDER'] = MATERIALS_UPLOAD_FOLDER 
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True) 
os.makedirs(app.config['MATERIALS_UPLOAD_FOLDER'], exist_ok=True) 
db = SQLAlchemy(app)

class Course(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(150), nullable=False, unique=True)
    description = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f'<Course {self.title}>'

class VideoMaterial(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    video_id = db.Column(db.Integer, db.ForeignKey('video.id'), nullable=False)
    material_type = db.Column(db.String(50), nullable=False)
    content = db.Column(db.Text, nullable=True) 
    filename = db.Column(db.String(255), nullable=True) 
    original_filename = db.Column(db.String(255), nullable=True)
    uploaded_at = db.Column(db.DateTime, default=datetime.utcnow)
    video = db.relationship('Video', backref=db.backref('materials', lazy='dynamic', cascade='all, delete-orphan'))

    def __repr__(self):
        return f'<VideoMaterial {self.id} type={self.material_type}>'

class Video(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text, nullable=True)
    filename = db.Column(db.String(100), nullable=False)
    uploaded_at = db.Column(db.DateTime, default=datetime.utcnow) 
    user_id = db.Column(db.Integer, nullable=True) 
    reviews = db.relationship('Review', backref='video', lazy='dynamic') 
    course_id = db.Column(db.Integer, db.ForeignKey('course.id'), nullable=False)
    course = db.relationship('Course', backref=db.backref('videos', lazy='dynamic'))

    def __repr__(self):
        return f"Video('{self.title}', '{self.filename}')"

class Review(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    video_id = db.Column(db.Integer, db.ForeignKey('video.id'), nullable=False)
    rating = db.Column(db.Integer, nullable=False) 
    comment = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow) 

    def __repr__(self):
        return f"<Review {self.id} {self.rating}>"

class VideoUploadForm(FlaskForm):
    title = StringField('Title', validators=[DataRequired()])
    description = TextAreaField('Description')
    video_file = FileField('Video File', validators=[DataRequired(), FileAllowed(['mp4', 'mov', 'avi', 'mkv'], 'Videos only!')])
    course = SelectField('Assign to Course', coerce=int, validators=[DataRequired()]) 
    submit = SubmitField('Upload Video')

class ReviewForm(FlaskForm):
    rating = SelectField('Rating', choices=[(str(i), f'{i} Star{"s" if i > 1 else ""}') for i in range(1, 6)], validators=[DataRequired()])
    comment = TextAreaField('Comment', validators=[Optional()])
    submit_review = SubmitField('Submit Review') 

class AddMaterialForm(FlaskForm):
    material_type = SelectField('Material Type', choices=[('comment', 'Comment'), ('link', 'Link/URL'), ('file', 'File Upload')], validators=[DataRequired()])
    content = TextAreaField('Comment or Link URL', validators=[Optional()])
    file = FileField('Upload File', validators=[Optional()])
    submit_material = SubmitField('Add Material') 

class EditorLoginForm(FlaskForm):
    password = PasswordField('Password', validators=[DataRequired()])
    submit = SubmitField('Enter Editor Mode')

class CourseForm(FlaskForm):
    title = StringField('Course Title', validators=[DataRequired(), Length(min=3, max=150)])
    description = TextAreaField('Course Description', validators=[Optional()])
    submit = SubmitField('Create Course')

def editor_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('is_editor'):
            flash('You need to be in editor mode to access this page.', 'warning')
            return redirect(url_for('editor_login', next=request.url))
        return f(*args, **kwargs)
    return decorated_function

@app.route('/')
def hello_world():
    return redirect(url_for('list_courses')) 

@app.route('/add_course', methods=['GET', 'POST'])
@editor_required
def add_course():
    form = CourseForm()
    if form.validate_on_submit():
        existing_course = Course.query.filter_by(title=form.title.data).first()
        if existing_course:
            flash('A course with this title already exists.', 'warning')
        else:
            new_course = Course(title=form.title.data, description=form.description.data)
            db.session.add(new_course)
            db.session.commit()
            flash(f'Course "{new_course.title}" created successfully!', 'success')
            return redirect(url_for('list_courses'))
    return render_template('add_course.html', form=form, page_title="Add New Course")

@app.route('/upload_video', methods=['GET', 'POST'])
@editor_required 
def upload_video():
    form = VideoUploadForm()
    form.course.choices = [(c.id, c.title) for c in Course.query.order_by('title').all()]
    if not form.course.choices:
        pass

    if form.validate_on_submit():
        video_file = form.video_file.data
        filename = secure_filename(video_file.filename)
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        video_file.save(file_path)

        video = Video(
            title=form.title.data,
            description=form.description.data,
            filename=filename,
            course_id=form.course.data, 
            user_id=None 
        )
        db.session.add(video)
        db.session.commit()
        flash('Video uploaded successfully!', 'success')
        return redirect(url_for('hello_world')) 

    return render_template('upload_video.html', form=form)

@app.route('/editor_login', methods=['GET', 'POST'])
def editor_login():
    form = EditorLoginForm()
    if form.validate_on_submit():
        if form.password.data == app.config['EDITOR_PASSWORD']:
            session['is_editor'] = True
            flash('Editor mode activated.', 'success')
            next_page = request.args.get('next')
            return redirect(next_page or url_for('hello_world'))
        else:
            flash('Incorrect password.', 'danger')
    return render_template('editor_login.html', form=form, page_title="Editor Login")

@app.route('/editor_logout')
def editor_logout():
    session.pop('is_editor', None)
    flash('Editor mode deactivated.', 'info')
    return redirect(url_for('hello_world'))

@app.route('/videos')
def video_list():
    videos = Video.query.all()
    return render_template('video_list.html', videos=videos)

@app.route('/video/<int:video_id>', methods=['GET', 'POST']) 
def view_video(video_id):
    video = db.session.get(Video, video_id)
    if not video:
        return render_template('404.html'), 404
    
    form = ReviewForm(prefix="review_form") 
    material_form = AddMaterialForm(prefix="material_form") 

    if request.method == 'POST':
        if material_form.submit_material.data and session.get('is_editor'):
            new_material = None # Initialize new_material here
            if material_form.validate_on_submit():
                material_type = material_form.material_type.data
                if material_type in ['comment', 'link']:
                    content = material_form.content.data 
                    if not content: 
                        flash('Content is required for comment or link type.', 'danger')
                    else: 
                        new_material = VideoMaterial(video_id=video.id, material_type=material_type, content=content)
                elif material_type == 'file': 
                    uploaded_file = material_form.file.data 
                    if uploaded_file and uploaded_file.filename != '': 
                        original_fn = secure_filename(uploaded_file.filename) 
                        unique_fn = str(uuid.uuid4()) + "_" + original_fn 
                        file_path = os.path.join(app.config['MATERIALS_UPLOAD_FOLDER'], unique_fn) 
                        uploaded_file.save(file_path) 
                        new_material = VideoMaterial(video_id=video.id, material_type=material_type, filename=unique_fn, original_filename=original_fn, content=f"File: {original_fn}") 
                    else: 
                        flash('No file selected for file upload type.', 'danger') 
                
                if new_material: # This block is now correctly indented INSIDE validate_on_submit
                    db.session.add(new_material)
                    db.session.commit()
                    flash('Material added successfully!', 'success')
                    return redirect(url_for('view_video', video_id=video.id))
            # If material_form was submitted but not valid, it will fall through to render_template with its errors.
        
        elif form.submit_review.data: 
            if form.validate_on_submit():
                rating = int(form.rating.data)
                comment = form.comment.data
                new_review = Review(video_id=video.id, rating=rating, comment=comment)
                db.session.add(new_review)
                db.session.commit()
                flash('Your review has been submitted successfully!', 'success')
                return redirect(url_for('view_video', video_id=video.id))
            # If review_form was submitted but not valid, it will fall through.
        
    reviews = video.reviews.order_by(Review.created_at.desc()).all()
    materials = video.materials.order_by(VideoMaterial.uploaded_at.asc()).all() 
    
    if reviews:
        avg_rating = sum(r.rating for r in reviews) / len(reviews)
    else:
        avg_rating = 0
        
    return render_template('view_video.html', video=video, form=form, material_form=material_form, reviews=reviews, materials=materials, avg_rating=avg_rating)

@app.route('/courses')
def list_courses():
    courses = Course.query.order_by('title').all()
    return render_template('course_list.html', courses=courses, page_title="Available Courses")

@app.route('/course/<int:course_id>')
def view_course(course_id):
    course = Course.query.get_or_404(course_id) 
    videos = course.videos.order_by(Video.uploaded_at.asc()).all() 
    return render_template('view_course.html', course=course, videos=videos, page_title=course.title)

@app.route('/download_material/<int:material_id>')
def download_material(material_id):
    material = VideoMaterial.query.get_or_404(material_id)
    if material.material_type == 'file' and material.filename:
        return send_from_directory(
            app.config['MATERIALS_UPLOAD_FOLDER'], 
            material.filename, 
            as_attachment=True, 
            download_name=material.original_filename
        )
    else:
        abort(404)

@app.route('/uploads/videos/<filename>')
def serve_video_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

@app.errorhandler(404)
def page_not_found(e):
    return render_template('404.html'), 404

with app.app_context():
    db.create_all()

if __name__ == '__main__':
    app.run(debug=True)
