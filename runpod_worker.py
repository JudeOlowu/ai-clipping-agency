import runpod
import os
import multiprocessing
import traceback

def clipper_process_wrapper(queue, video_url, client_title, style, api_key, generate_subtitles, custom_instructions):
    try:
        if api_key:
            os.environ["OPENROUTER_API_KEY"] = api_key
        from clipper_agent import run_clipper
        clip_path = run_clipper(video_url, client_title=client_title, style=style, force_no_subs=not generate_subtitles, custom_instructions=custom_instructions)
        queue.put({"success": True, "clip_path": clip_path})
    except Exception as e:
        queue.put({"success": False, "error": str(e), "traceback": traceback.format_exc()})

def handler(job):
    job_input = job.get("input", {})
    video_url = job_input.get("video_url")
    style = job_input.get("style", "DEFAULT")
    client_title = job_input.get("client_title", "")
    api_key = job_input.get("api_key", "")
    generate_subtitles = job_input.get("generateSubtitles", True)
    custom_instructions = job_input.get("customInstructions", "")
    
    if not video_url:
        return {"error": "Missing video_url"}
        
    try:
        print(f"Starting clipper process for {video_url}...")
        if custom_instructions:
            print(f"--> Director's Notes: {custom_instructions}")
        
        # Use multiprocessing to prevent C-level segfaults from killing the worker
        ctx = multiprocessing.get_context('spawn')
        q = ctx.Queue()
        p = ctx.Process(target=clipper_process_wrapper, args=(q, video_url, client_title, style, api_key, generate_subtitles, custom_instructions))
        p.start()
        p.join()
        
        if p.exitcode != 0:
            return {"error": f"Worker process crashed fatally with exit code {p.exitcode}. This usually indicates a Segmentation Fault or Out of Memory error in C-extensions (like OpenCV, FFmpeg, or Faster-Whisper)."}
            
        result = q.get()
        if not result.get("success"):
            return {"error": result.get("error"), "traceback": result.get("traceback")}
            
        clip_path = result.get("clip_path")
        
        # Upload to Catbox for public URL
        print(f"Uploading {clip_path} to Catbox...")
        import requests
        url = "https://catbox.moe/user/api.php"
        with open(clip_path, 'rb') as f:
            data = {'reqtype': 'fileupload'}
            files = {'fileToUpload': f}
            response = requests.post(url, data=data, files=files)
            
        if response.status_code == 200:
            public_url = response.text
        else:
            raise Exception(f"Catbox upload failed: {response.text}")
        
        # Clean up local file
        if os.path.exists(clip_path):
            os.remove(clip_path)
            
        return {
            "success": True,
            "public_url": public_url
        }
    except Exception as e:
        print(traceback.format_exc())
        return {"error": str(e)}

if __name__ == "__main__":
    runpod.serverless.start({"handler": handler})
