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
        logger.error("Missing required configuration for Cloud Tasks (project, queue, location, key, url).")
        return False

    try:
        client = tasks_v2.CloudTasksClient()
        queue_path = client.queue_path(project_id, location, queue_id)
        
        task = {
            "http_request": {
                "http_method": tasks_v2.HttpMethod.POST,
                "url": target_url,
                "headers": {
                    "Content-Type": "application/json",
                    "X-API-Key": api_key
                },
            }
        }

        if execution_timestamp:
            timestamp = timestamp_pb2.Timestamp()
            timestamp.FromDatetime(execution_timestamp)
            task["schedule_time"] = timestamp
            
            if round_id:
                safe_round_id = "".join(c for c in round_id if c.isalnum())
                # This name is predictable and unique per round
                task_name = f"round-{safe_round_id}"
                full_task_name = client.task_path(project_id, location, queue_id, task_name)
                task["name"] = full_task_name
                logger.info(f"Scheduling task '{task_name}' to run at {execution_timestamp.isoformat()}")
            else:
                logger.info(f"Scheduling unnamed task to run at {execution_timestamp.isoformat()}")

        else:
            logger.info("Scheduling task to run immediately.")

        response = client.create_task(parent=queue_path, task=task)
        logger.info(f"Successfully created task: {response.name}")
        return True

    except google_exceptions.AlreadyExists:
        logger.info("Task with this name already exists in the queue. Skipping creation.")
        return True # This is a success condition for our logic
    except Exception as e:
        logger.error(f"Failed to create Cloud Task: {e}")
        return False

if __name__ == "__main__":
    # ... (no changes to the __main__ block)
    from dotenv import load_dotenv
    from datetime import timedelta, timezone
    load_dotenv()
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

    if not all([os.getenv("GCP_PROJECT_ID"), os.getenv("GCP_TASKS_QUEUE_ID"), os.getenv("GCP_LOCATION")]):
        logger.critical("GCP_PROJECT_ID, GCP_TASKS_QUEUE_ID, or GCP_LOCATION not set in .env. Aborting CLI test.")
    else:
        logger.info("--- Cloud Tasks Scheduler CLI Test ---")
        TEST_URL = "https://example.com"
        future_time = datetime.now(timezone.utc) + timedelta(minutes=5)
        success = schedule_next_run(future_time, TEST_URL, round_id="cli-test-round")
        if success:
            logger.info(f"CLI Test successful. Task created to call {TEST_URL} at {future_time.isoformat()}")
        else:
            logger.error("CLI Test failed. Check logs for details.")