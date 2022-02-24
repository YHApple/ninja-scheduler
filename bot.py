import logging
import os
import json

from telegram.ext import Updater, CommandHandler
from telegram import InlineKeyboardButton, InlineKeyboardMarkup

import random

import firebase_admin
from firebase_admin import firestore
from firebase_admin import credentials

cred = credentials.Certificate(os.getenv("FIREBASE_CERT"))

firebase_admin.initialize_app(cred)

firestore_db = firestore.client()

# Enable logging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                    level=logging.INFO)

logger = logging.getLogger(__name__)

PORT = int(os.environ.get('PORT', '8443'))
TOKEN = os.getenv("TELEGRAM_TOKEN")
APP_NAME = os.getenv("APP_NAME")


def get_chat_id(update, context):
    chat_id = -1

    if update.message is not None:
        # text message
        chat_id = update.message.chat.id
    elif update.callback_query is not None:
        # callback message
        chat_id = update.callback_query.message.chat.id
    elif update.poll is not None:
        # answer in Poll
        chat_id = context.bot_data[update.poll.id]

    return chat_id

# Define a few command handlers. These usually take the two arguments update and
# context. Error handlers also receive the raised TelegramError object in error.
def start(update, context):
    # doc = firestore_db.collection(u'users').document(u'1').get()
    # doc_dict = doc.to_dict()
    # name = doc_dict['name']
    # update.message.reply_text(name)
    options = []
    options.append(InlineKeyboardButton(text='View Plan', callback_data='1'))
    options.append(InlineKeyboardButton(text='Upgrade Plan', callback_data='2'))
    options.append(InlineKeyboardButton(text='Set Delivery Date', callback_data='3'))
    options.append(InlineKeyboardButton(text='Reschedule Delivery Date', callback_data='4'))
    reply_markup = InlineKeyboardMarkup([options])

    context.bot.send_message(chat_id=get_chat_id(update, context), text='Welcome to Ninja Scheduler! How can I help you with your delivery today?', reply_markup=reply_markup)

    choice = update.callback_query.data

    if choice == '1':
    # Choice 1: Text
        update.callback_query.message.edit_text('You have chosen Text')

def error(update, context):
    """Log Errors caused by Updates."""
    logger.warning('Update "%s" caused error "%s"', update, context.error)


def main():
    """Start the bot."""
    # Create the Updater and pass it your bot's token.
    # Make sure to set use_context=True to use the new context based callbacks
    # Post version 12 this will no longer be necessary
    updater = Updater(TOKEN, use_context=True)

    # Get the dispatcher to register handlers
    dp = updater.dispatcher

    # on different commands - answer in Telegram
    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(CommandHandler("help", help))

    # log all errors
    dp.add_error_handler(error)

    # Start the Bot
    updater.start_webhook(listen="0.0.0.0",
                          port=PORT,
                          url_path=TOKEN)

    updater.bot.set_webhook(APP_NAME + TOKEN)

    # # Run the bot until you press Ctrl-C or the process receives SIGINT,
    # # SIGTERM or SIGABRT. This should be used most of the time, since
    # # start_polling() is non-blocking and will stop the bot gracefully.
    updater.idle()


if __name__ == '__main__':
    main()
