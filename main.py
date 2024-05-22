import os
import pymongo
import config
from bson import ObjectId
import numpy as np
from datetime import datetime
import requests
from sklearn.metrics.pairwise import cosine_similarity


def get_mongo_client(mongo_uri):
    try:
        client = pymongo.MongoClient(mongo_uri, appname="devrel.content.python")
        print("Connection to MongoDB successful")
        return client
    except pymongo.errors.ConnectionFailure as e:
        print(f"Connection failed: {e}")
        return None


def similarity_fun(all_session_embedding_pairs, user_pub_embeddings):
    np_user_embedding = np.array(user_pub_embeddings)
    user_avg_embedding = np.mean(np_user_embedding, axis=0)
    similarity_scores = [
        (sess_embed_pair[0], cosine_similarity([user_avg_embedding], [sess_embed_pair[1]])[0][0])
        for sess_embed_pair in all_session_embedding_pairs
    ]
    return similarity_scores


def RAG_retrieval(user_pub_embeddings, all_session_embedding_pairs):
    similarity_scores = similarity_fun(all_session_embedding_pairs, user_pub_embeddings)
    ranked_sessions = sorted(similarity_scores, key=lambda x: x[1], reverse=True)
    seen_sessions = set()
    unique_sessions = []
    for session in ranked_sessions[:15]:
        session_name = session[0]
        if session_name not in seen_sessions:
            unique_sessions.append(session)
            seen_sessions.add(session_name)
    return unique_sessions


def call_openai_api(headers, payload):
    response = requests.post("https://api.openai.com/v1/chat/completions", headers=headers, json=payload)
    print(response.json())
    return response.json()['choices'][0]['message']['content']


def user_profile_generation(user_json):
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {os.environ['GPT_KEY']}"
    }
    system_message = "As an executive assistant to an organiser of a SIGIR conference, build a concise description of the research profile of an attendee based on all the provided details."
    user_message = f"""{user_json['name']} details are as follows: 
    1. Recent publication history: {user_json['publications']},
    2. Types of publications: {user_json['publication_types']}, 
    3. Years active in the field: {user_json['no_of_years_active']} (from {user_json['first_pub_yr']} to {user_json['latest_pub_yr']}), 
    4. Conferences attended: {user_json['conferences_attended']}
    """
    payload = {
        "model": "gpt-3.5-turbo",
        "messages": [
            {"role": "system", "content": [{"type": "text", "text": system_message}]},
            {"role": "user", "content": [{"type": "text", "text": user_message}]}
        ]
    }
    return call_openai_api(headers, payload)


def generate_schedule_prompt(user_details, tech_sessions, breaks, social_events, logistics, start_date, end_date):
    prompt = f"""Generate a tailored conference schedule based on the following attendee profile: {user_details}. They plan to attend the conference from {start_date} to {end_date}.

    Must follow steps while generating the schedule:
    1. On the first day of attendance, i.e., {start_date}, always include the "Registration and Information Desk" to allow the attendee to register and gather more information about the conference.
    2. Tailor the schedule strictly to the attendee's profile. Only include events that are directly relevant and appropriate for the attendee based on their provided profile description. Events not suitable for the attendee should be completely omitted from the schedule without mention.
    3. "RETURN ONLY THE SCHEDULE WITH THE PROGRAM'S SUITABLE TO THE USER'S PROFILE. NOTHING ELSE", for example, the schedule shouldn't have student parties for an established researcher.
    4. List each event with its corresponding time, name, and location. Use the following format for each day:
        ```
        Date
        Time: Event, Location
        Time: Event, Location
        :
        :
        ```
    5. Do not add any events that are not explicitly mentioned in the provided program details. The schedule should reflect only the events available in the program details passed to you.
    6. Include detailed descriptions of technical sessions of the grouped programs by day as specified in the provided program details, especially the technical sessions and their corresponding descriptions:
        """


    prompt += "Sessions (in decreasing order of relevance with the attendee's past publications):\n"
    for session in tech_sessions:
        description = f" whose description is {session['description']}" if "description" in session else ""
        prompt += f"- {session['name']}{description} on {session['date']} at {session['time']}, located at {session['location']}\n"

    prompt += "\nDaily coffee and lunch break slots are as follows:\n"
    for break_event in breaks:
        start_time, end_time = break_event['date_time'].split(" ")[0].split("-")
        date = break_event['date_time'].split(" ")[1]
        prompt += f"- {break_event['name']} from {start_time} to {end_time} on {date} at {break_event['room']}\n"

    prompt += "\nChoose ONLY the relevant social events based on the attendee's research profile from the following set of social events at the conference:\n"
    for event in social_events:
        prompt += f"- {event['name']} on {event['date']} at {event['time']} located at {event['room']}\n"

    prompt += "\nEvery attendee must register themselves on the first day of their attendance. The registration slot is as follows: \n"
    prompt += f"- {logistics['name']} on {logistics['date']} at {logistics['time']} located at {logistics['room']}\n"

    return prompt


def convert_date(date_str):
    return datetime.strptime(date_str, "%B %d")

def format_sessions(sessions):
    from collections import defaultdict

    # Group sessions by date
    sessions_by_date = defaultdict(list)
    for session in sessions:
        sessions_by_date[session['date']].append(session)

    # Sort sessions by date
    sorted_dates = sorted(sessions_by_date.keys())

    # Format the grouped sessions
    formatted_output = ""
    for date in sorted_dates:
        formatted_output += f"**{date}**\n"
        for session in sessions_by_date[date]:
            formatted_output += (
                f"- **{session['name']}**\n"
                f"  - **Time**: {session['time']}\n"
                f"  - **Location**: {session['location']}\n"
                f"  - **Description**: {session['description']}\n\n"
            )

    return formatted_output

