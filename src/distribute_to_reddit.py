import os
import logging
import requests
import json
from datetime import datetime, timezone
from urllib.parse import quote_plus
from pytz import timezone as pytz_timezone

logger = logging.getLogger(__name__)

def _refresh_access_token():
    logger.info("Attempting to refresh Reddit access token.")
    client_id = os.getenv("REDDIT_CLIENT_ID")
    client_secret = os.getenv("REDDIT_CLIENT_SECRET")
    refresh_token = os.getenv("REDDIT_REFRESH_TOKEN")
    user_agent = os.getenv("REDDIT_USER_AGENT")

    if not all([client_id, client_secret, refresh_token, user_agent]):
        logger.error("Reddit API environment variables are missing.")
        return None

    token_endpoint = "https://www.reddit.com/api/v1/access_token"
    headers = {"User-Agent": user_agent}
    data = {"grant_type": "refresh_token", "refresh_token": refresh_token}
    auth = (client_id, client_secret)

    try:
        response = requests.post(url=token_endpoint, auth=auth, headers=headers, data=data, timeout=15)
        response.raise_for_status()
        token_data = response.json()
        new_access_token = token_data.get("access_token")
        if not new_access_token:
            logger.error("Token refresh response did not contain an access_token.")
            return None
        logger.info("Successfully refreshed Reddit access token.")
        return new_access_token
    except requests.exceptions.RequestException as e:
        logger.error(f"Error during Reddit token refresh: {e}")
        return None

def _format_post_body(round_data):
    if not round_data or "matches" not in round_data:
        logger.error("Cannot format post body, invalid round_data provided.")
        return None, None

    gr_timezone = pytz_timezone('Europe/Athens')
    competition_name = round_data.get("competition_name", "League")
    round_id = round_data.get("round_id")
    
    try:
        last_updated_utc_str = round_data.get("last_updated_utc", datetime.now(timezone.utc).isoformat())
        utc_dt = datetime.fromisoformat(last_updated_utc_str)
        gr_dt = utc_dt.astimezone(gr_timezone)
        last_updated_display = gr_dt.strftime('%Y-%m-%d %H:%M:%S') + " (GR)"
    except (ValueError, TypeError):
        last_updated_display = f"{last_updated_utc_str} (UTC)"

    title = f"{competition_name} Watch - {round_id}"
    
    header = "| Home | Score | Away | Status |\n"
    header += "|:---|:---:|:---|:---|\n"

    body_lines = []
    for match in round_data["matches"]:
        home_greek = match.get('home_team_greek') or match.get('home_team', 'N/A')
        away_greek = match.get('away_team_greek') or match.get('away_team', 'N/A')
        
        score = match.get('score', '-').strip() if (match.get('score') or "").strip() else "-"
        
        status_val = match.get('status', 'scheduled')
        status_display = "Scheduled"
        if status_val == "in_play":
            minute = match.get('live_minute', '')
            status_display = f"🔴 Live ({minute}')"
        elif status_val == "completed":
            status_display = f"🏁 Full Time"
        elif status_val == "not_started":
            try:
                date_str = match.get('date', '')
                time_str = match.get('kick_off_time_utc', '')
                if len(time_str) <= 2: time_str += ":00"
                
                utc_dt_str = f"{date_str}T{time_str}:00Z"
                match_utc_dt = datetime.fromisoformat(utc_dt_str.replace('Z', '+00:00'))
                match_gr_dt = match_utc_dt.astimezone(gr_timezone)
                status_display = f"📅 {match_gr_dt.strftime('%Y-%m-%d %H:%M')}"
            except (ValueError, TypeError):
                status_display = f"📅 {date_str} {time_str} (UTC)"

        line = f"| **{home_greek}** | **{score}** | **{away_greek}** | {status_display} |"
        body_lines.append(line)
    
    footer = f"\n\n---\n*Last updated: {last_updated_display}*"
    
    full_body = header + "\n".join(body_lines) + footer
    return title, full_body

def _find_existing_post_id(access_token, subreddit, title):
    logger.info(f"Searching for existing post with title '{title}' in r/{subreddit}")
    user_agent = os.getenv("REDDIT_USER_AGENT")
    headers = {"Authorization": f"Bearer {access_token}", "User-Agent": user_agent}
    
    search_url = f"https://oauth.reddit.com/r/{subreddit}/search.json"
    params = {"q": f'title:"{title}"', "restrict_sr": "on", "sort": "new", "limit": 1}

    try:
        response = requests.get(search_url, headers=headers, params=params, timeout=15)
        response.raise_for_status()
        results = response.json()
        posts = results.get("data", {}).get("children", [])
        if posts and posts[0].get("data", {}).get("title") == title:
            post_id = posts[0].get("data", {}).get("name")
            logger.info(f"Found existing post with matching title. ID: {post_id}")
            return post_id
    except requests.exceptions.RequestException as e:
        logger.error(f"API error while searching for post: {e}")
    
    logger.info("No existing post found with the exact title.")
    return None

