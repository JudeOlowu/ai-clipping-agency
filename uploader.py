import os
import google_auth_oauthlib.flow
import googleapiclient.discovery
import googleapiclient.errors
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.http import MediaFileUpload

# YouTube API scopes for uploading
SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]

def authenticate_youtube():
    """Handles OAuth2 authentication for YouTube API and saves the token for future use."""
    creds = None
    token_file = os.path.join(os.path.dirname(__file__), "token.json")
    client_secrets_file = os.path.join(os.path.dirname(__file__), "client_secrets.json")
    
    # Check if we already have a valid token
    if os.path.exists(token_file):
        creds = Credentials.from_authorized_user_file(token_file, SCOPES)
        
    # If no valid token, let the user log in
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not os.path.exists(client_secrets_file):
                print(f"ERROR: {client_secrets_file} not found. You must download this from Google Cloud Console.")
                return None
                
            print("No valid YouTube token found. Opening browser for authentication...")
            flow = google_auth_oauthlib.flow.InstalledAppFlow.from_client_secrets_file(
                client_secrets_file, SCOPES)
            # Use local server to catch the redirect
            creds = flow.run_local_server(port=0)
            
        # Save the credentials for the next run
        with open(token_file, "w") as token:
            token.write(creds.to_json())
            
    return googleapiclient.discovery.build("youtube", "v3", credentials=creds)

def upload_video(file_path: str, title: str = "AI Generated Viral Clip", description: str = "High-retention short form clip.", tags: list = None) -> str:
    """
    Uploads a video to YouTube as Unlisted and returns the public youtu.be URL.
    """
    if not os.path.exists(file_path):
        print(f"Error: File {file_path} does not exist.")
        return None
        
    print(f"Authenticating with YouTube API...")
    youtube = authenticate_youtube()
    if not youtube:
        return None
        
    if tags is None:
        tags = ["Shorts", "TikTok", "Viral", "AI"]
        
    print(f"Uploading {file_path} to YouTube as Unlisted...")
    
    try:
        request_body = {
            "snippet": {
                "title": title[:100],  # YouTube titles max 100 chars
                "description": description,
                "tags": tags,
                "categoryId": "22"  # 22 = People & Blogs
            },
            "status": {
                "privacyStatus": "unlisted",  # Unlisted so it doesn't notify subscribers
                "selfDeclaredMadeForKids": False
            }
        }
        
        media_file = MediaFileUpload(file_path, chunksize=-1, resumable=True)
        
        request = youtube.videos().insert(
            part="snippet,status",
            body=request_body,
            media_body=media_file
        )
        
        # Execute the upload request
        response = request.execute()
        
        video_id = response.get("id")
        if video_id:
            public_url = f"https://youtu.be/{video_id}"
            print(f"--> Upload successful! YouTube URL: {public_url}")
            return public_url
        else:
            print("--> YouTube upload failed, no Video ID returned.")
            return None
            
    except googleapiclient.errors.HttpError as e:
        print(f"--> YouTube API Error: {e.resp.status} {e.content}")
        return None
    except Exception as e:
        print(f"--> Unexpected upload error: {e}")
        return None

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        upload_video(sys.argv[1])
    else:
        # If no arguments provided, just run authentication to generate the token.json
        print("Running initial authentication setup...")
        youtube = authenticate_youtube()
        if youtube:
            print("Authentication successful! token.json has been created.")
