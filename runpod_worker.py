import runpod
import os
import multiprocessing
import traceback
import subprocess

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
    job_type = job_input.get("job_type", "shortform")
    
    if job_type == "longform_assembly":
        zip_url = job_input.get("zip_url")
        if not zip_url:
            return {"error": "Missing zip_url for longform assembly"}
            
        try:
            print(f"Starting longform assembly process...")
            ctx = multiprocessing.get_context('spawn')
            q = ctx.Queue()
            import subprocess
            p = ctx.Process(target=longform_process_wrapper, args=(q, zip_url))
            p.start()
            p.join()
            
            if p.exitcode != 0:
                return {"error": f"Worker crashed with exit code {p.exitcode}."}
                
            result = q.get()
            if not result.get("success"):
                return {"error": result.get("error"), "traceback": result.get("traceback")}
                
            clip_path = result.get("clip_path")
            print(f"Uploading final documentary {clip_path}...")
            import requests
            public_url = None
            
            # Provider 1: Catbox
            try:
                print("Trying Catbox...")
                url = "https://catbox.moe/user/api.php"
                with open(clip_path, 'rb') as f:
                    response = requests.post(url, data={'reqtype': 'fileupload'}, files={'fileToUpload': f}, timeout=60)
                if response.status_code == 200 and response.text.startswith("https://"):
                    public_url = response.text
            except Exception as e:
                print(f"Catbox failed: {e}")
                
            # Provider 2: Tmpfiles
            if not public_url:
                try:
                    print("Trying Tmpfiles...")
                    url = "https://tmpfiles.org/api/v1/upload"
                    with open(clip_path, 'rb') as f:
                        response = requests.post(url, files={'file': f}, timeout=60).json()
                    if response.get('status') == 'success':
                        public_url = response['data']['url'].replace("tmpfiles.org/", "tmpfiles.org/dl/")
                except Exception as e:
                    print(f"Tmpfiles failed: {e}")
                    
            # Provider 3: File.io
            if not public_url:
                try:
                    print("Trying File.io...")
                    with open(clip_path, 'rb') as f:
                        response = requests.post("https://file.io", files={'file': f}, timeout=60).json()
                    if response.get("success"):
                        public_url = response.get("link")
                except Exception as e:
                    print(f"File.io failed: {e}")

            if public_url:
                return {"success": True, "public_url": public_url}
            else:
                return {"error": "All upload providers failed or timed out."}
        except Exception as e:
            return {"error": str(e), "traceback": traceback.format_exc()}
            
    # Default shortform handler logic
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
        print(f"Uploading {clip_path}...")
        import requests
        public_url = None
        
        try:
            print("Trying Catbox...")
            url = "https://catbox.moe/user/api.php"
            with open(clip_path, 'rb') as f:
                response = requests.post(url, data={'reqtype': 'fileupload'}, files={'fileToUpload': f}, timeout=60)
            if response.status_code == 200 and response.text.startswith("https://"):
                public_url = response.text
        except Exception as e:
            print(f"Catbox failed: {e}")
            
        if not public_url:
            try:
                print("Trying Tmpfiles...")
                url = "https://tmpfiles.org/api/v1/upload"
                with open(clip_path, 'rb') as f:
                    response = requests.post(url, files={'file': f}, timeout=60).json()
                if response.get('status') == 'success':
                    public_url = response['data']['url'].replace("tmpfiles.org/", "tmpfiles.org/dl/")
            except Exception as e:
                print(f"Tmpfiles failed: {e}")

        if public_url:
            # Clean up local file
            if os.path.exists(clip_path):
                os.remove(clip_path)
            return {
                "success": True,
                "public_url": public_url
            }
        else:
            raise Exception("All upload providers failed or timed out.")
    except Exception as e:
        print(traceback.format_exc())
        return {"error": str(e)}

def get_audio_duration(filepath):
    cmd = [
        "ffprobe", "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        filepath
    ]
    res = subprocess.run(cmd, capture_output=True, text=True)
    return float(res.stdout.strip())