def initialize_db(mongo_client, user_id, conference_instance_id, start_date, end_date):
    db = mongo_client['CIIR']
    user_c = db['User']
    publication_c = db['Publication']
    session_c = db['Session_Instance']
    conference_c = db['Conference_Instance']

    user_json = {}
    tech_sessions = []
    user = user_c.find_one({'_id': user_id})
    conference_instance = conference_c.find_one({'_id': ObjectId(conference_instance_id)})
    sessions = conference_instance['session_instances']
    sessions_l = []
    all_session_embedding_pairs = []
    breaks = []
    social_events = []
    logistics = []

    for session_id in sessions:
        session = session_c.find_one({'_id': session_id})
        sessions_l.append(session)
        session['time'] = session['date_time'].split(" ")[0]
        session['date'] = session['date_time'].split(session['time'])[1].lstrip()
        start_date_dt = convert_date(start_date)
        end_date_dt = convert_date(end_date)
        date_to_check_dt = convert_date(session['date'])

        if start_date_dt <= date_to_check_dt <= end_date_dt:
            if session['category'] == "session":
                session['topics_discussed'] = []
                if 'publications' in session:
                    for pub_id in session['publications']:
                        pub = publication_c.find_one({'_id': pub_id})
                        session['topics_discussed'].append(pub['title'])
                        all_session_embedding_pairs.append((session_id, pub['embeddings']))
            elif session['category'] == "break":
                breaks.append(session)
            elif session['category'] == "social event":
                social_events.append(session)
            elif session['category'] == "registration & information":
                logistics.append(session)

    transformed_sessions = {session['_id']: session for session in sessions_l if session}

    user_pub_embeddings = []
    user_publications = []
    for pub_id in user['Publications']:
        pub = publication_c.find_one({'_id': pub_id})
        user_pub_embeddings.append(pub['embeddings'])
        user_publications.append(pub['title'])

    years = [int(s) for s in user['Years Active']]
    user_json.update({
        'name': user['Name'],
        'publications': user_publications,
        'no_of_years_active': len(years),
        'first_pub_yr': min(years),
        'latest_pub_yr': max(years),
        'conferences_attended': user['Conferences_attended'],
        'publication_types': user['Publication_types']
    })

    relevant_sessions = RAG_retrieval(user_pub_embeddings, all_session_embedding_pairs)
    for relevant_session in relevant_sessions:
        session_info = transformed_sessions.get(relevant_session[0])
        if session_info:
            session_json = {
                'name': session_info['name'],
                'description': session_info['description'],
                'date': session_info['date'],
                'time': session_info['time'],
                'location': session_info['room']
            }
            tech_sessions.append(session_json)
        else:
            print(f"No session found with ObjectId: {relevant_session[0]}")

    user_profile = user_profile_generation(user_json)
    return user['Name'], user_profile, tech_sessions, breaks, social_events, logistics


def handle_user_query(mongo_client, user_id, conference_instance_id, start_date, end_date):
    user_name, user_profile, tech_sessions, breaks, social_events, logistics = initialize_db(mongo_client, user_id,
                                                                                             conference_instance_id,
                                                                                             start_date, end_date)
    formatted_tech_sessions = format_sessions(tech_sessions[:15])
    formatted_tech_sessions = formatted_tech_sessions.replace("**", "").strip()
    #print(formatted_tech_sessions)
    system_message = """
    As the executive assistant responsible for organizing the SIGIR conference, your task is to create a tailored and feasible conference schedule for an attendee based on the user's research history and the detailed program of the event. The schedule should encompass a balanced mix of technical sessions, sufficient breaks, and engaging social events.

    Please ensure:
    - Include the "Registration and Information Desk" slot for the attendee on the start_date, as it is mandatory for attending the conference.
    - Resolve overlapping sessions by prioritizing those that align closely with the attendee's research interests.
    - Tailor social events based on the attendee's profile. For example, established researchers should not be scheduled for student parties, and vice versa. Only students can attend student parties.
    - Organize each day's schedule in chronological order without any time clashes.
    - Allocate appropriate time for breaks and social interactions to enhance networking opportunities.
    - **Include only the technical sessions retrieved by the RAG module, which are most relevant to the attendee's research interests. Do not use placeholders like "Event yet to be finalized".**
    - Present the schedule directly to the user without referring to them in the third person. Use direct and engaging language.

    The schedule should be structured as follows:
    
    Date
    Time: Event, Location
    Time: Event, Location
    :
    :
    
    Date
    Time: Event, Location
    Time: Event, Location
    :
    :
    
    For instance, if there are multiple sessions scheduled at the same time, choose the session that best matches the attendee's research focus and exclude the others from that time slot. Aim to enhance the attendee’s engagement and learning by making the schedule relevant and logistically practical.
    """

    user_message = generate_schedule_prompt(user_profile, tech_sessions, breaks, social_events, logistics[0],
                                            start_date, end_date)
    schedule = call_openai_api({
        "Content-Type": "application/json",
        "Authorization": f"Bearer {os.environ['GPT_KEY']}"
    }, {
        "model": "gpt-3.5-turbo",
        "messages": [
            {"role": "system", "content": [{"type": "text", "text": system_message}]},
            {"role": "user", "content": [{"type": "text", "text": user_message}]}
        ]
    })
    cleaned_schedule = schedule.strip("`").replace("**", "").strip()

    return user_name, cleaned_schedule, formatted_tech_sessions


if __name__ == "__main__":
    mongo_uri = config.DATABASE_URI
    mongo_client = get_mongo_client(mongo_uri)
    handle_user_query(mongo_client, "150/5324", "6611ba89fa030550ebe455e0", "July 25", "July 26")
