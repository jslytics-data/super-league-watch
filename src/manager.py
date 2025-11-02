import os
import logging
from datetime import datetime, timedelta, timezone

from . import discover_current_round_id
from . import fetch_and_consolidate_round_data
from . import analyze_round_state
from . import manage_firestore_state
from . import schedule_next_run
from . import distribute_to_reddit

logger = logging.getLogger(__name__)

LEAGUE_NAME = "superleague_greece"
SEASON_ID = "season_2024_2025"
LEAGUE_COMPETITION_ID = 9
HOURS_BEFORE_KICKOFF_TO_POST = 1

def run_orchestration_logic():
    logger.info("--- Starting Orchestration Logic ---")
    
    pointer_data = manage_firestore_state.get_current_round_pointer()
    
    if not pointer_data or pointer_data.get("document_path") == "completed":
        logger.warning("No active round pointer found. Attempting to discover a new round.")
        current_round_id = discover_current_round_id.discover_current_round_id(LEAGUE_COMPETITION_ID)

        if not current_round_id:
            logger.warning("Discovery failed. Likely end of season. Scheduling check for tomorrow.")
            next_run = datetime.now(timezone.utc) + timedelta(days=1)
            target_url = os.getenv("CLOUD_RUN_SERVICE_URL")
            schedule_next_run.schedule_next_run(next_run, target_url)
            return True

        doc_path = f"leagues/{LEAGUE_NAME}/seasons/{SEASON_ID}/rounds/{current_round_id}"
        if not manage_firestore_state.set_current_round_pointer(doc_path, current_round_id):
            return False # Halt
        
        pointer_data = manage_firestore_state.get_current_round_pointer()
        if not pointer_data:
            logger.error("Failed to retrieve newly created pointer.")
            return False # Halt

    current_round_id = pointer_data.get("round_id")
    round_doc_path = pointer_data.get("document_path")
    reddit_post_id = pointer_data.get("reddit_post_id")
    reddit_post_finalized = pointer_data.get("reddit_post_finalized", False)
    
    if not current_round_id or not round_doc_path:
        logger.error("Pointer document is corrupt. Halting.")
        return False # Halt

    logger.info(f"Processing Round: {current_round_id}. Reddit Post ID: {reddit_post_id}")

    new_round_data = fetch_and_consolidate_round_data.fetch_and_consolidate_round_data(
        competition_id=LEAGUE_COMPETITION_ID,
        round_id=current_round_id
    )
    if not new_round_data:
        return False # Halt

    analysis = analyze_round_state.analyze_round_state(new_round_data)
    if not analysis:
        return False # Halt
        
    round_state = analysis.get("round_state")
    next_run_timestamp_iso = analysis.get("next_run_timestamp")

    if not manage_firestore_state.set_round_data(round_doc_path, new_round_data):
        return False # Halt

    # --- Reddit Logic Decision Tree ---
    post_creation_states = ["not_started", "in_play", "partially_completed"]
    if not reddit_post_id and round_state in post_creation_states:
        
        should_create = False
        if round_state == "not_started":
            if next_run_timestamp_iso:
                first_kickoff = datetime.fromisoformat(next_run_timestamp_iso)
                if first_kickoff - datetime.now(timezone.utc) <= timedelta(hours=HOURS_BEFORE_KICKOFF_TO_POST):
                    logger.info("First match is soon. Time to create Reddit post.")
                    should_create = True
        else: # If in_play or partially_completed and no post exists, create it immediately.
            logger.info(f"Round is active ('{round_state}') but no post exists. Creating one now.")
            should_create = True

        if should_create:
            new_post_id = distribute_to_reddit.create_or_get_post(new_round_data)
            if new_post_id:
                if not manage_firestore_state.update_pointer_with_reddit_details(post_id=new_post_id):
                    return False # Halt
                reddit_post_id = new_post_id
    
    elif reddit_post_id and round_state == "in_play":
        logger.info("Round is in play. Updating Reddit post with live scores.")
        distribute_to_reddit.update_post(reddit_post_id, new_round_data)

    elif reddit_post_id and round_state == "completed" and not reddit_post_finalized:
        logger.info("Round is complete. Performing final update on Reddit post.")
        distribute_to_reddit.update_post(reddit_post_id, new_round_data)
        if not manage_firestore_state.update_pointer_with_reddit_details(is_finalized=True):
            return False # Halt

    if round_state == "completed":
        logger.info(f"Round {current_round_id} is complete. Marking pointer to trigger discovery on next run.")
        if not manage_firestore_state.set_current_round_pointer("completed", current_round_id):
             return False # Halt

    target_url = os.getenv("CLOUD_RUN_SERVICE_URL")
    if not target_url:
        logger.error("CLOUD_RUN_SERVICE_URL not set. Cannot schedule next run.")
        return False # Halt

    next_run_dt = datetime.fromisoformat(next_run_timestamp_iso) if next_run_timestamp_iso else None
    
    if not schedule_next_run.schedule_next_run(next_run_dt, target_url):
        return False # Halt

    logger.info("--- Orchestration Logic Completed Successfully ---")
    return True