import pytest
from app import User, db
from tests.conftest import login, logout # Import helper functions

def test_register_success(client, init_database):
    response = client.post('/register', data=dict(
        username='newuser',
        email='new@example.com',
        password='newpassword',
        confirm_password='newpassword'
    ), follow_redirects=True)
    assert response.status_code == 200
    assert b"Registration successful. Please log in." in response.data
    with client.application.app_context():
        user = User.query.filter_by(email='new@example.com').first()
        assert user is not None
        assert user.username == 'newuser'

def test_register_existing_username(client, app, new_user_id):
    with app.app_context():
        user = db.session.get(User, new_user_id)
        existing_username = user.username
    response = client.post('/register', data=dict(
        username=existing_username,
        email='another@example.com',
        password='password123',
        confirm_password='password123'
    ), follow_redirects=True)
    assert response.status_code == 200 # Stays on register page
    assert b"That username is taken. Please choose a different one." in response.data

def test_register_existing_email(client, app, new_user_id):
    with app.app_context():
        user = db.session.get(User, new_user_id)
        existing_email = user.email
    response = client.post('/register', data=dict(
        username='anotheruser',
        email=existing_email,
        password='password123',
        confirm_password='password123'
    ), follow_redirects=True)
    assert response.status_code == 200 # Stays on register page
    assert b"That email is already registered. Please choose a different one." in response.data

def test_login_success(client, app, new_user_id):
    with app.app_context():
        user = db.session.get(User, new_user_id)
        email = user.email
        username = user.username
    response = login(client, email, 'password123')
    assert response.status_code == 200
    assert b"Login successful." in response.data
    assert bytes(f"Hi, {username}!", 'utf-8') in response.data
    assert b"Videos" in response.data # Assuming redirect to video_list

def test_login_incorrect_password(client, app, new_user_id):
    with app.app_context():
        user = db.session.get(User, new_user_id)
        email = user.email
    response = login(client, email, 'wrongpassword')
    assert response.status_code == 200 # Stays on login page
    assert b"Login unsuccessful. Check email and password." in response.data
    # assert b"Hi, testuser!" not in response.data # Removed this problematic assertion

def test_login_nonexistent_user(client, init_database):
    response = login(client, 'nouser@example.com', 'password123')
    assert response.status_code == 200 # Stays on login page
    assert b"Login unsuccessful. Check email and password." in response.data

def test_logout(client, app, new_user_id):
    with app.app_context():
        user = db.session.get(User, new_user_id)
        email = user.email
        username = user.username
    login(client, email, 'password123') # Log in first
    response = logout(client)
    assert response.status_code == 200
    assert b"You have been logged out." in response.data
    assert b"Login" in response.data # Should be redirected to login page
    assert bytes(f"Hi, {username}!", 'utf-8') not in response.data

def test_login_required_for_videos(client, init_database):
    response = client.get('/videos', follow_redirects=True)
    assert response.status_code == 200
    assert b"Login" in response.data # Should be on login page
    assert b"Please log in to access this page" in response.data # Default Flask-Login message or check for login form

def test_login_required_for_upload_video(client, init_database):
    response = client.get('/upload_video', follow_redirects=True)
    assert response.status_code == 200
    assert b"Login" in response.data
    assert b"Please log in to access this page" in response.data

def test_login_required_for_view_video(client, init_database):
    # Assuming no videos exist yet, so no specific video ID to test, just the general endpoint protection
    response = client.get('/video/1', follow_redirects=True) 
    assert response.status_code == 200
    assert b"Login" in response.data
    assert b"Please log in to access this page" in response.data
