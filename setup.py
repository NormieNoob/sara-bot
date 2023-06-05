import logging
import threading
from telegram.ext import CallbackContext, ConversationHandler, CommandHandler, MessageHandler, Filters
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update, Bot, ChatAction, User
import os
from googletrans import Translator
import soundfile as sf
from prompts import get_text_messages, get_voice_messages, starter_prompt, get_start_messages
from api import xi_labs_api, openai_api
import openai
from Users import Users
from db import db_connection, create_user, get_voice_mode, set_voice_mode, get_user_details, get_user_balance
from payments import create_payment_request, send_payment_request, handle_api_response
import uuid

# Global database connection object
collection = db_connection()

# Use file-based logging
logging.basicConfig(filename='Sara_bot_log.txt', format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                    level=logging.INFO)
logger = logging.getLogger(__name__)


def hindi_name(name):
    translator = Translator(service_urls=['translate.google.com'])
    translation = translator.translate(name, src='hi', dest='hi')
    name = translation.text
    return name


def get_system_prompt(user_name):
    name = hindi_name(user_name)
    return {'role': 'system',
            'content': f"Address the user by their first name in all responses, the users first name is {name}"}


def start(update: Update, context: CallbackContext):
    chat_id = update.effective_chat.id
    convo_starter, photo_url, consent_text = get_start_messages()
    context.bot.send_message(chat_id=chat_id, text=convo_starter)
    context.bot.send_photo(chat_id=chat_id, photo=photo_url)

    # Inline keyboard with a single button to Agree & continue
    button = InlineKeyboardButton("Agree & Continue", callback_data="agree")
    keyboard = InlineKeyboardMarkup([[button]])
    context.bot.send_message(chat_id=update.effective_chat.id, text=consent_text, reply_markup=keyboard)


def button_callback(update: Update, context: CallbackContext):
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id
    firstname = update.effective_user.first_name
    username = update.effective_user.username
    if chat_id not in Users.all_users:
        user = Users(chat_id=chat_id, user_id=user_id, firstname=firstname, username=username)
    user = Users.all_users.get(chat_id)
    query = update.callback_query.data
    if query == 'agree':
        user.set_consent(True)
        try:
            if collection.count_documents({'_id': chat_id}) == 0:
                create_user(chat_id=chat_id, user_id=user_id, firstname=firstname, username=username,
                            collection=collection)
                logging.info(f"Added {update.effective_user.first_name} to the database")
        except Exception as e:
            logging.info(f"Could not add {chat_id} - {update.effective_user.first_name} to the database")
        # User clicked "Agree & Continue" button
        context.bot.send_message(chat_id=chat_id, text="You have agreed and can continue.")
        start_message = starter_prompt(user.firstname)
        context.bot.send_chat_action(chat_id=chat_id, action=ChatAction.RECORD_AUDIO)
        xi_labs = xi_labs_api(message=start_message, chat_id=chat_id)
        if xi_labs is not None:
            audio_file, output_filename = xi_labs
            context.bot.send_voice(chat_id=chat_id, voice=audio_file, filename=output_filename)
            os.remove(output_filename)
        else:
            logging.info("XI labs issue")


def voice_handler(update: Update, context: CallbackContext) -> None:
    file_id = update.message.voice.file_id
    new_file = context.bot.getFile(file_id)
    new_file.download('voice.ogg')

    # Convert to WAV
    output_file = f"voice.wav"
    data, sample_rate = sf.read("voice.ogg")
    sf.write(output_file, data, sample_rate, format='WAV', subtype='PCM_16')
    audio_file = open(output_file, "rb")
    transcript = openai.Audio.transcribe("whisper-1", audio_file)
    readable_string = transcript['text'].encode('utf-16', 'surrogatepass').decode('utf-16')
    reply(update=update, context=context, voice_to_text=readable_string)
    os.remove(output_file)


def reply(update: Update, context: CallbackContext, voice_to_text=None):
    chat_id = update.effective_chat.id
    message_id = update.message.message_id
    user_id = update.effective_user.id
    username = update.effective_user.username
    firstname = update.effective_user.first_name
    if chat_id not in Users.all_users:
        user = get_user_details(chat_id=chat_id, collection=collection, Users=Users)
    user = Users.all_users.get(chat_id)
    if user is not None:
        try:
            if collection.count_documents({'_id': chat_id}) == 0:
                create_user(chat_id=chat_id, user_id=user_id, firstname=firstname, username=username,
                            collection=collection)
                logging.info(f"Added {update.effective_user.first_name} to the database")
        except Exception as e:
            logging.info(f"Could not add {chat_id} - {update.effective_user.first_name} to the database")

        user.voiceMode = get_voice_mode(chat_id, collection)
        if user.voiceMode or user.voiceMode is None:
            messages = get_voice_messages()
        else:
            messages = get_text_messages()
        if voice_to_text is None:
            message = update.message.text
        else:
            message = voice_to_text
        send_message(bot=context.bot, text=message, global_messages=messages, message_id=message_id,
                     user=user)
    else:
        # Create an inline keyboard with a single button
        button = InlineKeyboardButton("Agree & Continue", callback_data="agree")
        keyboard = InlineKeyboardMarkup([[button]])
        consent_text = "You must agree to our terms & conditions. Click the below Agree & Continue button to continue."
        context.bot.send_message(chat_id=chat_id, text=consent_text, reply_markup=keyboard)


