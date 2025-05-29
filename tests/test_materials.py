import pytest
from app import db, VideoMaterial, Course # Added Course for context if needed
from flask import url_for
import io
import os

# --- Material Creation Tests (Editor Mode) ---

def test_add_material_form_not_visible_to_public(client, app, video_with_course_id): 
    # video_with_course_id uses editor_client to create video.
    # We use the standard 'client' (not editor_client) to make the request for public view.
    response = client.get(url_for('view_video', video_id=video_with_course_id))
    assert response.status_code == 200
    assert b"Add New Material" not in response.data 
    assert b"material_type" not in response.data 

def test_add_material_form_visible_to_editor(editor_client, video_with_course_id):
    response = editor_client.get(url_for('view_video', video_id=video_with_course_id))
    assert response.status_code == 200
    assert b"Add New Material" in response.data
    assert b"material_type" in response.data 

def test_add_comment_material(editor_client, app, video_with_course_id):
    material_data = {
        'material_type': 'comment',
        'content': 'This is a detailed comment material.',
        'submit_material': 'Add Material' # Specify which form's submit
    }
    response = editor_client.post(url_for('view_video', video_id=video_with_course_id), data=material_data, follow_redirects=False)
    assert response.status_code == 302, f"Expected 302, got {response.status_code}. Data: {response.data.decode()}"
    assert url_for('view_video', video_id=video_with_course_id) in response.location

    redirected_response = editor_client.get(response.location)
    assert b"Material added successfully!" in redirected_response.data

    with app.app_context():
        material = VideoMaterial.query.filter_by(video_id=video_with_course_id, material_type='comment', content='This is a detailed comment material.').first()
        assert material is not None
        assert material.filename is None
        assert material.original_filename is None

def test_add_link_material(editor_client, app, video_with_course_id):
    link_url = 'http://example.com/resource'
    material_data = {
        'material_type': 'link',
        'content': link_url,
        'submit_material': 'Add Material' 
    }
    response = editor_client.post(url_for('view_video', video_id=video_with_course_id), data=material_data, follow_redirects=False)
    assert response.status_code == 302, f"Expected 302, got {response.status_code}. Data: {response.data.decode()}"

    with app.app_context():
        material = VideoMaterial.query.filter_by(video_id=video_with_course_id, material_type='link', content=link_url).first()
        assert material is not None

def test_add_file_material(editor_client, app, video_with_course_id):
    file_content = b"This is some test file content."
    original_filename = f"test_document_{uuid.uuid4().hex[:6]}.txt"
    material_data = {
        'material_type': 'file',
        'file': (io.BytesIO(file_content), original_filename),
        'submit_material': 'Add Material'
    }
    response = editor_client.post(url_for('view_video', video_id=video_with_course_id), data=material_data, content_type='multipart/form-data', follow_redirects=False)
    assert response.status_code == 302, f"Expected 302, got {response.status_code}. Data: {response.data.decode()}"

    with app.app_context():
        material = VideoMaterial.query.filter_by(video_id=video_with_course_id, material_type='file', original_filename=original_filename).first()
        assert material is not None
        assert material.filename is not None 
        assert material.filename.endswith(original_filename)
        
        file_path = os.path.join(app.config['MATERIALS_UPLOAD_FOLDER'], material.filename)
        assert os.path.exists(file_path)
        with open(file_path, 'rb') as f:
            assert f.read() == file_content
        os.remove(file_path) 

def test_add_material_missing_content_for_comment(editor_client, video_with_course_id):
    material_data = {'material_type': 'comment', 'content': '', 'submit_material': 'Add Material'}
    response = editor_client.post(url_for('view_video', video_id=video_with_course_id), data=material_data, follow_redirects=True)
    assert response.status_code == 200 
    assert b"Content is required for comment or link type." in response.data
    assert b"Material added successfully!" not in response.data

def test_add_material_missing_content_for_link(editor_client, video_with_course_id):
    material_data = {'material_type': 'link', 'content': '', 'submit_material': 'Add Material'}
    response = editor_client.post(url_for('view_video', video_id=video_with_course_id), data=material_data, follow_redirects=True)
    assert response.status_code == 200
    assert b"Content is required for comment or link type." in response.data

