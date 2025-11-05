import os
import logging
from datetime import datetime, timedelta, timezone

from . import prepare_current_round_state
from . import analyze_round_state
from . import manage_firestore_state
from . import schedule_next_run
from . import distribute_to_reddit

logger = logging.getLogger(__name__)

LEAGUE_ID = os.getenv("API_FOOTBALL_LEAGUE_ID")
SEASON = os.getenv("API_FOOTBALL_SEASON")
HOURS_BEFORE_KICKOFF_TO_POST = 1

def run_orchestration_logic():
    logger.info("--- Starting Orchestration Logic ---")
    
    if not LEAGUE_ID or not SEASON:
        logger.critical("API_FOOTBALL_LEAGUE_ID and/or API_FOOTBALL_SEASON not set. Halting.")
        return False

    # Step 1: Always get the latest state from the API
    new_round_data = prepare_current_round_state.prepare_current_round_state(
        league_id=LEAGUE_ID,
        season=SEASON
    )
    if not new_round_data:
        logger.warning("Failed to prepare new round state. Possibly end of season. Scheduling check for tomorrow.")
        next_run = datetime.now(timezone.utc) + timedelta(days=1)
        target_url = os.getenv("CLOUD_RUN_SERVICE_URL")
        schedule_next_run.schedule_next_run(next_run, target_url) # No round_id needed
        return True

    current_round_id = new_round_data.get("round_id")
    round_doc_path = f"leagues/{LEAGUE_ID}/seasons/{SEASON}/rounds/{current_round_id}"

    # Step 2: Check our system's memory (Firestore)
    pointer_data = manage_firestore_state.get_current_round_pointer()

    # Step 3: If the round has changed, reset our system's memory
    if not pointer_data or pointer_data.get("round_id") != current_round_id:
        logger.info(f"New round detected ({current_round_id}). Resetting pointer.")
        if not manage_firestore_state.set_current_round_pointer(round_doc_path, current_round_id):
            return False
        pointer_data = {"round_id": current_round_id, "reddit_post_id": None, "reddit_post_finalized": False}

    # Step 4: Run the analysis and update data
    analysis = analyze_round_state.analyze_round_state(new_round_data)
    if not analysis: return False
    
    if not manage_firestore_state.set_round_data(round_doc_path, new_round_data): return False

    # Step 5: Execute Reddit logic based on current state and memory
    round_state = analysis.get("round_state")
    reddit_post_id = pointer_data.get("reddit_post_id")
    reddit_post_finalized = pointer_data.get("reddit_post_finalized", False)

    logger.info(f"Processing Round: {current_round_id}. State: {round_state}. Reddit Post ID: {reddit_post_id}")

    if not reddit_post_id and round_state in ["not_started", "in_play", "partially_completed"]:
        should_create = (round_state != "not_started") or (
            analysis.get("next_run_timestamp") and
            datetime.fromisoformat(analysis["next_run_timestamp"]) - datetime.now(timezone.utc) <= timedelta(hours=HOURS_BEFORE_KICKOFF_TO_POST)
        )
        if should_create:
            logger.info(f"Conditions met to create Reddit post.")
            new_post_id = distribute_to_reddit.create_or_get_post(new_round_data)
            if not new_post_id: return False
            if not manage_firestore_state.update_pointer_with_reddit_details(post_id=new_post_id): return False
            reddit_post_id = new_post_id
    
    elif reddit_post_id and round_state == "in_play":
        logger.info("Round is in play. Updating Reddit post.")
        if not distribute_to_reddit.update_post(reddit_post_id, new_round_data): return False

    elif reddit_post_id and round_state == "completed" and not reddit_post_finalized:
        logger.info("Round is complete. Performing final update on Reddit post.")
        if not distribute_to_reddit.update_post(reddit_post_id, new_round_data): return False
        if not manage_firestore_state.update_pointer_with_reddit_details(is_finalized=True): return False

    if round_state == "completed":
        logger.info(f"Round {current_round_id} is complete. Marking pointer for discovery on next run.")
        if not manage_firestore_state.set_current_round_pointer("completed", current_round_id): return False

    # Step 6: Schedule the next run
    target_url = os.getenv("CLOUD_RUN_SERVICE_URL")
    if not target_url:
        logger.error("CLOUD_RUN_SERVICE_URL not set.")
        return False

    next_run_dt = datetime.fromisoformat(analysis["next_run_timestamp"]) if analysis.get("next_run_timestamp") else None
    
    if not schedule_next_run.schedule_next_run(next_run_dt, target_url, round_id=current_round_id): 
        return False

    logger.info("--- Orchestration Logic Completed Successfully ---")
    return True