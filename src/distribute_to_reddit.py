import os
import logging
import requests
import json
from datetime import datetime, timezone
from urllib.parse import quote_plus

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

    round_id = round_data.get("round_id")
    last_updated_utc_str = round_data.get("last_updated_utc", datetime.now(timezone.utc).isoformat())

    title = f"Super League Watch Thread: Αγωνιστική {round_id}"
    
    header = "| Home | Score | Away | Status |\n"
    header += "|:---|:---:|:---|:---|\n"

    body_lines = []
    for match in round_data["matches"]:
        home_team = match.get('home_team', 'N/A')
        away_team = match.get('away_team', 'N/A')
        home_greek = match.get('home_team_greek') or home_team
        away_greek = match.get('away_team_greek') or away_team
        
        home_subreddit = match.get('home_team_subreddit')
        away_subreddit = match.get('away_team_subreddit')

        home_display = f"[{home_greek}]({home_subreddit})" if home_subreddit else home_greek
        away_display = f"[{away_greek}]({away_subreddit})" if away_subreddit else away_greek
        
        score = match.get('score', '-').strip() if (match.get('score') or "").strip() else "-"
        search_query = quote_plus(f"{home_team} vs {away_team}")
        google_link = f"https://www.google.com/search?q={search_query}"
        score_display = f"[{score}]({google_link})" if score != "-" else score

        status_val = match.get('status', 'scheduled')
        status_display = "Scheduled"
        if status_val == "in_play":
            minute = match.get('live_minute', '')
            status_display = f"🔴 Live ({minute}')"
        elif status_val == "completed":
            status_display = "Full Time"
        elif status_val == "not_started":
            date = match.get('date', '')
            time = match.get('kick_off_time_utc', '')
            if len(time) == 2:
                time += ":00"
            status_display = f"{date} {time}"

        line = f"| {home_display} | **{score_display}** | {away_display} | {status_display} |"
        body_lines.append(line)
    
    footer = f"\n\n---\n*Last updated: {last_updated_utc_str} (UTC)*"
    
    full_body = header + "\n".join(body_lines) + footer
    return title, full_body

def _find_existing_post_id(access_token, subreddit, title):
    logger.info(f"Searching for existing post with title '{title}' in r/{subreddit}")
    user_agent = os.getenv("REDDIT_USER_AGENT")
    headers = {"Authorization": f"Bearer {access_token}", "User-Agent": user_agent}
    
    search_url = f"https://oauth.reddit.com/r/{subreddit}/search.json"
    params = {
        "q": f'title:"{title}"',
        "restrict_sr": "on",
        "sort": "new",
        "limit": 1
    }

    try:
        response = requests.get(search_url, headers=headers, params=params, timeout=15)
        response.raise_for_status()
        results = response.json()
        posts = results.get("data", {}).get("children", [])
        if posts:
            post_title = posts[0].get("data", {}).get("title")
            if post_title == title:
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
    data = {
        "sr": subreddit,
        "title": title,
        "kind": "self",
        "text": markdown_body,
        "api_type": "json"
    }

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
    access_token = _refresh_access_token()
    if not access_token:
        return False
        
    _, markdown_body = _format_post_body(round_data)
    if not markdown_body:
        return False
        
    user_agent = os.getenv("REDDIT_USER_AGENT")
    headers = {"Authorization": f"Bearer {access_token}", "User-Agent": user_agent}
    data = {
        "thing_id": post_id,
        "text": markdown_body,
        "api_type": "json"
    }
    
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
    if not access_token:
        return None
        
    title, markdown_body = _format_post_body(round_data)
    if not title or not markdown_body:
        return None
    
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
        files = [f for f in os.listdir(EXPORT_DIR) if f.startswith("consolidated_round_") and f.endswith(".json")]
        files.sort(key=lambda f: os.path.getmtime(os.path.join(EXPORT_DIR, f)), reverse=True)
        if files:
            latest_file_path = os.path.join(EXPORT_DIR, files[0])
    except FileNotFoundError:
        logger.warning(f"Export directory '{EXPORT_DIR}' not found.")

    if not latest_file_path:
        logger.error("No consolidated data file found in 'exports/'. Aborting CLI test.")
    else:
        logger.info(f"--- Reddit Distributor CLI Test ---")
        logger.info(f"Using latest data file: {latest_file_path}")

        with open(latest_file_path, 'r', encoding='utf-8') as f:
            test_round_data = json.load(f)

        logger.info("\n1. Testing 'create_or_get_post'...")
        post_id = create_or_get_post(test_round_data)

        if post_id:
            logger.info(f"Success. Got Post ID: {post_id}")

            logger.info("\n2. Testing 'update_post' with the same data to check formatting...")
            update_success = update_post(post_id, test_round_data)

            if update_success:
                logger.info("Success. Post updated with new formatting.")
                print("\nCLI Test PASSED.")
            else:
                logger.error("Failure. Post update failed.")
                print("\nCLI Test FAILED during update.")
        else:
            logger.error("Failure. Could not create or get post.")
            print("\nCLI Test FAILED during creation/get.")

        logger.info("--- CLI Test Complete ---")