def _create_post(access_token, subreddit, title, markdown_body):
    logger.info(f"Creating new post in r/{subreddit}")
    user_agent = os.getenv("REDDIT_USER_AGENT")
    headers = {"Authorization": f"Bearer {access_token}", "User-Agent": user_agent}
    data = {"sr": subreddit, "title": title, "kind": "self", "text": markdown_body, "api_type": "json"}

    try:
        response = requests.post("https://oauth.reddit.com/api/submit", headers=headers, data=data, timeout=30)
        response.raise_for_status()
        response_json = response.json()
        if response_json.get("json", {}).get("errors"):
            logger.error(f"Reddit API returned errors on post creation: {response_json['json']['errors']}")
            return None
        post_id = response_json.get("json", {}).get("data", {}).get("name")
        if not post_id:
            logger.error("Post creation successful but no post ID ('name') found in response.")
            return None
        logger.info(f"Successfully created new Reddit post. ID: {post_id}")
        return post_id
    except requests.exceptions.RequestException as e:
        logger.error(f"HTTP error creating post: {e}")
        return None

def update_post(post_id, round_data):
    logger.info(f"Attempting to update Reddit post {post_id}")
    if not post_id or not post_id.startswith('t3_'):
        logger.error(f"Invalid post_id provided for update: {post_id}. It must start with 't3_'.")
        return False
        
    access_token = _refresh_access_token()
    if not access_token: return False
        
    _, markdown_body = _format_post_body(round_data)
    if not markdown_body: return False
        
    user_agent = os.getenv("REDDIT_USER_AGENT")
    headers = {"Authorization": f"Bearer {access_token}", "User-Agent": user_agent}
    data = {"thing_id": post_id, "text": markdown_body, "api_type": "json"}
    
    try:
        response = requests.post("https://oauth.reddit.com/api/editusertext", headers=headers, data=data, timeout=30)
        response.raise_for_status()
        response_json = response.json()
        if response_json.get("json", {}).get("errors"):
            logger.error(f"Reddit API returned errors on post update: {response_json['json']['errors']}")
            return False
        logger.info(f"Successfully updated post {post_id}")
        return True
    except requests.exceptions.RequestException as e:
        logger.error(f"HTTP error updating post: {e}")
        return False

def create_or_get_post(round_data):
    logger.info("Attempting to create or get Reddit post.")
    subreddit = os.getenv("TARGET_SUBREDDIT")
    if not subreddit:
        logger.error("TARGET_SUBREDDIT is not set in environment.")
        return None

    access_token = _refresh_access_token()
    if not access_token: return None
    
    title, markdown_body = _format_post_body(round_data)
    if not title or not markdown_body: return None
    
    existing_post_id = _find_existing_post_id(access_token, subreddit, title)
    if existing_post_id:
        return existing_post_id
    
    return _create_post(access_token, subreddit, title, markdown_body)

if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

    EXPORT_DIR = "exports"
    latest_file_path = None
    try:
        files = sorted([f for f in os.listdir(EXPORT_DIR) if f.startswith("prepared_round_state_") and f.endswith(".json")], 
                       key=lambda f: os.path.getmtime(os.path.join(EXPORT_DIR, f)), reverse=True)
        if files: latest_file_path = os.path.join(EXPORT_DIR, files[0])
    except FileNotFoundError:
        logger.warning(f"Export directory '{EXPORT_DIR}' not found.")

    if not latest_file_path:
        logger.error("No prepared state file found in 'exports/'. Aborting CLI test.")
    else:
        logger.info(f"--- Reddit Distributor CLI Test ---")
        logger.info(f"Using latest data file: {latest_file_path}")

        with open(latest_file_path, 'r', encoding='utf-8') as f: test_round_data = json.load(f)
        
        logger.info("\n1. Testing 'create_or_get_post' with new formatting...")
        post_id = create_or_get_post(test_round_data)

        if post_id:
            logger.info(f"Success. Got Post ID: {post_id}")
            logger.info("\n2. Testing 'update_post' with the same data to confirm formatting...")
            update_success = update_post(post_id, test_round_data)
            if update_success:
                logger.info("Success. Post updated.")
                print("\nCLI Test PASSED.")
            else:
                logger.error("Failure. Post update failed.")
                print("\nCLI Test FAILED during update.")
        else:
            logger.error("Failure. Could not create post.")
            print("\nCLI Test FAILED during creation.")
        logger.info("--- CLI Test Complete ---")