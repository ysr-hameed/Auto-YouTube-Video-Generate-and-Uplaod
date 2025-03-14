import os  
import json  
import time  
import random  
import subprocess
import shlex
import re  
import requests  
import google.generativeai as genai  
from flask import Flask, render_template, redirect, url_for, session, request,jsonify  
from google.oauth2.credentials import Credentials  
from google_auth_oauthlib.flow import Flow  
from googleapiclient.discovery import build  
from googleapiclient.http import MediaFileUpload  
import subprocess  
from dotenv import load_dotenv  
from google.auth.transport.requests import Request

# Load environment variables  
load_dotenv()  
  
app = Flask(__name__)  
app.secret_key = os.environ.get('FLASK_SECRET_KEY', 'default_secret_key_change_me')  
  
# YouTube API scope  
SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload",  # ✅ Upload videos
    "https://www.googleapis.com/auth/youtube",         # ✅ Manage YouTube account
    "https://www.googleapis.com/auth/youtube.force-ssl", # ✅ Required for some operations
    "https://www.googleapis.com/auth/userinfo.email",  # ✅ Get user email (optional)
    "openid"  # ✅ Required for authentication (optional)
]
CLIENT_SECRET_FILE = 'client_secret.json'  
TOKEN_FILE = 'token.json'  # File to store the credentials

# Ensure directories exist  
os.makedirs('audio', exist_ok=True)  
os.makedirs('uploads', exist_ok=True)  
  
# Gemini AI Configuration  
GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY')  
  
# Function to generate a unique programming quote  
  
  
# 🔑 Function to Get Credentials (Auto-Refresh)  
def save_credentials(credentials, username):
    token_data = {}

    # Load existing credentials if file exists
    if os.path.exists("token.json"):
        with open("token.json", "r") as f:
            token_data = json.load(f)

    # Save new user credentials
    token_data[username] = {
        "token": credentials.token,
        "refresh_token": credentials.refresh_token,  # Ensure refresh token is stored
        "token_uri": credentials.token_uri,
        "client_id": credentials.client_id,
        "client_secret": credentials.client_secret,
        "scopes": credentials.scopes
    }

    with open("token.json", "w") as f:
        json.dump(token_data, f, indent=4)
        


def get_credentials(username):
    if os.path.exists("token.json"):
        with open("token.json", "r") as f:
            token_data = json.load(f)

        if username in token_data:
            creds = Credentials.from_authorized_user_info(token_data[username], SCOPES)

            # ✅ Force refresh if expired
            if creds.expired and creds.refresh_token:
                try:
                    creds.refresh(Request())
                    save_credentials(creds, username)  # ✅ Save updated token
                except Exception as e:
                    print(f"Token refresh failed for {username}: {e}")
                    return None  # 🔴 Force re-authentication

            return creds  # ✅ Return valid credentials

    return None  # 🔴 No credentials found
    
    
def generate_unique_quote():    
    try:    
        if not GEMINI_API_KEY:    
            return None, "Gemini API key is missing"    
  
        genai.configure(api_key=GEMINI_API_KEY)    
        model = genai.GenerativeModel('gemini-2.0-flash')    
  
        prompt = (    
            "Generate a unique, deep, and inspiring programming quote. "    
            "The response must be a single quote enclosed in double quotes (\"\"). "    
            "No extra text, no author name, no explanations. Only the quote inside double quotes."    
        )    
  
        response = model.generate_content(prompt)    
  
        if not response or not response.text:    
            return None, "Empty response from Gemini API"    
  
        # Extract quote using regex    
        cleaned_text = response.text.strip().replace("\n", " ").strip()    
        match = re.search(r'"(.*?)"', cleaned_text, re.DOTALL)    
  
        if match:    
            return f'"{match.group(1)}"', None    
  
        return None, "Failed to extract a valid quote"    
  
    except Exception as e:    
        return None, f"Error: {str(e)}"  
# Function to select a random audio file from the "audio" folder  
  
  
AUDIO_SAVE_FILE = "selected_audio.json"  # File to store selected audio  
  
def get_random_audio():  
    try:  
        audio_folder = os.path.abspath("audio")  # Get absolute path  
        print("Checking folder:", audio_folder)  
  
        if not os.path.exists(audio_folder):  
            return None, f"Audio folder not found: {audio_folder}"  
  
        # Try to load previously saved audio file  
        if os.path.exists(AUDIO_SAVE_FILE):  
            with open(AUDIO_SAVE_FILE, "r") as f:  
                saved_audio = json.load(f).get("selected_audio")  
                if saved_audio and os.path.exists(saved_audio):  
                    print("Reusing saved audio:", saved_audio)  
                    return saved_audio, None  # Use the saved audio file  
  
        # List all files in the folder  
        all_files = os.listdir(audio_folder)  
        print("All files in 'audio' folder:", all_files)  # Debug print  
  
        # If no files exist, return an error  
        if not all_files:  
            return None, "No files found in 'audio' folder"  
  
        # Filter audio files (common formats)  
        audio_extensions = (".mp3", ".wav", ".ogg", ".aac", ".flac", ".m4a")  
        audio_files = [f for f in all_files if f.lower().endswith(audio_extensions)]  
        print("Filtered audio files:", audio_files)  # Debug print  
  
        # If no audio files are found, select ANY file as fallback  
        selected_file = random.choice(audio_files) if audio_files else random.choice(all_files)  
        selected_audio = os.path.join(audio_folder, selected_file)  
  
        # Save selected audio for future use  
        with open(AUDIO_SAVE_FILE, "w") as f:  
            json.dump({"selected_audio": selected_audio}, f)  
  
        print("Newly selected and saved audio:", selected_audio)  
        return selected_audio, None  
  
    except Exception as e:  
        return None, str(e)  
