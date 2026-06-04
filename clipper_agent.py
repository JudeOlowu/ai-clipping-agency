import os
import sys
import time
import textwrap
import yt_dlp
from faster_whisper import WhisperModel
from moviepy import VideoFileClip, CompositeVideoClip, ImageClip
import moviepy.video.fx as vfx
from PIL import Image, ImageDraw, ImageFont
import numpy as np
from openai import OpenAI
from dotenv import load_dotenv


# Inject the bundled ffmpeg into PATH so both Whisper and yt-dlp can find it
import imageio_ffmpeg as _iio_ff
_ffmpeg_dir = os.path.dirname(_iio_ff.get_ffmpeg_exe())
if _ffmpeg_dir not in os.environ.get("PATH", ""):
    os.environ["PATH"] = _ffmpeg_dir + os.pathsep + os.environ.get("PATH", "")

load_dotenv()

# ── Cross-platform font resolver ─────────────────────────────────────────────
_FONT_FALLBACK = {
    "arialbd.ttf":  "LiberationSans-Bold.ttf",
    "impact.ttf":   "LiberationSans-Bold.ttf",
    "tahoma.ttf":   "DejaVuSans.ttf",
    "comicbd.ttf":  "DejaVuSans-Bold.ttf",
    "trebucbd.ttf": "LiberationSans-Bold.ttf",
}
_FONT_DIRS = [
    r"C:\Windows\Fonts",
    "/usr/share/fonts/truetype/liberation",
    "/usr/share/fonts/truetype/dejavu",
    "/usr/share/fonts/truetype",
    "/usr/share/fonts",
]

def resolve_font(font_name: str):
    """Return an absolute font path that works on Windows and Linux."""
    for candidate in [font_name, _FONT_FALLBACK.get(font_name, font_name)]:
        for d in _FONT_DIRS:
            path = os.path.join(d, candidate)
            if os.path.exists(path):
                return path
    return None  # triggers ImageFont.load_default() fallback
# ─────────────────────────────────────────────────────────────────────────────

# Setup OpenRouter (using OpenAI SDK)
client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=os.getenv("OPENROUTER_API_KEY"),
)

def download_video(url: str, output_path: str = "temp_video.mp4") -> str:
    """Downloads a YouTube video to a local mp4 file using yt-dlp."""
    print(f"Downloading video from {url}...")
    
    import imageio_ffmpeg
    ffmpeg_path = imageio_ffmpeg.get_ffmpeg_exe()

    import time
    if output_path == "temp_video.mp4":
        output_path = f"temp_video_{int(time.time())}.mp4"

    ydl_opts = {
        # Grab the best video up to 1080p and merge with the best audio using FFmpeg
        'format': 'bestvideo[height<=720][ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
        'outtmpl': output_path,
        'quiet': False,
        'playlist_items': '1',           # Prevent downloading entire channels/playlists
        'ffmpeg_location': ffmpeg_path,  # Point yt-dlp to the bundled ffmpeg binary
    }
    
    if os.path.exists("cookies.txt"):
        print("--> Using cookies.txt for authentication bypass...")
        ydl_opts['cookiefile'] = 'cookies.txt'
    
    if os.path.exists(output_path):
        try:
            os.remove(output_path)
        except PermissionError:
            print(f"--> Warning: {output_path} is locked by another process. Skipping delete and overwriting.")

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        res = ydl.download([url])
        if res != 0:
            raise Exception(f"yt-dlp failed to download {url} (exit code {res})")
            
    if not os.path.exists(output_path):
        raise Exception(f"yt-dlp finished but {output_path} was not created.")
        
    print(f"--> Downloaded to {output_path}")
    return output_path

