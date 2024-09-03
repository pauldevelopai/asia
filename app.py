import streamlit as st
import requests
from bs4 import BeautifulSoup
from openai import OpenAI
from dotenv import load_dotenv
import os
import logging  # Import the logging module
from sqlalchemy import create_engine, Column, Integer, String, Text, ForeignKey, DateTime
from sqlalchemy.orm import declarative_base, sessionmaker, relationship
from datetime import datetime
from pydub import AudioSegment
import io
import tempfile

# Set up logging
logging.basicConfig(level=logging.DEBUG)

# Load environment variables from .env file
load_dotenv()

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

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

# Function to fetch available voices from Eleven Labs
def fetch_available_voices():
    url = 'https://api.elevenlabs.io/v1/voices'
    headers = {
        'xi-api-key': ELEVEN_LABS_API_KEY
    }
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        voices = response.json().get('voices', [])
        return {voice['name']: voice['voice_id'] for voice in voices}
    else:
        st.error(f"Failed to fetch voices: {response.status_code} - {response.text}")
        return {}

# Fetch available voices
available_voices = fetch_available_voices()

# Streamlit UI
st.title("Burn It Down Podcast Generator")

# Input for podcast information
name = st.text_input("Podcast Name", value="Burn It Down")
description = st.text_area("Podcast Description", value="about how technology and AI is changing our world, for good and bad.")
host1 = st.text_input("Host 1", value="Amina Ahmed")
host1_voice = st.selectbox("Voice for Host 1", options=list(available_voices.keys()))
host2 = st.text_input("Host 2", value="Will Adams")
host2_voice = st.selectbox("Voice for Host 2", options=list(available_voices.keys()))
host3 = st.text_input("Host 3", value="Khaya Dlanga")
host3_voice = st.selectbox("Voice for Host 3", options=list(available_voices.keys()))
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
    current_date = datetime.now()
    prompt = f"""Create a podcast script for the show called "{name}". The show is about {description}. Do not put emotions of speakers in brackets. Be sure to mention "{current_date.strftime('%B %d, %Y')}" but in a casual way. Always have the person's name before someone speaks. {hosts[0]} will introduce co-host {hosts[1]} and the main topic they want to talk about. {hosts[0]} is occasionally excited but is generally positive about the world and {hosts[1]} will be logical, but can be negative. At the very start {hosts[0]} and {hosts[1]} chat together in a friendly way and relate the day's stories to their own lives. They won't ask each other directly how the other one is feeling. In every script they have a different emotion and personal anecdote and a different reason for feeling that. They do not talk about the weather. They are joined by {hosts[2]} who will introduce himself and explain that he will make a prediction of what will happen next in each story over the following week, his prediction is usually negative as he believes we should burn the world down and start again. {hosts[0]}, {hosts[1]}, and {hosts[2]} need to all speak like they have known each other for years. Discuss the following. This is just the first segment, end the segment promising more in the next segment.

    Research Content:
    {research_content}
    """

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
def generate_audio(script, voices):
    lines = script.split('\n')
    audio_segments = []

    for i, line in enumerate(lines):
        if ':' in line:
            name, text = line.split(':', 1)
            name = name.strip()
            text = text.strip()

            if name in voices:
                voice_id = voices[name]
            else:
                continue

            url = f'https://api.elevenlabs.io/v1/text-to-speech/{voice_id}'
            headers = {
                'accept': 'audio/mpeg',
                'xi-api-key': ELEVEN_LABS_API_KEY,
                'Content-Type': 'application/json'
            }
            data = {
                'text': text,
                'voice_settings': {
                    'voice_id': voice_id,
                    'stability': 0.75,
                    'similarity_boost': 0.75
                }
            }

            response = requests.post(url, headers=headers, json=data)

            if response.status_code == 200:
                audio_segment = AudioSegment.from_file(io.BytesIO(response.content), format="mp3")
                audio_segments.append(audio_segment)
            else:
                st.error(f"Failed to create audio for line {i+1}: {response.status_code} - {response.text}")

    if audio_segments:
        combined_audio = sum(audio_segments)
        with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as temp_file:
            combined_audio.export(temp_file.name, format="mp3")
            return temp_file.name
    else:
        return None

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

            # Display the generated script in an editable text area
            st.session_state.script_content = st.text_area("Generated Script", value=script_content, height=300)

            # Save the script in the database
            saved_script = save_script_in_db(name, description, [host1, host2, host3], script_content, research_url)
            st.success("Podcast script generated and saved successfully!")
        else:
            st.error("Failed to fetch or generate content.")
    else:
        st.error("Please fill out the required fields.")

# Button to generate audio from the script
if "script_content" in st.session_state:
    if st.button("Generate Audio"):
        script_content = st.session_state.script_content  # Retrieve script content from session state
        voices = {
            host1: available_voices[host1_voice],
            host2: available_voices[host2_voice],
            host3: available_voices[host3_voice]
        }
        audio_file_path = generate_audio(script_content, voices)
        if audio_file_path:
            st.audio(audio_file_path, format="audio/mp3")
            with open(audio_file_path, "rb") as file:
                st.download_button(label="Download Audio", data=file, file_name="podcast_audio.mp3")