
import os
import json
import time
import random
import requests
import google.generativeai as genai
from flask import Flask, render_template, request, redirect, url_for, session, jsonify
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
import subprocess
import threading

app = Flask(__name__)
app.secret_key = 'your_secret_key'  # Replace with a secure secret key

# Configure Gemini API
GEMINI_API_KEY = None  # Will be set via environment variable

# YouTube API scopes
SCOPES = ['https://www.googleapis.com/auth/youtube.upload']

# Create templates directory if it doesn't exist
os.makedirs('templates', exist_ok=True)
os.makedirs('static', exist_ok=True)
os.makedirs('uploads', exist_ok=True)

@app.route('/')
def home():
    try:
        user_id = request.headers.get('X-Replit-User-Id')
        user_name = request.headers.get('X-Replit-User-Name')
        user_roles = request.headers.get('X-Replit-User-Roles')
        
        authenticated = user_id is not None
        
        return render_template(
            'index.html',
            authenticated=authenticated,
            user_id=user_id,
            user_name=user_name,
            user_roles=user_roles
        )
    except Exception as e:
        return f"Error: {str(e)}"

@app.route('/generate_quote', methods=['POST'])
def generate_quote():
    try:
        if not GEMINI_API_KEY:
            return jsonify({"error": "Gemini API key not configured"}), 500
        
        genai.configure(api_key=GEMINI_API_KEY)
        model = genai.GenerativeModel('gemini-1.5-flash')
        
        prompt = "Generate a powerful and inspiring programming quote that is deep and meaningful. Return exactly two sentences, with each sentence on a new line. First line should be the quote, second line should be the author."
        
        response = model.generate_content(prompt)
        quote_text = response.text.strip().split('\n')
        
        if len(quote_text) >= 2:
            quote = quote_text[0].strip('"')
            author = quote_text[1].strip()
        else:
            quote = quote_text[0].strip('"')
            author = "Unknown"
        
        return jsonify({"quote": quote, "author": author})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/get_trending_audio')
def get_trending_audio():
    # For demo purposes, we'll use a list of popular songs
    # In a real app, you would integrate with a music API
    songs = [
        {"title": "Trending Song 1", "artist": "Artist 1", "url": "https://example.com/song1.mp3"},
        {"title": "Trending Song 2", "artist": "Artist 2", "url": "https://example.com/song2.mp3"},
        {"title": "Trending Song 3", "artist": "Artist 3", "url": "https://example.com/song3.mp3"}
    ]
    
    return jsonify({"songs": songs})

@app.route('/create_video', methods=['POST'])
def create_video():
    data = request.json
    quote = data.get('quote', '')
    author = data.get('author', '')
    
    # Here we would use ffmpeg to create a video
    # For demonstration, we'll just create a placeholder
    video_path = 'uploads/quote_video.mp4'
    
    # In a real implementation, you would:
    # 1. Create an HTML canvas with the quote
    # 2. Capture it as an image
    # 3. Use ffmpeg to create a video with the image and audio
    
    cmd = f"echo 'Video would be created with quote: {quote} by {author}' > {video_path}"
    subprocess.run(cmd, shell=True)
    
    return jsonify({"video_path": video_path})

@app.route('/youtube/auth')
def youtube_auth():
    flow = Flow.from_client_secrets_file(
        'client_secret.json',
        scopes=SCOPES,
        redirect_uri=url_for('oauth2callback', _external=True)
    )
    
    authorization_url, state = flow.authorization_url(
        access_type='offline',
        include_granted_scopes='true'
    )
    
    session['state'] = state
    
    return redirect(authorization_url)

@app.route('/oauth2callback')
def oauth2callback():
    state = session.get('state')
    
    flow = Flow.from_client_secrets_file(
        'client_secret.json',
        scopes=SCOPES,
        state=state,
        redirect_uri=url_for('oauth2callback', _external=True)
    )
    
    # Use the authorization server's response to fetch the OAuth 2.0 tokens
    authorization_response = request.url
    flow.fetch_token(authorization_response=authorization_response)
    
    credentials = flow.credentials
    session['credentials'] = {
        'token': credentials.token,
        'refresh_token': credentials.refresh_token,
        'token_uri': credentials.token_uri,
        'client_id': credentials.client_id,
        'client_secret': credentials.client_secret,
        'scopes': credentials.scopes
    }
    
    return redirect(url_for('home'))

@app.route('/upload_to_youtube', methods=['POST'])
def upload_to_youtube():
    if 'credentials' not in session:
        return jsonify({"error": "Not authenticated with YouTube"}), 401
    
    credentials = Credentials(
        **session['credentials']
    )
    
    youtube = build('youtube', 'v3', credentials=credentials)
    
    data = request.json
    video_path = data.get('video_path')
    
    # Generate SEO-friendly title and description using Gemini
    genai.configure(api_key=GEMINI_API_KEY)
    model = genai.GenerativeModel('gemini-1.5-flash')
    
    seo_prompt = f"Generate a catchy YouTube title, description with hashtags for a programming quote video containing this quote: {data.get('quote')} by {data.get('author')}. Format the response as JSON with fields: title, description, tags (as an array)."
    
    seo_response = model.generate_content(seo_prompt)
    seo_text = seo_response.text
    
    # Extract JSON from response
    seo_data = json.loads(seo_text)
    
    # Upload to YouTube (this would work if we had a real video file)
    body = {
        'snippet': {
            'title': seo_data.get('title'),
            'description': seo_data.get('description'),
            'tags': seo_data.get('tags'),
            'categoryId': '28'  # Science & Technology category
        },
        'status': {
            'privacyStatus': 'public'
        }
    }
    
    try:
        # This would be the actual upload code
        # media = MediaFileUpload(video_path, chunksize=-1, resumable=True)
        # request = youtube.videos().insert(part="snippet,status", body=body, media_body=media)
        # response = request.execute()
        
        # For demonstration, we'll just return a success message
        return jsonify({"success": True, "message": "Video would be uploaded with title: " + seo_data.get('title')})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    # Check for Gemini API key
    GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY')
    
    app.run(host='0.0.0.0', port=8080, debug=True)
