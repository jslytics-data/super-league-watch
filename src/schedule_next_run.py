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

    # If a round is completed, there's no timestamp and nothing to schedule.
    if not execution_timestamp:
        logger.info("No execution timestamp provided. No new task will be scheduled.")
        return True

    client = tasks_v2.CloudTasksClient()
    queue_path = client.queue_path(project_id, location, queue_id)

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

    task_name_for_logs = "unnamed"
    if round_id:
        safe_round_id = "".join(c for c in str(round_id) if c.isalnum())
        time_window_str = execution_timestamp.strftime('%Y%m%d-%H%M')
        
        task_name = f"round-{safe_round_id}-minute-{time_window_str}"
        full_task_name = client.task_path(project_id, location, queue_id, task_name)
        task["name"] = full_task_name
        task_name_for_logs = task_name

    try:
        logger.info(f"Attempting to schedule task '{task_name_for_logs}' to run at {execution_timestamp.isoformat()}")
        response = client.create_task(parent=queue_path, task=task)
        logger.info(f"Successfully created task: {response.name}")
        return True
    except google_exceptions.AlreadyExists:
        logger.info(f"Task '{task_name_for_logs}' already exists for this time window. Skipping creation.")
        return True # This is a success condition, as another instance already scheduled it.
    except Exception as e:
        logger.error(f"A critical error occurred creating the task: {e}")
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
        
        # Test with a round_id to simulate the new naming convention
        success = schedule_next_run(future_time, TEST_URL, round_id="cli-test-round")
        
        if success:
            logger.info(f"CLI Test successful.")
        else:
            logger.error("CLI Test failed.")