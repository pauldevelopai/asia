import streamlit as st
import requests
from bs4 import BeautifulSoup
from openai import OpenAI
from dotenv import load_dotenv
import os
import logging  # Import the logging module
from sqlalchemy import create_engine, Column, Integer, String, Text, ForeignKey, DateTime, LargeBinary
from sqlalchemy.orm import declarative_base, sessionmaker, relationship
from datetime import datetime, timedelta
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
    audio = Column(LargeBinary)  # Add this line to store audio as BLOB
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

# Input for Google News keywords
keywords = st.text_input("Google News Keywords", value="tech and media and AI")

# Function to scrape Google News
def scrape_google_news(keywords):
    query = "+".join(keywords.split())
    google_news_url_today = f"https://news.google.com/rss/search?q={query}%20when:1d&hl=en-US&gl=US&ceid=US:en"
    google_news_url_yesterday = f"https://news.google.com/rss/search?q={query}%20when:2d-1d&hl=en-US&gl=US&ceid=US:en"

    # Get the current date and time
    current_date = datetime.utcnow()

    # Subtract one day from the current date to get yesterday's date
    yesterday_date = current_date - timedelta(days=1)

    # Send the request to Google News for today's news
    google_news_response_today = requests.get(google_news_url_today)

    # Parse the response from Google News
    google_news_data_today = BeautifulSoup(google_news_response_today.text, "lxml")

    # Extract the stories from Google News that were published today
    google_news_stories_today = []
    for story in google_news_data_today.find_all("item"):
        pub_date = story.find("pubDate")
        if pub_date and datetime.strptime(pub_date.text, "%a, %d %b %Y %H:%M:%S %Z").date() == current_date.date():
            google_news_stories_today.append({
                'title': story.title.text,
                'date': pub_date.text,
                'description': story.description.text,
                'link': story.link.text
            })

    # Send the request to Google News for yesterday's news
    google_news_response_yesterday = requests.get(google_news_url_yesterday)

    # Parse the response from Google News
    google_news_data_yesterday = BeautifulSoup(google_news_response_yesterday.text, "lxml")

    # Extract the stories from Google News that were published yesterday
    google_news_stories_yesterday = []
    for story in google_news_data_yesterday.find_all("item"):
        pub_date = story.find("pubDate")
        if pub_date and datetime.strptime(pub_date.text, "%a, %d %b %Y %H:%M:%S %Z").date() == yesterday_date.date():
            google_news_stories_yesterday.append({
                'title': story.title.text,
                'date': pub_date.text,
                'description': story.description.text,
                'link': story.link.text
            })

    # Combine today's and yesterday's stories
    all_stories = google_news_stories_today + google_news_stories_yesterday

    # Extract the top 8 stories
    top_stories = all_stories[:8]

    return top_stories

# Scrape button
if st.button("Scrape Google News"):
    stories = scrape_google_news(keywords)
    st.session_state.stories = stories  # Store stories in session state
    if stories:
        st.success("Scraped Google News successfully!")
    else:
        st.error("No stories found. Please try different keywords.")

# Display scraped stories in a dropdown menu
if "stories" in st.session_state:
    story_options = {story['title']: story['link'] for story in st.session_state.stories}
    selected_story = st.selectbox("Select a story", options=list(story_options.keys()))

    # Button to use the selected story
    if st.button("Use Selected Story"):
        research_url = story_options[selected_story]
        st.session_state.research_url = research_url
        st.success(f"Selected story: {selected_story}")

# Function to fetch research content
def fetch_content_from_url(url):
    try:
        response = requests.get(url)
        soup = BeautifulSoup(response.content, 'html.parser')
        return soup.get_text()
    except requests.RequestException as e:
        st.error(f"Failed to fetch research content: {e}")
        return ""

# Function to extract 20 facts from content using OpenAI
def extract_facts_from_content(content):
    prompt = f"Extract 20 interesting facts from the following content:\n\n{content}"
    response = client.chat.completions.create(
        model="gpt-4",
        messages=[
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": prompt}
        ]
    )

    return response.choices[0].message.content.strip()

