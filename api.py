import time
import requests
import openai
from dotenv import load_dotenv
import os

if os.path.exists('.env'):
    load_dotenv()
    openai.api_key = os.environ.get('OPENAI_API_KEY')
    bot_token = os.environ.get('BOT_API_KEY')
    xi_api_key = os.environ.get('XI_API_KEY')
    XI_API_URL = os.environ.get('XI_API_URL')
else:
    openai.api_key = os.getenv('OPENAI_API_KEY')
    bot_token = os.getenv('BOT_API_KEY')
    xi_api_key = os.getenv('XI_API_KEY')
    XI_API_URL = os.environ.get('XI_API_URL')


def openai_api(message_array):
    response = openai.ChatCompletion.create(model="gpt-3.5-turbo", messages=message_array)
    return response

def xi_labs_api(message, chat_id):
    CHUNK_SIZE = 1024
    xi_api_url = XI_API_URL
    HEADERS = {
        "Accept": "audio/mpeg",
        "Content-Type": "application/json",
        "xi-api-key": xi_api_key
    }
    data = {
        "text": message,
        "model_id": "eleven_multilingual_v1",
        "voice_settings": {
            "stability": 0.5,
            "similarity_boost": 0.95
        }
    }
    response = requests.post(xi_api_url, json=data, headers=HEADERS, stream=True)

    # logging.info(f"XI Labs API call took {xiLabs_call_time-time.time()} seconds")
    output_filename = f'{chat_id}output.mp3'

    # If the response is received within the timeout period, cancel the timer and set the flag
    if response.status_code == 200:
        response_received = True

        with open(output_filename, 'wb') as f:
            for chunk in response.iter_content(chunk_size=CHUNK_SIZE):
                if chunk:
                    f.write(chunk)

        # Open and return the audio file
        audio_file = open(output_filename, 'rb')
        return [audio_file, output_filename]

    return None