def transcribe_video(video_path: str):
    """Uses faster-whisper (base model) to transcribe the video - fallback when no captions available."""
    print("Loading faster-whisper model (base)...")
    # Using CUDA since we are on RunPod GPUs now!
    model = WhisperModel("base", device="cuda", compute_type="float16")
    
    print("Transcribing video (with word-level timestamps)...")
    segments_gen, _ = model.transcribe(video_path, beam_size=1, word_timestamps=True, task="translate")
    segments = []
    for s in segments_gen:
        if not s.words:
            segments.append({"start": s.start, "end": s.end, "text": s.text})
        else:
            # Group words into small chunks (e.g., 2-3 words max) for snappy TikTok-style captions
            current_chunk = []
            chunk_start = None
            
            for word in s.words:
                if chunk_start is None:
                    chunk_start = word.start
                
                current_chunk.append(word.word.strip())
                
                # If we hit 3 words or the word ends with punctuation, flush the chunk
                is_punctuation = any(p in word.word for p in ['.', '!', '?', ','])
                if len(current_chunk) >= 3 or is_punctuation:
                    segments.append({
                        "start": chunk_start,
                        "end": word.end,
                        "text": " ".join(current_chunk)
                    })
                    current_chunk = []
                    chunk_start = None
                    
            # Flush any remaining words
            if current_chunk and chunk_start is not None:
                segments.append({
                    "start": chunk_start,
                    "end": s.words[-1].end,
                    "text": " ".join(current_chunk)
                })
            
    print("--> Transcription complete.")
    return segments


def find_viral_clip(segments: list, client_title: str = "") -> tuple:
    """Uses OpenRouter to analyze the transcript and select the best 30-60s clip based on client context."""
    print("Analyzing transcript with AI to find the most viral segment...")
    
    transcript = ""
    for s in segments:
        transcript += f"[{s['start']:.2f} - {s['end']:.2f}] {s['text']}\\n"
        
    transcript = transcript[:15000]
    
    context_instruction = ""
    if client_title:
        context_instruction = f"IMPORTANT: The client specifically requested the following: '{client_title}'. Please prioritize a segment that directly addresses this topic or niche!"
        
    prompt = f"""
    You are an expert short-form video editor specialized in TikTok, Reels, and Shorts.
    Read the following timestamped transcript of a video.
    Identify the absolute best, most punchy and viral 30 to 45 second segment. It should have a strong hook and clear topic.
    CRITICAL: You MUST select a highly engaging snippet that is STRICTLY between 30 and 45 seconds long. If the clip is less than 25 seconds, it is too short and will be rejected. Do NOT just select the entire video. Cut out the fluff and find the core message.
    {context_instruction}
    
    You must also determine the best subtitle aesthetic based on the video's vibe.
    Choose a 'font_color' from: 'yellow', 'white', '#00FF00', '#FF00FF', '#00FFFF'.
    Choose a 'font_name' from: 'arialbd.ttf', 'impact.ttf', 'tahoma.ttf', 'comicbd.ttf', 'trebucbd.ttf'.
    
    Return ONLY a JSON object with this exact format:
    {{"start": [START_TIME_IN_SECONDS], "end": [END_TIME_IN_SECONDS], "color": "yellow", "font": "impact.ttf"}}
    Do not include any markdown formatting, backticks, or other text. Just the raw JSON.
    
    Transcript:
    {transcript}
    """
    
    try:
        response = client.chat.completions.create(
            model="openai/gpt-4o",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.0
        )
        content = response.choices[0].message.content.strip()
        
        import json
        if content.startswith("```json"):
            content = content[7:-3].strip()
        elif content.startswith("```"):
            content = content[3:-3].strip()
            
        data = json.loads(content)
        start_time = float(data.get("start", 0.0))
        end_time = float(data.get("end", 30.0))
        font_color = data.get("color", "yellow")
        font_name = data.get("font", "arialbd.ttf")
        
        # Enforce max 45 seconds to prevent massive rendering times
        if end_time - start_time > 45.0:
            print(f"--> AI chose a {end_time - start_time}s clip! Truncating to 45s for faster rendering.")
            end_time = start_time + 45.0
            
        print(f"--> AI selected viral clip from {start_time}s to {end_time}s")
        print(f"--> AI selected branding: {font_color} text with {font_name} font")
        return start_time, end_time, font_color, font_name
    except Exception as e:
        print(f"Error calling OpenRouter: {e}")
        print("Fallback: Clipping the first 30 seconds with default branding.")
        return 0.0, 30.0, "yellow", "arialbd.ttf"

