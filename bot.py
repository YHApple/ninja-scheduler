import logging
import os
import datetime
from flask import Flask
import threading
import json
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


def get_update_keyboard():
    options = []
    options.append(InlineKeyboardButton(text='View Orders', callback_data='view_orders_action'))
    options.append(InlineKeyboardButton(text='Upgrade Plan', callback_data='upgrade_plan_action_'))
    options.append(InlineKeyboardButton(text='Set Delivery Date', callback_data='set_date_action'))
    options.append(InlineKeyboardButton(text='Reschedule Delivery Date', callback_data='reschedule_action_'))
    keyboard = InlineKeyboardMarkup([options])
    return keyboard

# Handles the callback functions
def query_handler(update, context):
    # Here, we'll have access to the user's answer
    query = update.callback_query
    query.answer()

    # Change your comparisons depending on what you chose as 'callback_data'
    if query.data == 'view_orders_action':
        view_orders(update, context)
    elif 'upgrade_plan_action_' in query.data:
        upgrade_plan(update, context)
    elif "view-order-id-" in query.data:
        order_id = query.data[14:]
        get_order(update, context, order_id)
    elif "upgrade-order-id-" in query.data:
        order_id = query.data[17:]
        upgrade_order(update, context, order_id)
    elif "_to_express_tier" in query.data:
        order_id = query.data[8:]
        upgrade_to_express(update, context, order_id)
    elif "_to_timeslot_tier" in query.data:
        order_id = query.data[8:]
        upgrade_to_timeslot(update, context, order_id)
    elif "_to_14day_tier" in query.data:
        order_id = query.data[8:]
        upgrade_to_14day(update, context, order_id)
    return


# Define a few command handlers. These usually take the two arguments update and
# context. Error handlers also receive the raised TelegramError object in error.
def start(update, context):
    context.bot.send_message(chat_id=get_chat_id(update, context),
                             text='Welcome to Ninja Scheduler! How can I help you with your delivery today?',
                             reply_markup=get_update_keyboard())
    # input from text message
    

def convert_order_to_button(order_id, action):
    return InlineKeyboardButton(text=str(order_id), callback_data= action + "-order-id-" + str(order_id))


def get_orders_keyboard(update, context, action):
    users_collection = firestore_db.collection(u'users')
    doc = users_collection.document(update.callback_query.message.chat.username).get()
    doc_dict = doc.to_dict()
    orders = doc_dict['orders']
    options = list(map(convert_order_to_button, orders, (action,) * len(orders)))
    keyboard = InlineKeyboardMarkup([options])
    return keyboard

# Retrieves the orders
def view_orders(update, context):
    try:
        context.bot.send_chat_action(chat_id=get_chat_id(update, context), action=ChatAction.TYPING, timeout=1)
        time.sleep(1)
        context.bot.send_message(chat_id=get_chat_id(update, context),
                                 text='Which order do you want to view?',
                                 reply_markup=get_orders_keyboard(update, context, "view"))
    except Exception as e:
        print(e)
        context.bot.send_message(chat_id=get_chat_id(update, context),
                                 text="Sorry, unable to retrieve orders.")


def get_order_keyboard(order_id):
    options = [InlineKeyboardButton(text='Upgrade Plan', callback_data='upgrade-order-id_' + order_id),
               InlineKeyboardButton(text='Reschedule Order', callback_data='reschedule_action_' + order_id)]
    keyboard = InlineKeyboardMarkup([options])
    return keyboard


def get_order(update, context, order_id):
    try:
        context.bot.send_chat_action(chat_id=get_chat_id(update, context), action=ChatAction.TYPING, timeout=1)
        time.sleep(1)
        order = firestore_db.collection(u'orders').document(order_id).get();
        order_dict = order.to_dict()
        date_time = order_dict["deliveryDate"].strftime("%m/%d/%Y, %H:%M:%S")
        del_type = order_dict["deliveryType"]
        num_res = order_dict["numReschedules"]
        text = "Your order {} is due to arrive on {}. \nThe current delivery type for this order is: {}.\n You have {" \
               "} reschedules left.\n What do you want to do? "
        formatted_text = text.format(order_id, date_time, del_type, str(2 - int(num_res)))
        context.bot.send_message(chat_id=get_chat_id(update, context),
                                 text=formatted_text,
                                 reply_markup=get_order_keyboard(order_id))
    except Exception as e:
        print(e)
        context.bot.send_message(chat_id=get_chat_id(update, context),
                                 text="Sorry, unable to retrieve order.")


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
            today = datetime.now().replace(hour=0, minute=0)
            print(today)

            userInput = update.message.text
            #split date and time
            splitInput = userInput.split(' ')
            print(splitInput)
            #split day/month/year
            splitDate = splitInput.split('/')
            rescheduleDateTime = datetime.datetime(splitDate[2], splitDate[1], splitDate[0], 0, 0)

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
                rescheduleDateTime.replace(hour=int(time[:2]), minute=int(time[2:]))
    
            if not dateInRange(rescheduleDateTime, minDate, maxDate):
                update.message.reply_text('Date out of range')
            else:
                numReschedules += 1
                order.update({ "numReschedules" : numReschedules })
                order.update({ "deliveryDate" : rescheduleDateTime })
                context.bot.send_message(chat_id=get_chat_id(update, context), text=f"Your delivery has been rescheduled to {rescheduleDateTime}")

