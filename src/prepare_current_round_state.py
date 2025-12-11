import os
import logging
import json
from datetime import datetime, timezone

from .api_providers.api_football_api.discover_current_round import discover_current_round_from_api
from .api_providers.api_football_api.fetch_fixtures import fetch_fixtures_from_api
from .team_mappings import MAPPINGS

logger = logging.getLogger(__name__)

def _transform_fixture_data(fixture_obj):
    fixture = fixture_obj.get("fixture", {})
    league = fixture_obj.get("league", {})
    teams = fixture_obj.get("teams", {})
    goals = fixture_obj.get("goals", {})
    venue = fixture.get("venue", {})
    status_short = fixture.get("status", {}).get("short")

    clean_status = "unknown"
    if status_short in {"TBD", "NS", "PST", "CANC"}:
        clean_status = "not_started"
    elif status_short == "HT":
        clean_status = "half_time"
    elif status_short in {"1H", "2H", "ET", "BT", "P", "LIVE"}:
        clean_status = "in_play"
    elif status_short in {"FT", "AET", "PEN"}:
        clean_status = "completed"

    dt_object = datetime.fromisoformat(fixture.get("date")).astimezone(timezone.utc)
    date_str = dt_object.strftime("%Y-%m-%d")
    time_str = dt_object.strftime("%H:%M")

    home_team_name = teams.get("home", {}).get("name", "N/A")
    away_team_name = teams.get("away", {}).get("name", "N/A")

    score_str = ""
    if goals.get('home') is not None and goals.get('away') is not None:
        score_str = f"{goals['home']} - {goals['away']}"

    return {
        "fixture_id": fixture.get("id"),
        "date": date_str,
        "kick_off_time_utc": time_str,
        # Team Names & Mappings
        "home_team": home_team_name,
        "away_team": away_team_name,
        "home_team_greek": MAPPINGS["team_to_greek"].get(home_team_name),
        "away_team_greek": MAPPINGS["team_to_greek"].get(away_team_name),
        "home_team_subreddit": MAPPINGS["team_to_subreddit"].get(home_team_name),
        "away_team_subreddit": MAPPINGS["team_to_subreddit"].get(away_team_name),
        # Logos
        "home_team_logo": teams.get("home", {}).get("logo"),
        "away_team_logo": teams.get("away", {}).get("logo"),
        # Match Details
        "status": clean_status,
        "score": score_str,
        "live_minute": fixture.get("status", {}).get("elapsed"),
        # Metadata
        "referee": fixture.get("referee"),  # Can be None
        "stadium": venue.get("name"),       # Can be None
        "city": venue.get("city"),          # Can be None
        # League Context (used for top-level extraction later)
        "competition_name": league.get("name", "Super League"),
        "league_logo": league.get("logo")
    }

def prepare_current_round_state(league_id, season):
    logger.info(f"Preparing current round state for league {league_id}, season {season}.")

    current_round = discover_current_round_from_api(league=league_id, season=season)
    if not current_round:
        logger.error("Could not discover current round. Halting state preparation.")
        return None

    fixtures = fetch_fixtures_from_api(
        league=league_id,
        season=season,
        round=current_round,
        timezone="UTC"
    )
    
    if fixtures is None:
        logger.error("API fetch for fixtures failed. Halting state preparation.")
        return None

    clean_matches = [_transform_fixture_data(f) for f in fixtures]
    clean_matches.sort(key=lambda x: (x.get('date', ''), x.get('kick_off_time_utc', '')))
    
    # Extract top-level metadata from the first match (safe assumption for a single round)
    competition_name = "Super League"
    league_logo = None
    
    if clean_matches:
        competition_name = clean_matches[0].get('competition_name', competition_name)
        league_logo = clean_matches[0].get('league_logo')

    final_data_structure = {
        "round_id": current_round,
        "competition_name": competition_name,
        "league_logo": league_logo,
        "matches": clean_matches,
        "last_updated_utc": datetime.now(timezone.utc).isoformat()
    }
    
    logger.info(f"Successfully prepared state for {len(clean_matches)} matches in round '{current_round}'.")
    return final_data_structure

if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

    LEAGUE_ID_TO_TEST = os.getenv("API_FOOTBALL_LEAGUE_ID")
    SEASON_TO_TEST = os.getenv("API_FOOTBALL_SEASON")

    if not LEAGUE_ID_TO_TEST or not SEASON_TO_TEST:
        logger.critical("API_FOOTBALL_LEAGUE_ID and/or API_FOOTBALL_SEASON not set in .env file. Aborting test.")
    else:
        logger.info("CLI Test: Preparing current round state...")
        prepared_data = prepare_current_round_state(
            league_id=LEAGUE_ID_TO_TEST,
            season=SEASON_TO_TEST
        )
        
        if prepared_data:
            output_dir = "exports"
            os.makedirs(output_dir, exist_ok=True)
            
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            current_round = prepared_data.get("round_id", "unknown_round")
            safe_round = "".join(c for c in current_round if c.isalnum())
            filename = f"{output_dir}/prepared_round_state_{safe_round}_{timestamp}.json"
            
            try:
                with open(filename, 'w', encoding='utf-8') as f:
                    json.dump(prepared_data, f, indent=4, ensure_ascii=False)
                logger.info(f"Successfully saved prepared state data to {filename}")
            except IOError as e:
                logger.error(f"Failed to write to file {filename}: {e}")
        else:
            logger.error("Failed to prepare current round state.")