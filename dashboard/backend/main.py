import csv
import os
import urllib.parse
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from uploader import upload_video

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), ".env"))

app = FastAPI()

OUTPUT_CLIPS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "output_clips")
os.makedirs(OUTPUT_CLIPS_DIR, exist_ok=True)
if os.path.exists(OUTPUT_CLIPS_DIR):
    app.mount("/output_clips", StaticFiles(directory=OUTPUT_CLIPS_DIR), name="output_clips")


# Allow frontend to access the API (Useful in dev)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


LEADS_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "leads.csv")

class PitchRequest(BaseModel):
    row_index: int

@app.get("/api/leads")
def get_leads():
    print("LEADS_FILE is:", LEADS_FILE, "Exists:", os.path.exists(LEADS_FILE))
    if not os.path.exists(LEADS_FILE):
        return []
        
    leads = []
    with open(LEADS_FILE, 'r', encoding='utf-8') as f:
        reader = csv.reader(f)
        header = next(reader, None)
        print("Header is:", header)
        for i, row in enumerate(reader):
            if len(row) >= 4:
                # Format: Subreddit, URL, Title, Drafted Proposal, VideoPath(optional)
                contacted = "[CONTACTED]" in row[3]
                video_path = row[4].strip() if len(row) > 4 and row[4].strip() else None
                has_video = video_path is not None and os.path.exists(video_path)
                
                final_pitch = row[3].replace("[CONTACTED] ", "") if contacted else row[3]
                
                import urllib.parse
                encoded_subject = urllib.parse.quote("Free Sample Video Edit for your channel!")
                encoded_message = urllib.parse.quote(final_pitch)
                compose_url = f"https://www.reddit.com/message/compose/?subject={encoded_subject}&message={encoded_message}"

                leads.append({
                    "id": i,
                    "subreddit": row[0],
                    "url": row[1],
                    "title": row[2],
                    "proposal": final_pitch,
                    "has_video": has_video,
                    "video_path": video_path,
                    "contacted": contacted,
                    "compose_url": compose_url
                })
    return leads

class DeleteLeadsRequest(BaseModel):
    indices: list[int] = []