def send_message(bot: Bot, text: str, global_messages, message_id, user):
    chat_id = user.chat_id
    input_messages = global_messages.copy()
    name = hindi_name(user.firstname)
    if user.voiceMode:
        voice_convo_start = starter_prompt(name)
        input_messages.append({"role": "assistant", "content": voice_convo_start})
    input_messages.append(get_system_prompt(user.firstname))
    message = {"role": "user", "content": text}
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
            xi_labs = xi_labs_api(message=bot_reply, chat_id=chat_id)
            if xi_labs is not None:
                audio_file, output_filename = xi_labs
                bot.send_voice(chat_id=chat_id, voice=audio_file, filename=output_filename,
                               reply_to_message_id=message_id)
                os.remove(output_filename)
            else:
                logging.info("XI labs issue")
                bot.send_message(chat_id=chat_id, text="Sorry, I cannot speak now. Change to /text mode.",
                                 reply_to_message_id=message_id)

    except Exception as e:
        logging.error(f"Could not update {user.firstname} message: {str(e)}")
        bot.send_message(chat_id, text="Sorry, I’m busy at the moment. Text me after sometime",
                         reply_to_message_id=message_id)


def voice(update: Update, context: CallbackContext):
    chat_id = update.effective_chat.id
    if chat_id not in Users.all_users:
        user = get_user_details(chat_id=chat_id, collection=collection, Users=Users)
    else:
        user = Users.all_users.get(chat_id)
    if user is None:
        update.message.reply_text(f"Please click here to /start")
    else:
        user.voiceMode = True
        set_voice_mode(chat_id=chat_id, voice_mode=True, collection=collection)
        update.message.reply_text(f"Switched to voice mode.")


def text(update: Update, context: CallbackContext):
    chat_id = update.effective_chat.id
    if chat_id not in Users.all_users:
        user = get_user_details(chat_id=chat_id, collection=collection, Users=Users)
    else:
        user = Users.all_users.get(chat_id)
    if user is None:
        update.message.reply_text(f"Please click here to /start")
    else:
        user.voiceMode = False
        set_voice_mode(chat_id=chat_id, voice_mode=False, collection=collection)
        update.message.reply_text(f"Switched to text mode.")


def balance(update, context):
    balance = get_user_balance(chat_id=update.effective_chat.id, collection=collection)
    if balance is not None:
        update.message.reply_text(f"Your account balance is Rs.{balance}")
    else:
        update.message.reply_text(f"Please click here to /start")


def recharge(update, context):
    text = "Enter Amount you want to deposit in Rupees.\n\nIf you want to deposit Rs.500 then only enter 500.\n\n\nPlease Note that you'll be charged Rs.100 per a minute of voice message."
    context.bot.send_message(chat_id=update.effective_chat.id, text=text)
    return UPID_STATE


def handle_amount(update, context):
    amount = update.message.text
    context.chat_data['amount'] = amount
    context.bot.send_message(chat_id=update.effective_chat.id, text="Enter the upi id")
    return UPID_STATE


def handle_upi_id(update, context):
    upi_id = update.message.text
    chat_id = update.message.chat_id
    amount = "100"
    transaction_id = str(uuid.uuid4())
    payload = create_payment_request(amount=amount, transaction_id=transaction_id, user_id=chat_id, vpa=upi_id)
    print(f"Payment initiated for the user {chat_id} & the transaction_id - {transaction_id} for the Amount - {amount}")
    response = send_payment_request(payload)
    print(response)
    payment_status = handle_api_response(response)
    print(payment_status)
    if payment_status is None:
        context.bot.send_message(chat_id=chat_id, text="Payment Failed")
    else:
        context.bot.send_message(chat_id=chat_id, text=f"Payment Initiated.\n Please open your UPI app & proceed to pay.\n\nTransaction Id - {payment_status}")
    return ConversationHandler.END


def cancel(update, context):
    context.bot.send_message(chat_id=update.effective_chat.id, text="Recharge canceled.")
    return ConversationHandler.END


UPID_STATE = 1
AMOUNT_STATE = 2


def payment_handlers(dispatcher):
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('recharge', recharge)],
        states={
            # AMOUNT_STATE: [MessageHandler(Filters.text, handle_amount)],
            UPID_STATE: [MessageHandler(Filters.text, handle_upi_id)],
        },
        fallbacks=[CommandHandler('cancel', cancel)]
    )

    dispatcher.add_handler(conv_handler)


# def payment_handlers(dispatcher):
#     threading.Thread(target=handle_payments, args=(dispatcher,)).start()


def error(update: Update, context: CallbackContext):
    logger.warning('Update "%s" caused error "%s"', update, context.error)


def handle_consent_button(update: Update, context: CallbackContext):
    threading.Thread(target=button_callback, args=(update, context,)).start()


def handle_message(update: Update, context: CallbackContext) -> None:
    threading.Thread(target=reply, args=(update, context,)).start()


def handle_voice(update: Update, context: CallbackContext) -> None:
    threading.Thread(target=voice_handler, args=(update, context,)).start()


def handle_balance_enquiry(update: Update, context: CallbackContext):
    threading.Thread(target=balance, args=(update, context,)).start()


def handle_recharge(update: Update, context: CallbackContext):
    threading.Thread(target=recharge, args=(update, context,)).start()
