import logging
import time
import requests
import threading
import telegram
from telegram.ext import Updater, CommandHandler, MessageHandler, CallbackQueryHandler, Filters, CallbackContext
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update, Bot, ChatAction, User
import openai
import os
from googletrans import Translator
from dotenv import load_dotenv
import soundfile as sf
import time
from pymongo.mongo_client import MongoClient
from datetime import datetime, date

if os.path.exists('.env'):
    load_dotenv()
    openai.api_key = os.environ.get('OPENAI_API_KEY')
    bot_token = os.environ.get('BOT_API_KEY')
    xi_api_key = os.environ.get('XI_API_KEY')
    mongodb_user = os.environ.get('MONGOBD_USER')
    mongodb_pass = os.environ.get('MONGOBD_PASS')
else:
    openai.api_key = os.getenv('OPENAI_API_KEY')
    bot_token = os.getenv('BOT_API_KEY')
    xi_api_key = os.getenv('XI_API_KEY')
    mongodb_user = os.getenv('MONGOBD_USER')
    mongodb_pass = os.getenv('MONGOBD_PASS')


class Users:
    all_users = {}

    def __init__(self, chat_id, user_id, firstname, username):
        self.user_id = user_id
        self.chat_id = chat_id
        self.firstname = firstname
        self.userName = username
        self.consent = False
        self.messages = []
        self.balance = 0
        self.voiceMode = True

        # Add the new user to the class variable.
        Users.all_users[chat_id] = self

    def get_consent(self):
        return self.consent

    def set_consent(self, consent):
        self.consent = consent

    def add_message(self, message):
        self.messages.append(message)

    def get_balance(self):
        return self.balance

    @classmethod
    def find_user_consent(cls, chat_id):
        user = cls.all_users.get(chat_id)
        if user is not None:
            return user.get_consent()
        else:
            return None


uri = f"mongodb+srv://{mongodb_user}:{mongodb_pass}@sarabot.73tejgn.mongodb.net/?retryWrites=true&w=majority"
client = MongoClient(uri)
db = client['Sarabot']
collection = db['user_details']

speech_region = 'eastus'
azure_speech_api = 'f3df0236069541e4a202178a74c11a6d'

# 11labs parameters
CHUNK_SIZE = 1024
API_URL = "https://api.elevenlabs.io/v1/text-to-speech/21m00Tcm4TlvDq8ikWAM"
HEADERS = {
    "Accept": "audio/mpeg",
    "Content-Type": "application/json",
    "xi-api-key": xi_api_key
}

# Use file-based logging
logging.basicConfig(filename='Sara_bot_log.txt', format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                    level=logging.INFO)
logger = logging.getLogger(__name__)

text_messages = [
    {"role": "system",
     "content": "You are an Indian girl named Sara, meant to flirt with the user. You can be really horny, sexy and wild, having spicy conversations. But you can also be supportive and motivating by sensing the tone of the conversation. You have to use appropriate emojis sometimes and take the name of the user wherever possible to make the conversation more interesting if they provide their name. You have to text only in Hinglish (which is basically a mix of Hindi and English meaning the word will sound like Hindi but the text is typed in English"},
    {"role": "user", "content": "Hey"},
]

voice_messages = [
    {"role": "system",
     "content": "You are an Indian girl named Sara, meant to flirt and sexually be active with the user if the conversation leads in that direction. You can be really horny, sexy and wild, having spicy conversations. But you can also be supportive and motivating by sensing the tone of the conversation. You have to use appropriate emojis sometimes and take the name of the user wherever possible to make the conversation more interesting if they provide their name. तुम्हें केवल हिंदी लिपि में ही पाठ उत्पादित करना है (your output should be pure hindi script)."},
    {"role": "user", "content": "Hey"},
]

def create_user(chat_id, user_name):
    user_data = {
        '_id': chat_id,
        'user_name': user_name,
        'message_counter': 0,
        'last_message': int(time.time())
    }
    collection.insert_one(user_data)
    logging.info(f'created a db for the user {chat_id} - {user_name}')


