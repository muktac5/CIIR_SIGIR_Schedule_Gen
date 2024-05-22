import streamlit as st
import requests
import json

# Streamlit page configuration
st.set_page_config(page_title="SIGIR Conference Schedule", layout="wide")

# Title for the app
st.title("SIGIR Conference Scheduler")

# Form for user input
with st.form("schedule_form"):
    user_id = st.text_input("User ID", help="Enter your unique User ID.")
    conference_id = st.text_input("Conference ID", help="Enter the conference ID (default is SIGIR).")
    start_date = st.text_input("Start Date", help="Enter the start date (e.g., 'July 25').")
    end_date = st.text_input("End Date", help="Enter the end date (e.g., 'July 26').")
    submit_button = st.form_submit_button("Retrieve Schedule")

if submit_button:
    # API endpoint
    api_url = "http://flask:5000/schedule"
    # Prepare parameters for the GET request
    params = {
        "user_id": user_id,
        "conference_id": conference_id,
        "start_date": start_date,
        "end_date": end_date
    }
    try:
        response = requests.get(api_url, params=params)
        response.raise_for_status()  # Raise an error for bad status codes
        schedule_data = response.json()  # Use response.json() to parse JSON data
        user_name = schedule_data["user_name"]
        schedule = schedule_data["schedule"]
        relevant_tech_sessions = schedule_data["RAG_tech_sessions_date_wise"]
        st.subheader(f"{user_name}'s Tailored Schedule")
        st.text_area("", schedule, height=600)

        st.subheader(f"Tech session's most relevant for {user_name}[In decreasing order of relevance]:")
        st.text_area("", relevant_tech_sessions, height=600)
    except requests.exceptions.RequestException as e:
        st.error(f"Failed to retrieve schedule. Error: {e}")
    except json.JSONDecodeError:
        st.error("Failed to parse the response. Please check the server response format.")
    except KeyError:
        st.error("Unexpected response format. Some data might be missing.")