def make_subtitle_clip(text: str, duration: float, frame_w: int,
                       font_path: str = None,
                       font_size: int = 50, font_color: str = "white") -> ImageClip:
    """Render subtitle text using Pillow (no ImageMagick). Returns a transparent ImageClip."""
    try:
        resolved = font_path or resolve_font("arialbd.ttf")
        font = ImageFont.truetype(resolved, font_size) if resolved else ImageFont.load_default()
    except Exception:
        font = ImageFont.load_default()

    # Word-wrap text to fit inside the frame
    wrapped = textwrap.fill(text.strip().upper(), width=22)

    # Measure how tall the text block will be
    dummy = Image.new('RGBA', (1, 1))
    d = ImageDraw.Draw(dummy)
    bbox = d.multiline_textbbox((0, 0), wrapped, font=font, spacing=8)
    text_w = bbox[2] - bbox[0]
    text_h = bbox[3] - bbox[1]
    padding = 16
    img_w = min(frame_w, text_w + padding * 2)
    img_h = text_h + padding * 2

    img = Image.new('RGBA', (img_w, img_h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    x = img_w // 2
    y = padding

    # Draw black outline by drawing text in 8 directions
    outline = 3
    for dx in range(-outline, outline + 1):
        for dy in range(-outline, outline + 1):
            if dx != 0 or dy != 0:
                draw.multiline_text((x + dx, y + dy), wrapped, font=font,
                                    fill=(0, 0, 0, 255), anchor='ma', align='center', spacing=8)
    # Draw main text on top
    draw.multiline_text((x, y), wrapped, font=font,
                        fill=font_color, anchor='ma', align='center', spacing=8)

    arr = np.array(img)
    return ImageClip(arr, is_mask=False).with_duration(duration)


def _generate_subtitles(segments, start_time, end_time, target_w, target_h, font_color, font_name):
    subtitle_clips = []
    if segments:
        for s in segments:
            s_start = max(0, s['start'] - start_time)
            s_end = min((end_time - start_time), s['end'] - start_time)
            if s_start < (end_time - start_time) and s_end > 0 and s_end > s_start:
                txt = s['text'].strip().upper()
                if txt:
                    duration = max(0.1, s_end - s_start)
                    sub_clip = make_subtitle_clip(txt, duration, target_w, font_path=resolve_font(font_name), font_color=font_color)
                    sub_x = (target_w - sub_clip.size[0]) // 2
                    subtitle_y = int(target_h * 0.60)
                    sub_clip = sub_clip.with_position((sub_x, subtitle_y)).with_start(s_start)
                    subtitle_clips.append(sub_clip)
    return subtitle_clips

def create_default_clip(video_path: str, start_time: float, end_time: float, output_path: str, segments: list = None, font_color: str = "yellow", font_name: str = "arialbd.ttf"):
    """Cuts the video, creates a 9:16 vertical background, and overlays AI subtitles."""
    print(f"Editing video: DEFAULT template from {start_time}s to {end_time}s...")
    clip = VideoFileClip(video_path).subclipped(start_time, end_time)
    target_w, target_h = 720, 1280
    bg_clip = clip.resized(height=target_h)
    x_center = bg_clip.size[0] / 2
    bg_clip = bg_clip.cropped(x1=x_center - target_w/2, y1=0, x2=x_center + target_w/2, y2=target_h)
    bg_clip = bg_clip.with_effects([vfx.MultiplyColor(0.25)])
    fg_clip = clip.resized(width=target_w).with_position("center")
    subtitle_clips = _generate_subtitles(segments, start_time, end_time, target_w, target_h, font_color, font_name)
    final_clip = CompositeVideoClip([bg_clip, fg_clip] + subtitle_clips, size=(target_w, target_h))
    print(f"Exporting final clip to {output_path}...")
    final_clip.write_videofile(output_path, codec="libx264", audio_codec="aac", threads=8, preset="ultrafast")
    print("--> Export complete.")
    clip.close()
    final_clip.close()

def create_gaming_overlay_clip(video_path: str, start_time: float, end_time: float, output_path: str, segments: list = None, font_color: str = "yellow", font_name: str = "arialbd.ttf"):
    print(f"Editing video: GAMING OVERLAY template from {start_time}s to {end_time}s...")
    clip = VideoFileClip(video_path).subclipped(start_time, end_time)
    target_w, target_h = 720, 1280
    w, h = clip.size
    
    import cv2
    import numpy as np
    face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')
    
    face_box = None
    for t in [0, min(2.0, clip.duration/2), max(0, clip.duration-2.0)]:
        frame = clip.get_frame(t)
        gray = cv2.cvtColor(frame, cv2.COLOR_RGB2GRAY)
        faces = face_cascade.detectMultiScale(gray, 1.1, 4)
        if len(faces) > 0:
            faces = sorted(faces, key=lambda f: f[2]*f[3], reverse=True)
            fx, fy, fw, fh = faces[0]
            pad_x = int(fw * 0.4)
            pad_y = int(fh * 0.4)
            x1 = max(0, fx - pad_x)
            y1 = max(0, fy - pad_y)
            x2 = min(w, fx + fw + pad_x)
            y2 = min(h, fy + fh + pad_y)
            face_box = (x1, y1, x2, y2)
            break
            
    if not face_box:
        print("--> No face found for the gaming facecam! Falling back to DEFAULT template.")
        clip.close()
        return create_default_clip(video_path, start_time, end_time, output_path, segments, font_color, font_name)
        
    x1, y1, x2, y2 = face_box
    facecam = clip.cropped(x1=x1, y1=y1, x2=x2, y2=y2).resized(width=target_w)
    
    # Gameplay is the full video resized
    gameplay = clip.resized(width=target_w)
    
    # Place facecam at the top, gameplay below it
    facecam = facecam.with_position(("center", 100))
    gameplay_y = facecam.size[1] + 150
    gameplay = gameplay.with_position(("center", gameplay_y))
    
    subtitle_clips = _generate_subtitles(segments, start_time, end_time, target_w, target_h, font_color, font_name)
    bg_color = ImageClip(np.zeros((target_h, target_w, 3), dtype=np.uint8)).with_duration(clip.duration)
    
    final_clip = CompositeVideoClip([bg_color, gameplay, facecam] + subtitle_clips, size=(target_w, target_h))
    print(f"Exporting final clip to {output_path}...")
    final_clip.write_videofile(output_path, codec="libx264", audio_codec="aac", threads=8, preset="ultrafast")
    clip.close()
    final_clip.close()

def create_split_screen_clip(video_path: str, start_time: float, end_time: float, output_path: str, segments: list = None, font_color: str = "yellow", font_name: str = "arialbd.ttf"):
    print(f"Editing video: SPLIT SCREEN template from {start_time}s to {end_time}s...")
    clip = VideoFileClip(video_path).subclipped(start_time, end_time)
    duration = end_time - start_time
    target_w, target_h = 720, 1280
    
    # Top part: the client's video
    part1 = clip.resized(width=target_w)
    h_part1 = part1.size[1]
    y1 = max(0, (target_h // 2 - h_part1) // 2)
    part1 = part1.with_position(("center", int(y1)))
    
    # Bottom part: Satisfying video
    satisfying_file = "satisfying_bg.mp4"
    if not os.path.exists(satisfying_file):
        print("--> Downloading satisfying background video (first time only)...")
        # Minecraft Parkour video
        download_video("https://www.youtube.com/watch?v=9JGcV1DbrM4", satisfying_file)
        
    part2 = VideoFileClip(satisfying_file)
    if part2.duration > duration:
        import random
        max_start = part2.duration - duration
        s_start = random.uniform(0, max_start)
        part2 = part2.subclipped(s_start, s_start + duration)
    else:
        part2 = part2.subclipped(0, part2.duration)
    
    # Ensure it fills the bottom half correctly
    part2 = part2.resized(width=target_w)
    if part2.size[1] < target_h // 2:
        part2 = part2.resized(height=target_h // 2)
    
    x_center = part2.size[0] / 2
    y_center = part2.size[1] / 2
    part2 = part2.cropped(x1=x_center - target_w/2, y1=y_center - target_h/4, x2=x_center + target_w/2, y2=y_center + target_h/4)
    
    # Place on bottom half
    y2 = target_h // 2
    part2 = part2.with_position(("center", int(y2)))
    
    subtitle_clips = _generate_subtitles(segments, start_time, end_time, target_w, target_h, font_color, font_name)
    bg_color = ImageClip(np.zeros((target_h, target_w, 3), dtype=np.uint8)).with_duration(clip.duration)
    
    final_clip = CompositeVideoClip([bg_color, part2, part1] + subtitle_clips, size=(target_w, target_h))
    print(f"Exporting final clip to {output_path}...")
    final_clip.write_videofile(output_path, codec="libx264", audio_codec="aac", threads=8, preset="ultrafast")
    clip.close()
    part2.close()
    final_clip.close()

def create_talking_head_clip(video_path: str, start_time: float, end_time: float, output_path: str, segments: list = None, font_color: str = "yellow", font_name: str = "arialbd.ttf"):
    print(f"Editing video: TALKING HEAD template from {start_time}s to {end_time}s...")
    clip = VideoFileClip(video_path).subclipped(start_time, end_time)
    target_w, target_h = 720, 1280
    
    # 1. Resize so height matches 1280
    fg_clip = clip.resized(height=target_h)
    
    print("--> Running OpenCV face tracking to smoothly pan the camera...")
    import cv2
    import numpy as np
    
    face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')
    fps_sample = 2
    duration = fg_clip.duration
    times = np.arange(0, duration, 1.0 / fps_sample)
    
    x_centers = []
    last_x = fg_clip.size[0] / 2
    
    for t in times:
        frame = fg_clip.get_frame(t)
        gray = cv2.cvtColor(frame, cv2.COLOR_RGB2GRAY)
        faces = face_cascade.detectMultiScale(gray, 1.1, 4)
        if len(faces) > 0:
            faces = sorted(faces, key=lambda f: f[2]*f[3], reverse=True)
            x, y, w, h = faces[0]
            face_center_x = x + w/2
            last_x = face_center_x
        x_centers.append(last_x)
        
    def get_x_center(t):
        if t < 0: t = 0
        if t > duration: t = duration
        idx = t * fps_sample
        idx0 = int(idx)
        idx1 = min(idx0 + 1, len(x_centers) - 1)
        if idx0 >= len(x_centers): return x_centers[-1]
        weight = idx - idx0
        return x_centers[idx0] * (1 - weight) + x_centers[idx1] * weight

    # 2. Dynamic crop filter
    def crop_filter(get_frame, t):
        img = get_frame(t)
        xc = get_x_center(t)
        half_w = target_w / 2
        xc = max(half_w, min(xc, img.shape[1] - half_w))
        x1 = int(xc - half_w)
        x2 = x1 + target_w
        return img[:, x1:x2]

    # Use MoviePy's transform to apply frame transformation
    fg_clip = fg_clip.transform(lambda gf, t: crop_filter(gf, t))
    
    # 3. Generate subtitles
    subtitle_clips = _generate_subtitles(segments, start_time, end_time, target_w, target_h, font_color, font_name)
    
    final_clip = CompositeVideoClip([fg_clip] + subtitle_clips, size=(target_w, target_h))
    
    print(f"Exporting final clip to {output_path}...")
    final_clip.write_videofile(output_path, codec="libx264", audio_codec="aac", threads=8, preset="ultrafast")
    clip.close()
    fg_clip.close()
    final_clip.close()

def apply_template(style: str, video_path: str, start_time: float, end_time: float, output_path: str, segments: list = None, font_color: str = "yellow", font_name: str = "arialbd.ttf"):
    if style == "GAMING_OVERLAY":
        create_gaming_overlay_clip(video_path, start_time, end_time, output_path, segments, font_color, font_name)
    elif style == "SPLIT_SCREEN":
        create_split_screen_clip(video_path, start_time, end_time, output_path, segments, font_color, font_name)
    elif style == "TALKING_HEAD":
        create_talking_head_clip(video_path, start_time, end_time, output_path, segments, font_color, font_name)
    else:
        create_default_clip(video_path, start_time, end_time, output_path, segments, font_color, font_name)

def detect_existing_subtitles(video_path: str) -> bool:
    """Extracts a frame from the middle of the video and uses GPT-4o Vision to check for hardcoded subtitles."""
    print("Checking video for existing hardcoded subtitles via OCR...")
    try:
        clip = VideoFileClip(video_path)
        mid_time = clip.duration / 2
        frame = clip.get_frame(mid_time)
        clip.close()
        
        img = Image.fromarray(frame)
        import base64
        from io import BytesIO
        buffered = BytesIO()
        # Resize to save bandwidth
        img.thumbnail((512, 512))
        img.save(buffered, format="JPEG")
        img_str = base64.b64encode(buffered.getvalue()).decode()
        
        response = client.chat.completions.create(
            model="openai/gpt-4o",
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "Does this video frame contain large, centered, word-by-word rolling subtitles (like TikTok captions) spanning across the middle or bottom? Ignore small text, channel logos, lower-thirds, or background text. Reply with ONLY 'true' if there are massive video captions, or 'false' if there are none."},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{img_str}",
                                "detail": "low"
                            }
                        }
                    ]
                }
            ],
            max_tokens=10,
            temperature=0.0
        )
        
        result = response.choices[0].message.content.strip().lower()
        if 'true' in result:
            print("--> AI detected existing subtitles! Skipping subtitle generation to prevent overlap.")
            return True
        else:
            print("--> No existing subtitles detected. We will generate our own.")
            return False
    except Exception as e:
        print(f"--> OCR Error: {e}")
        return False

