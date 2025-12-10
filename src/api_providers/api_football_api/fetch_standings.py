import os
import logging
import requests
import json
from datetime import datetime

logger = logging.getLogger(__name__)

BASE_URL = "https://v3.football.api-sports.io"
API_HOST = "v3.football.api-sports.io"

def _api_request(endpoint, params):
    api_key = os.environ.get("API_FOOTBALL_API_KEY")
    if not api_key:
        logger.error("API_FOOTBALL_API_KEY not found in environment.")
        return None

    headers = {
        "x-rapidapi-key": api_key,
        "x-rapidapi-host": API_HOST
    }
    
    url = f"{BASE_URL}/{endpoint}"
    logger.info(f"Requesting from API Football endpoint: {endpoint} with params: {params}")

    try:
        response = requests.get(url, headers=headers, params=params, timeout=20)
        response.raise_for_status()
        response_data = response.json()

        if response_data.get("errors"):
            logger.error(f"API returned errors: {response_data['errors']}")
            return None
        
        if "response" not in response_data:
            logger.error("API response is missing the 'response' key.")
            return None
        
        response_items = response_data["response"]
        logger.info(f"Successfully received {len(response_items)} items from the API.")
        return response_items

    except requests.exceptions.RequestException as e:
        logger.error(f"HTTP request to API Football failed: {e}")
        return None
    except json.JSONDecodeError:
        logger.error("Failed to decode JSON from API Football response.")
        return None

def fetch_standings_from_api(league, season):
    logger.info(f"Fetching standings for league {league}, season {season}.")
    params = {"league": league, "season": season}
    return _api_request("standings", params)

if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    
    LEAGUE_ID_TO_TEST = os.getenv("API_FOOTBALL_LEAGUE_ID")
    SEASON_TO_TEST = os.getenv("API_FOOTBALL_SEASON")

    if not LEAGUE_ID_TO_TEST or not SEASON_TO_TEST:
        logger.critical("API_FOOTBALL_LEAGUE_ID and/or API_FOOTBALL_SEASON not set in .env file. Aborting test.")
    else:
        logger.info(f"CLI Test: Fetching current standings for League {LEAGUE_ID_TO_TEST}, Season {SEASON_TO_TEST}")

        standings_data = fetch_standings_from_api(
            league=LEAGUE_ID_TO_TEST,
            season=SEASON_TO_TEST
        )

        if standings_data is not None:
            output_dir = "exports"
            os.makedirs(output_dir, exist_ok=True)
            
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"{output_dir}/standings_{LEAGUE_ID_TO_TEST}_{timestamp}.json"
            
            try:
                with open(filename, 'w', encoding='utf-8') as f:
                    json.dump(standings_data, f, indent=4, ensure_ascii=False)
                logger.info(f"Successfully saved standings data to {filename}")
            except IOError as e:
                logger.error(f"Failed to write to file {filename}: {e}")
        else:
            logger.error("Failed to fetch standings from API-Football, no output file generated.")