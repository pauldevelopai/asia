import openai
from openai import OpenAI

client = OpenAI(api_key=openai_api_key)
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

def test_api_key():
    # Get the API key from the environment variable
    openai_api_key = os.getenv("OPENAI_API_KEY")

    if not openai_api_key:
        raise ValueError("OPENAI_API_KEY not found in environment variables")

    print(f"Loaded API Key: {openai_api_key[:5]}...")  # Print the first few characters of the API key for verification

    try:
        # Initialize the OpenAI client with the API key

        # Make a simple request to the OpenAI API
        response = client.completions.create(model="text-davinci-003",
        prompt="Say hello, world!",
        max_tokens=5)
        print("API Key is valid. Response:")
        print(response.choices[0].text.strip())
    except openai.AuthenticationError:
        print("Invalid API Key. Please check your API key and try again.")
    except Exception as e:
        print(f"An error occurred: {e}")

if __name__ == "__main__":
    test_api_key()