# Function to create a video with a quote and background music  
  
  

def wrap_text(quote, max_chars_per_line=30):
    """Splits long text into multiple lines based on character limit."""
    words = quote.split()
    lines = []
    current_line = ""

    for word in words:
        if len(current_line) + len(word) < max_chars_per_line:
            current_line += " " + word
        else:
            lines.append(current_line.strip())
            current_line = word

    if current_line:
        lines.append(current_line.strip())

    return lines

def create_video(quote, audio_path):
    try:
        video_path = "uploads/final_video.mp4"  
        background_image = "assets/dark_background.jpg"  
        font_path = "assets/Poppins-Regular.ttf"  

        wrapped_lines = wrap_text(quote, max_chars_per_line=30)
        total_lines = len(wrapped_lines)

        text_filters = []
        for i, line in enumerate(wrapped_lines):
            y_position = f"(h/2 - {((total_lines - i - 1) * 80)})"

            # ✅ Properly escape text
            escaped_line = shlex.quote(line)

            text_filters.append(
                f"drawtext=text={escaped_line}:"
                f"fontfile={shlex.quote(font_path)}:"
                "fontsize=60:fontcolor=white:"
                "x=(w-text_w)/2:"
                f"y={y_position}:"
                "box=1:boxcolor=black@0.5:boxborderw=20"
            )

        text_filter = ",".join(text_filters)

        ffmpeg_cmd = [
            "ffmpeg", "-y",
            "-loop", "1", "-i", background_image,  
            "-i", audio_path,  
            "-filter_complex", f"[0:v]scale=1080:1920,format=rgba,{text_filter}[v]",
            "-map", "[v]",
            "-map", "1:a",
            "-c:v", "libx264",
            "-pix_fmt", "yuv420p",  
            "-b:v", "2500k",  
            "-r", "30",  
            "-preset", "medium",  
            "-profile:v", "high",  
            "-tune", "stillimage",  
            "-c:a", "aac",
            "-b:a", "192k",
            "-ar", "44100",  
            "-shortest",
            video_path
        ]

        print("Running FFmpeg command:", " ".join(ffmpeg_cmd))
        subprocess.run(ffmpeg_cmd, check=True)

        return video_path, None

    except subprocess.CalledProcessError as e:
        return None, f"FFmpeg process error: {e}"

    except Exception as e:
        return None, str(e)
        
def generate_youtube_metadata():  
    try:  
        genai.configure(api_key=GEMINI_API_KEY)  
        model = genai.GenerativeModel('gemini-2.0-flash')  

        # **Prompt for Title**  
        title_prompt = (  
            "Generate a highly engaging and eye-catching YouTube **title** for a short motivational video about programming and coding. "
            "It must **never be the same as previous ones**. Ensure it includes **at least 2 trending hashtags** that are popular in coding-related videos."
            "Return **only** the title, no extra text."  
        )  
        title_response = model.generate_content(title_prompt)  
        title = title_response.text.strip()  

        # **Prompt for Description**  
        description_prompt = (  
            "Generate a **unique and engaging YouTube description** for a short video about programming motivation. "
            "Make sure it has a **strong call-to-action**, includes a few relevant **hashtags**, and never repeats previous descriptions. "
            "Return **only** the description, no extra text."  
        )  
        description_response = model.generate_content(description_prompt)  
        description = description_response.text.strip()  

        # **Prompt for Tags**  
        tags_prompt = (  
            "Generate **highly optimized YouTube tags** for a short motivational programming video. "
            "Ensure they are **SEO-friendly**, relevant to coding, and always **unique** for each video. "
            "Separate each tag with a comma and return **only** the tags, no extra text."  
        )  
        tags_response = model.generate_content(tags_prompt)  

        # ✅ Sanitize tags
        import re
        tags = [re.sub(r'[^a-zA-Z0-9# ]', '', tag).strip() for tag in tags_response.text.strip().split(",") if tag.strip()]
        tags = list(set(tags))[:10]  # Remove duplicates and limit to 10

        return {"title": title, "description": description, "tags": tags}, None  
    except Exception as e:  
        return None, str(e)
        
