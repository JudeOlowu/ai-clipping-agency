import os
import csv
import time
import json
import requests
from openai import OpenAI
from dotenv import load_dotenv

# Import the clipper agent pipeline
import clipper_agent

load_dotenv()

# Setup OpenRouter (using OpenAI SDK)
client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=os.getenv("OPENROUTER_API_KEY"),
)

LEADS_FILE = "leads.csv"

def extract_lead_info(title: str, text: str) -> dict:
    """Uses OpenRouter to determine if it's a clipping job and extract any media URL."""
    prompt = f"""
    You are an AI assistant qualifying leads for a video editing agency.
    We ONLY want jobs where the client explicitly needs short-form clips, TikToks, Shorts, or Reels edited from longer content.
    CRITICAL FILTERS: 
    1. If the user is OFFERING their services as an editor, this is NOT a lead.
    2. If the post mentions "revenue share", "revshare", "% of revenue", or "unpaid", this is NOT a lead.
    3. If the post requires you to "record your own gameplay", "create original content", or do heavy manual VFX/animations, this is NOT a lead. We only do repurposing/clipping.
    
    Also, scan the text for ANY link to a video or channel (YouTube, Twitch, Twitter, Drive, etc).
    Finally, classify the required video style. Choose exactly one of: "GAMING_OVERLAY", "SPLIT_SCREEN", "TALKING_HEAD", or "DEFAULT". If unsure, use "DEFAULT".
    
    Title: {title}
    Description: {text}
    
    You must reply ONLY in valid JSON format exactly like this:
    {{
        "is_lead": true or false,
        "video_url": "the URL found", // or JSON null if no URL exists. NEVER use the string "null".
        "style": "DEFAULT"
    }}
    """
    
    try:
        response = client.chat.completions.create(
            model="openai/gpt-4o",
            messages=[{"role": "user", "content": prompt}],
            response_format={ "type": "json_object" },
            temperature=0.0
        )
        content = response.choices[0].message.content.strip()
        return json.loads(content)
    except Exception as e:
        print(f"Error calling OpenRouter: {e}")
        return {"is_lead": False, "video_url": None}

