import os
import logging
from datetime import datetime
from google.cloud import tasks_v2
from google.protobuf import timestamp_pb2

logger = logging.getLogger(__name__)

def schedule_next_run(execution_timestamp, target_url):
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
            logger.info(f"Scheduling task to run at {execution_timestamp.isoformat()}")
        else:
            logger.info("Scheduling task to run immediately.")

        response = client.create_task(parent=queue_path, task=task)
        logger.info(f"Successfully created task: {response.name}")
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
        logger.critical("GCP_PROJECT_ID, GCP_TASKS_QUEUE_ID, or GCP_LOCATION not set in .env. Aborting CLI test.")
    else:
        logger.info("--- Cloud Tasks Scheduler CLI Test ---")
        
        # For this test, we'll schedule a task to a public mock endpoint.
        # This proves task creation works without needing a deployed service.
        TEST_URL = "https://example.com"
        
        # Schedule a task to run 5 minutes from now
        future_time = datetime.now(timezone.utc) + timedelta(minutes=5)
        
        success = schedule_next_run(future_time, TEST_URL)
        
        if success:
            logger.info(f"CLI Test successful. Task created to call {TEST_URL} at {future_time.isoformat()}")
        else:
            logger.error("CLI Test failed. Check logs for details.")