from telegram.ext import Updater, CommandHandler, MessageHandler, CallbackQueryHandler, Filters
from setup import start, voice, text, handle_voice, handle_message, error, handle_balance_enquiry, handle_recharge, \
    handle_consent_button
from api import bot_token


def main():
    updater = Updater(token=bot_token, use_context=True)
    dp = updater.dispatcher
    dp.add_handler(CallbackQueryHandler(handle_consent_button))
    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(CommandHandler("voice", voice))
    dp.add_handler(CommandHandler("text", text))
    dp.add_handler(MessageHandler(Filters.text & ~Filters.command, handle_message))
    dp.add_handler(MessageHandler(Filters.voice & ~Filters.command, handle_voice))
    dp.add_handler(CommandHandler("balance", handle_balance_enquiry))
    dp.add_handler(CommandHandler("recharge", handle_recharge))
    dp.add_error_handler(error)

    updater.start_polling()

    updater.idle()


if __name__ == '__main__':
    main()
