import pytest
import os
import tempfile
from app import app as flask_app, db, User, Video
from werkzeug.security import generate_password_hash

@pytest.fixture(scope='module')
def app():
    """Instance of Main flask app"""
    flask_app.config['TESTING'] = True
    flask_app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
    flask_app.config['WTF_CSRF_ENABLED'] = False  # Disable CSRF for testing forms
    flask_app.config['SECRET_KEY'] = 'test-secret-key' 

    # Create a temporary folder for uploads during tests
    temp_upload_folder = tempfile.mkdtemp()
    flask_app.config['UPLOAD_FOLDER'] = temp_upload_folder
    
    with flask_app.app_context():
        db.create_all()
        yield flask_app
        db.drop_all()
        # Clean up the temporary upload folder
        for root, dirs, files in os.walk(temp_upload_folder, topdown=False):
            for name in files:
                os.remove(os.path.join(root, name))
            for name in dirs:
                os.rmdir(os.path.join(root, name))
        os.rmdir(temp_upload_folder)


@pytest.fixture(scope='module')
def client(app):
    """A test client for the app."""
    return app.test_client()

@pytest.fixture(scope='function') # Use function scope to ensure clean DB for each test
def init_database(app):
    """Clear and re-initialize the database for each test function."""
    with app.app_context():
        db.session.remove()
        db.drop_all()
        db.create_all()
        yield db # Not strictly necessary to yield db, but can be useful

@pytest.fixture(scope='function')
def new_user_id(app, init_database):
    user = User(username='testuser', email='test@example.com', password_hash=generate_password_hash('password123'))
    with app.app_context():
        db.session.add(user)
        db.session.commit()
        user_id = user.id
    return user_id

@pytest.fixture(scope='function')
def editor_user_id(app, init_database):
    user = User(username='editoruser', email='editor@example.com', password_hash=generate_password_hash('password123'), is_editor=True)
    with app.app_context():
        db.session.add(user)
        db.session.commit()
        user_id = user.id
    return user_id

@pytest.fixture(scope='function')
def uploaded_video_id(app, init_database, editor_user_id):
    # Need the editor user object to link the video
    with app.app_context():
        editor = db.session.get(User, editor_user_id)
        video = Video(title='Test Video', description='A test video', filename='test.mp4', uploader=editor)
        db.session.add(video)
        db.session.commit()
        video_id = video.id
    return video_id

# Helper function to log in a user
def login(client, email, password):
    return client.post('/login', data=dict(
        email=email,
        password=password
    ), follow_redirects=True)

# Helper function to log out a user
def logout(client):
    return client.get('/logout', follow_redirects=True)
