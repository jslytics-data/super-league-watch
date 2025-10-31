import os
import logging
import google.cloud.logging

# IMPORTANT: This needs to be the first thing to run to set up logging.
if "K_SERVICE" in os.environ:
    # Running in a Google Cloud environment
    client = google.cloud.logging.Client()
    client.setup_logging()
else:
    # Running locally
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )

from flask import Flask, request
from dotenv import load_dotenv

from src import manager

load_dotenv()
app = Flask(__name__)

@app.route("/run", methods=["POST"])
def run_main_trigger():
    auth_header = request.headers.get("X-API-Key")
    expected_key = os.getenv("INTERNAL_API_KEY")

    if not expected_key or auth_header != expected_key:
        logging.error("Unauthorized access attempt.")
        return "Unauthorized", 401

    logging.info("Authorized request received. Starting main logic.")
    
    success = manager.run_orchestration_logic()
    
    if success:
        logging.info("Main logic completed successfully.")
        return "OK", 200
    else:
        logging.error("Main logic execution failed.")
        return "Error", 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))