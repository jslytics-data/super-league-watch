cd super-league-watch
pip install -r requirements.txt

python -m src.api_providers.live_score_api.fetch_live_scores
python -m src.api_providers.live_score_api.fetch_fixtures
python -m src.api_providers.live_score_api.fetch_results
python -m src.discover_current_round_id
python -m src.fetch_and_consolidate_round_data
python -m src.analyse_round_state
python -m src.manage_firestore_state
python -m src.schedule_next_run

python -m src.distribute_to_reddit
