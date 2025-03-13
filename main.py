
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
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

app = Flask(__name__)
app.secret_key = os.environ.get('FLASK_SECRET_KEY', 'default_secret_key_change_me')

# YouTube API scope
SCOPES = ['https://www.googleapis.com/auth/youtube.upload']

# Ensure directories exist
os.makedirs('templates', exist_ok=True)
os.makedirs('static', exist_ok=True)
os.makedirs('uploads', exist_ok=True)

# Create client_secret.json template if it doesn't exist
CLIENT_SECRET_TEMPLATE = {
    "web": {
        "client_id": "",
        "project_id": "",
        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
        "token_uri": "https://oauth2.googleapis.com/token",
        "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
        "client_secret": "",
        "redirect_uris": []
    }
}

@app.route('/')
def home():
    try:
        # Check for API keys
        gemini_api_key = os.environ.get('GEMINI_API_KEY')
        client_secret_exists = os.path.exists('client_secret.json')
        
        # If API keys are not set, redirect to setup page
        if not gemini_api_key or not client_secret_exists:
            return redirect(url_for('setup'))
            
        user_id = request.headers.get('X-Replit-User-Id')
        user_name = request.headers.get('X-Replit-User-Name')
        user_roles = request.headers.get('X-Replit-User-Roles')
        
        authenticated = user_id is not None
        
        return render_template(
            'index.html',
            authenticated=authenticated,
            user_id=user_id,
            user_name=user_name,
            user_roles=user_roles,
            auto_start=True
        )
    except Exception as e:
        return f"Error: {str(e)}"

@app.route('/setup')
def setup():
    gemini_api_key = os.environ.get('GEMINI_API_KEY')
    client_secret_exists = os.path.exists('client_secret.json')
    
    return render_template(
        'setup.html',
        gemini_api_key=gemini_api_key,
        client_secret_exists=client_secret_exists
    )

@app.route('/save_keys', methods=['POST'])
def save_keys():
    try:
        gemini_api_key = request.form.get('gemini_api_key')
        client_id = request.form.get('client_id')
        client_secret = request.form.get('client_secret')
        project_id = request.form.get('project_id')
        redirect_uri = url_for('oauth2callback', _external=True)
        
        # Save Gemini API key to .env file
        with open('.env', 'w') as f:
            f.write(f"GEMINI_API_KEY={gemini_api_key}\n")
            f.write(f"FLASK_SECRET_KEY={os.urandom(24).hex()}\n")
        
        # Update environment variables
        os.environ['GEMINI_API_KEY'] = gemini_api_key
        
        # Save client secret to file
        if client_id and client_secret:
            client_secret_json = CLIENT_SECRET_TEMPLATE.copy()
            client_secret_json['web']['client_id'] = client_id
            client_secret_json['web']['client_secret'] = client_secret
            client_secret_json['web']['project_id'] = project_id
            client_secret_json['web']['redirect_uris'] = [redirect_uri]
            
            with open('client_secret.json', 'w') as f:
                json.dump(client_secret_json, f, indent=2)
        
        return redirect(url_for('home'))
    except Exception as e:
        return f"Error saving keys: {str(e)}"

