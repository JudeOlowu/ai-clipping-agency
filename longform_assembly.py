import os, zipfile, subprocess, requests, traceback

def get_audio_duration(filepath):
    cmd = ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", filepath]
    res = subprocess.run(cmd, capture_output=True, text=True)
    return float(res.stdout.strip())

def assemble_longform(zip_url, work_dir="/app/wework_temp"):
    print(f"Downloading {zip_url}...")
    os.makedirs(work_dir, exist_ok=True)
    zip_path = os.path.join(work_dir, "assets.zip")
    r = requests.get(zip_url, stream=True)
    with open(zip_path, 'wb') as f:
        for chunk in r.iter_content(1024): f.write(chunk)
            
    with zipfile.ZipFile(zip_path, 'r') as zip_ref: zip_ref.extractall(work_dir)
        
    audio_path = os.path.join(work_dir, "longform_voiceover.mp3")
    drone_audio = "/app/wework_assets/cinematic_drone.wav"
    duration = get_audio_duration(audio_path)
    
    assets = [f for f in sorted(os.listdir(work_dir)) if f.endswith(('.jpg', '.png', '.mp4')) and "raw_video" not in f and "final" not in f]
    clip_files = []
    
    for i in range(int(duration / 15.0) + 1):
        asset = assets[i % len(assets)]
        asset_path = os.path.join(work_dir, asset)
        out_clip = os.path.join(work_dir, f"clip_{i}.mp4")
        
        cmd = ["ffmpeg", "-y", "-loop", "1", "-i", asset_path, "-t", "15.0", "-filter_complex", "scale=8000:-1,zoompan=z='min(zoom+0.0005,1.5)':d=1500:x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)',scale=1920:1080,format=yuv420p", "-c:v", "libx264", "-preset", "fast", "-crf", "23", out_clip]
        if asset.endswith(".mp4"):
            cmd = ["ffmpeg", "-y", "-stream_loop", "-1", "-i", asset_path, "-t", "15.0", "-vf", "scale=1920:1080:force_original_aspect_ratio=increase,crop=1920:1080", "-c:v", "libx264", "-preset", "fast", "-crf", "23", out_clip]
            
        subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        clip_files.append(out_clip)
        
    concat_txt = os.path.join(work_dir, "concat.txt")
    with open(concat_txt, "w") as f:
        for cf in clip_files: f.write(f"file '{os.path.basename(cf)}'\n")
            
    raw_video = os.path.join(work_dir, "raw.mp4")
    subprocess.run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", concat_txt, "-c", "copy", raw_video], check=True)
    
    final_out = os.path.join(work_dir, "wework_longform_final.mp4")
    subprocess.run(["ffmpeg", "-y", "-i", raw_video, "-i", audio_path, "-stream_loop", "-1", "-i", drone_audio, "-filter_complex", "[1:a]volume=1.0[a1];[2:a]volume=0.2[a2];[a1][a2]amix=inputs=2:duration=first:dropout_transition=2[a]", "-map", "0:v", "-map", "[a]", "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-t", str(duration + 1.5), final_out], check=True)
    
    return final_out
