import pytest
from app import Video, db, Review, Course # Added Course import
import io
import os
from flask import url_for # Added for url_for usage

# --- Video Upload Tests (Editor Mode) ---

def test_upload_video_page_loads_for_editor(editor_client, app, new_course_id): # Ensure a course exists for the form
    """Test that the video upload page loads and shows course selection for an editor."""
    # Create a course first to ensure the dropdown isn't empty
    with app.app_context():
        course = db.session.get(Course, new_course_id)
        assert course is not None, "Course fixture did not create a course"
        
    response = editor_client.get(url_for('upload_video'))
    assert response.status_code == 200
    assert b"Upload New Video" in response.data
    assert b"Assign to Course" in response.data 
    assert bytes(f'<option value="{new_course_id}">{course.title}</option>', 'utf-8') in response.data

def test_successful_video_upload_with_course(editor_client, app, new_course_id):
    """Test successful video upload by an editor, assigning to a course."""
    video_data = {
        'title': 'Video for My Course',
        'description': 'A new video for a specific course.',
        'video_file': (io.BytesIO(b"course video data"), 'my_course_video.mp4'),
        'course': str(new_course_id) 
    }
    response = editor_client.post(url_for('upload_video'), data=video_data, content_type='multipart/form-data', follow_redirects=True)
    # Check if the redirect is to the course page or home page
    # Current app.py redirects to url_for('hello_world') which is list_courses
    assert response.status_code == 200 
    assert url_for('list_courses') in response.request.path # Check if redirected to courses list
    assert b"Video uploaded successfully!" in response.data
    
    with app.app_context():
        video = Video.query.filter_by(title='Video for My Course').first()
        assert video is not None
        assert video.course_id == new_course_id
        assert video.user_id is None 

def test_video_upload_no_course_selected(editor_client, app):
    """Test video upload attempt without selecting a course."""
    # Create a course so the dropdown is populated, making "not selected" meaningful.
    with app.app_context():
        temp_course = Course(title="Temporary Course for Select")
        db.session.add(temp_course)
        db.session.commit()
        # temp_course_id = temp_course.id

    video_data = {
        'title': 'Video Missing Course',
        'description': 'Trying to upload without selecting a course.',
        'video_file': (io.BytesIO(b"video data"), 'missing_course.mp4'),
        # 'course': '...' # Course is deliberately omitted
    }
    response = editor_client.post(url_for('upload_video'), data=video_data, content_type='multipart/form-data', follow_redirects=True)
    assert response.status_code == 200 
    assert b"This field is required." in response.data # Error for the course field
    assert b"Video uploaded successfully!" not in response.data

def test_video_upload_form_validation_other_fields(editor_client, new_course_id):
    """Test other form validations like missing title, file, or invalid file type for video upload."""
    # Missing title
    response = editor_client.post(url_for('upload_video'), data={
        'description': 'No title video', 'video_file': (io.BytesIO(b"data"), 'file.mp4'), 'course': str(new_course_id)
    }, content_type='multipart/form-data', follow_redirects=True)
    assert b"This field is required." in response.data # For title
    assert b"Upload New Video" in response.data 

    # Missing file
    response = editor_client.post(url_for('upload_video'), data={
        'title': 'No file video', 'description': '...', 'course': str(new_course_id)
    }, content_type='multipart/form-data', follow_redirects=True)
    assert b"This field is required." in response.data # For file

    # Invalid file type
    response = editor_client.post(url_for('upload_video'), data={
        'title': 'Bad file type', 'video_file': (io.BytesIO(b"data"), 'file.txt'), 'course': str(new_course_id)
    }, content_type='multipart/form-data', follow_redirects=True)
    assert b"Videos only!" in response.data


# --- Video Viewing Tests (Public) ---

def test_public_can_access_all_videos_list(client, app, video_with_course_id): 
    with app.app_context():
        video = db.session.get(Video, video_with_course_id)
        assert video is not None, "Video fixture did not create a video"
        video_title = video.title
        
    response = client.get(url_for('video_list')) 
    assert response.status_code == 200
    assert b"All Videos" in response.data
    assert bytes(video_title, 'utf-8') in response.data