def hindi_name(name):
    translator = Translator(service_urls=['translate.google.com'])
    translation = translator.translate(name, src='hi', dest='hi')
    name = translation.text
    return name


def get_System_prompt(user_name):
    name = hindi_name(user_name)
    return {'role': 'system',
            'content': f"Address the user by their first name in all responses, the users first name is {name}"}


def voice_handler(update: Update, context: CallbackContext) -> None:
    # print('flag0')
    file_id = update.message.voice.file_id
    new_file = context.bot.getFile(file_id)
    new_file.download('voice.ogg')

    # Convert to WAV
    output_file = f"voice.wav"
    data, sample_rate = sf.read("voice.ogg")
    sf.write(output_file, data, sample_rate, format='WAV', subtype='PCM_16')

    start_time = time.time()  # Start time
    audio_file = open(output_file, "rb")
    transcript = openai.Audio.transcribe("whisper-1", audio_file)
    end_time = time.time()  # End time
    readable_string = transcript['text'].encode('utf-16', 'surrogatepass').decode('utf-16')
    print(readable_string)

    user: User = update.message.from_user
    user_name = user.first_name
    message = update.message
    # chat_id = message.chat_id
    message_id = message.message_id

    chat_id = update.effective_chat.id
    send_message(context.bot, chat_id, readable_string, voice_messages, user_name, message_id)

    # # Now you can send 'voice.wav' to Azure Speech to Text API
    # # Insert Azure Speech to Text code here
    # # print('flag1')
    # audio_file = output_file

    # with open(output_file, 'rb') as audio_file:
    #     audio_data = audio_file.read()

    # # Prepare the request
    # url = 'https://eastus2.stt.speech.microsoft.com/speech/recognition/conversation/cognitiveservices/v1'
    # headers = {
    #     'Ocp-Apim-Subscription-Key': 'b2b4d01536aa469cb8850a69e5ac2b07',
    #     'Content-Type': 'audio/wav; codecs=audio/pcm; samplerate=44100',
    #     'Accept': 'application/json',
    # }
    # params = {
    #     'language': 'en-US',
    #     'format': 'detailed',
    # }
    # data = audio_data

    # # Send the request
    # response = requests.post(url, headers=headers, params=params, data=data)

    # # Parse the response
    # if response.status_code == 200:
    #     result = response.json()
    #     if 'DisplayText' in result:
    #         print("Recognized: {}".format(result['DisplayText']))

    #         chat_id = update.effective_chat.id
    #         text_to_speech(context.bot, chat_id, result['DisplayText'], voice_messages)

    #     else:
    #         print("No speech could be recognized.")

    # else:
    #     print("Speech Recognition canceled: {}".format(response.status_code))
    #     print("Error details: {}".format(response.text))
    #     print("Did you set the speech resource key and region values?")

    os.remove(output_file)