@app.route('/generate_quote', methods=['POST'])
def generate_quote():
    try:
        gemini_api_key = os.environ.get('GEMINI_API_KEY')
        if not gemini_api_key:
            return jsonify({"error": "Gemini API key not configured"}), 500
        
        genai.configure(api_key=gemini_api_key)
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
    try:
        from pytube import YouTube
        import os
        
        # Pre-selected popular videos for simplicity
        popular_videos = [
            "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
            "https://www.youtube.com/watch?v=JGwWNGJdvx8",
            "https://www.youtube.com/watch?v=kJQP7kiw5Fk"
        ]
        
        # Random selection for variety
        random.shuffle(popular_videos)
        
        songs = []
        
        for video_url in popular_videos[:1]:  # Just get one song for speed
            try:
                # Get video info
                yt = YouTube(video_url)
                
                # Download audio only
                audio_path = os.path.join('uploads', f"{yt.title.replace(' ', '_')}_audio.mp3")
                
                if not os.path.exists(audio_path):
                    audio = yt.streams.filter(only_audio=True).first()
                    audio.download(output_path='uploads', filename=os.path.basename(audio_path))
                
                songs.append({
                    "title": yt.title,
                    "artist": yt.author,
                    "url": audio_path,
                    "thumbnail": yt.thumbnail_url
                })
            except Exception as e:
                print(f"Error processing video {video_url}: {str(e)}")
        
        # If we failed to get any songs, provide a fallback
        if not songs:
            songs = [
                {"title": "Default Background Music", "artist": "System", "url": "uploads/default_audio.mp3"}
            ]
            
        return jsonify({"songs": songs})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/create_video', methods=['POST'])
def create_video():
    try:
        data = request.json
        quote = data.get('quote', '')
        author = data.get('author', '')
        audio_url = data.get('audio_url', '')
        
        if not os.path.exists('uploads'):
            os.makedirs('uploads')
            
        # Generate a unique filename
        timestamp = int(time.time())
        video_path = f'uploads/quote_video_{timestamp}.mp4'
        
        # Create a video with text using ffmpeg
        text_cmd = [
            'ffmpeg', '-y',
            '-f', 'lavfi', 
            '-i', f'color=c=black:s=720x1280:d=15', 
            '-vf', f"drawtext=text='{quote}':fontcolor=white:fontsize=40:x=(w-text_w)/2:y=(h-text_h)/2:fontfile=/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf," +
                  f"drawtext=text='- {author}':fontcolor=white:fontsize=30:x=(w-text_w)/2:y=(h-text_h)/2+200:fontfile=/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            '-c:v', 'libx264', 
            '-t', '15',
            '-pix_fmt', 'yuv420p',
            video_path
        ]
        
        subprocess.run(text_cmd)
        
        # Add audio if it exists
        if os.path.exists(audio_url) and audio_url.startswith('uploads/'):
            temp_video = f'uploads/temp_{timestamp}.mp4'
            os.rename(video_path, temp_video)
            
            audio_cmd = [
                'ffmpeg', '-y',
                '-i', temp_video,
                '-i', audio_url,
                '-c:v', 'copy',
                '-c:a', 'aac',
                '-shortest',
                video_path
            ]
            
            subprocess.run(audio_cmd)
            
            # Clean up temp file
            if os.path.exists(temp_video):
                os.remove(temp_video)
        
        return jsonify({"video_path": video_path})
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

@app.route('/youtube/auth')
def youtube_auth():
    if not os.path.exists('client_secret.json'):
        return redirect(url_for('setup'))
        
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
    quote = data.get('quote', '')
    author = data.get('author', '')
    
    # Generate SEO-friendly title and description using Gemini
    gemini_api_key = os.environ.get('GEMINI_API_KEY')
    if not gemini_api_key:
        return jsonify({"error": "Gemini API key not configured"}), 500
        
    genai.configure(api_key=gemini_api_key)
    model = genai.GenerativeModel('gemini-1.5-flash')
    
    seo_prompt = f"Generate a catchy YouTube title, description with hashtags for a programming quote video containing this quote: {quote} by {author}. Format the response as JSON with fields: title, description, tags (as an array)."
    
    try:
        seo_response = model.generate_content(seo_prompt)
        seo_text = seo_response.text
        
        # Extract JSON from response
        seo_data = json.loads(seo_text)
        
        # Upload to YouTube
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
        
        # This is the actual upload
        media = MediaFileUpload(video_path, chunksize=-1, resumable=True)
        request = youtube.videos().insert(part="snippet,status", body=body, media_body=media)
        response = request.execute()
        
        return jsonify({
            "success": True, 
            "message": "Video uploaded with title: " + seo_data.get('title'),
            "video_id": response.get('id')
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080, debug=True)