def longform_process_wrapper(queue, zip_url):
    try:
        import zipfile
        import requests
        
        work_dir = "/app/wework_temp"
        print(f"Downloading assets from {zip_url}...")
        os.makedirs(work_dir, exist_ok=True)
        zip_path = os.path.join(work_dir, "assets.zip")
        
        import time
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}
        
        success = False
        for attempt in range(3):
            try:
                r = requests.get(zip_url, headers=headers, timeout=60)
                if r.status_code == 200:
                    with open(zip_path, 'wb') as f:
                        f.write(r.content)
                    success = True
                    break
                else:
                    print(f"Attempt {attempt+1}: Status {r.status_code}")
            except Exception as e:
                print(f"Attempt {attempt+1} exception: {e}")
                time.sleep(3)
                
        if not success:
            raise Exception(f"Failed to download zip from {zip_url} after 3 attempts.")
            
        print("Extracting assets...")
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(work_dir)
            
        audio_path = os.path.join(work_dir, "longform_voiceover.mp3")
        drone_audio = os.path.join(work_dir, "cinematic_drone.wav")
        
        if not os.path.exists(audio_path):
            raise Exception("Missing longform_voiceover.mp3 in zip payload")
        
        if not os.path.exists(drone_audio):
            fallback = "/app/wework_assets/cinematic_drone.wav"
            if os.path.exists(fallback):
                drone_audio = fallback
            else:
                raise Exception("Missing cinematic_drone.wav")

        print("[2/3] Preparing video sequences...")
        duration = get_audio_duration(audio_path)
        print(f"  Total Audio Duration: {duration:.2f}s")
        
        segment_duration = 15.0
        num_segments = int(duration / segment_duration) + 1
        
        assets = []
        for f in sorted(os.listdir(work_dir)):
            if f.endswith(".jpg") or f.endswith(".png") or f.endswith(".mp4"):
                if "raw_video.mp4" not in f and "final" not in f:
                    assets.append(f)
                    
        if not assets:
            raise Exception("No image/video assets found in zip to assemble!")
            
        clip_files = []
        for i in range(num_segments):
            asset = assets[i % len(assets)]
            asset_path = os.path.join(work_dir, asset)
            out_clip = os.path.join(work_dir, f"long_clip_{i}.mp4")
            
            if asset.endswith(".mp4"):
                cmd = [
                    "ffmpeg", "-y", "-stream_loop", "-1", "-i", asset_path,
                    "-t", str(segment_duration),
                    "-vf", "scale=1920:1080:force_original_aspect_ratio=increase,crop=1920:1080",
                    "-c:v", "libx264", "-preset", "fast", "-crf", "23",
                    out_clip
                ]
            else:
                cmd = [
                    "ffmpeg", "-y", "-loop", "1", "-i", asset_path,
                    "-t", str(segment_duration),
                    "-vf", "scale=1920:1080:force_original_aspect_ratio=increase,crop=1920:1080,format=yuv420p",
                    "-c:v", "libx264", "-preset", "ultrafast", "-crf", "23",
                    out_clip
                ]
                
            print(f"  Generating sequence {i+1}/{num_segments} from {asset}...")
            import subprocess
            subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            clip_files.append(out_clip)
            
        print("  Concatenating visual sequences...")
        concat_txt = os.path.join(work_dir, "video_concat.txt")
        with open(concat_txt, "w") as f:
            for cf in clip_files:
                f.write(f"file '{os.path.basename(cf)}'\n")
                
        raw_video = os.path.join(work_dir, "raw_video.mp4")
        subprocess.run([
            "ffmpeg", "-y", "-f", "concat", "-safe", "0",
            "-i", concat_txt, "-c", "copy", raw_video
        ], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        
        print("[3/3] Final Mixing...")
        final_out = os.path.join(work_dir, "wework_longform_final.mp4")
        mix_cmd = [
            "ffmpeg", "-y",
            "-i", raw_video,
            "-i", audio_path,
            "-stream_loop", "-1", "-i", drone_audio,
            "-filter_complex", "[1:a]volume=1.0[a1];[2:a]volume=0.2[a2];[a1][a2]amix=inputs=2:duration=first:dropout_transition=2[a]",
            "-map", "0:v", "-map", "[a]",
            "-c:v", "copy",
            "-c:a", "aac", "-b:a", "192k",
            "-t", str(duration + 1.5),
            final_out
        ]
        subprocess.run(mix_cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        queue.put({"success": True, "clip_path": final_out})
    except Exception as e:
        queue.put({"success": False, "error": str(e), "traceback": traceback.format_exc()})

if __name__ == "__main__":
    runpod.serverless.start({"handler": handler})
