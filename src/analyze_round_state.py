import os
import logging
import json
from datetime import datetime, timedelta, timezone

logger = logging.getLogger(__name__)

def analyze_round_state(round_data):
    if not isinstance(round_data, dict) or "matches" not in round_data:
        logger.error("Invalid input: round_data must be a dict with a 'matches' key.")
        return None
    
    matches = round_data.get("matches", [])
    if not matches:
        logger.warning("No matches found in round data to analyze.")
        return {"round_state": "completed", "next_run_timestamp": None}

    statuses = {match.get("status") for match in matches}
    
    round_state = "unknown"
    if "in_play" in statuses:
        round_state = "in_play"
    elif statuses == {"completed"}:
        round_state = "completed"
    elif statuses == {"not_started"}:
        round_state = "not_started"
    elif "completed" in statuses and "not_started" in statuses:
        round_state = "partially_completed"
    else: # Catches other combinations, like in_play and not_started
        if "not_started" in statuses or "in_play" in statuses:
             round_state = "partially_completed" # Treat as active
        else:
            logger.warning(f"Could not determine a clear round state from statuses: {statuses}")
            next_run_timestamp = datetime.now(timezone.utc) + timedelta(minutes=5)
            return {"round_state": round_state, "next_run_timestamp": next_run_timestamp.isoformat()}
    
    logger.info(f"Determined overall round state as: {round_state}")
    
    next_run_timestamp = None
    if round_state == "in_play":
        next_run_timestamp = datetime.now(timezone.utc) + timedelta(seconds=60)
    
    elif round_state in ["not_started", "partially_completed"]:
        next_match_timestamp = None
        for match in matches:
            if match.get("status") == "not_started":
                try:
                    kick_off_time = match.get('kick_off_time_utc', '')
                    match_dt_str = f"{match.get('date')}T{kick_off_time}"
                    match_dt = datetime.fromisoformat(match_dt_str).replace(tzinfo=timezone.utc)
                    
                    if next_match_timestamp is None or match_dt < next_match_timestamp:
                        next_match_timestamp = match_dt
                except (TypeError, ValueError) as e:
                    logger.warning(f"Could not parse timestamp for fixture {match.get('fixture_id')}: {e}")
                    continue
        
        if next_match_timestamp:
            # --- THIS IS THE NEW SANITY CHECK ---
            now = datetime.now(timezone.utc)
            if next_match_timestamp < now:
                logger.warning(f"Next match kickoff ({next_match_timestamp}) is in the past. API data may be lagging. Scheduling a check in 60 seconds.")
                next_run_timestamp = now + timedelta(seconds=60)
            else:
                next_run_timestamp = next_match_timestamp
            # --- END OF NEW LOGIC ---
        else: # No 'not_started' matches left, but not 'completed' yet.
            logger.info("No more upcoming matches in this round, but not all are completed. Checking again in 60s.")
            next_run_timestamp = datetime.now(timezone.utc) + timedelta(seconds=60)
            
    elif round_state == "completed":
        next_run_timestamp = None
        
    analysis = {
        "round_state": round_state,
        "next_run_timestamp": next_run_timestamp.isoformat() if next_run_timestamp else None
    }
    
    logger.info(f"Analysis complete: {analysis}")
    return analysis

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

    EXPORT_DIR = "exports"
    try:
        files = sorted(
            [f for f in os.listdir(EXPORT_DIR) if f.startswith("prepared_round_state_") and f.endswith(".json")],
            key=lambda f: os.path.getmtime(os.path.join(EXPORT_DIR, f)),
            reverse=True
        )
        
        if not files:
            logger.error(f"No 'prepared_round_state_*.json' files found in '{EXPORT_DIR}' for CLI test.")
        else:
            latest_file = os.path.join(EXPORT_DIR, files[0])
            logger.info(f"Running CLI test on latest consolidated file: {latest_file}")
            
            with open(latest_file, 'r', encoding='utf-8') as f:
                test_data = json.load(f)
            
            analysis_result = analyze_round_state(test_data)
            
            if analysis_result:
                print("\n--- Analysis Result ---")
                print(f"  Round State: {analysis_result.get('round_state')}")
                print(f"  Next Scheduled Run (UTC): {analysis_result.get('next_run_timestamp')}")
                print("-----------------------\n")
            else:
                logger.error("Analysis failed.")

    except FileNotFoundError:
        logger.error(f"Export directory '{EXPORT_DIR}' not found.")
    except Exception as e:
        logger.error(f"An error occurred during CLI test: {e}")