def run_clipper(video_url: str, client_title: str = "", style: str = "DEFAULT", force_no_subs: bool = False):
    print(f"Starting Fully Local Clipper Agent Pipeline... (Style: {style})")
    output_dir = "output_clips"
    os.makedirs(output_dir, exist_ok=True)

    temp_video = download_video(video_url)
    
    if force_no_subs:
        print("--> User requested NO SUBTITLES via --no-subs flag. Skipping AI subtitle detection/generation.")
        has_subtitles = True
    else:
        has_subtitles = detect_existing_subtitles(temp_video)

    print("--> Extracting audio and transcribing via local Whisper model...")
    segments = transcribe_video(temp_video)

    start_time, end_time, font_color, font_name = find_viral_clip(segments, client_title)

    output_filename = f"{output_dir}/viral_clip_{int(time.time())}.mp4"
    
    # If the video already has subtitles, we pass None to skip generating our own.
    final_segments = None if has_subtitles else segments
    
    apply_template(style, temp_video, start_time, end_time, output_filename, final_segments, font_color=font_color, font_name=font_name)

    print(f"\n[DONE] Clipper Agent finished! Final video: {output_filename}")
    return os.path.abspath(output_filename)

if __name__ == "__main__":
    style = "DEFAULT"
    force_no_subs = "--no-subs" in sys.argv
    args = [arg for arg in sys.argv[1:] if arg != "--no-subs"]
    
    if len(args) > 0:
        video_url = args[0]
        if len(args) > 1:
            style = args[1]
    else:
        video_url = input("Enter YouTube URL (or press Enter to use your last video): ")
        if not video_url.strip():
            # Defaults back to the user's previously provided video
            video_url = "https://youtu.be/7Ff09Qgmgnw?si=JW9LCg7Y-f_ozlP4"
    
    run_clipper(video_url, style=style, force_no_subs=force_no_subs)