@app.post("/api/leads/delete")
def clear_leads(req: DeleteLeadsRequest):
    if not os.path.exists(LEADS_FILE):
        return {"success": True}
        
    if not req.indices:
        # Clear all leads
        with open(LEADS_FILE, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(["Subreddit", "URL", "Title", "Drafted Proposal", "Local Clip Path"])
    else:
        # Clear only selected leads
        with open(LEADS_FILE, 'r', encoding='utf-8') as f:
            reader = csv.reader(f)
            rows = list(reader)
        
        if len(rows) > 0:
            header = rows[0]
            data_rows = rows[1:]
            
            indices_to_delete = set(req.indices)
            new_data_rows = [row for i, row in enumerate(data_rows) if i not in indices_to_delete]
            
            with open(LEADS_FILE, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(header)
                writer.writerows(new_data_rows)
            
    return {"success": True}

@app.post("/api/generate-pitch-url")
def generate_pitch_url(req: PitchRequest):
    row_index = req.row_index
    
    if not os.path.exists(LEADS_FILE):
        raise HTTPException(status_code=404, detail="leads.csv not found")
        
    rows = []
    with open(LEADS_FILE, 'r', encoding='utf-8') as f:
        reader = csv.reader(f)
        rows = list(reader)
        
    # The frontend sends an index starting at 0 for the first lead.
    # Since our CSV has a header, the actual row is at row_index + 1.
    actual_row_index = row_index + 1
    
    if actual_row_index >= len(rows):
        raise HTTPException(status_code=404, detail="Lead not found")
        
    row = rows[actual_row_index]
    if len(row) < 5 or not row[4].strip():
        raise HTTPException(status_code=400, detail="No generated video found for this lead")
        
    video_path = row[4].strip()
    proposal = row[3]
    
    if video_path.startswith("http"):
        public_url = video_path
    else:
        if not os.path.exists(video_path):
            raise HTTPException(status_code=400, detail="Video file not found on disk")
        # 1. Upload the video
        print(f"Calling upload_video({video_path})")
        public_url = upload_video(video_path)
        print(f"public_url returned: {public_url}")
        if not public_url:
            raise HTTPException(status_code=500, detail="Failed to upload video")
        
    # 2. Inject URL into pitch
    final_pitch = proposal.replace(f"[LINK TO LOCAL FILE: {video_path}]", public_url)
    
    # 3. Mark as contacted
    if "[CONTACTED]" not in final_pitch:
        rows[actual_row_index][3] = "[CONTACTED] " + final_pitch
        with open(LEADS_FILE, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerows(rows)
            
    # 4. Generate Reddit Compose URL
    # Extract post ID from URL to get author
    reddit_url = row[1]
    author = ""
    try:
        # We can't use PRAW anymore, so we don't dynamically fetch the author's exact username from the post ID.
        # But we can try to guess it if we had it, or we just leave 'to' blank and the user fills it,
        # OR we can just instruct the dashboard to tell the user to click the reddit link, find the author, and use the URL.
        # Wait, without PRAW we don't know the author's username just from a post URL unless we scrape it.
        # So we'll just leave `to` empty. The user will have to manually type the username or we open the post URL instead!
        pass
    except Exception:
        pass
        
    encoded_subject = urllib.parse.quote("Free Sample Video Edit for your channel!")
    encoded_message = urllib.parse.quote(final_pitch)
    
    compose_url = f"https://www.reddit.com/message/compose/?subject={encoded_subject}&message={encoded_message}"
    
    return {
        "success": True,
        "compose_url": compose_url,
        "post_url": reddit_url,
        "public_video_url": public_url,
        "final_pitch": final_pitch
    }

class ManualClipRequest(BaseModel):
    url: str
    style: str
    generateSubtitles: bool = True



from fastapi import BackgroundTasks

def process_manual_clip_runpod(req: ManualClipRequest, runpod_api_key: str, runpod_endpoint_id: str, output_dir: str):
    import requests
    import os
    import time
    
    headers = {
        "Authorization": f"Bearer {runpod_api_key}",
        "Content-Type": "application/json"
    }
    payload = {
        "input": {
            "video_url": req.url,
            "style": req.style,
            "generateSubtitles": req.generateSubtitles,
            "api_key": os.getenv("OPENROUTER_API_KEY", "")
        }
    }
    url = f"https://api.runpod.ai/v2/{runpod_endpoint_id}/runsync"
    try:
        print(f"Waiting for RunPod to finish manual clip for {req.url}...")
        response = requests.post(url, json=payload, headers=headers).json()
        
        job_id = response.get("id")
        status = response.get("status")
        
        def robust_get(url, headers, max_retries=5):
            import time
            for i in range(max_retries):
                try:
                    return requests.get(url, headers=headers).json()
                except Exception as e:
                    print(f"Network error: {e}. Retrying in 5 seconds...")
                    time.sleep(5)
            raise Exception("Max retries exceeded")

        # If it takes longer than 90 seconds, runsync returns IN_PROGRESS, so we poll
        while status in ["IN_QUEUE", "IN_PROGRESS"]:
            print(f"Job {job_id} is {status}, waiting 10s...")
            time.sleep(10)
            status_url = f"https://api.runpod.ai/v2/{runpod_endpoint_id}/status/{job_id}"
            response = robust_get(status_url, headers)
            status = response.get("status")
        
        if status == "COMPLETED":
            output = response.get("output", {})
            if output.get("success"):
                public_url = output.get("public_url")
                print(f"RunPod finished! Downloading {public_url} to gallery...")
                
                video_data = None
                dl_headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'}
                for attempt in range(5):
                    try:
                        video_data = requests.get(public_url, headers=dl_headers, timeout=60).content
                        break
                    except Exception as e:
                        print(f"Download attempt {attempt+1} failed: {e}. Retrying in 5 seconds...")
                        time.sleep(5)
                
                if not video_data:
                    raise Exception("Failed to download video from Catbox after 5 attempts")
                    
                filename = f"manual_clip_{int(time.time())}.mp4"
                filepath = os.path.join(output_dir, filename)
                
                os.makedirs(output_dir, exist_ok=True)
                with open(filepath, "wb") as f:
                    f.write(video_data)
                    
                print(f"Successfully saved to {filepath}!")
            else:
                print(f"RunPod worker error: {output.get('error')}")
        else:
            print(f"RunPod job failed with status {status}: {response}")
    except Exception as e:
        print(f"Failed to process manual clip via RunPod: {e}")

@app.post("/api/manual-clip")
def trigger_manual_clip(req: ManualClipRequest, background_tasks: BackgroundTasks):
    import subprocess
    import sys
    
    runpod_api_key = os.getenv("RUNPOD_API_KEY")
    runpod_endpoint_id = os.getenv("RUNPOD_ENDPOINT_ID")
    
    if runpod_api_key and runpod_endpoint_id:
        print(f"Triggering RunPod Serverless API for {req.url}")
        background_tasks.add_task(process_manual_clip_runpod, req, runpod_api_key, runpod_endpoint_id, OUTPUT_CLIPS_DIR)
        return {"success": True, "message": f"Started RunPod background job for {req.url}. It will appear in the gallery when finished."}
    else:
        print(f"Triggering local manual clip for {req.url}")
        project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        script_path = os.path.join(project_root, "clipper_agent.py")
        
        args = [sys.executable, script_path, req.url, req.style]
        if not req.generateSubtitles:
            args.append("--no-subs")
            
        # Run the clipper script in the background locally
        subprocess.Popen(args, cwd=project_root)
        
        return {"success": True, "message": f"Started local manual clipping in background for {req.url}. It will appear in the gallery when finished."}

@app.get("/api/gallery")
def get_gallery():
    import glob
    import time
    if not os.path.exists(OUTPUT_CLIPS_DIR):
        return []
    
    files = glob.glob(os.path.join(OUTPUT_CLIPS_DIR, "*.mp4"))
    files.sort(key=os.path.getctime, reverse=True)
    
    videos = []
    for f in files:
        filename = os.path.basename(f)
        videos.append({
            "filename": filename,
            "url": f"/output_clips/{filename}",
            "created_at": os.path.getctime(f)
        })
    return videos

frontend_dist = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "frontend", "dist")
if os.path.exists(frontend_dist):
    app.mount("/", StaticFiles(directory=frontend_dist, html=True), name="static")

if __name__ == "__main__":
    import uvicorn
    print("Starting Agency Dashboard Backend on http://localhost:8000")
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