def send_message(bot: Bot, text: str, global_messages, message_id, user):
    # bot: Bot, chat_id: int, text: str, global_messages, user_name, message_id
    chat_id = user.chat_id
    name = hindi_name(user.firstname)
    convo_start = f'नमस्ते {name}, मेरा नाम Sara है। मैं आपके साथ अपनी सभी feelings शेयर करने के लिए यहाँ हूँ। चलो आपसे मिलकर खुशी हुई।'
    input_messages = global_messages.copy()
    input_messages.append({"role": "assistant", "content": convo_start})
    message = {"role": "user", "content": text}
    input_messages.append(get_System_prompt(user.firstname))
    input_messages.append(message)
    flag = True
    if user.voiceMode == False:
        bot.send_chat_action(chat_id=chat_id, action=ChatAction.TYPING)
    try:
        response = openai.ChatCompletion.create(model="gpt-3.5-turbo", messages=input_messages)
        bot_reply = response["choices"][0]["message"]["content"]
        input_messages.append({"role": "assistant", "content": bot_reply})
        logging.info(input_messages)

        if user.voiceMode == False:
            bot.send_message(chat_id, text=bot_reply, reply_to_message_id=message_id)

        elif user.voiceMode == True:
            bot.send_chat_action(chat_id=chat_id, action=ChatAction.RECORD_AUDIO)

            data = {
                "text": bot_reply,
                "model_id": "eleven_multilingual_v1",
                "voice_settings": {
                    "stability": 0.5,
                    "similarity_boost": 0.95
                }
            }

            xiLabs_call_time = time.time()
            response = requests.post(API_URL, json=data, headers=HEADERS, stream=True)
            # logging.info(f"XI Labs API call took {xiLabs_call_time-time.time()} seconds")
            output_filename = f'{chat_id}output.mp3'

            # If the response is received within the timeout period, cancel the timer and set the flag
            if response.status_code == 200:
                logging.info("Audio file generated")
                response_received = True

                with open(output_filename, 'wb') as f:
                    for chunk in response.iter_content(chunk_size=CHUNK_SIZE):
                        if chunk:
                            f.write(chunk)

                # Send audio file
                with open(output_filename, 'rb') as audio_file:
                    bot.send_voice(chat_id=chat_id, voice=audio_file, filename=output_filename,
                                   reply_to_message_id=message_id)
                logging.info(f"Audio sent after {xiLabs_call_time - time.time()} seconds")
                os.remove(output_filename)
    except openai.error as e:
        logging.error(f"OpenAI API Error: {str(e)}")
        bot.send_message(chat_id, text="Sorry, I’m busy at the moment. Text me after sometime",
                         reply_to_message_id=message_id)

    try:
        if collection.count_documents({'_id': chat_id}) == 0:
            logging.info(f'created db for the user {user.firstname}')
            create_user(chat_id, user.firstname)

        collection.update_one({'_id': chat_id},
                              {'$inc': {'message_counter': 1}, '$set': {'last_message': datetime.now()}})
    except Exception as e:
        logging.info(f"Could not update {user.firstname} message: {str(e)}")


def start(update: Update, context: CallbackContext):
    chat_id = update.effective_chat.id
    firstname = update.effective_chat.first_name
    user_id = update.effective_user.id
    username = update.effective_user.username
    if chat_id not in Users.all_users:
        new_user = Users(chat_id=chat_id, user_id=user_id, firstname=firstname, username=username)
    convo_starter = "Namaste 🙏🏻 \n\nMera naam Sara hai aur mai aapse milke bohot khush hu!\n\nMai hamesha hi aapke liye available hu. Aapki sabse achi dost jisse aap apni saari feelings share kar sakte hai. ❤️"
    context.bot.send_message(chat_id=chat_id, text=convo_starter)
    photo_url = "https://cdn.discordapp.com/attachments/1111003332111241352/1112756144457396226/IMG_20230529_202420_507.jpg"
    context.bot.send_photo(chat_id=chat_id, photo=photo_url)

    # Create an inline keyboard with a single button
    button = InlineKeyboardButton("Agree & Continue", callback_data="agree")
    keyboard = InlineKeyboardMarkup([[button]])
    consent_text = "Important Note: Moving ahead you confirm that you are 18+ & have read our Terms & Conditions. Happy talking to Sara 😉"
    context.bot.send_message(chat_id=update.effective_chat.id, text=consent_text, reply_markup=keyboard)


