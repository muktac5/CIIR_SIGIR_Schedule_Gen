# Use an official Python runtime as a parent image
FROM python:3.9-slim

# Set the working directory in the container
WORKDIR /app

# Copy the current directory contents into the container at /app
COPY . /app

# Install any needed packages specified in requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Make port 5000 available to the world outside this container (for Flask)
EXPOSE 5000

# Make port 8501 available to the world outside this container (for Streamlit)
EXPOSE 8501

# Run the command to start both Flask and Streamlit
CMD ["sh", "-c", "python app.py & streamlit run streamlit.py"]