def test_public_can_access_individual_video_page(client, app, video_with_course_id): 
    with app.app_context():
        video = db.session.get(Video, video_with_course_id)
        assert video is not None
        video_id = video.id
        video_title = video.title
        video_description = video.description
        
    response = client.get(url_for('view_video', video_id=video_id))
    assert response.status_code == 200
    assert bytes(video_title, 'utf-8') in response.data
    assert bytes(video_description, 'utf-8') in response.data
    assert b'<video' in response.data 
    assert b'controls' in response.data

def test_view_non_existent_video_404_public(client, init_database):
    response = client.get(url_for('view_video', video_id=999)) 
    assert response.status_code == 404
    assert b"Page Not Found" in response.data

def test_video_file_serving_public(client, app, video_with_course_id): 
    with app.app_context():
        video = db.session.get(Video, video_with_course_id)
        assert video is not None
        video_filename = video.filename

    upload_folder = client.application.config['UPLOAD_FOLDER']
    dummy_file_path = os.path.join(upload_folder, video_filename)
    
    os.makedirs(upload_folder, exist_ok=True)
    with open(dummy_file_path, 'wb') as f:
        f.write(b"dummy public video content for serving test")

    response = client.get(url_for('serve_video_file', filename=video_filename))
    assert response.status_code == 200
    assert response.data == b"dummy public video content for serving test"
    
    os.remove(dummy_file_path)


# --- Review Submission Tests ---

def test_successful_review_submission(client, app, video_with_course_id): 
    review_data = {
        'rating': '4', 
        'comment': 'Great course video!'
    }
    response = client.post(url_for('view_video', video_id=video_with_course_id), data=review_data, follow_redirects=False)
    assert response.status_code == 302
    assert url_for('view_video', video_id=video_with_course_id) in response.location

    redirected_response = client.get(response.location)
    assert b"Your review has been submitted successfully!" in redirected_response.data

    with app.app_context():
        review = Review.query.filter_by(video_id=video_with_course_id, rating=4).first()
        assert review is not None
        assert review.comment == 'Great course video!'

# --- Review Display Tests ---

def test_review_display_on_video_page(client, app, video_with_course_id): 
    # Create a review directly for the video_with_course_id for this test.
    with app.app_context():
        review_for_course_video = Review(video_id=video_with_course_id, rating=5, comment="Review for course video")
        db.session.add(review_for_course_video)
        db.session.commit()
        review_comment = review_for_course_video.comment
        review_rating = str(review_for_course_video.rating)

    response = client.get(url_for('view_video', video_id=video_with_course_id))
    assert response.status_code == 200
    assert bytes(review_comment, 'utf-8') in response.data
    assert bytes(f"Rating: {review_rating}/5", 'utf-8') in response.data
    assert b"Reviewed on:" in response.data

def test_average_rating_display(client, app, video_with_course_id): 
    client.post(url_for('view_video', video_id=video_with_course_id), data={'rating': '5', 'comment': 'Excellent!'})
    client.post(url_for('view_video', video_id=video_with_course_id), data={'rating': '3', 'comment': 'Okay.'})
    client.post(url_for('view_video', video_id=video_with_course_id), data={'rating': '4', 'comment': 'Good.'})

    response = client.get(url_for('view_video', video_id=video_with_course_id))
    assert response.status_code == 200
    assert b"Average Rating: 4.0 / 5 Stars" in response.data
    assert b"(3 reviews)" in response.data

def test_average_rating_display_no_reviews(client, app, video_with_course_id): 
    response = client.get(url_for('view_video', video_id=video_with_course_id))
    assert response.status_code == 200
    assert b"Average Rating: 0.0 / 5 Stars" in response.data
    assert b"(0 reviews)" in response.data
    assert b"No reviews yet. Be the first to review!" in response.data
