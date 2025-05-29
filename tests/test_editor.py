import pytest
from flask import session, url_for
import urllib.parse 
from app import db, Course # Import db and Course

# Tests from old test_auth.py to ensure old auth routes are gone
def test_register_route_is_gone(client):
    response = client.get('/register', follow_redirects=False)
    assert response.status_code == 404

def test_login_route_is_gone(client): # User login, not editor login
    response = client.get('/login', follow_redirects=False)
    assert response.status_code == 404

def test_logout_route_is_gone(client): # User logout, not editor logout
    response = client.get('/logout', follow_redirects=False)
    assert response.status_code == 404

# --- Editor Login/Logout Tests ---

def test_editor_login_page_loads(client):
    response = client.get(url_for('editor_login'))
    assert response.status_code == 200
    assert b"Editor Mode Login" in response.data
    assert b"Password" in response.data

def test_editor_login_success(client, app): 
    with client: 
        response = client.post(url_for('editor_login'), data={'password': app.config['EDITOR_PASSWORD']}, follow_redirects=True)
        assert response.status_code == 200
        assert b"Editor mode activated." in response.data
        assert url_for('list_courses') in response.request.path 
        with client.session_transaction() as sess:
            assert sess.get('is_editor') is True
        # Clean up session for next test using this client
        client.get(url_for('editor_logout'))


def test_editor_login_incorrect_password(client, app): 
    response = client.post(url_for('editor_login'), data={'password': 'wrongpassword'}, follow_redirects=True)
    assert response.status_code == 200
    assert b"Incorrect password." in response.data
    with client.session_transaction() as sess: 
        assert sess.get('is_editor') is None

def test_editor_logout(editor_client, app): # editor_client fixture logs in first
    response = editor_client.get(url_for('editor_logout'), follow_redirects=True)
    assert response.status_code == 200
    assert b"Editor mode deactivated." in response.data
    assert url_for('list_courses') in response.request.path 
    
    # Verify session is cleared by trying to access a protected route
    after_logout_response = editor_client.get(url_for('add_course'), follow_redirects=False)
    assert after_logout_response.status_code == 302 
    assert url_for('editor_login') in after_logout_response.location

# --- @editor_required Decorator Tests ---

def test_editor_required_redirects_for_add_course(client):
    target_url_path = url_for('add_course')
    response = client.get(target_url_path, follow_redirects=False)
    assert response.status_code == 302 
    # Check if the location STARTS with the editor_login URL
    assert response.location.startswith(url_for('editor_login'))
    # Check if the 'next' parameter correctly contains the URL-encoded target path
    assert "next=" + urllib.parse.quote(target_url_path, safe='') in response.location

def test_editor_required_redirects_for_upload_video(client):
    target_url_path = url_for('upload_video')
    response = client.get(target_url_path, follow_redirects=False)
    assert response.status_code == 302
    assert response.location.startswith(url_for('editor_login'))
    assert "next=" + urllib.parse.quote(target_url_path, safe='') in response.location


def test_editor_can_access_add_course_when_logged_in(editor_client, app): 
    response = editor_client.get(url_for('add_course'))
    assert response.status_code == 200
    assert b"Add New Course" in response.data

def test_editor_can_access_upload_video_when_logged_in(editor_client, app, new_course_id): 
    response = editor_client.get(url_for('upload_video'))
    assert response.status_code == 200
    assert b"Upload New Video" in response.data
    assert b"Assign to Course" in response.data 
    with app.app_context(): 
        course = db.session.get(Course, new_course_id)
        assert course is not None, "Course from fixture not found"
        assert bytes(f'<option value="{new_course_id}">{course.title}</option>', 'utf-8') in response.data
