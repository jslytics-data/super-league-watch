import os
import logging
import requests
import json
from datetime import datetime, timedelta, timezone

logger = logging.getLogger(__name__)

BASE_URL = "https://livescore-api.com/api-client/fixtures/list.json"

def fetch_fixtures_from_api(competition_id=None, date=None, round=None, lang=None):
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
        "date": date,
        "round": round,
        "lang": lang,
    }

    for key, value in optional_params.items():
        if value is not None:
            query_params[key] = value
    
    all_fixtures = []
    current_page = 1

    while True:
        query_params["page"] = current_page
        
        loggable_params = {k: v for k, v in query_params.items() if k not in ['key', 'secret']}
        logger.info(f"Requesting fixtures with params: {loggable_params}")

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

        fixtures_on_page = response_data.get("data", {}).get("fixtures", [])
        
        if not fixtures_on_page:
            logger.info(f"No more fixtures found on page {current_page}. Concluding fetch.")
            break

        all_fixtures.extend(fixtures_on_page)
        
        if len(fixtures_on_page) < 30:
            logger.info("Received fewer than 30 fixtures, indicating this is the last page.")
            break
            
        current_page += 1

    logger.info(f"Successfully fetched a total of {len(all_fixtures)} fixtures across {current_page - 1} page(s).")
    return all_fixtures

if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

    COMPETITION_ID_TO_TEST = 9
    DAYS_AHEAD_TO_TEST = 30
    
    logger.info(f"CLI Test: Fetching all fixtures for competition {COMPETITION_ID_TO_TEST} for the next {DAYS_AHEAD_TO_TEST} days.")

    today = datetime.now(timezone.utc)
    all_upcoming_fixtures = []
    test_successful = True

    for i in range(DAYS_AHEAD_TO_TEST):
        check_date = today + timedelta(days=i)
        date_str = check_date.strftime("%Y-%m-%d")
        
        daily_fixtures = fetch_fixtures_from_api(
            competition_id=COMPETITION_ID_TO_TEST,
            date=date_str
        )
        
        if daily_fixtures is None:
            logger.error(f"Failed to fetch fixtures for {date_str}. Halting test.")
            test_successful = False
            break
        
        all_upcoming_fixtures.extend(daily_fixtures)

    if test_successful and all_upcoming_fixtures is not None:
        output_dir = "exports"
        os.makedirs(output_dir, exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{output_dir}/fixtures_{COMPETITION_ID_TO_TEST}_{timestamp}.json"
        
        try:
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(all_upcoming_fixtures, f, indent=4)
            logger.info(f"Successfully saved {len(all_upcoming_fixtures)} fixtures to {filename}")
        except IOError as e:
            logger.error(f"Failed to write to file {filename}: {e}")
    else:
        logger.error("Failed to fetch fixtures, no output file generated.")