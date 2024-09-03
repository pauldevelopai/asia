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

# Function to fetch the actual article URL from a news link
def fetch_actual_article_url(news_url):
    try:
        response = requests.get(news_url)
        soup = BeautifulSoup(response.content, 'html.parser')
        link_tag = soup.find('a', href=True)
        if link_tag:
            actual_url = link_tag['href']
            return actual_url
        else:
            logging.error("Failed to find the actual article link.")
            return None
    except Exception as e:
        logging.error(f"Failed to fetch actual article URL: {e}")
        return None

# Function to scrape news using NewsAPI
def scrape_news(keywords):
    api_key = "a5e5898731c74bfe97bae546ef04dea6"
    url = f"https://newsapi.org/v2/everything?q={keywords}&apiKey={api_key}"
    response = requests.get(url)
    if response.status_code == 200:
        articles = response.json().get('articles', [])
        stories = []
        for article in articles:
            title = article.get('title')
            link = article.get('url')
            pub_date = article.get('publishedAt')
            if title and link and pub_date:
                stories.append({
                    'title': title,
                    'actual_link': link,
                    'pub_date': pub_date
                })
        return stories
    else:
        st.error(f"Failed to fetch news: {response.status_code} - {response.text}")
        return []

# Fetch available voices
available_voices = fetch_available_voices()

# Streamlit UI
st.title("Develop AI Podcast Generator")

# Input for podcast information
name = st.text_input("Podcast Name", value="Burn It Down")
description = st.text_area("Podcast Description", value="about how technology and AI is changing our world, for good and bad.")
host1 = st.text_input("Host 1", value="Amina Ahmed")
host1_voice = st.selectbox("Voice for Host 1", options=list(available_voices.keys()))
host2 = st.text_input("Host 2", value="Will Adams")
host2_voice = st.selectbox("Voice for Host 2", options=list(available_voices.keys()))
host3 = st.text_input("Host 3", value="Khaya Dlanga")
host3_voice = st.selectbox("Voice for Host 3", options=list(available_voices.keys()))

# Input for host personalities
host1_personality = st.text_area("Personality for Host 1", value="occasionally excited but generally positive about the world")
host2_personality = st.text_area("Personality for Host 2", value="logical, but can be negative")
host3_personality = st.text_area("Personality for Host 3", value="believes we should burn the world down and start again")

# Input for news keywords
keywords = st.text_input("News Keywords", value="tech and media and AI")

# Scrape button
if st.button("Scrape News"):
    stories = scrape_news(keywords)
    st.session_state.stories = stories  # Store stories in session state
    if stories:
        st.success("Scraped news successfully!")
    else:
        st.error("No stories found. Please try different keywords.")

