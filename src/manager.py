import os
import logging
from datetime import datetime, timedelta, timezone

from . import discover_current_round_id
from . import fetch_and_consolidate_round_data
from . import analyze_round_state
from . import manage_firestore_state
from . import schedule_next_run

logger = logging.getLogger(__name__)

LEAGUE_NAME = "bundesliga"
SEASON_ID = "season_2024_2025"
LEAGUE_COMPETITION_ID = 1 

def run_orchestration_logic():
    logger.info("--- Starting Orchestration Logic ---")
    
    # Step 1: Determine the current round ID
    pointer_data = manage_firestore_state.get_current_round_pointer()
    if not pointer_data:
        logger.warning("No round pointer found. Attempting to discover a new round.")
        current_round_id = discover_current_round_id.discover_current_round_id(LEAGUE_COMPETITION_ID)

        if not current_round_id:
            logger.warning("Discovery failed to find a new round. Likely end of season.")
            # Schedule a check for tomorrow
            target_url = os.getenv("CLOUD_RUN_SERVICE_URL")
            next_run = datetime.now(timezone.utc) + timedelta(days=1)
            schedule_next_run.schedule_next_run(next_run, target_url)
            return True

        doc_path = f"leagues/{LEAGUE_NAME}/seasons/{SEASON_ID}/rounds/{current_round_id}"
        if not manage_firestore_state.set_current_round_pointer(doc_path, current_round_id):
            logger.error("Failed to set the new round pointer in Firestore.")
            return False
    else:
        current_round_id = pointer_data.get("round_id")
        if not current_round_id:
            logger.error("Pointer document is corrupt or missing 'round_id'.")
            return False

    logger.info(f"Successfully identified current round: {current_round_id}")

    # Step 2: Fetch and consolidate the latest data for this round
    consolidated_data = fetch_and_consolidate_round_data.fetch_and_consolidate_round_data(
        competition_id=LEAGUE_COMPETITION_ID,
        round_id=current_round_id
    )
    if not consolidated_data:
        logger.error("Failed to fetch and consolidate round data. Halting.")
        return False

    # Step 3: Analyze the consolidated data
    analysis = analyze_round_state.analyze_round_state(consolidated_data)
    if not analysis:
        logger.error("Failed to analyze round state. Halting.")
        return False
        
    round_state = analysis.get("round_state")
    next_run_timestamp_iso = analysis.get("next_run_timestamp")

    # Step 4: Persist the new state to Firestore
    round_doc_path = f"leagues/{LEAGUE_NAME}/seasons/{SEASON_ID}/rounds/{current_round_id}"
    if not manage_firestore_state.set_round_data(round_doc_path, consolidated_data):
        logger.error("Failed to write updated round data to Firestore. Halting.")
        return False

    # Step 5: If the round is now complete, clear the pointer for next run's discovery
    if round_state == "completed":
        logger.info(f"Round {current_round_id} is complete. Clearing pointer to trigger discovery on next run.")
        if not manage_firestore_state.set_current_round_pointer("completed", current_round_id):
             logger.error("Failed to update round pointer to 'completed' state.")
             return False

    # Step 6: Schedule the next run
    target_url = os.getenv("CLOUD_RUN_SERVICE_URL")
    if not target_url:
        logger.error("CLOUD_RUN_SERVICE_URL environment variable is not set. Cannot schedule next run.")
        return False

    next_run_dt = datetime.fromisoformat(next_run_timestamp_iso) if next_run_timestamp_iso else None
    
    if not schedule_next_run.schedule_next_run(next_run_dt, target_url):
        logger.error("Failed to schedule the next run via Cloud Tasks. Halting.")
        return False

    logger.info("--- Orchestration Logic Completed Successfully ---")
    return True