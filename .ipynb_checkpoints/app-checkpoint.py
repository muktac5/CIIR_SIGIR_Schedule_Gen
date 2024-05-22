from flask import Flask, jsonify, request, Response
import config
from main import handle_user_query, get_mongo_client

app = Flask(__name__)

# Initialize the MongoDB client once at the start
mongo_client = get_mongo_client(config.DATABASE_URI)

@app.route('/schedule', methods=['GET'])
def get_schedule():
    user_id = request.args.get('user_id')
    conference_id = request.args.get('conference_id')
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')

    if not all([user_id, conference_id, start_date, end_date]):
        return Response("Missing required query parameters", status=400)

    if not mongo_client:
        return Response("Failed to connect to the database", status=500)

    try:
        user_name, schedule_data, tech_sessions_info = handle_user_query(mongo_client, user_id, conference_id, start_date, end_date)
        data = {
            "user_name": user_name,
            "schedule": schedule_data,
            "RAG_tech_sessions_date_wise": tech_sessions_info
        }
        return jsonify(data)
    except Exception as e:
        return Response(f"An error occurred: {e}", status=500)


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
