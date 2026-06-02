# AI Clipping Agency - Project Handoff

This document contains a comprehensive summary of the recent upgrades, bug fixes, and future implementation plans. Please read this to catch up on the current state of the project.

## 1. What Has Been Completed & Fixed
* **The Emoji Crash (Windows Terminal):** `scout_agent.py` previously crashed when attempting to print job titles containing emojis on Windows. A `safe_print` wrapper was added to gracefully handle Unicode encoding errors.
* **Dashboard Filtering Removed:** The frontend React dashboard (`App.tsx`) was updated to stop hiding leads that didn't have a downloaded video. All 20+ leads scraped are now visible in the CRM.
* **No-Video Outreach Capability:** Updated `main.py` and `App.tsx` to provide a "Send Pitch (No Video)" button for leads whose videos couldn't be downloaded (e.g. native Reddit videos). Clicking it directly opens a Reddit DM with the pitch pre-filled offering to do a free sample if they send a link.
* **Lead Deduplication:** Updated `scout_agent.py` to read `leads.csv` on startup, store `existing_urls` in a Set, and skip scraping posts it has already seen. This completely solves the issue of duplicate leads appearing in the dashboard on consecutive runs.
* **Clear CRM Endpoint:** Added a `DELETE /api/leads` endpoint to `main.py` to allow the user to easily wipe the `leads.csv` (excluding headers). 

## 2. What Needs to be Finished Next (Action Items)
* **Add the "Clear Leads" Button to Frontend:** The backend `DELETE` endpoint is ready, but the UI button still needs to be added to the header in `dashboard/frontend/src/App.tsx`.
* **Explain Video Formats to User:** The user requested an explanation with examples of the different types of video templates the agent could learn to edit.

## 3. The Future Roadmap (Template Matching Architecture)
The user has approved the concept of upgrading the agent from a single, generic editing style to a dynamic **Template Matching** architecture. 

**The Strategy:**
1. **Scout Agent Upgrade:** The LLM prompt in `extract_lead_info` will be updated to not only qualify the lead, but also classify the visual style they are requesting (e.g. `Style: GAMING_OVERLAY`, `Style: TALKING_HEAD`, `Style: SPLIT_SCREEN`).
2. **Clipper Agent Routing:** `clipper_agent.py` will be refactored to accept this `style` parameter and route the video into distinct predefined Python scripts/FFMPEG commands (e.g., `build_gaming_template()`, `build_split_screen()`) instead of applying a universal centered crop.

---
**Note to new AI:** The pipeline is stable and currently uses `yt-dlp` with a `cookies.txt` file to bypass external authentication walls. The dashboard is running on Vite (React) and FastAPI.
