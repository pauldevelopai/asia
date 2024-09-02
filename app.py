import streamlit as st
import requests
from bs4 import BeautifulSoup
from openai import OpenAI

from dotenv import load_dotenv
import os

# Load environment variables from .env file
load_dotenv()

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

from sqlalchemy import create_engine, Column, Integer, String, Text, ForeignKey, DateTime
from sqlalchemy.orm import declarative_base, sessionmaker, relationship
from datetime import datetime
from pydub import AudioSegment
import io
import tempfile

# Load environment variables
load_dotenv()

# OpenAI and Eleven Labs API keys
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
ELEVEN_LABS_API_KEY = os.getenv("ELEVEN_LABS_API_KEY")

# Set up SQLAlchemy
DATABASE_URI = f"sqlite:///podcasts.db"  # Database location
engine = create_engine(DATABASE_URI)
Base = declarative_base()
Session = sessionmaker(bind=engine)
session = Session()

# Define your models
class Podcast(Base):
    __tablename__ = 'podcast'
    id = Column(Integer, primary_key=True)
    name = Column(String(150), nullable=False)
    description = Column(Text, nullable=False)
    host1 = Column(Text)
    host2 = Column(Text)
    host3 = Column(Text)
    research = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    scripts = relationship('Script', backref='podcast', lazy=True)

class Script(Base):
    __tablename__ = 'script'
    id = Column(Integer, primary_key=True)
    podcast_id = Column(Integer, ForeignKey('podcast.id'), nullable=False)
    content = Column(Text, nullable=False)
    research_url = Column(String(255))
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

# Create the tables if they don't exist
Base.metadata.create_all(engine)

# Streamlit UI
st.title("Burn It Down Podcast Generator")

# Input for podcast information
name = st.text_input("Podcast Name", value="Burn It Down")
description = st.text_area("Podcast Description", value="about how technology and AI is changing our world, for good and bad.")
host1 = st.text_input("Host 1", value="Amina Ahmed")
host2 = st.text_input("Host 2", value="Will Adams")
host3 = st.text_input("Host 3", value="Khaya Dlanga")
research_url = st.text_input("Research URL", value="")

# Function to fetch research content
def fetch_content_from_url(url):
    try:
        response = requests.get(url)
        soup = BeautifulSoup(response.content, 'html.parser')
        return soup.get_text()
    except requests.RequestException as e:
        st.error(f"Failed to fetch research content: {e}")
        return ""

# Function to generate podcast script using OpenAI
def generate_podcast_script(name, description, hosts, research_content):
    prompt = f"""Generate a podcast script for the podcast titled '{name}' 
    hosted by {hosts[0]}, {hosts[1]}, and {hosts[2]}. 
    The podcast description is: {description}.

    Research Content:
    {research_content}

    Please generate a detailed script based on the above information."""

    response = client.chat.completions.create(model="gpt-4",
    messages=[
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": prompt}
    ])

    return response.choices[0].message.content.strip()

def save_script_in_db(podcast_name, description, hosts, script_content, research_url):
    # Create and save podcast
    new_podcast = Podcast(
        name=podcast_name,
        description=description,
        host1=hosts[0],
        host2=hosts[1],
        host3=hosts[2],
        research=research_url
    )
    session.add(new_podcast)
    session.commit()

    # Create and save script
    new_script = Script(
        podcast_id=new_podcast.id,
        content=script_content,
        research_url=research_url
    )
    session.add(new_script)
    session.commit()

    return new_script

# Function to generate audio using Eleven Labs API
def generate_audio(script):
    headers = {
        'Content-Type': 'application/json',
        'xi-api-key': ELEVEN_LABS_API_KEY
    }
    payload = {
        'text': script,
        'voice_settings': {
            'stability': 0.75,
            'similarity_boost': 0.75
        }
    }
    url = 'https://api.elevenlabs.io/v1/text-to-speech'  # Verify this URL
    response = requests.post(url, headers=headers, json=payload)
    if response.status_code != 200:
        st.error(f"Failed to create audio: {response.status_code} - {response.text}")
        st.write(response.json())  # Log the full response for debugging
        return None
    return response.content

# Function to fetch old scripts from the database
def fetch_old_scripts():
    return session.query(Script).all()

# Fetch old scripts for the dropdown menu
old_scripts = fetch_old_scripts()
script_options = {f"{script.podcast.name} - {script.created_at}": script.id for script in old_scripts}

# Dropdown menu to select an old script
selected_script_id = st.selectbox("Select an old script to import", options=list(script_options.keys()))

# Button to import the selected script
if st.button("Import Script"):
    selected_script = session.get(Script, script_options[selected_script_id])
    if selected_script:
        st.session_state.script_content = selected_script.content
        st.success("Script imported successfully!")
        st.write(selected_script.content)
    else:
        st.error("Failed to import script.")

# Button to generate podcast script
if st.button("Generate Podcast Script", key="generate_script"):
    if name and description:
        research_content = fetch_content_from_url(research_url)
        if research_content:
            script_content = generate_podcast_script(name, description, [host1, host2, host3], research_content)
            st.session_state.script_content = script_content  # Store script content in session state

            # Save the script in the database
            saved_script = save_script_in_db(name, description, [host1, host2, host3], script_content, research_url)
            st.success("Podcast script generated and saved successfully!")
            st.write(script_content)
        else:
            st.error("Failed to fetch or generate content.")
    else:
        st.error("Please fill out the required fields.")

# Button to generate audio from the script
if "script_content" in st.session_state:
    if st.button("Generate Audio"):
        script_content = st.session_state.script_content  # Retrieve script content from session state
        audio_data = generate_audio(script_content)
        if audio_data:
            with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as temp_file:
                temp_file.write(audio_data)
                st.audio(temp_file.name, format="audio/mp3")
                st.download_button(label="Download Audio", data=audio_data, file_name="podcast_audio.mp3")