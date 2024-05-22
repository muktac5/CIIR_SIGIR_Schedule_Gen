# CIIR_SIGIR_Schedule_Gen
A schedule generation application for SIGIR'23 conference

=================================================================

Steps to run this application:
Note: Replace the GPT_Key and Mongo_URI in the "config.py" file.


docker-compose build

docker-compose up

These commands will result in a streamlit application.

=================================================================

Application:

Input: {
        "user_id": user_id,  # DBLP user id
        "conference_id": conference_id,# from MongoDB database
        "attendee's_start_date":start_date,
        "attendee's_end_date":end_date
       }

Output: {
          Tailored schedule,
          Most Relevant Tech session Information
        }

