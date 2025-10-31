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

from flask import Flask, request, jsonify, render_template
from dotenv import load_dotenv

from src import manager
from src.manage_firestore_state import get_current_round_pointer, get_round_data_by_path

load_dotenv()
app = Flask(__name__, template_folder='templates', static_folder='static')


@app.route("/")
def serve_homepage():
    return render_template('index.html')

@app.route("/api/get_current_round")
def get_current_round_data():
    try:
        pointer = get_current_round_pointer()
        if not pointer or not pointer.get("document_path"):
            logging.warning("API call made but no current round pointer is set.")
            return jsonify({"error": "No current round data available."}), 404

        round_data = get_round_data_by_path(pointer["document_path"])
        if not round_data:
            return jsonify({"error": "Could not retrieve round data."}), 404

        return jsonify(round_data)

    except Exception as e:
        logging.error(f"API Error fetching current round data: {e}")
        return jsonify({"error": "An internal error occurred."}), 500

@app.route("/run", methods=["POST"])
def run_main_trigger():
    auth_header = request.headers.get("X-API-Key")
    expected_key = os.getenv("INTERNAL_API_KEY")

    if not expected_key or auth_header != expected_key:
        logging.error("Unauthorized access attempt to /run endpoint.")
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