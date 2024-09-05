import requests
import logging
import openai
from models import session, ShowProfile, Script, Podcast  # Add Podcast to the imports
from bs4 import BeautifulSoup
from datetime import datetime
from pydub import AudioSegment
import io
import tempfile

def fetch_available_voices(ELEVEN_LABS_API_KEY):
    url = 'https://api.elevenlabs.io/v1/voices'
    headers = {
        'xi-api-key': ELEVEN_LABS_API_KEY
    }
    response = requests.get(url, headers=headers)
    logging.debug(f"Eleven Labs API response: {response.status_code} - {response.text}")
    if response.status_code == 200:
        voices = response.json().get('voices', [])
        return {voice['name']: voice['voice_id'] for voice in voices}
    else:
        return {}

def save_show_profile(name, description, host1, host1_voice, host1_personality, host2, host2_voice, host2_personality, host3, host3_voice, host3_personality):
    new_show_profile = ShowProfile(
        name=name,
        description=description,
        host1=host1,
        host1_voice=host1_voice,
        host1_personality=host1_personality,
        host2=host2,
        host2_voice=host2_voice,
        host2_personality=host2_personality,
        host3=host3,
        host3_voice=host3_voice,
        host3_personality=host3_personality
    )
    session.add(new_show_profile)
    session.commit()

def fetch_old_scripts(show_id):
    return session.query(Script).filter_by(show_id=show_id).all()

def fetch_content_from_url(url):
    try:
        response = requests.get(url)
        response.raise_for_status()  # Raise an HTTPError for bad responses
        soup = BeautifulSoup(response.content, 'html.parser')
        paragraphs = soup.find_all('p')
        content = "\n".join([para.get_text() for para in paragraphs])
        if not content:
            logging.error("No content found in the fetched URL.")
        return content
    except requests.RequestException as e:
        logging.error(f"Failed to fetch research content: {e}")
        return ""

def extract_facts_from_content(content, client):
    prompt = f"Extract 20 interesting facts from the following content:\n\n{content}"
    response = client.chat.completions.create(model="gpt-4",
    messages=[
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": prompt}
    ])
    return response.choices[0].message.content.strip()

def generate_podcast_script(name, description, hosts, personalities, facts, client):
    current_date = datetime.now()
    prompt = f"""Create a podcast script for the show called "{name}". The show is about {description}. Do not put emotions of speakers in brackets. Be sure to mention "{current_date.strftime('%B %d, %Y')}" but in a casual way. Always have the person's name before someone speaks. {hosts[0]} will introduce co-host {hosts[1]} and the main topic they want to talk about. {personalities[0]}. {hosts[1]} will be logical, but can be negative. At the very start {hosts[0]} and {hosts[1]} chat together in a friendly way and relate the day's stories to their own lives. They won't ask each other directly how the other one is feeling. In every script they have a different emotion and personal anecdote and a different reason for feeling that. They do not talk about the weather. They are joined by {hosts[2]} who will introduce himself and explain that he will make a prediction of what will happen next in each story over the following week, his prediction is usually negative as he believes we should burn the world down and start again. {hosts[0]}, {hosts[1]}, and {hosts[2]} need to all speak like they have known each other for years. Discuss the following. This is just the first segment, end the segment promising more in the next segment.

    Facts:
    {facts}
    """

    response = client.chat.completions.create(model="gpt-4",
    messages=[
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": prompt}
    ])

    return response.choices[0].message.content.strip()

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

def generate_audio(script, voices, ELEVEN_LABS_API_KEY, intro_clip=None, outro_clip=None):
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

def search_articles(api_key, query):
    url = f"https://newsapi.org/v2/everything?q={query}&apiKey={api_key}"
    response = requests.get(url)
    if response.status_code == 200:
        return response.json().get('articles', [])
    else:
        logging.error(f"Failed to fetch articles: {response.status_code} - {response.text}")
        return []