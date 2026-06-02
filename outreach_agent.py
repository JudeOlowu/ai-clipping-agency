import csv
import os
import time
import praw
from dotenv import load_dotenv
from uploader import upload_video

load_dotenv()

LEADS_FILE = "leads.csv"

def init_reddit():
    """Initialize PRAW with credentials from .env"""
    client_id = os.getenv("REDDIT_CLIENT_ID")
    client_secret = os.getenv("REDDIT_CLIENT_SECRET")
    password = os.getenv("REDDIT_PASSWORD")
    username = os.getenv("REDDIT_USERNAME")
    
    if not all([client_id, client_secret, username, password]):
        print("Error: Missing Reddit credentials in .env file.")
        print("Please ensure REDDIT_CLIENT_ID, REDDIT_CLIENT_SECRET, REDDIT_USERNAME, and REDDIT_PASSWORD are set.")
        return None
        
    reddit = praw.Reddit(
        client_id=client_id,
        client_secret=client_secret,
        password=password,
        user_agent=f"video_agency_outreach_bot_by_{username}",
        username=username,
    )
    return reddit

def extract_username(url: str) -> str:
    """Extract the author username from a Reddit post URL, or fetch it via PRAW."""
    # To reliably get the user to DM, we can just extract the post ID from the URL and fetch the author
    # e.g. https://www.reddit.com/r/HireAnEditor/comments/1tssv3j/hiring_clippers/
    try:
        parts = url.split('/')
        if 'comments' in parts:
            idx = parts.index('comments')
            post_id = parts[idx + 1]
            return post_id
    except Exception:
        pass
    return None

def run_outreach():
    print("Starting Automated Outreach Agent...")
    reddit = init_reddit()
    if not reddit:
        return
        
    if not os.path.exists(LEADS_FILE):
        print(f"No {LEADS_FILE} found. Run scout_agent.py first.")
        return
        
    rows = []
    with open(LEADS_FILE, 'r', encoding='utf-8') as f:
        reader = csv.reader(f)
        header = next(reader)
        rows.append(header)
        for row in reader:
            rows.append(row)
            
    contacted_count = 0
    
    # Process rows (skip header)
    for i in range(1, len(rows)):
        row = rows[i]
        
        # Skip empty rows or malformed rows
        if len(row) < 4:
            continue
            
        subreddit = row[0]
        url = row[1]
        title = row[2]
        proposal = row[3]
        
        # Check if already contacted
        if "[CONTACTED]" in proposal:
            continue
            
        # Check if we have a generated video path
        video_path = row[4] if len(row) > 4 else None
        
        if video_path and os.path.exists(video_path):
            print(f"\nProcessing Lead: {title}")
            print(f"URL: {url}")
            
            # 1. Upload video to get public link
            public_url = upload_video(video_path)
            
            if not public_url:
                print("Skipping lead due to upload failure.")
                continue
                
            # 2. Replace local file path in the proposal with the public URL
            final_pitch = proposal.replace(f"[LINK TO LOCAL FILE: {video_path}]", public_url)
            
            # 3. Get the Reddit user to DM
            post_id = extract_username(url)
            if not post_id:
                print("Could not extract post ID from URL.")
                continue
                
            try:
                submission = reddit.submission(id=post_id)
                author = submission.author
                
                if not author:
                    print("Author is deleted or missing.")
                    continue
                    
                print(f"Sending DM to u/{author.name}...")
                
                # Send the DM!
                author.message(subject="Free Sample Video Edit for your channel!", message=final_pitch)
                
                print("DM Sent successfully!")
                contacted_count += 1
                
                # Mark as contacted in the CSV memory
                rows[i][3] = "[CONTACTED] " + final_pitch
                
                # Sleep to respect Reddit API rate limits
                time.sleep(5)
                
            except Exception as e:
                print(f"Failed to send DM: {e}")
                
    # Save the updated leads back to the CSV
    with open(LEADS_FILE, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerows(rows)
        
    print(f"\nOutreach Agent finished. Sent {contacted_count} DMs.")

if __name__ == "__main__":
    run_outreach()
