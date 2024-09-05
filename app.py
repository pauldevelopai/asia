import streamlit as st
import openai
from dotenv import load_dotenv
import os
import logging
from models import session, ShowProfile, Script  # Add Script to the imports
from utils import fetch_available_voices, save_show_profile, fetch_old_scripts, fetch_content_from_url, extract_facts_from_content, generate_podcast_script, save_script_in_db, generate_audio, search_articles

# Load environment variables from .env file
load_dotenv()

# Get the API keys from the environment variables
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
ELEVEN_LABS_API_KEY = os.getenv("ELEVEN_LABS_API_KEY")
NEWS_API_KEY = os.getenv("NEWS_API_KEY")

if not OPENAI_API_KEY:
    raise ValueError("OPENAI_API_KEY not found in environment variables")

if not ELEVEN_LABS_API_KEY:
    raise ValueError("ELEVEN_LABS_API_KEY not found in environment variables")

if not NEWS_API_KEY:
    raise ValueError("NEWS_API_KEY not found in environment variables")

# Initialize the OpenAI client with the API key
openai.api_key = OPENAI_API_KEY
client = openai

# Add the logo with specified width
st.image("logo.jpeg", width=150)  # Adjust the width as needed

# Set up logging
logging.basicConfig(level=logging.DEBUG)

# Fetch available voices
available_voices = fetch_available_voices(ELEVEN_LABS_API_KEY)

# Streamlit UI
st.title("Develop AI Podcast Generator")

# Dropdown menu to choose a show
show_profiles = session.query(ShowProfile).all()
show_options = {show.name: show.id for show in show_profiles}
selected_show_name = st.selectbox("Choose Show", options=[""] + list(show_options.keys()))

# Load the selected show's information
if selected_show_name:
    selected_show = session.get(ShowProfile, show_options[selected_show_name])
    if selected_show:
        name = selected_show.name
        description = selected_show.description
        host1 = selected_show.host1
        host1_voice = selected_show.host1_voice
        host1_personality = selected_show.host1_personality
        host2 = selected_show.host2
        host2_voice = selected_show.host2_voice
        host2_personality = selected_show.host2_personality
        host3 = selected_show.host3
        host3_voice = selected_show.host3_voice
        host3_personality = selected_show.host3_personality
    else:
        st.error("Failed to load the selected show.")
else:
    name = ""
    description = ""
    host1 = ""
    host1_voice = ""
    host1_personality = ""
    host2 = ""
    host2_voice = ""
    host2_personality = ""
    host3 = ""
    host3_voice = ""
    host3_personality = ""

# Input fields for show profile
name = st.text_input("Show Name", value=name)
description = st.text_area("Show Description", value=description)
host1 = st.text_input("Host 1 Name", value=host1)
host1_voice = st.selectbox("Voice for Host 1", options=list(available_voices.keys()), index=list(available_voices.keys()).index(host1_voice) if host1_voice else 0)
host1_personality = st.text_area("Personality for Host 1", value=host1_personality)
host2 = st.text_input("Host 2 Name", value=host2)
host2_voice = st.selectbox("Voice for Host 2", options=list(available_voices.keys()), index=list(available_voices.keys()).index(host2_voice) if host2_voice else 0)
host2_personality = st.text_area("Personality for Host 2", value=host2_personality)
host3 = st.text_input("Host 3 Name", value=host3)
host3_voice = st.selectbox("Voice for Host 3", options=list(available_voices.keys()), index=list(available_voices.keys()).index(host3_voice) if host3_voice else 0)
host3_personality = st.text_area("Personality for Host 3", value=host3_personality)

# Button to save the show profile
if st.button("Save Show"):
    save_show_profile(name, description, host1, host1_voice, host1_personality, host2, host2_voice, host2_personality, host3, host3_voice, host3_personality)
    st.success("Show profile saved successfully!")  # Add this line for confirmation

# Add "Update Show" button
if st.button("Update Show"):
    show_id = show_options[selected_show_name]  # Get the show_id from the selected show
    update_show_profile(show_id, name, description, host1, host1_voice, host1_personality, host2, host2_voice, host2_personality, host3, host3_voice, host3_personality)

# Function to fetch old scripts from the database for the selected show
if selected_show_name:
    old_scripts = fetch_old_scripts(show_options[selected_show_name])
    script_options = {f"{script.show.name} - {script.created_at}": script.id for script in old_scripts}

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
            # Display the accompanying audio if available
            if selected_script.audio:
                st.audio(selected_script.audio, format="audio/mp3")
                st.download_button(label="Download Old Script Audio", data=selected_script.audio, file_name="old_script_audio.mp3", mime="audio/mpeg")
        else:
            st.error("Failed to import script.")

# Keyword search and scrape functionality
st.header("Keyword Search and Scrape")
keyword = st.text_input("Enter keyword to search for articles")
if st.button("Search Articles"):
    articles = search_articles(NEWS_API_KEY, keyword)
    if articles:
        st.session_state.articles = articles
        st.success(f"Found {len(articles)} articles")
    else:
        st.error("No articles found")

# Display articles in a dropdown menu
if "articles" in st.session_state:
    article_options = {f"{article['title']} - {article['url']}": article['url'] for article in st.session_state.articles}
    selected_article = st.selectbox("Select an article", options=list(article_options.keys()))

    # Button to use the selected article
    if st.button("Use Selected Article"):
        actual_article_url = article_options[selected_article]
        st.session_state.research_url = actual_article_url  # Store the actual article URL in session state
        st.success(f"Selected article: {selected_article}")
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
                    facts = extract_facts_from_content(research_content, client)
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
                    script_content = generate_podcast_script(name, description, [host1, host2, host3], [host1_personality, host2_personality, host3_personality], facts, client)
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
                    audio_file_path = generate_audio(script_content, voices, ELEVEN_LABS_API_KEY, intro_clip, outro_clip)
                    if audio_file_path:
                        # Save the script and audio in the database
                        saved_script = save_script_in_db(show_options[selected_show_name], name, description, [host1, host2, host3], script_content, research_url, audio_file_path)
                        st.success("Podcast script and audio generated and saved successfully!")
                        # Provide a download button for the generated audio
                        with open(audio_file_path, "rb") as file:
                            st.download_button(label="Download Audio", data=file, file_name="podcast_audio.mp3", mime="audio/mpeg")
                        # Provide an audio player for the generated audio
                        st.audio(audio_file_path, format="audio/mp3")
                    else:
                        # Save the script in the database without audio
                        saved_script = save_script_in_db(show_options[selected_show_name], name, description, [host1, host2, host3], script_content, research_url)
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
        audio_file_path = generate_audio(script_content, voices, ELEVEN_LABS_API_KEY, intro_clip, outro_clip)
        if audio_file_path:
            # Provide a download button for the generated audio
            with open(audio_file_path, "rb") as file:
                st.download_button(label="Download Audio", data=file, file_name="podcast_audio.mp3", mime="audio/mpeg")
            # Provide an audio player for the generated audio
            st.audio(audio_file_path, format="audio/mp3")
        else:
            st.error("Failed to generate audio.")

# Button to save the edited script
if "script_content" in st.session_state:
    edited_script_content = st.text_area("Edit Script", value=st.session_state.script_content, height=300, key="edited_script")
    if st.button("Save Script"):
        # Save the edited script to the database
        save_script_in_db(show_options[selected_show_name], name, description, [host1, host2, host3], edited_script_content, research_url)
        st.success("Edited script saved successfully!")