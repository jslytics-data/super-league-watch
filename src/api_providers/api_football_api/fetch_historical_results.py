import os
import logging
import requests
import json
import csv # Import the csv module
from datetime import datetime

# --- Configuration for Elo Calculation ---
INITIAL_ELO = 1500
K_FACTOR = 30
HOME_ADVANTAGE = 100

logger = logging.getLogger(__name__)

# --- Data Fetching (Unaltered) ---

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
        response = requests.get(url, headers=headers, params=params, timeout=30)
        response.raise_for_status()
        response_data = response.json()

        if response_data.get("errors"):
            logger.error(f"API returned errors: {response_data['errors']}")
            return None
        
        if "response" not in response_data:
            logger.error("API response is missing the 'response' key.")
            return None
        
        response_items = response_data["response"]
        logger.info(f"Successfully received {len(response_items)} items for params {params}.")
        return response_items

    except requests.exceptions.RequestException as e:
        logger.error(f"HTTP request to API Football failed: {e}")
        return None
    except json.JSONDecodeError:
        logger.error("Failed to decode JSON from API Football response.")
        return None

def _transform_fixture_to_result_schema(fixture_obj):
    fixture_status = fixture_obj.get("fixture", {}).get("status", {}).get("short")
    
    finished_statuses = {"FT", "AET", "PEN"}
    if fixture_status not in finished_statuses:
        return None

    fixture_details = fixture_obj.get("fixture", {})
    teams = fixture_obj.get("teams", {})
    goals = fixture_obj.get("goals", {})
    
    try:
        date_str = datetime.fromisoformat(fixture_details.get("date")).strftime('%Y-%m-%d')
    except (ValueError, TypeError):
        date_str = None

    home_goals = goals.get("home")
    away_goals = goals.get("away")

    if date_str is None or home_goals is None or away_goals is None:
        logger.warning(f"Skipping fixture {fixture_details.get('id')} due to missing critical data.")
        return None

    return {
        "date": date_str,
        "home_team": teams.get("home", {}).get("name"),
        "away_team": teams.get("away", {}).get("name"),
        "home_goals": home_goals,
        "away_goals": away_goals,
    }

def fetch_historical_results(league_id, seasons):
    if not isinstance(seasons, list):
        logger.error("Seasons parameter must be a list of years.")
        return None
        
    all_transformed_results = []
    
    for season in seasons:
        logger.info(f"Fetching data for season: {season}")
        params = {"league": league_id, "season": season}
        
        fixtures_data = _api_request("fixtures", params)
        
        if fixtures_data is None:
            logger.warning(f"Failed to fetch data for season {season}. Skipping.")
            continue
            
        for fixture in fixtures_data:
            transformed_result = _transform_fixture_to_result_schema(fixture)
            if transformed_result:
                all_transformed_results.append(transformed_result)
                
    if not all_transformed_results:
        logger.warning("No historical results could be fetched or transformed.")
        return None
    
    all_transformed_results.sort(key=lambda x: x['date'])
    logger.info(f"Successfully fetched and transformed {len(all_transformed_results)} results across {len(seasons)} seasons.")
    return all_transformed_results

# --- Elo Calculation Logic (Unaltered) ---

