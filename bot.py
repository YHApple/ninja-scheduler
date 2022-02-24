import logging
import os
from telegram.ext import Updater, CommandHandler
from telegram import InlineKeyboardButton, InlineKeyboardMarkup

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
TOKEN = os.getenv("TELEGRAM_TEST_TOKEN")
APP_NAME = os.getenv("TEST_APP_NAME")


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

def get_update_keyboard():
    options = []
    options.append(InlineKeyboardButton(text='View Plan', callback_data='1'))
    options.append(InlineKeyboardButton(text='Upgrade Plan', callback_data='2'))
    options.append(InlineKeyboardButton(text='Set Delivery Date', callback_data='3'))
    options.append(InlineKeyboardButton(text='Reschedule Delivery Date', callback_data='4'))
    keyboard = InlineKeyboardMarkup([options])
    return keyboard


# def query_handler(update, context):
#     # Here, we'll have access to the user's answer
#     query = update.callback_query
#     query.answer()
#
#     # Change your comparisons depending on what you chose as 'callback_data'
#     if query.data == 'wrong':
#         wrong = "Sorry, that's not the right answer. Try again."
#         context.bot.send_message(chat_id=update.effective_chat.id, text=wrong)
#     if query.data == 'right':
#         right = "Congratulations! You have chosen the right answer."
#         context.bot.send_message(chat_id=update.effective_chat.id, text=right)
#
#     return

# Define a few command handlers. These usually take the two arguments update and
# context. Error handlers also receive the raised TelegramError object in error.
START_GREETING = 'Welcome to Ninja Scheduler! How can I help you with your delivery today?'


def start(update, context):
    context.bot.send_message(chat_id=get_chat_id(update, context), text=START_GREETING)


def view_type(update, context):
    # retrieve the deliveryType from firestore
    if update.message.text.strip() == '/view': 
        update.message.reply_text("Please specify the order which you wish to check the delivery type! \n Usage:/view [orderId] \n eg. /view 100")
    else: 
        # Obtain arguments of the command
        command = update.message.text.split(" ")
        order_id = command[1]    
        doc = firestore_db.collection(u'orders').document(order_id).get()
        doc_dict = doc.to_dict()
        deliveryType = doc_dict['deliveryType']
        context.bot.send_message(chat_id=get_chat_id(update, context), text=deliveryType)
    

def upgrade_plan(update, context):
    # Check if command usage is correct
    if update.message.text.strip() == '/upgrade': 
        update.message.reply_text("Please specify the type of plan you want to upgrade to! \n Usage:/upgrade [orderId] [deliveryType] \n eg. /upgrade 100 time-slot")
    else: 
        # Obtain arguments of the command
        command = update.message.text.split(" ")
        order_id = command[1]
        delivery_type = command[2]
        
        # TODO: insert order_id into the database read
        order_ref = firestore_db.collection(u'orders').document(u'100')
        order_doc = order_ref.get()
        order_dict = order_doc.to_dict()
        current_type = order_dict["deliveryType"]
        if current_type == "standard":
            upgrade_from_standard(update, delivery_type, order_ref)
        elif current_type == "express":
            upgrade_from_express(update, delivery_type, order_ref)
        else:
            update.message.reply_text("You are already at the highest delivery tier! Do /reschedule if you wish to reschedule your package.")


def upgrade_from_standard(update, del_type, order_ref):
    if del_type == "standard":
        update.message.reply_text("You are already at this tier.")
    elif del_type == "express" or  del_type == "time-slot":
        # stripe API
        order_ref.update({
            "deliveryType": del_type
        })
        update.message.reply_text("Successfully upgraded to " + del_type + "!")


def upgrade_from_express(update, del_type, order_ref):
    if del_type == "standard" or del_type == "express":
        update.message.reply_text("You are already at/above this tier. Do /reschedule if you wish to reschedule your package.")
    elif del_type == "time-slot":
        # stripe API
        order_ref.update({
            "deliveryType": del_type
        })
        update.message.reply_text("Successfully upgraded to " + del_type + "!")


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
    dp.add_handler(CommandHandler("upgrade", upgrade_plan))
    dp.add_handler(CommandHandler("view", view_type))

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
