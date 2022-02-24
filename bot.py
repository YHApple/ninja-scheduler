import logging
import os
import datetime
from flask import Flask
import threading
import json
from telegram.ext import Updater, CommandHandler
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
# from telegram_bot_calendar import DetailedTelegramCalendar, LSTEP

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

app = Flask(__name__)

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

# Define a few command handlers. These usually take the two arguments update and
# context. Error handlers also receive the raised TelegramError object in error.
def start(update, context):
    # doc = firestore_db.collection(u'users').document(u'1').get()
    # doc_dict = doc.to_dict()
    # name = doc_dict['name']
    # update.message.reply_text(name)
    context.bot.send_message(chat_id=get_chat_id(update, context), text='Welcome to Ninja Scheduler! How can I help you with your delivery today?')
    # input from text message
    

def viewType(update, context):
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
    
def getDate(date):
    splitDate = date.split(" at ")
    d = datetime.strptime(splitDate[0], '%d %B %Y')
    return d

def dateInRange(dateToCheck, minDate, maxDate):
    return minDate >= dateToCheck and dateToCheck <= maxDate

def setDate(update, context):
    # update the delivery date on firestore
    doc = firestore_db.collection(u'users').document(u'1').get()
    doc_dict = doc.to_dict()
    deliveryDate = doc_dict['deliveryDate']
    deliveryType = doc_dict['deliveryType']
    # context.bot.send_message(chat_id=get_chat_id(update, context), text=deliveryDate)
    if update.message.text.strip() == '/setdate': 
        update.message.reply_text("Please specify the date to reschedule to! \n Usage:/setdate [dd-mm-yy] \n eg. /upgrade 02/24/22")
    else:
        deliveryDateConv = getDate(deliveryDate)
        command = update.message.text.split(" ")
        inputDate = datetime.strptime(command[0], '%d/%m/%y')
        if deliveryType == 'standard':
            # restrict date range to 3-7
            minDate = deliveryDateConv + datetime.timedelta(days=3)
            maxDate = deliveryDateConv + datetime.timedelta(days=7)
            if not dateInRange(inputDate, minDate, maxDate):
                update.message.reply_text('Date out of range')
            else:
                doc.update({ "deliveryDate" : inputDate })
            # calendar, step = DetailedTelegramCalendar(min_date, max_date).build()
        elif deliveryType == 'express':
            # restrict date range to 7
            minDate = deliveryDateConv + datetime.timedelta(days=1)
            maxDate = deliveryDateConv + datetime.timedelta(days=7)
            if not dateInRange(inputDate, minDate, maxDate):
                update.message.reply_text('Date out of range')
            else:
                doc.update({ "deliveryDate" : inputDate })
            # calendar, step = DetailedTelegramCalendar(min_date, max_date).build()
        else:
            # restrict date range to 3-14
            minDate = deliveryDateConv + datetime.timedelta(days=3)
            maxDate = deliveryDateConv + datetime.timedelta(days=14)
            if not dateInRange(inputDate, minDate, maxDate):
                update.message.reply_text('Date out of range')
            else:
                doc.update({ "deliveryDate" : inputDate })
            # calendar, step = DetailedTelegramCalendar(min_date, max_date).build()

def reschedule(update, context):
    if update.message.text.strip() == '/reschedule': 
        update.message.reply_text("Please specify the reschedule date! \n Usage:/reschedule [dd/mm/yyyy] \n eg. /reschedule 02/24/22")
    else:
        # update the deliveryDate and update the numReschedules
        order = firestore_db.collection(u'orders').document(u'1').get()
        order_dict = order.to_dict()
        #check if rescheduling is allowed
        numReschedules = order_dict['numReschedules']
        if numReschedules >= 2:
            context.bot.send_message(chat_id=get_chat_id(update, context), text="Number of reschedules has already exceeded the limit! Would you like to pay to reschedule?")
        else:
            deliveryType = order_dict['deliveryType']
            pickUpDate = order_dict['pickUpDate'].date()
            today = datetime.today()

            userInput = update.message.text
            splitInput = userInput.split(' ')
            splitDate = splitInput.split('/')
            rescheduleDate = datetime.datetime(splitDate[2], splitDate[1], splitDate[0])

            if deliveryType=="standard":
                minDate = today + datetime.timedelta(days=3)
                maxDate = pickUpDate + datetime.timedelta(days=7) 
            elif deliveryType=="express" or deliveryType=="timeslot":
                minDate = today + datetime.timedelta(days=1)
                maxDate = pickUpDate + datetime.timedelta(days=7)
            else:
                minDate = today + datetime.timedelta(days=1)
                maxDate = pickUpDate + datetime.timedelta(days=14)

            if "timeslot" in deliveryType:
                time = userInput[1]
    
            if not dateInRange(rescheduleDate, minDate, maxDate):
                update.message.reply_text('Date out of range')
            else:
                numReschedules += 1
                order.update({ "numReschedules" : numReschedules })
                order.update({ "deliveryDate" : rescheduleDate })
                context.bot.send_message(chat_id=get_chat_id(update, context), text=f"Your delivery has been rescheduled to {rescheduleDate}")

def upgradePlan(update, context):
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
    dp.add_handler(CommandHandler("upgrade", upgradePlan))
    dp.add_handler(CommandHandler("view", viewType))
    dp.add_handler(CommandHandler("reschedue", reschedule))

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
    first_thread = threading.Thread(target=main)
    second_thread = threading.Thread(target=app.run)
    first_thread.start()
    second_thread.start()