def upgradePlan(update, context):
    try:
        context.bot.send_chat_action(chat_id=get_chat_id(update, context), action=ChatAction.TYPING, timeout=1)
        time.sleep(1)
        context.bot.send_message(chat_id=get_chat_id(update, context),
                                 text='Which order do you want to upgrade?',
                                 reply_markup=get_orders_keyboard(update, context, "upgrade"))
    except Exception as e:
        print(e)
        context.bot.send_message(chat_id=get_chat_id(update, context),
                                 text="Sorry, unable to retrieve orders.")

def upgrade_order(update, context, order_id):
    try:
        context.bot.send_chat_action(chat_id=get_chat_id(update, context), action=ChatAction.TYPING, timeout=1)
        time.sleep(1)
        order = firestore_db.collection(u'orders').document(order_id).get();
        order_dict = order.to_dict()
        date_time = order_dict["deliveryDate"].strftime("%m/%d/%Y, %H:%M:%S")
        del_type = order_dict["deliveryType"]
        num_res = order_dict["numReschedules"]
        text = "Your order {} is due to arrive on {}. \nThe current delivery type for this order is: {}.\n You have {" \
               "} reschedules left.\n What plan would you like to upgrade to? "
        formatted_text = text.format(order_id, date_time, del_type, str(2 - int(num_res)))
        context.bot.send_message(chat_id=get_chat_id(update, context),
                                 text=formatted_text,
                                 reply_markup=get_upgrade_keyboard(order_id))
    except Exception as e:
        print(e)
        context.bot.send_message(chat_id=get_chat_id(update, context),
                                 text="Sorry, unable to retrieve order.")

def get_upgrade_keyboard(order_id):
    options = []
    options.append(InlineKeyboardButton(text='Express Tier', callback_data="upgrade-" + order_id + "_to_express_tier"))
    options.append(InlineKeyboardButton(text='TimeSlot Tier', callback_data="upgrade-" + order_id + "_to_timeslot_tier"))
    options.append(InlineKeyboardButton(text='14 Day Tier', callback_data="upgrade-" + order_id + "_to_14day_tier"))
    keyboard = InlineKeyboardMarkup([options])
    return keyboard

def upgrade_to_express(update, context, order_id):
    try:
        context.bot.send_chat_action(chat_id=get_chat_id(update, context), action=ChatAction.TYPING, timeout=1)
        time.sleep(1)
        order = firestore_db.collection(u'orders').document(order_id).get();
        order_dict = order.to_dict()
        del_type = order_dict["deliveryType"]
        if "express" in del_type:
            update.message.reply_text("You are already at this tier. Do /reschedule if you wish to reschedule your package.")
        elif "timeslot" in del_type:
            update.message.reply_text("You are already at a higher tier. Do /reschedule if you wish to reschedule your package.")
        else:
            # stripe API
            order_id.update({
                "deliveryType": "express"
            })
            update.message.reply_text("Successfully upgraded to express tier!")
    except Exception as e:
        print(e)
        context.bot.send_message(chat_id=get_chat_id(update, context),
                                 text="Sorry, unable to retrieve order.")

def upgrade_to_timeslot(update, context, order_id):
    try:
        context.bot.send_chat_action(chat_id=get_chat_id(update, context), action=ChatAction.TYPING, timeout=1)
        time.sleep(1)
        order = firestore_db.collection(u'orders').document(order_id).get();
        order_dict = order.to_dict()
        del_type = order_dict["deliveryType"]
        if "timeslot" in del_type:
            update.message.reply_text("You are already at this tier. Do /reschedule if you wish to reschedule your package.")
        else:
            # stripe API
            order_id.update({
                "deliveryType": "timeslot"
            })
            update.message.reply_text("Successfully upgraded to timeslot tier!")
    except Exception as e:
        print(e)
        context.bot.send_message(chat_id=get_chat_id(update, context),
                                 text="Sorry, unable to retrieve order.")

def upgrade_to_14day(update, context, order_id):
    try:
        context.bot.send_chat_action(chat_id=get_chat_id(update, context), action=ChatAction.TYPING, timeout=1)
        time.sleep(1)
        order = firestore_db.collection(u'orders').document(order_id).get();
        order_dict = order.to_dict()
        del_type = order_dict["deliveryType"]
        if "14day" in del_type:
            update.message.reply_text("You are already at this tier. Do /reschedule if you wish to reschedule your package.")
        else:
            # stripe API
            order_id.update({
                "deliveryType": "14day " + del_type
            })
            update.message.reply_text("Successfully upgraded to 14day " + del_type + " tier!")
    except Exception as e:
        print(e)
        context.bot.send_message(chat_id=get_chat_id(update, context),
                                 text="Sorry, unable to retrieve order.")


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
    dp.add_handler(CallbackQueryHandler(query_handler))

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