# Function to upload video to YouTube  
def upload_to_youtube(video_path, quote):
    try:
        if not os.path.exists(TOKEN_FILE):
            return None, "No authenticated users found"

        with open(TOKEN_FILE, "r") as f:
            all_users = json.load(f)

        if not all_users:
            return None, "No saved user credentials"

        # ✅ Generate unique metadata using AI
        metadata, metadata_error = generate_youtube_metadata()
        if metadata_error:
            return None, f"Metadata generation failed: {metadata_error}"

        video_title = metadata["title"]
        video_description = metadata["description"]
        video_tags = metadata["tags"]

        uploaded_videos = []

        for user_email, user_creds in all_users.items():
            creds = get_credentials(user_email)  # ✅ Always load latest credentials
            if not creds or not creds.valid:
                return None, f"Invalid credentials for {user_email}"

            youtube = build('youtube', 'v3', credentials=creds)

            body = {
                'snippet': {
                    'title': video_title,
                    'description': video_description,
                    'tags': video_tags,
                    'categoryId': '28'
                },
                'status': {'privacyStatus': 'public'}
            }

            media = MediaFileUpload(video_path, chunksize=-1, resumable=True)
            request = youtube.videos().insert(part="snippet,status", body=body, media_body=media)
            response = request.execute()

            video_id = response.get('id')
            uploaded_videos.append({"email": user_email, "video_id": video_id})

        return uploaded_videos, None

    except Exception as e:
        return None, str(e)
@app.route('/')
def home():
    try:
        quote, quote_error = generate_unique_quote()
        if quote_error:
            return jsonify({"error": f"Quote generation failed: {quote_error}"}), 500

        audio_path, audio_error = get_random_audio()
        if audio_error:
            return jsonify({"error": f"Audio selection failed: {audio_error}"}), 500

        video_path, video_error = create_video(quote, audio_path)
        if video_error:
            return jsonify({"error": f"Video creation failed: {video_error}"}), 500

        # ✅ Load credentials for all users and upload to their YouTube channels
        if not os.path.exists(TOKEN_FILE):
            return jsonify({"error": "No saved YouTube credentials found"}), 401

        with open(TOKEN_FILE, "r") as token_file:
            all_users = json.load(token_file)

        upload_results = []
        for user_email, user_creds in all_users.items():
            creds = Credentials.from_authorized_user_info(user_creds, SCOPES)

            video_id, upload_error = video_id, upload_error = upload_to_youtube(video_path, quote)  # ✅ Pass 'quote' argument
            if upload_error:
                upload_results.append({"user": user_email, "error": upload_error})
            else:
                upload_results.append({"user": user_email, "video_id": video_id})

        return jsonify({"success": True, "uploads": upload_results})
    
    except Exception as e:
        return jsonify({"error": str(e)}), 500
        
@app.route('/youtube/auth')
def youtube_auth():
    try:
        flow = Flow.from_client_secrets_file(
            CLIENT_SECRET_FILE,
            scopes=SCOPES,
            redirect_uri=url_for('oauth2callback', _external=True)
        )
        authorization_url, state = flow.authorization_url(
            access_type='offline',
            include_granted_scopes='true',
            prompt='consent'  # Ensures refresh token is generated
        )
        session['state'] = state
        return redirect(authorization_url)

    except Exception as e:
        return jsonify({"error": f"OAuth auth failed: {str(e)}"}), 500

@app.route('/oauth2callback')
def oauth2callback():
    try:
        state = session.get('state')
        flow = Flow.from_client_secrets_file(
            CLIENT_SECRET_FILE,
            scopes=SCOPES,
            state=state,
            redirect_uri=url_for('oauth2callback', _external=True)
        )
        flow.fetch_token(authorization_response=request.url)
        creds = flow.credentials

        # Get user email to store credentials uniquely
        session['credentials'] = credentials_to_dict(creds)
        youtube = build('youtube', 'v3', credentials=creds)
        user_info = youtube.channels().list(part="snippet", mine=True).execute()
        user_email = user_info["items"][0]["id"]  # ✅ Always exists and is unique

        # Load existing tokens
        if os.path.exists(TOKEN_FILE):
            with open(TOKEN_FILE, 'r') as f:
                tokens = json.load(f)
        else:
            tokens = {}

        # ✅ Save user credentials separately
        tokens[user_email] = credentials_to_dict(creds)

        with open(TOKEN_FILE, 'w') as f:
            json.dump(tokens, f, indent=4)

        return redirect(url_for('home'))

    except Exception as e:
        return jsonify({"error": f"OAuth callback failed: {str(e)}"}), 500
        
def credentials_to_dict(credentials):  
    return {  
        'token': credentials.token,  
        'refresh_token': credentials.refresh_token,  
        'token_uri': credentials.token_uri,  
        'client_id': credentials.client_id,  
        'client_secret': credentials.client_secret,  
        'scopes': credentials.scopes  
    }  
  
if __name__ == '__main__':  
    app.run(host='0.0.0.0', port=8080, debug=True)   
