import os
import logging
import json
from datetime import datetime, timezone
from google.cloud import firestore
from google.cloud.firestore_v1.base_document import DocumentSnapshot

from dotenv import load_dotenv
load_dotenv()

logger = logging.getLogger(__name__)

db = firestore.Client(
    project=os.getenv("GCP_PROJECT_ID"),
    database=os.getenv("FIRESTORE_DATABASE_ID")
)

POINTER_COLLECTION = "system_state"
POINTER_DOCUMENT = "current_round_pointer"
LEAGUE_COLLECTION = "leagues"

def get_current_round_pointer():
    try:
        doc_ref = db.collection(POINTER_COLLECTION).document(POINTER_DOCUMENT)
        doc = doc_ref.get()
        if doc.exists:
            logger.info(f"Successfully retrieved current round pointer.")
            return doc.to_dict()
        else:
            logger.warning("Current round pointer document does not exist.")
            return None
    except Exception as e:
        logger.error(f"Failed to get current round pointer from Firestore: {e}")
        return None

def set_current_round_pointer(document_path, round_id):
    try:
        doc_ref = db.collection(POINTER_COLLECTION).document(POINTER_DOCUMENT)
        doc_ref.set({
            "document_path": document_path,
            "round_id": round_id,
            "reddit_post_id": None,
            "reddit_post_finalized": False,
            "last_updated_utc": datetime.now(timezone.utc).isoformat()
        })
        logger.info(f"Successfully set/reset current round pointer for path: {document_path}")
        return True
    except Exception as e:
        logger.error(f"Failed to set current round pointer in Firestore: {e}")
        return False

def update_pointer_with_reddit_details(post_id=None, is_finalized=None):
    update_data = {"last_updated_utc": datetime.now(timezone.utc).isoformat()}
    log_messages = []

    if post_id is not None:
        update_data["reddit_post_id"] = post_id
        log_messages.append(f"reddit_post_id={post_id}")

    if is_finalized is not None:
        update_data["reddit_post_finalized"] = is_finalized
        log_messages.append(f"reddit_post_finalized={is_finalized}")

    if not log_messages:
        logger.warning("update_pointer_with_reddit_details called without any data to update.")
        return True

    try:
        doc_ref = db.collection(POINTER_COLLECTION).document(POINTER_DOCUMENT)
        doc_ref.update(update_data)
        logger.info(f"Successfully updated pointer with: {', '.join(log_messages)}")
        return True
    except Exception as e:
        logger.error(f"Failed to update pointer with Reddit details: {e}")
        return False

def get_round_data_by_path(document_path):
    try:
        doc_ref = db.document(document_path)
        doc = doc_ref.get()
        if doc.exists:
            logger.info(f"Successfully retrieved data for document: {document_path}")
            return doc.to_dict()
        else:
            logger.warning(f"Document does not exist at path: {document_path}")
            return None
    except Exception as e:
        logger.error(f"Failed to get document from Firestore at path {document_path}: {e}")
        return None

def set_round_data(document_path, data):
    try:
        doc_ref = db.document(document_path)
        doc_ref.set(data)
        logger.info(f"Successfully set data for document: {document_path}")
        return True
    except Exception as e:
        logger.error(f"Failed to set document in Firestore at path {document_path}: {e}")
        return False

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

    if not os.getenv("GCP_PROJECT_ID"):
        logger.critical("GCP_PROJECT_ID environment variable not set. Aborting test.")
    elif not os.getenv("FIRESTORE_DATABASE_ID"):
        logger.critical("FIRESTORE_DATABASE_ID environment variable not set. Aborting test.")
    else:
        logger.info("--- Firestore Manager CLI Test ---")
        
        TEST_LEAGUE = "superleague_greece_test"
        TEST_SEASON = "season_2024_2025_test"
        
        EXPORT_DIR = "exports"
        latest_file_path = None
        try:
            files = [f for f in os.listdir(EXPORT_DIR) if f.startswith("consolidated_round_") and f.endswith(".json")]
            files.sort(key=lambda f: os.path.getmtime(os.path.join(EXPORT_DIR, f)), reverse=True)
            if files:
                latest_file_path = os.path.join(EXPORT_DIR, files[0])
        except FileNotFoundError:
            logger.warning(f"Export directory '{EXPORT_DIR}' not found. Cannot test set_round_data.")

        if not latest_file_path:
            logger.warning("No consolidated data file found. Test will be partial.")
            test_round_data = None
            test_round_id = "test_round_cli"
        else:
            logger.info(f"Using latest consolidated file for test: {latest_file_path}")
            with open(latest_file_path, 'r', encoding='utf-8') as f:
                test_round_data = json.load(f)
            test_round_id = test_round_data.get("round_id", "unknown_round")

        test_doc_path = f"{LEAGUE_COLLECTION}/{TEST_LEAGUE}/seasons/{TEST_SEASON}/rounds/{test_round_id}"

        if test_round_data:
            logger.info(f"\n1. Attempting to WRITE round data to: {test_doc_path}")
            if set_round_data(test_doc_path, test_round_data): logger.info("WRITE successful.")
            else: logger.error("WRITE failed.")
        
        logger.info(f"\n2. Attempting to READ round data from: {test_doc_path}")
        retrieved_data = get_round_data_by_path(test_doc_path)
        if retrieved_data: logger.info("READ successful.")
        else: logger.error("READ failed.")

        logger.info(f"\n3. Attempting to SET/RESET pointer to: {test_doc_path}")
        if set_current_round_pointer(test_doc_path, test_round_id): logger.info("Pointer SET successful.")
        else: logger.error("Pointer SET failed.")
            
        logger.info(f"\n4. Attempting to READ pointer.")
        retrieved_pointer = get_current_round_pointer()
        if retrieved_pointer: logger.info(f"Pointer READ successful: {retrieved_pointer}")
        else: logger.error("Pointer READ failed.")
        
        logger.info(f"\n5. Attempting to UPDATE pointer with Reddit Post ID.")
        if update_pointer_with_reddit_details(post_id="t3_test123"): logger.info("Pointer UPDATE successful.")
        else: logger.error("Pointer UPDATE failed.")

        logger.info(f"\n6. Attempting to READ pointer again to verify update.")
        retrieved_pointer = get_current_round_pointer()
        if retrieved_pointer and retrieved_pointer.get("reddit_post_id") == "t3_test123":
            logger.info(f"Pointer READ successful and ID is correct: {retrieved_pointer}")
        else:
            logger.error(f"Pointer READ failed or ID was incorrect: {retrieved_pointer}")

        logger.info("\n--- CLI Test Complete ---")