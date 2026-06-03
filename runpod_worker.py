import runpod
import os
from clipper_agent import run_clipper
from uploader import upload_video

def handler(job):
    job_input = job.get("input", {})
    video_url = job_input.get("video_url")
    style = job_input.get("style", "DEFAULT")
    client_title = job_input.get("client_title", "")
    
    if not video_url:
        return {"error": "Missing video_url"}
        
    try:
        # Generate the clip
        clip_path = run_clipper(video_url, client_title=client_title, style=style)
        
        # Upload to Catbox for public URL
        print(f"Uploading {clip_path} to Catbox...")
        public_url = upload_video(clip_path)
        
        # Clean up local file
        if os.path.exists(clip_path):
            os.remove(clip_path)
            
        return {
            "success": True,
            "public_url": public_url
        }
    except Exception as e:
        import traceback
        print(traceback.format_exc())
        return {"error": str(e)}

if __name__ == "__main__":
    runpod.serverless.start({"handler": handler})
