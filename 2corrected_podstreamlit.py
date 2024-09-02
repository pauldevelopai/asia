
import streamlit as st
import requests
from bs4 import BeautifulSoup
import re
from openai import OpenAI

client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"),
api_key=os.environ.get("OPENAI_API_KEY"))
import os
import tempfile
from gtts import gTTS
from pydub import AudioSegment
import io
import datetime

# --- Functions ---

def fetch_google_news(query, time_period="1d"):
    base_url = "https://news.google.com/rss/search"
    params = {
        'q': query,
        'when': time_period,
        'hl': 'en-US',
        'gl': 'US',
        'ceid': 'US:en'
    }
    response = requests.get(base_url, params=params)
    soup = BeautifulSoup(response.text, "xml")
    stories = []
    for story in soup.find_all("item"):
        stories.append({
            'title': story.title.text,
            'date': story.pubDate.text,
            'description': story.description.text,
            'link': story.link.text
        })
    return stories

def fetch_content_from_url(url):
    response = requests.get(url)
    soup = BeautifulSoup(response.text, "html.parser")
    title = soup.find("title").text
    text = soup.get_text()
    return title, text

def truncate_text(text, max_length=30000):
    text = re.sub(r'\W+', ' ', text)
    if len(text) > max_length:
        text = text[:max_length] + '...'
    return text

def extract_facts(article_text, num_facts=20):
    prompt = f"Use all the information found in the article and give me the {num_facts} most important facts:\n\n{article_text}"
    response = client.chat.completions.create(model="gpt-4",
    messages=[
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": prompt}
    ])
    facts_text = response.choices[0].message.content.strip()
    facts = [fact.strip() for fact in facts_text.split('\n') if fact.strip()]
    return facts

def generate_intro(facts, host1_name, host2_name, host3_name, podcast_name, podcast_description):
    facts_string = "\n\n".join(facts)
    current_date = datetime.datetime.utcnow()
    prompt = f'''Create a podcast script for the show called "{podcast_name}".
    The show is {podcast_description}
    Do not put emotions of speakers in brackets.
    Be sure to mention "{current_date.strftime('%B %d, %Y')}" but in a casual way.
    Always have the person's name before someone speaks.
    {host1_name} will introduce co-host {host2_name} and the main topic she wants to talk about.
    {host1_name} is occassionally excited but is generally positive about the world and {host2_name} will be logical, but can be negative.
    At the very start {host1_name} and {host2_name} chat together in a friendly way and relate the day's stories to their own lives.
    They won't ask each other directly how the other one is feeling.
    In every script they have a different emotion and personal anecdote and a different reason for feeling that.
    They do not talk about the weather.
    They are joined by {host3_name} who will introduce himself and explain that he will make a prediction of what will happen next in each story over the following week,
    his prediction is usally negative as he believes we should burn the world down and start again.
    {host1_name}, {host2_name} and {host3_name} need to all speak like they have known each other for years.
    Discuss the following: \n\n{facts_string}.
    This is just the first segment, end the segment promising more in the next segment.'''

    response = client.chat.completions.create(model="gpt-4",
    messages=[
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": prompt}
    ])
    intro_text = response.choices[0].message.content.strip()
    return intro_text

def format_script(script_text, host1_name, host2_name, host3_name):
    lines = script_text.split("\n")
    formatted_lines = []
    for line in lines:
        line = line.replace("Amina:", f"{host1_name}:")
        line = line.replace("Will:", f"{host2_name}:")
        line = line.replace("Khaya:", f"{host3_name}:")
        formatted_lines.append(line)
    return "\n".join(formatted_lines)

def generate_audio(line, voice_name):
    api_key = os.environ.get("ELEVEN_LABS_API_KEY")
    headers = {
        "Content-Type": "application/json",
        "xi-api-key": api_key
    }
    data = {
        "text": line,
        "voice_settings": {
            "stability": 0,
            "similarity_boost": 0
        }
    }
    voices_endpoint = "https://api.elevenlabs.io/v1/voices"
    response = requests.get(voices_endpoint, headers=headers)
    voices = response.json().voices
    voice_id = next((voice["voice_id"] for voice in voices if voice["name"] == voice_name), None)

    if voice_id:
        audio_endpoint = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"
        response = requests.post(audio_endpoint, headers=headers, json=data)
        if response.status_code == 200:
            return response.content
        else:
            st.error(f"Error generating audio: {response.status_code}")
            return None
    else:
        st.error(f"Voice '{voice_name}' not found.")
        return None

def normalize_audio(audio_data, target_loudness=-20):
    audio_segment = AudioSegment.from_file(io.BytesIO(audio_data), format="mp3")
    loudness_difference = target_loudness - audio_segment.dBFS
    normalized_audio = audio_segment.apply_gain(loudness_difference)
    return normalized_audio

def stitch_audio(audio_files):
    combined_audio = AudioSegment.empty()
    for audio_data in audio_files:
        normalized_audio = normalize_audio(audio_data)
        combined_audio += normalized_audio
    return combined_audio

# --- Streamlit App ---

def main():
    st.title("Burn It Down Podcast Generator")

    podcast_name = st.text_input("Enter the name of the podcast:", "Burn It Down")
    podcast_description = st.text_input("Enter a brief description of your podcast:", "about how technology and AI is changing our world, for good and bad.")
    host1_name = st.text_input("Enter the name of the first host:", "Amina Ahmed")
    host2_name = st.text_input("Enter the name of the second host:", "Will Adams")
    host3_name = st.text_input("Enter the name of the third host:", "Khaya Dlanga")

    search_query = st.text_input("Enter your search query:", "")
    time_period = st.selectbox("Select time period:", ["1d", "2d-1d"])

    if st.button("Get News"):
        articles = fetch_google_news(search_query, time_period)
        if articles:
            for i, article in enumerate(articles):
                with st.expander(f"Article {i+1}: {article['title']}"):
                    st.write(article['description'])
                    st.write(f"[Read more]({article['link']})")
        else:
            st.write("No articles found for this query.")

    user_url = st.text_input("Enter a URL to fetch content from:", "")

    if st.button("Get Content"):
        if user_url:
            title, text = fetch_content_from_url(user_url)
            truncated_text = truncate_text(text)
            st.write(f"**Title:** {title}")
            st.write(truncated_text)
            facts = extract_facts(truncated_text)
            intro = generate_intro(facts, host1_name, host2_name, host3_name, podcast_name, podcast_description)
            formatted_intro = format_script(intro, host1_name, host2_name, host3_name)
            st.write("**Podcast Intro:**")
            editable_intro = st.text_area("", value=formatted_intro, height=200)

            introlines_dict = {f'line{i+1}': line for i, line in enumerate(formatted_intro.split('\n'))}

            audio_files = []
            for i, line in introlines_dict.items():
                if i == 'line1':
                    audio_data = generate_audio(line, "voice1")
                elif i == 'line2':
                    audio_data = generate_audio(line, "voice2")
                else:
                    audio_data = generate_audio(line, "voice3")
                if audio_data:
                    audio_files.append(audio_data)

            if audio_files:
                combined_audio = stitch_audio(audio_files)
                with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as temp_file:
                    combined_audio.export(temp_file.name, format="mp3")
                st.audio(temp_file.name, format="audio/mp3")
                os.remove(temp_file.name)

if __name__ == "__main__":
    main()
