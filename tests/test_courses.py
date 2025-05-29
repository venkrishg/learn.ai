import pytest
from app import db, Course, Video 
from flask import url_for
import uuid # Added uuid import

# --- Course Creation Tests (Editor Mode) ---

def test_add_course_page_loads_for_editor(editor_client):
    response = editor_client.get(url_for('add_course'))
    assert response.status_code == 200
    assert b"Add New Course" in response.data

def test_successful_course_creation(editor_client, app):
    unique_title = f"New Unique Course {uuid.uuid4().hex[:6]}"
    course_data = {
        'title': unique_title,
        'description': 'A description for this unique course.'
    }
    response = editor_client.post(url_for('add_course'), data=course_data, follow_redirects=False)
    assert response.status_code == 302 
    assert url_for('list_courses') in response.location

    redirected_response = editor_client.get(response.location) 
    assert redirected_response.status_code == 200
    # Flask's flash messages are HTML escaped by default by Jinja2
    expected_flash_message = f'Course "{unique_title}" created successfully!'.replace('"', '&quot;')
    assert bytes(expected_flash_message, 'utf-8') in redirected_response.data
    
    with app.app_context():
        course = Course.query.filter_by(title=unique_title).first()
        assert course is not None
        assert course.description == 'A description for this unique course.'

def test_create_course_existing_title(editor_client, app, new_course_id): 
    with app.app_context():
        existing_course = db.session.get(Course, new_course_id)
        assert existing_course is not None, "Fixture new_course_id did not create a course."
        existing_title = existing_course.title
        
    course_data = {
        'title': existing_title, 
        'description': 'Another description.'
    }
    response = editor_client.post(url_for('add_course'), data=course_data, follow_redirects=True)
    assert response.status_code == 200 
    assert b"A course with this title already exists." in response.data
    
    with app.app_context():
        courses_with_title = Course.query.filter_by(title=existing_title).all()
        assert len(courses_with_title) == 1

def test_create_course_missing_title(editor_client):
    course_data = {
        'title': '', 
        'description': 'Description without a title.'
    }
    response = editor_client.post(url_for('add_course'), data=course_data, follow_redirects=True)
    assert response.status_code == 200 
    assert b"This field is required." in response.data 

# --- Public Course Listing Tests ---

def test_public_course_listing(client, app, new_course_id): 
    with app.app_context():
        course = db.session.get(Course, new_course_id)
        assert course is not None, "Course fixture did not create a course."
        course_title_bytes = bytes(course.title, 'utf-8')

    response = client.get(url_for('list_courses'))
    assert response.status_code == 200
    assert b"Available Courses" in response.data
    assert course_title_bytes in response.data 
    
    expected_link = url_for('view_course', course_id=new_course_id)
    assert bytes(expected_link, 'utf-8') in response.data

def test_public_course_listing_no_courses(client, init_database): 
    response = client.get(url_for('list_courses'))
    assert response.status_code == 200
    assert b"Available Courses" in response.data
    assert b"No courses available at the moment." in response.data

# --- Public Course Viewing Tests ---

def test_public_view_course_with_videos(client, app, video_with_course_id): 
    with app.app_context():
        video = db.session.get(Video, video_with_course_id)
        assert video is not None, "Video fixture did not create a video."
        course_id = video.course_id
        course = db.session.get(Course, course_id)
        assert course is not None, "Course associated with video not found."
        
        course_title_bytes = bytes(course.title, 'utf-8')
        video_title_bytes = bytes(video.title, 'utf-8')

    response = client.get(url_for('view_course', course_id=course_id))
    assert response.status_code == 200
    assert course_title_bytes in response.data 
    assert b"Videos in this Course" in response.data
    assert video_title_bytes in response.data 
    
    expected_video_link = url_for('view_video', video_id=video_with_course_id)
    assert bytes(expected_video_link, 'utf-8') in response.data

def test_public_view_course_no_videos(client, app, new_course_id): 
    with app.app_context():
        course = db.session.get(Course, new_course_id)
        assert course is not None, "Course fixture did not create a course."
        course_title_bytes = bytes(course.title, 'utf-8')

    response = client.get(url_for('view_course', course_id=new_course_id))
    assert response.status_code == 200
    assert course_title_bytes in response.data
    assert b"Videos in this Course" in response.data
    assert b"No videos have been added to this course yet." in response.data

def test_view_invalid_course_id_404(client, init_database):
    response = client.get(url_for('view_course', course_id=999)) 
    assert response.status_code == 404
    assert b"404 - Page Not Found" in response.data # Check for content from templates/404.html
    assert b"Sorry, the page you are looking for does not exist." in response.data
