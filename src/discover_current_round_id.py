import os
import logging
from datetime import datetime, timedelta, timezone

from .api_providers.live_score_api.fetch_fixtures import fetch_fixtures_from_api

logger = logging.getLogger(__name__)

def discover_current_round_id(competition_id, lookahead_days=30, lang=None):
    logger.info(f"Discovering current round ID for competition {competition_id} by searching day-by-day.")
    
    today = datetime.now(timezone.utc)
    
    for i in range(lookahead_days):
        check_date = today + timedelta(days=i)
        date_str = check_date.strftime("%Y-%m-%d")
        
        logger.info(f"Checking for fixtures on {date_str}...")
        daily_fixtures = fetch_fixtures_from_api(
            competition_id=competition_id, 
            date=date_str, 
            lang=lang
        )

        if daily_fixtures is None:
            logger.error(f"API call to fetch fixtures failed for date {date_str}. Aborting discovery.")
            return None
        
        if not daily_fixtures:
            continue

        logger.info(f"Found {len(daily_fixtures)} fixture(s) on {date_str}. Determining round ID.")

        min_round = float('inf')
        for fixture in daily_fixtures:
            try:
                round_val = fixture.get('round')
                if round_val:
                    min_round = min(min_round, int(round_val))
            except (ValueError, TypeError):
                continue

        if min_round != float('inf'):
            logger.info(f"Successfully discovered current round ID: {min_round}")
            return str(min_round)
        else:
            logger.warning(f"Fixtures found on {date_str}, but could not determine a round ID. Continuing search.")

    logger.warning(f"No upcoming fixtures with a valid round ID found for competition {competition_id} in the next {lookahead_days} days.")
    return None

if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

    COMPETITION_ID_TO_TEST = 9
    
    round_id = discover_current_round_id(competition_id=COMPETITION_ID_TO_TEST)

    if round_id:
        print(f"CLI Test Success: Discovered current round ID -> {round_id}")
        logger.info(f"Discovered current round ID: {round_id}")
    else:
        print("CLI Test Info: Could not discover a current round ID (end of season or recent API error).")
        logger.warning("Could not discover a current round ID.")