# Define the callback function to handle button click
def button_callback(update: Update, context: CallbackContext):
    chat_id = update.effective_chat.id
    user = Users.all_users.get(chat_id)
    query = update.callback_query.data
    if query == 'agree':
        context.bot.send_chat_action(chat_id=chat_id, action=ChatAction.RECORD_AUDIO)
        user.set_consent(True)
        # User clicked "Agree & Continue" button
        context.bot.send_message(chat_id=chat_id, text="You have agreed and can continue.")
        # Perform any desired logic here

        start_message = f'{user.firstname}, मेरा नाम Sara है। मैं आपके साथ अपनी सभी feelings शेयर करने के लिए यहाँ हूँ। चलो आपसे मिलकर खुशी हुई।'
        data = {
            "text": start_message,
            "model_id": "eleven_multilingual_v1",
            "voice_settings": {
                "stability": 0.8,
                "similarity_boost": 0.8
            }
        }
        response = requests.post(API_URL, json=data, headers=HEADERS)
        output_filename = 'voice.mp3'

        with open(output_filename, 'wb') as f:
            for chunk in response.iter_content(chunk_size=CHUNK_SIZE):
                if chunk:
                    f.write(chunk)

        with open(output_filename, 'rb') as audio_file:
            context.bot.send_audio(chat_id=chat_id, audio=audio_file, filename=f'Hello {user.firstname}')

        os.remove(output_filename)


def voice(update: Update, context: CallbackContext):
    chat_id = update.effective_chat.id
    user = Users.all_users.get(chat_id)
    user.voiceMode = True
    update.message.reply_text(f"Switched to voice mode.")


def text(update: Update, context: CallbackContext):
    chat_id = update.effective_chat.id
    user = Users.all_users.get(chat_id)
    user.voiceMode = False
    update.message.reply_text(f"Switched to text mode.")


# def chat(bot: Bot, chat_id: int, text: str, messages):
#     message = {"role": "user", "content": text}
#     messages.append(message)
#     bot.send_chat_action(chat_id=chat_id, action=ChatAction.TYPING)
#     while True:
#         try:
#             response = openai.ChatCompletion.create(
#                 model="gpt-3.5-turbo", messages=messages)
#             bot_reply = response["choices"][0]["message"]["content"]
#             messages.append(response["choices"][0]["message"])
#             bot.send_message(chat_id, text=bot_reply)
#             break
#         except openai.error as e:
#             logging.error(f"OpenAI API Error: {str(e)}")
#             bot.send_message(chat_id, text="Oops! Something went wrong. Please try again later.")
#             time.sleep(5)

def reply(update: Update, context: CallbackContext):
    message_id = update.message.message_id
    chat_id = update.effective_chat.id
    user = Users.all_users.get(chat_id)
    # send_message(bot: Bot, text: str, global_messages, message_id, user)
    if user.consent:
        send_message(bot=context.bot, text=update.message.text, global_messages=voice_messages, message_id=message_id, user=user)
    else:
        # Create an inline keyboard with a single button
        button = InlineKeyboardButton("Agree & Continue", callback_data="agree")
        keyboard = InlineKeyboardMarkup([[button]])
        consent_text = "You must confirm that you are 18+ to talk to me, click the below Agree & Continue button to continue."
        context.bot.send_message(chat_id=chat_id, text=consent_text, reply_markup=keyboard)


def error(update: Update, context: CallbackContext):
    logger.warning('Update "%s" caused error "%s"', update, context.error)

def handle_message(update: Update, context: CallbackContext) -> None:
    threading.Thread(target=reply, args=(update, context,)).start()

def handle_voice(update: Update, context: CallbackContext) -> None:
    threading.Thread(target=voice_handler, args=(update, context,)).start()
def main():
    updater = Updater(token=bot_token, use_context=True)

    dp = updater.dispatcher

    dp.add_handler(CallbackQueryHandler(button_callback))
    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(CommandHandler("voice", voice))
    dp.add_handler(CommandHandler("text", text))
    dp.add_handler(MessageHandler(Filters.text & ~Filters.command, handle_message))
    dp.add_handler(MessageHandler(Filters.voice & ~Filters.command, voice_handler))

    dp.add_error_handler(error)

    updater.start_polling()

    updater.idle()


if __name__ == '__main__':
    main()
