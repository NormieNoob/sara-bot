import logging
import time
import requests
import threading
from telegram.ext import CallbackContext
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update, Bot, ChatAction, User
import os
from googletrans import Translator
import soundfile as sf
import time
from datetime import datetime, date
import psycopg2
from prompts import get_text_messages, get_voice_messages, starter_prompt, get_start_messages
from api import xi_labs_api, openai_api
import openai
from Users import Users

# 11labs parameters


# Use file-based logging
logging.basicConfig(filename='Sara_bot_log.txt', format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                    level=logging.INFO)
logger = logging.getLogger(__name__)


def create_user(chat_id, user_name, collection):
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
    message = update.message
    message_id = message.message_id

    chat_id = update.effective_chat.id
    user = Users.all_users.get(chat_id)
    messages = get_voice_messages()
    send_message(bot=context.bot, text=update.message.text, global_messages=messages, message_id=message_id,
                 user=user)
    os.remove(output_file)


def send_message(bot: Bot, text: str, global_messages, message_id, user):
    chat_id = user.chat_id
    name = hindi_name(user.firstname)
    convo_start = starter_prompt(name)
    input_messages = global_messages.copy()
    input_messages.append({"role": "assistant", "content": convo_start})
    message = {"role": "user", "content": text}
    input_messages.append(get_System_prompt(user.firstname))
    input_messages.append(message)
    if not user.voiceMode:
        bot.send_chat_action(chat_id=chat_id, action=ChatAction.TYPING)
    try:
        response = openai_api(input_messages)
        bot_reply = response["choices"][0]["message"]["content"]
        input_messages.append({"role": "assistant", "content": bot_reply})
        logging.info(input_messages)
        if not user.voiceMode:
            bot.send_message(chat_id, text=bot_reply, reply_to_message_id=message_id)

        elif user.voiceMode:
            bot.send_chat_action(chat_id=chat_id, action=ChatAction.RECORD_AUDIO)
            audio_file, output_filename = xi_labs_api(message=bot_reply, chat_id=chat_id)
            bot.send_voice(chat_id=chat_id, voice=audio_file, filename=output_filename, reply_to_message_id=message_id)
            os.remove(output_filename)

    except Exception as e:
        logging.info(f"Could not update {user.firstname} message: {str(e)}")
        bot.send_message(chat_id, text="Sorry, I’m busy at the moment. Text me after sometime",
                         reply_to_message_id=message_id)


def start(update: Update, context: CallbackContext):
    chat_id = update.effective_chat.id
    firstname = update.effective_chat.first_name
    user_id = update.effective_user.id
    username = update.effective_user.username
    if chat_id not in Users.all_users:
        new_user = Users(chat_id=chat_id, user_id=user_id, firstname=firstname, username=username)

    convo_starter, photo_url, consent_text = get_start_messages()
    context.bot.send_message(chat_id=chat_id, text=convo_starter)
    context.bot.send_photo(chat_id=chat_id, photo=photo_url)

    # Create an inline keyboard with a single button
    button = InlineKeyboardButton("Agree & Continue", callback_data="agree")
    keyboard = InlineKeyboardMarkup([[button]])
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
        start_message = starter_prompt(user.firstname)
        audio_file, output_filename = xi_labs_api(message=start_message, chat_id=chat_id)
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


def chat(bot: Bot, chat_id: int, text: str, messages):
    message = {"role": "user", "content": text}
    messages.append(message)
    bot.send_chat_action(chat_id=chat_id, action=ChatAction.TYPING)
    while True:
        try:
            response = openai_api(messages)
            bot_reply = response["choices"][0]["message"]["content"]
            messages.append(response["choices"][0]["message"])
            bot.send_message(chat_id, text=bot_reply)
            break
        except Exception as e:
            logging.error(f"OpenAI API Error: {str(e)}")
            bot.send_message(chat_id, text="Oops! Something went wrong. Please try again later.")
            time.sleep(5)


def reply(update: Update, context: CallbackContext):
    message_id = update.message.message_id
    chat_id = update.effective_chat.id
    user = Users.all_users.get(chat_id)
    try:
        if user.consent:
            messages = get_voice_messages()
            send_message(bot=context.bot, text=update.message.text, global_messages=messages, message_id=message_id, user=user)
        else:
            # Create an inline keyboard with a single button
            button = InlineKeyboardButton("Agree & Continue", callback_data="agree")
            keyboard = InlineKeyboardMarkup([[button]])
            consent_text = "You must agree to our terms & conditions. Click the below Agree & Continue button to continue."
            context.bot.send_message(chat_id=chat_id, text=consent_text, reply_markup=keyboard)
    except Exception as e:
        context.bot.send_message(chat_id=chat_id, text="Click the start here \n\n /start")


def error(update: Update, context: CallbackContext):
    logger.warning('Update "%s" caused error "%s"', update, context.error)


def handle_message(update: Update, context: CallbackContext) -> None:
    threading.Thread(target=reply, args=(update, context,)).start()


def handle_voice(update: Update, context: CallbackContext) -> None:
    threading.Thread(target=voice_handler, args=(update, context,)).start()
