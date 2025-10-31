import os
import logging
import json
from datetime import datetime, timedelta, timezone

from .api_providers.live_score_api.fetch_fixtures import fetch_fixtures_from_api
from .api_providers.live_score_api.fetch_live_scores import fetch_live_scores_from_api
from .api_providers.live_score_api.fetch_results import fetch_results_from_api

logger = logging.getLogger(__name__)

def _transform_match_data(merged_match):
    raw_status = merged_match.get('status', 'SCHEDULED').upper()
    
    clean_status = "not_started"
    if raw_status in {"IN PLAY", "HALF TIME BREAK", "ADDED TIME", "LIVE"}:
        clean_status = "in_play"
    elif raw_status == "FINISHED":
        clean_status = "completed"

    return {
        "fixture_id": merged_match.get('id') or merged_match.get('fixture_id'),
        "date": merged_match.get('date'),
        "kick_off_time_utc": merged_match.get('time') if raw_status != 'SCHEDULED' else merged_match.get('time', '').split(':00')[0],
        "home_team": (merged_match.get('home') or {}).get('name', 'N/A'),
        "away_team": (merged_match.get('away') or {}).get('name', 'N/A'),
        "status": clean_status,
        "score": (merged_match.get('scores') or {}).get('score', '').strip(),
        "live_minute": merged_match.get('time', '') if clean_status == "in_play" else None
    }

def fetch_and_consolidate_round_data(competition_id, round_id, lang=None):
    logger.info(f"Consolidating data for competition {competition_id}, round {round_id}.")

    fixtures = fetch_fixtures_from_api(competition_id=competition_id, round=round_id, lang=lang)
    live_scores = fetch_live_scores_from_api(competition_id=competition_id, lang=lang)
    
    today = datetime.now(timezone.utc)
    from_date = (today - timedelta(days=7)).strftime("%Y-%m-%d")
    to_date = (today + timedelta(days=7)).strftime("%Y-%m-%d")
    results = fetch_results_from_api(competition_id=competition_id, from_date=from_date, to_date=to_date, lang=lang)

    if fixtures is None or live_scores is None or results is None:
        logger.error("One or more required API fetches failed. Cannot consolidate round data.")
        return None

    merged_matches = {}

    for fixture in fixtures:
        fixture_id = fixture.get("id")
        if fixture_id:
            merged_matches[str(fixture_id)] = fixture
    logger.info(f"Processed {len(fixtures)} matches from the fixtures list as baseline.")

    for live_match in live_scores:
        fixture_id = live_match.get("fixture_id")
        if not fixture_id:
            continue
        
        key = str(fixture_id)
        if key in merged_matches:
            merged_matches[key].update(live_match)
            logger.info(f"Updated match {key} with live data.")
        else:
            merged_matches[key] = live_match
            logger.info(f"Added new match {key} found only in the live feed.")

    for result_match in results:
        fixture_id = result_match.get("fixture_id")
        result_round = result_match.get("round")
        if not fixture_id or str(result_round) != str(round_id):
            continue

        key = str(fixture_id)
        if key in merged_matches:
            merged_matches[key].update(result_match)
            logger.info(f"Updated match {key} with result data.")
        else:
            merged_matches[key] = result_match
            logger.info(f"Added new match {key} found only in the results feed.")

    clean_matches = [_transform_match_data(m) for m in merged_matches.values()]
    clean_matches.sort(key=lambda x: (x.get('date', ''), x.get('kick_off_time_utc', '')))
    
    final_data_structure = {
        "round_id": round_id,
        "matches": clean_matches,
        "last_updated_utc": datetime.now(timezone.utc).isoformat()
    }
    
    logger.info(f"Successfully consolidated data for {len(clean_matches)} total matches in round {round_id}.")
    return final_data_structure

if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

    COMPETITION_ID_TO_TEST = 9
    ROUND_ID_TO_TEST = "9" 

    consolidated_data = fetch_and_consolidate_round_data(
        competition_id=COMPETITION_ID_TO_TEST,
        round_id=ROUND_ID_TO_TEST
    )
    
    if consolidated_data:
        output_dir = "exports"
        os.makedirs(output_dir, exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{output_dir}/consolidated_round_{ROUND_ID_TO_TEST}_{timestamp}.json"
        
        try:
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(consolidated_data, f, indent=4)
            logger.info(f"Successfully saved consolidated data for round {ROUND_ID_TO_TEST} to {filename}")
        except IOError as e:
            logger.error(f"Failed to write to file {filename}: {e}")
    else:
        logger.error(f"Failed to fetch and consolidate data for round {ROUND_ID_TO_TEST}.")