# Function to fetch content from URL
def fetch_content_from_url(url):
    try:
        response = requests.get(url)
        response.raise_for_status()  # Raise an HTTPError for bad responses
        soup = BeautifulSoup(response.content, 'html.parser')
        paragraphs = soup.find_all('p')
        content = "\n".join([para.get_text() for para in paragraphs])
        if not content:
            logging.error("No content found in the fetched URL.")
            st.error("No content found in the fetched URL.")
        return content
    except requests.RequestException as e:
        logging.error(f"Failed to fetch research content: {e}")
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
def generate_podcast_script(name, description, hosts, personalities, facts):
    current_date = datetime.now()
    prompt = f"""Create a podcast script for the show called "{name}". The show is about {description}. Do not put emotions of speakers in brackets. Be sure to mention "{current_date.strftime('%B %d, %Y')}" but in a casual way. Always have the person's name before someone speaks. {hosts[0]} will introduce co-host {hosts[1]} and the main topic they want to talk about. {personalities[0]}. {hosts[1]} will be logical, but can be negative. At the very start {hosts[0]} and {hosts[1]} chat together in a friendly way and relate the day's stories to their own lives. They won't ask each other directly how the other one is feeling. In every script they have a different emotion and personal anecdote and a different reason for feeling that. They do not talk about the weather. They are joined by {hosts[2]} who will introduce himself and explain that he will make a prediction of what will happen next in each story over the following week, his prediction is usually negative as he believes we should burn the world down and start again. {hosts[0]}, {hosts[1]}, and {hosts[2]} need to all speak like they have known each other for years. Discuss the following. This is just the first segment, end the segment promising more in the next segment.

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

# Function to save the script in the database
def save_script_in_db(podcast_name, description, hosts, script_content, research_url, audio_file_path=None):
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

    # Read audio file as binary if available
    audio_data = None
    if audio_file_path:
        with open(audio_file_path, "rb") as file:
            audio_data = file.read()

    # Create and save script
    new_script = Script(
        podcast_id=new_podcast.id,
        content=script_content,
        research_url=research_url,
        audio=audio_data  # Save audio data if available
    )
    session.add(new_script)
    session.commit()

    return new_script

# Function to generate audio using Eleven Labs API
def generate_audio(script, voices, intro_clip=None, outro_clip=None):
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

            # Debugging statements
            logging.debug(f"Request data: {data}")
            logging.debug(f"Response status code: {response.status_code}")
            logging.debug(f"Response content: {response.content}")

            if response.status_code == 200:
                audio_segment = AudioSegment.from_file(io.BytesIO(response.content), format="mp3")
                audio_segments.append(audio_segment)
            else:
                st.error(f"Failed to create audio for line {i+1}: {response.status_code} - {response.text}")

    if audio_segments:
        combined_audio = sum(audio_segments)
        
        # Add intro and outro clips if provided
        if intro_clip:
            combined_audio = AudioSegment.from_file(intro_clip) + combined_audio
        if outro_clip:
            combined_audio = combined_audio + AudioSegment.from_file(outro_clip)
        
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

# Display scraped stories in a dropdown menu
if "stories" in st.session_state:
    story_options = {f"{story['title']} - {story['actual_link']}": story['actual_link'] for story in st.session_state.stories}
    selected_story = st.selectbox("Select a story", options=list(story_options.keys()))

    # Button to use the selected story
    if st.button("Use Selected Story"):
        actual_article_url = story_options[selected_story]
        st.session_state.research_url = actual_article_url  # Store the actual article URL in session state
        st.success(f"Selected story: {selected_story}")
        st.write(f"Research URL: {actual_article_url}")

# Input for research URL
st.write("Please copy and paste the actual article URL into the field below if it was not fetched automatically.")
research_url = st.text_input("Research URL", value=st.session_state.get("research_url", ""))

# Upload boxes for intro and outro music clips
intro_clip = st.file_uploader("Upload Intro Music Clip", type=["mp3"])
outro_clip = st.file_uploader("Upload Outro Music Clip", type=["mp3"])

# Button to generate podcast script
if st.button("Generate Podcast Script", key="generate_script"):
    if name and description:
        if research_url:
            st.write(f"Using research URL: {research_url}")  # Log the research URL
            if research_url != st.session_state.get("research_url"):
                research_content = fetch_content_from_url(research_url)
                if research_content:
                    facts = extract_facts_from_content(research_content)
                    st.session_state.facts = facts  # Store facts in session state
                else:
                    st.error("Failed to fetch or generate content.")
                    facts = None
            else:
                facts = st.session_state.get("facts")

            if facts:
                # Ensure all 20 facts are used
                facts_list = facts.split('\n')
                if len(facts_list) == 20:
                    script_content = generate_podcast_script(name, description, [host1, host2, host3], [host1_personality, host2_personality, host3_personality], facts)
                    st.session_state.script_content = script_content  # Store script content in session state

                    # Display the generated script in an editable text area
                    st.text_area("Generated Script", value=script_content, height=300, key="generated_script")

                    # Display the extracted facts in the sidebar
                    st.sidebar.header("Extracted Facts")
                    st.sidebar.text_area("Facts", value=facts, height=300, key="extracted_facts")

                    # Generate audio
                    voices = {
                        host1: available_voices[host1_voice],
                        host2: available_voices[host2_voice],
                        host3: available_voices[host3_voice]
                    }
                    audio_file_path = generate_audio(script_content, voices, intro_clip, outro_clip)
                    if audio_file_path:
                        # Save the script and audio in the database
                        saved_script = save_script_in_db(name, description, [host1, host2, host3], script_content, research_url, audio_file_path)
                        st.success("Podcast script and audio generated and saved successfully!")
                    else:
                        # Save the script in the database without audio
                        saved_script = save_script_in_db(name, description, [host1, host2, host3], script_content, research_url)
                        st.success("Podcast script generated and saved successfully!")
                else:
                    st.error("Failed to extract 20 facts. Please try again.")
            else:
                st.error("Failed to fetch or generate content.")
        else:
            st.error("Research URL is empty. Please select a story first.")
    else:
        st.error("Please fill out the required fields.")

# Button to generate audio from the script
if "script_content" in st.session_state:
    st.text_area("Generated Script", value=st.session_state.script_content, height=300, key="generated_script_display")
    if "facts" in st.session_state:
        st.sidebar.text_area("Facts", value=st.session_state.facts, height=300, key="extracted_facts_display")
    if st.button("Generate Audio"):
        script_content = st.session_state.script_content  # Retrieve script content from session state
        voices = {
            host1: available_voices[host1_voice],
            host2: available_voices[host2_voice],
            host3: available_voices[host3_voice]
        }
        audio_file_path = generate_audio(script_content, voices, intro_clip, outro_clip)
        if audio_file_path:
            st.audio(audio_file_path, format="audio/mp3")
            with open(audio_file_path, "rb") as file:
                st.download_button(label="Download Audio", data=file, file_name="podcast_audio.mp3")
        else:
            st.warning("No audio data available for the generated script.")

# Display imported audio if available
if "audio_data" in st.session_state:
    if st.session_state.audio_data is not None:
        st.audio(io.BytesIO(st.session_state.audio_data), format="audio/mp3")
        st.download_button(label="Download Imported Audio", data=st.session_state.audio_data, file_name="imported_podcast_audio.mp3")
    else:
        if st.button("Play Imported Audio"):
            st.warning("No audio data available for the imported script.")