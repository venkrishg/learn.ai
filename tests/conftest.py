import pytest
import os
import tempfile
import io 
import uuid # For unique titles
from app import app as flask_app, db, Video, Review, Course, VideoMaterial # Ensure all models are imported

@pytest.fixture(scope='module')
def app():
    """Instance of Main flask app"""
    flask_app.config['TESTING'] = True
    flask_app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
    flask_app.config['WTF_CSRF_ENABLED'] = False  
    flask_app.config['SECRET_KEY'] = 'test-secret-key' 
    flask_app.config['EDITOR_PASSWORD'] = 'Scrolls@2021' 

    temp_upload_folder = tempfile.mkdtemp(prefix="vid_") 
    flask_app.config['UPLOAD_FOLDER'] = temp_upload_folder
    
    temp_materials_folder = tempfile.mkdtemp(prefix="mat_") 
    flask_app.config['MATERIALS_UPLOAD_FOLDER'] = temp_materials_folder

    with flask_app.app_context():
        db.create_all()
        yield flask_app # Tests run here
        db.drop_all() # Ensure this happens after all tests in the module
        
        # Cleanup temporary folders
        for folder_path in [temp_upload_folder, temp_materials_folder]:
            if os.path.exists(folder_path) and os.path.isdir(folder_path):
                for root, dirs, files in os.walk(folder_path, topdown=False):
                    for name in files:
                        try: os.remove(os.path.join(root, name))
                        except OSError: pass 
                    for name in dirs:
                        try: os.rmdir(os.path.join(root, name))
                        except OSError: pass
                try: os.rmdir(folder_path)
                except OSError: pass

@pytest.fixture(scope='module')
def client(app): # client has module scope, depends on app (module scope)
    return app.test_client()

@pytest.fixture(scope='function') 
def init_database(app): # app is module-scoped, but this fixture is function-scoped
    with app.app_context():
        db.session.remove() 
        db.drop_all() 
        db.create_all() 
        yield db
        db.session.remove() 

@pytest.fixture(scope='function')
def uploaded_video_id(app, init_database): 
    with app.app_context():
        unique_filename = f'test_no_course_{uuid.uuid4().hex[:6]}.mp4'
        video = Video(title=f'Test Video NoCourse {uuid.uuid4().hex[:6]}', 
                      description='A test video without a course.', 
                      filename=unique_filename, 
                      user_id=None)
        db.session.add(video)
        db.session.commit()
        upload_folder = app.config['UPLOAD_FOLDER']
        os.makedirs(upload_folder, exist_ok=True)
        with open(os.path.join(upload_folder, unique_filename), 'wb') as f:
            f.write(b"dummy video data")
        return video.id

@pytest.fixture(scope='function')
def editor_client(client, app, init_database): 
    """Logs in as an editor and yields the test client. Ensures session is clean before login."""
    # Use a separate client instance for editor to avoid session conflicts with the main 'client'
    editor_test_client = app.test_client()
    with editor_test_client.session_transaction() as sess: 
        sess.clear()

    response = editor_test_client.post('/editor_login', data={'password': app.config['EDITOR_PASSWORD']}, follow_redirects=True)
    assert response.status_code == 200, f"Editor login failed. Response data: {response.data.decode()}"
    assert b"Editor mode activated." in response.data
    
    yield editor_test_client 
    
    editor_test_client.get('/editor_logout', follow_redirects=True)
    with editor_test_client.session_transaction() as sess:
         assert 'is_editor' not in sess, "Editor session was not cleared after test."


@pytest.fixture(scope='function')
def new_course_id(editor_client, app, init_database): 
    """Creates a sample course with a unique title using the editor_client and returns its ID."""
    unique_title = f"Test Course Fixture {uuid.uuid4().hex[:8]}"
    course_data = {
        'title': unique_title,
        'description': 'Test course description for fixture.'
    }
    response = editor_client.post('/add_course', data=course_data, follow_redirects=False)
    assert response.status_code == 302, f"Course creation for '{unique_title}' should redirect. Status: {response.status_code}. HTML: {response.data.decode()}"
    assert '/courses' in response.location, "Should redirect to courses list."
    
    with app.app_context():
        course = Course.query.filter_by(title=unique_title).first()
        assert course is not None, f"Course '{unique_title}' was not found in DB after creation by fixture."
        return course.id

@pytest.fixture(scope='function')
def video_with_course_id(editor_client, app, new_course_id, init_database): 
    """Uploads a video associated with the course from new_course_id and returns video ID."""
    unique_title = f"Test Video for Course {uuid.uuid4().hex[:8]}"
    unique_filename = f'course_video_fixture_{uuid.uuid4().hex[:6]}.mp4'
    video_data = {
        'title': unique_title,
        'description': 'A video linked to a test course for fixture.',
        'video_file': (io.BytesIO(b"fake video data for course video fixture"), unique_filename),
        'course': str(new_course_id) 
    }
    response = editor_client.post('/upload_video', data=video_data, content_type='multipart/form-data', follow_redirects=True)
    assert response.status_code == 200, f"Video upload for '{unique_title}' failed. HTML: {response.data.decode()}"
    assert b"Video uploaded successfully!" in response.data

    with app.app_context():
        video = Video.query.filter_by(title=unique_title).first()
        assert video is not None, f"Video '{unique_title}' for course not found in DB (fixture)."
        assert video.course_id == new_course_id
        upload_folder = app.config['UPLOAD_FOLDER']
        os.makedirs(upload_folder, exist_ok=True)
        with open(os.path.join(upload_folder, unique_filename), 'wb') as f:
            f.write(b"fake video data for course video fixture")
        return video.id

@pytest.fixture(scope='function')
def new_material_id(editor_client, app, video_with_course_id, init_database): 
    """Adds a sample material (comment type) to the video and returns material ID."""
    unique_content = f'Sample material comment for fixture {uuid.uuid4().hex[:8]}'
    material_data = {
        'material_type': 'comment',
        'content': unique_content,
        'submit_material': 'Add Material' # Explicitly "click" the submit button
    }
    response = editor_client.post(f'/video/{video_with_course_id}', data=material_data, follow_redirects=False) 
    assert response.status_code == 302, f"Material submission for video {video_with_course_id} failed. HTML: {response.data.decode()}"
    assert f'/video/{video_with_course_id}' in response.location

    with app.app_context():
        material = VideoMaterial.query.filter_by(video_id=video_with_course_id, content=unique_content).first()
        assert material is not None, f"Material '{unique_content}' not found in DB (fixture)."
        return material.id

@pytest.fixture(scope='function')
def new_review_id(client, app, uploaded_video_id, init_database): 
    """Submits a sample review for the video created by uploaded_video_id fixture."""
    unique_comment = f'This is a test review comment for fixture {uuid.uuid4().hex[:8]}!'
    review_data = {
        'rating': '5', 
        'comment': unique_comment,
        'submit_review': 'Submit Review' # Explicitly "click" the submit button
    }
    response = client.post(f'/video/{uploaded_video_id}', data=review_data, follow_redirects=False)
    assert response.status_code == 302, f"Review submission for video {uploaded_video_id} failed. HTML: {response.data.decode()}"
    assert f'/video/{uploaded_video_id}' in response.location

    with app.app_context():
        review = Review.query.filter_by(video_id=uploaded_video_id, comment=unique_comment).order_by(Review.created_at.desc()).first()
        assert review is not None, f"Review '{unique_comment}' not found in DB (fixture)."
        return review.id