def test_add_material_missing_file_for_file_type(editor_client, video_with_course_id):
    material_data = {'material_type': 'file', 'submit_material': 'Add Material'} 
    response = editor_client.post(url_for('view_video', video_id=video_with_course_id), data=material_data, content_type='multipart/form-data', follow_redirects=True)
    assert response.status_code == 200
    assert b"No file selected for file upload type." in response.data

# --- Material Display Tests (Public) ---

def test_display_comment_material(client, app, new_material_id): 
    with app.app_context():
        material = db.session.get(VideoMaterial, new_material_id)
        assert material is not None, "new_material_id fixture failed to create material"
        assert material.material_type == 'comment', "Fixture should create a comment material"
        video_id = material.video_id
        content = material.content
        
    response = client.get(url_for('view_video', video_id=video_id))
    assert response.status_code == 200
    assert b"Additional Materials" in response.data
    assert b"<strong>Comment:</strong>" in response.data
    assert bytes(content, 'utf-8') in response.data

def test_display_link_material(client, editor_client, app, video_with_course_id): # Use client for public view
    link_url = f"http://example.com/test_link_display_{uuid.uuid4().hex[:6]}"
    editor_client.post(url_for('view_video', video_id=video_with_course_id), data={'material_type': 'link', 'content': link_url, 'submit_material': 'Add Material'})
    
    response = client.get(url_for('view_video', video_id=video_with_course_id)) 
    assert response.status_code == 200
    assert b"<strong>Link:</strong>" in response.data
    assert bytes(f'<a href="{link_url}" target="_blank">{link_url}</a>', 'utf-8') in response.data

def test_display_file_material_download_link(client, editor_client, app, video_with_course_id): # Use client for public view
    original_filename = f"display_test_{uuid.uuid4().hex[:6]}.pdf"
    editor_client.post(
        url_for('view_video', video_id=video_with_course_id), 
        data={'material_type': 'file', 'file': (io.BytesIO(b"dummy"), original_filename), 'submit_material': 'Add Material'},
        content_type='multipart/form-data'
    )
    
    with app.app_context():
        material = VideoMaterial.query.filter_by(video_id=video_with_course_id, original_filename=original_filename).first()
        assert material is not None, f"Material with original_filename '{original_filename}' not found."
        download_url = url_for('download_material', material_id=material.id)

    response = client.get(url_for('view_video', video_id=video_with_course_id))
    assert response.status_code == 200
    assert b"<strong>File:</strong>" in response.data
    assert bytes(f'<a href="{download_url}">{original_filename}</a>', 'utf-8') in response.data

    if material and material.filename: # Cleanup
         file_path = os.path.join(app.config['MATERIALS_UPLOAD_FOLDER'], material.filename)
         if os.path.exists(file_path): os.remove(file_path)


# --- File Download Tests ---

def test_download_file_material_success(client, editor_client, app, video_with_course_id): # client for download
    file_content = b"Downloadable content."
    original_filename = f"download_me_{uuid.uuid4().hex[:6]}.zip"
    editor_client.post(
        url_for('view_video', video_id=video_with_course_id), 
        data={'material_type': 'file', 'file': (io.BytesIO(file_content), original_filename), 'submit_material': 'Add Material'},
        content_type='multipart/form-data'
    )

    with app.app_context():
        material = VideoMaterial.query.filter_by(video_id=video_with_course_id, original_filename=original_filename).first()
        assert material is not None
    
    response = client.get(url_for('download_material', material_id=material.id))
    assert response.status_code == 200
    assert response.data == file_content
    assert response.headers['Content-Disposition'] == f'attachment; filename="{original_filename}"'

    if material and material.filename: # Cleanup
         file_path = os.path.join(app.config['MATERIALS_UPLOAD_FOLDER'], material.filename)
         if os.path.exists(file_path): os.remove(file_path)


def test_download_non_file_material_404(client, new_material_id): # new_material_id creates a 'comment'
    response = client.get(url_for('download_material', material_id=new_material_id))
    assert response.status_code == 404

def test_download_invalid_material_id_404(client, init_database): # init_database for clean state
    response = client.get(url_for('download_material', material_id=9999))
    assert response.status_code == 404