# Function to generate podcast script using OpenAI
def generate_podcast_script(name, description, hosts, facts):
    current_date = datetime.now()
    prompt = f"""Create a podcast script for the show called "{name}". The show is about {description}. Do not put emotions of speakers in brackets. Be sure to mention "{current_date.strftime('%B %d, %Y')}" but in a casual way. Always have the person's name before someone speaks. {hosts[0]} will introduce co-host {hosts[1]} and the main topic they want to talk about. {hosts[0]} is occasionally excited but is generally positive about the world and {hosts[1]} will be logical, but can be negative. At the very start {hosts[0]} and {hosts[1]} chat together in a friendly way and relate the day's stories to their own lives. They won't ask each other directly how the other one is feeling. In every script they have a different emotion and personal anecdote and a different reason for feeling that. They do not talk about the weather. They are joined by {hosts[2]} who will introduce himself and explain that he will make a prediction of what will happen next in each story over the following week, his prediction is usually negative as he believes we should burn the world down and start again. {hosts[0]}, {hosts[1]}, and {hosts[2]} need to all speak like they have known each other for years. Discuss the following. This is just the first segment, end the segment promising more in the next segment.

    Facts:
    {facts}
    """

    response = client.chat.completions.create(
        model="gpt-4",
        messages=[
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": prompt}
        ]
    )

    return response.choices[0].message.content.strip()

def save_script_in_db(podcast_name, description, hosts, script_content, research_url, audio_file_path):
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

    # Read audio file as binary
    with open(audio_file_path, "rb") as file:
        audio_data = file.read()

    # Create and save script
    new_script = Script(
        podcast_id=new_podcast.id,
        content=script_content,
        research_url=research_url,
        audio=audio_data  # Save audio data
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
        st.session_state.audio_data = selected_script.audio  # Store audio data in session state
        st.success("Script imported successfully!")
        st.write(selected_script.content)
    else:
        st.error("Failed to import script.")

# Button to generate podcast script
if st.button("Generate Podcast Script", key="generate_script"):
    if name and description:
        research_content = fetch_content_from_url(research_url)
        if research_content:
            facts = extract_facts_from_content(research_content)
            st.session_state.facts = facts  # Store facts in session state
            script_content = generate_podcast_script(name, description, [host1, host2, host3], facts)
            st.session_state.script_content = script_content  # Store script content in session state

            # Display the generated script in an editable text area
            st.session_state.script_content = st.text_area("Generated Script", value=script_content, height=300)

            # Display the extracted facts in the sidebar
            st.sidebar.header("Extracted Facts")
            st.sidebar.text_area("Facts", value=facts, height=300)

            # Generate audio
            voices = {
                host1: available_voices[host1_voice],
                host2: available_voices[host2_voice],
                host3: available_voices[host3_voice]
            }
            audio_file_path = generate_audio(script_content, voices)
            if audio_file_path:
                # Save the script and audio in the database
                saved_script = save_script_in_db(name, description, [host1, host2, host3], script_content, research_url, audio_file_path)
                st.success("Podcast script and audio generated and saved successfully!")
        else:
            st.error("Failed to fetch or generate content.")
    else:
        st.error("Please fill out the required fields.")

# Button to generate audio from the script
if "script_content" in st.session_state:
    st.text_area("Generated Script", value=st.session_state.script_content, height=300)
    if "facts" in st.session_state:
        st.sidebar.text_area("Facts", value=st.session_state.facts, height=300)
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

# Display imported audio if available
if "audio_data" in st.session_state and st.session_state.audio_data is not None:
    st.audio(io.BytesIO(st.session_state.audio_data), format="audio/mp3")
    st.download_button(label="Download Imported Audio", data=st.session_state.audio_data, file_name="imported_podcast_audio.mp3")
else:
    st.warning("No audio data available for the imported script.")