def calculate_elo_ratings(matches):
    elo_ratings = {}
    
    for match in matches:
        home_team = match["home_team"]
        away_team = match["away_team"]

        if home_team not in elo_ratings: elo_ratings[home_team] = INITIAL_ELO
        if away_team not in elo_ratings: elo_ratings[away_team] = INITIAL_ELO
        
        home_elo_before = elo_ratings[home_team]
        away_elo_before = elo_ratings[away_team]
        
        match["home_team_elo_before"] = home_elo_before
        match["away_team_elo_before"] = away_elo_before

        elo_diff = (away_elo_before - (home_elo_before + HOME_ADVANTAGE)) / 400
        expected_home = 1 / (1 + 10**elo_diff)
        expected_away = 1 - expected_home

        if match["home_goals"] > match["away_goals"]: actual_home, actual_away = 1.0, 0.0
        elif match["home_goals"] < match["away_goals"]: actual_home, actual_away = 0.0, 1.0
        else: actual_home, actual_away = 0.5, 0.5
            
        match["outcome"] = "H" if actual_home == 1.0 else "A" if actual_away == 1.0 else "D"

        new_home_elo = home_elo_before + K_FACTOR * (actual_home - expected_home)
        new_away_elo = away_elo_before + K_FACTOR * (actual_away - expected_away)

        elo_ratings[home_team] = new_home_elo
        elo_ratings[away_team] = new_away_elo
        
        match["home_team_elo_after"] = new_home_elo
        match["away_team_elo_after"] = new_away_elo
        match["elo_change"] = new_home_elo - home_elo_before

    sorted_final_ratings = dict(sorted(elo_ratings.items(), key=lambda item: item[1], reverse=True))

    return matches, sorted_final_ratings

# --- NEW: Function to create data for CSV export ---

def create_running_elo_history_for_csv(matches_with_elo):
    """
    Transforms the detailed match list into a long format for CSV export.

    Args:
        matches_with_elo (list): The list of matches after Elo calculation.

    Returns:
        list: A list of dictionaries, where each dict is a row for the CSV.
    """
    running_history = []
    for match in matches_with_elo:
        # Row for the home team
        running_history.append({
            "date": match["date"],
            "team": match["home_team"],
            "elo_rating": round(match["home_team_elo_after"], 2)
        })
        # Row for the away team
        running_history.append({
            "date": match["date"],
            "team": match["away_team"],
            "elo_rating": round(match["away_team_elo_after"], 2)
        })
    return running_history

# --- Main execution block (Updated) ---

if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    
    LEAGUE_ID_TO_TEST = 197 # Super League Greece
    SEASONS_TO_TEST = [2024, 2023, 2022, 2021, 2020]

    logger.info(f"CLI: Fetching historical results for League {LEAGUE_ID_TO_TEST} for seasons: {SEASONS_TO_TEST}")

    results_data = fetch_historical_results(
        league_id=LEAGUE_ID_TO_TEST,
        seasons=SEASONS_TO_TEST
    )

    if results_data:
        logger.info("Calculating running Elo scores for all historical matches...")
        results_with_elo, final_elo_rankings = calculate_elo_ratings(results_data)
        logger.info("Elo calculation complete.")

        output_dir = "exports"
        os.makedirs(output_dir, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        history_filename = f"{output_dir}/slg_results_with_elo_{timestamp}.json"
        rankings_filename = f"{output_dir}/slg_final_elo_rankings_{timestamp}.json"
        # NEW: CSV filename
        csv_filename = f"{output_dir}/slg_running_elo_history_{timestamp}.csv"
        
        try:
            with open(history_filename, 'w', encoding='utf-8') as f:
                json.dump(results_with_elo, f, indent=4, ensure_ascii=False)
            logger.info(f"Successfully saved detailed history to {history_filename}")

            with open(rankings_filename, 'w', encoding='utf-8') as f:
                json.dump(final_elo_rankings, f, indent=4, ensure_ascii=False)
            logger.info(f"Successfully saved final Elo rankings to {rankings_filename}")

            # --- NEW: CSV Export Logic ---
            logger.info("Generating and saving running Elo history to CSV...")
            running_elo_data = create_running_elo_history_for_csv(results_with_elo)
            
            # Define the headers for the CSV file
            csv_headers = ["date", "team", "elo_rating"]
            
            with open(csv_filename, 'w', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=csv_headers)
                writer.writeheader()
                writer.writerows(running_elo_data)
            logger.info(f"Successfully saved running Elo history to {csv_filename}")
            # --- End of new logic ---

        except IOError as e:
            logger.error(f"Failed to write to file: {e}")
    else:
        logger.error("Failed to fetch any historical results. No output files were generated.")