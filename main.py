from telegram.ext import Updater, CommandHandler, MessageHandler, CallbackQueryHandler, Filters
from setup import button_callback, start, voice, text, handle_voice, handle_message, error
from api import bot_token

def main():
    updater = Updater(token=bot_token, use_context=True)
    dp = updater.dispatcher
    dp.add_handler(CallbackQueryHandler(button_callback))
    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(CommandHandler("voice", voice))
    dp.add_handler(CommandHandler("text", text))
    dp.add_handler(MessageHandler(Filters.text & ~Filters.command, handle_message))
    dp.add_handler(MessageHandler(Filters.voice & ~Filters.command, handle_voice))
    dp.add_error_handler(error)

    updater.start_polling()

    updater.idle()


if __name__ == '__main__':
    main()
