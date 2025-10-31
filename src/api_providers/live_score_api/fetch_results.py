import os
import logging
import requests
import json
from datetime import datetime, timedelta, timezone

logger = logging.getLogger(__name__)

BASE_URL = "https://livescore-api.com/api-client/matches/history.json"

def fetch_results_from_api(competition_id=None, from_date=None, to_date=None, lang=None):
    api_key = os.environ.get("LIVE_SCORE_API_KEY")
    api_secret = os.environ.get("LIVE_SCORE_API_SECRET")

    if not api_key or not api_secret:
        logger.error("API key or secret is not configured in environment.")
        return None

    query_params = {
        "key": api_key,
        "secret": api_secret,
    }

    if to_date is None:
        to_date = from_date

    optional_params = {
        "competition_id": competition_id,
        "from": from_date,
        "to": to_date,
        "lang": lang
    }

    for key, value in optional_params.items():
        if value is not None:
            query_params[key] = value
            
    all_matches = []
    current_page = 1
    
    while True:
        query_params["page"] = current_page
        
        loggable_params = {k: v for k, v in query_params.items() if k not in ['key', 'secret']}
        logger.info(f"Requesting match history with params: {loggable_params}")

        try:
            response = requests.get(BASE_URL, params=query_params, timeout=15)
            response.raise_for_status()
            response_data = response.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"HTTP request failed on page {current_page}: {e}")
            return None
        except json.JSONDecodeError:
            logger.error(f"Failed to decode JSON from response on page {current_page}.")
            return None

        if not response_data.get("success", False):
            logger.error(f"API indicated failure on page {current_page}: {response_data.get('message', 'No message')}")
            return None

        matches_on_page = response_data.get("data", {}).get("match", [])

        if not matches_on_page:
            logger.info(f"No more historical matches found on page {current_page}. Concluding fetch.")
            break

        all_matches.extend(matches_on_page)
        
        if len(matches_on_page) < 30:
            logger.info("Received fewer than 30 matches, indicating this is the last page.")
            break
            
        current_page += 1

    logger.info(f"Successfully fetched a total of {len(all_matches)} historical matches across {current_page - 1} page(s).")
    return all_matches

if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    
    COMPETITION_ID_TO_TEST = 67
    DAYS_AGO_TO_TEST = 7
    
    logger.info(f"CLI Test: Fetching all results for competition {COMPETITION_ID_TO_TEST} for the last {DAYS_AGO_TO_TEST} days.")

    today = datetime.now(timezone.utc)
    from_date = today - timedelta(days=DAYS_AGO_TO_TEST - 1)
    
    from_date_str = from_date.strftime("%Y-%m-%d")
    to_date_str = today.strftime("%Y-%m-%d")

    results_data = fetch_results_from_api(
        competition_id=COMPETITION_ID_TO_TEST,
        from_date=from_date_str,
        to_date=to_date_str
    )

    if results_data is not None:
        output_dir = "exports"
        os.makedirs(output_dir, exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{output_dir}/results_{COMPETITION_ID_TO_TEST}_{timestamp}.json"
        
        try:
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(results_data, f, indent=4)
            logger.info(f"Successfully saved {len(results_data)} results to {filename}")
        except IOError as e:
            logger.error(f"Failed to write to file {filename}: {e}")
    else:
        logger.error("Failed to fetch match results, no output file generated.")