import os
import logging
from datetime import datetime
from google.cloud import tasks_v2
from google.protobuf import timestamp_pb2
from google.api_core import exceptions as google_exceptions

logger = logging.getLogger(__name__)

def schedule_next_run(execution_timestamp, target_url, round_id=None):
    project_id = os.getenv("GCP_PROJECT_ID")
    queue_id = os.getenv("GCP_TASKS_QUEUE_ID")
    location = os.getenv("GCP_LOCATION")
    api_key = os.getenv("INTERNAL_API_KEY")

    if not all([project_id, queue_id, location, api_key, target_url]):
        logger.error("Missing required configuration for Cloud Tasks.")
        return False

    client = tasks_v2.CloudTasksClient()
    queue_path = client.queue_path(project_id, location, queue_id)
    
    task_name = None
    full_task_name = None
    if round_id:
        safe_round_id = "".join(c for c in round_id if c.isalnum())
        task_name = f"round-{safe_round_id}"
        full_task_name = client.task_path(project_id, location, queue_id, task_name)

    # --- NEW: Delete existing task first to prevent race conditions ---
    if full_task_name:
        try:
            client.delete_task(name=full_task_name)
            logger.info(f"Successfully deleted existing task: {task_name}")
        except google_exceptions.NotFound:
            logger.info(f"No existing task named '{task_name}' to delete. Proceeding to create.")
        except Exception as e:
            logger.error(f"Error deleting task '{task_name}': {e}")
            return False # Halt on unexpected deletion errors
    # --- END NEW LOGIC ---

    if not execution_timestamp:
        logger.info("No execution timestamp provided. No new task will be scheduled.")
        return True

    task = {
        "http_request": {
            "http_method": tasks_v2.HttpMethod.POST,
            "url": target_url,
            "headers": {"Content-Type": "application/json", "X-API-Key": api_key},
        }
    }
    
    timestamp = timestamp_pb2.Timestamp()
    timestamp.FromDatetime(execution_timestamp)
    task["schedule_time"] = timestamp

    if full_task_name:
        task["name"] = full_task_name

    try:
        logger.info(f"Scheduling task '{task_name or 'unnamed'}' to run at {execution_timestamp.isoformat()}")
        response = client.create_task(parent=queue_path, task=task)
        logger.info(f"Successfully created task: {response.name}")
        return True
    except google_exceptions.AlreadyExists:
        # This is now a fallback, but the delete should prevent it.
        logger.warning("Task already exists, likely due to a race condition. The previous run should handle it.")
        return True 
    except Exception as e:
        logger.error(f"Failed to create Cloud Task: {e}")
        return False

if __name__ == "__main__":
    from dotenv import load_dotenv
    from datetime import timedelta, timezone
    load_dotenv()
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

    if not all([os.getenv("GCP_PROJECT_ID"), os.getenv("GCP_TASKS_QUEUE_ID"), os.getenv("GCP_LOCATION")]):
        logger.critical("GCP environment variables not set. Aborting CLI test.")
    else:
        logger.info("--- Cloud Tasks Scheduler CLI Test ---")
        TEST_URL = "https://example.com"
        future_time = datetime.now(timezone.utc) + timedelta(minutes=5)
        success = schedule_next_run(future_time, TEST_URL, round_id="cli-test-round")
        if success:
            logger.info(f"CLI Test successful.")
        else:
            logger.error("CLI Test failed.")