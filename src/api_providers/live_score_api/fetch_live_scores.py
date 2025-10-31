import os
import logging
import requests
import json
from datetime import datetime

logger = logging.getLogger(__name__)

BASE_URL = "https://livescore-api.com/api-client/matches/live.json"

def fetch_live_scores_from_api(competition_id=None, lang=None):
    api_key = os.environ.get("LIVE_SCORE_API_KEY")
    api_secret = os.environ.get("LIVE_SCORE_API_SECRET")

    if not api_key or not api_secret:
        logger.error("API key or secret is not configured in environment.")
        return None

    query_params = {
        "key": api_key,
        "secret": api_secret,
    }

    optional_params = {
        "competition_id": competition_id,
        "lang": lang,
    }

    for key, value in optional_params.items():
        if value is not None:
            query_params[key] = value
            
    loggable_params = {k: v for k, v in query_params.items() if k not in ['key', 'secret']}
    logger.info(f"Requesting live scores with params: {loggable_params}")

    try:
        response = requests.get(BASE_URL, params=query_params, timeout=15)
        response.raise_for_status()
        response_data = response.json()
    except requests.exceptions.RequestException as e:
        logger.error(f"HTTP request failed: {e}")
        return None
    except json.JSONDecodeError:
        logger.error("Failed to decode JSON from response.")
        return None

    if not response_data.get("success", False):
        logger.error(f"API indicated failure: {response_data.get('message', 'No message')}")
        return None

    live_matches = response_data.get("data", {}).get("match", [])
    
    logger.info(f"Successfully fetched a total of {len(live_matches)} live matches.")
    return live_matches

if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()

    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    
    logger.info("CLI Test: Fetching all currently live matches for ALL competitions.")
    live_scores_data = fetch_live_scores_from_api()

    if live_scores_data is not None:
        output_dir = "exports"
        os.makedirs(output_dir, exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{output_dir}/live_scores_ALL_{timestamp}.json"
        
        try:
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(live_scores_data, f, indent=4)
            logger.info(f"Successfully saved {len(live_scores_data)} live scores to {filename}")
        except IOError as e:
            logger.error(f"Failed to write to file {filename}: {e}")
    else:
        logger.error("Failed to fetch live scores, no output file generated.")