def draft_proposal(title: str, text: str, video_path: str = None) -> str:
    """Drafts a personalized proposal for the lead, referencing the auto-generated clip if available."""
    
    if video_path:
        clip_mention = f"I went ahead and used my custom AI tools to pull your video and edit a free 9:16 viral clip for you as a sample! You can check it out here: {video_path} - Imagine having 10 of these ready to post every week."
    else:
        clip_mention = "I'd love to edit a free 9:16 sample clip for you from your latest video to prove the quality. Just drop me a link!"

    prompt = f"""
    Draft a short, engaging Reddit DM or reply to the following job post. 
    Offer our services: we are an AI-powered editing agency that specializes in high-retention short-form clips (TikTok/Reels/Shorts).
    Include this EXACT text seamlessly into the pitch: "{clip_mention}"
    Keep it under 4 sentences. Sound human, confident, and professional.
    
    CRITICAL INSTRUCTION: Read the Job Description carefully. If the poster explicitly asks you to start your message with a specific word (e.g., "Start your message with the word 'READY'"), or asks a specific question to filter out bots, YOU MUST OBEY THIS INSTRUCTION exactly. If they ask for a code word, put it at the very beginning of your pitch.
    
    Job Title: {title}
    Job Description: {text}
    """
    try:
        response = client.chat.completions.create(
            model="openai/gpt-4o",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=150,
            temperature=0.7
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        return f"Error drafting proposal: {e}"

def run_scout(subreddits=["CreatorServices", "YouTubeEditors", "HireAnEditor", "freelance_forhire"], limit=100):
    print(f"Starting Scout Agent. Checking r/{', r/'.join(subreddits)} for the last {limit} posts...")
    
    existing_urls = set()
    if not os.path.exists(LEADS_FILE):
        with open(LEADS_FILE, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(["Subreddit", "URL", "Title", "Drafted Proposal", "Local Clip Path"])
    else:
        with open(LEADS_FILE, 'r', encoding='utf-8') as f:
            reader = csv.reader(f)
            next(reader, None) # skip header
            for row in reader:
                if len(row) > 1:
                    existing_urls.add(row[1])
            
    found_leads = 0
    headers = {"User-agent": "VideoClippingScout/1.2 (MVP Auto-Responder)"}
    
    for sub_name in subreddits:
        print(f"\\nScraping r/{sub_name}...")
        url = f"https://www.reddit.com/r/{sub_name}/new.rss?limit={limit}"
        
        try:
            import feedparser
            import requests
            
            response = requests.get(url, headers=headers)
            feed = feedparser.parse(response.text)
            
            if not feed.entries:
                print(f"Failed to fetch or parse {sub_name} RSS feed.")
                time.sleep(2)
                continue
            
            for entry in feed.entries:
                title = entry.get('title', '')
                # Reddit RSS puts HTML in summary, we'll extract raw text if possible, or just use it as is
                # For basic keyword matching, raw HTML summary is fine
                text = entry.get('summary', '')
                post_url = entry.get('link', '')
                
                if post_url in existing_urls:
                    continue
                
                def safe_print(text):
                    try:
                        print(text)
                    except UnicodeEncodeError:
                        print(text.encode('ascii', 'ignore').decode('ascii'))
                        
                # --- LOCAL FILTER TO SAVE API CREDITS ---
                title_lower = title.lower()
                text_lower = text.lower()
                
                if any(tag in title_lower for tag in ['[offer]', '[for hire]', 'hire me', 'my portfolio']):
                    safe_print(f"Skipping (Offer/For Hire): {title[:50]}...")
                    continue
                    
                if not any(keyword in title_lower or keyword in text_lower for keyword in ['video', 'edit', 'clip', 'tiktok', 'reel', 'shorts', 'youtube']):
                    safe_print(f"Skipping (Irrelevant): {title[:50]}...")
                    continue
                # ----------------------------------------
                
                safe_print(f"Analyzing with AI: {title[:50]}...")
                lead_data = extract_lead_info(title, text)
                
                if lead_data.get("is_lead"):
                    print("--> MATCH FOUND!")
                    video_url = lead_data.get("video_url")
                    style = lead_data.get("style", "DEFAULT")
                    if video_url == "null" or video_url == "":
                        video_url = None
                    clip_path = None
                    
                    if video_url:
                        print(f"--> Found Video URL in post: {video_url}")
                        print(f"--> Detected Style: {style}")
                        
                        runpod_api_key = os.getenv("RUNPOD_API_KEY")
                        runpod_endpoint_id = os.getenv("RUNPOD_ENDPOINT_ID")
                        
                        if runpod_api_key and runpod_endpoint_id:
                            print("--> Offloading heavy clipping job to RunPod Serverless GPU...")
                            import requests
                            headers = {
                                "Authorization": f"Bearer {runpod_api_key}",
                                "Content-Type": "application/json"
                            }
                            payload = {
                                "input": {
                                    "video_url": video_url,
                                    "style": style,
                                    "client_title": title
                                }
                            }
                            try:
                                # Use runsync so we wait for the GPU to finish returning the URL before pitching
                                url = f"https://api.runpod.ai/v2/{runpod_endpoint_id}/runsync"
                                rp_res = requests.post(url, json=payload, headers=headers).json()
                                
                                if rp_res.get("status") == "COMPLETED":
                                    output = rp_res.get("output", {})
                                    if output.get("success"):
                                        clip_path = output.get("public_url")
                                        print(f"--> RunPod finished successfully! Public Asset URL: {clip_path}")
                                    else:
                                        print(f"--> RunPod worker reported an error: {output.get('error')}")
                                else:
                                    print(f"--> RunPod job failed or timed out: {rp_res}")
                            except Exception as e:
                                print(f"--> Failed to contact RunPod API: {e}")
                                
                        if not clip_path:
                            # Fallback if RunPod fails or isn't configured
                            print("--> No RunPod output (or not configured). Falling back to LOCAL processing...")
                            try:
                                clip_path = clipper_agent.run_clipper(video_url, title, style=style)
                                
                                if clip_path and os.path.exists(clip_path):
                                    print(f"--> Uploading local proof-of-work clip to host...")
                                    import uploader
                                    public_video_url = uploader.upload_video(clip_path)
                                    if public_video_url:
                                        clip_path = public_video_url
                            except Exception as e:
                                print(f"--> Local Clipper Agent failed to process URL: {e}")
                    else:
                        print("--> No Video URL found in post. Skipping auto-clipping.")
                    
                    proposal = draft_proposal(title, text, clip_path)
                    
                    with open(LEADS_FILE, 'a', newline='', encoding='utf-8') as f:
                        writer = csv.writer(f)
                        writer.writerow([sub_name, post_url, title, proposal, clip_path])
                        
                    print("--> Saved lead and proposal to leads.csv\n")

                    print(f"\\n--- DRAFT OUTREACH MESSAGE ---")
                    try:
                        print(proposal)
                    except UnicodeEncodeError:
                        print(proposal.encode('ascii', 'ignore').decode('ascii'))
                    print("------------------------------\\n")
                    
                    print(f"--> Saved lead and proposal to {LEADS_FILE}\\n")
                    found_leads += 1
            
            time.sleep(2)
            
        except Exception as e:
            print(f"Failed to scrape r/{sub_name}: {e}")
            
    print(f"\\nScout Agent finished. Found {found_leads} total leads.")

if __name__ == "__main__":
    run_scout()
