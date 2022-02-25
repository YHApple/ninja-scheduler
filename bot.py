import logging
import os
import datetime
import time

import telegramcalendar

from telegram.ext import Updater, CommandHandler, CallbackQueryHandler, PreCheckoutQueryHandler, MessageHandler, Filters
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, ChatAction, LabeledPrice, ReplyKeyboardRemove

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
    options = [InlineKeyboardButton(text='View Orders', callback_data='view_orders_action'),
               InlineKeyboardButton(text='Upgrade Orders', callback_data='upgrade_orders_action_')]
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
    elif query.data == 'reschedule-topup':
        top_up_reschedules(update, context)
    elif 'upgrade_orders_action_' in query.data:
        upgrade_orders(update, context)
    elif "view-order-id-" in query.data:
        order_id = query.data[14:]
        get_order(update, context, order_id)
    elif "reschedule_orders_action" in query.data:
        order_id = query.data[24:]
        order = firestore_db.collection(u'orders').document(order_id).get()
        order_dict = order.to_dict()
        date_time = order_dict["deliveryDate"].strftime("%m/%d/%Y")

        context.bot.send_message(chat_id=get_chat_id(update, context),
                                 text="Your delivery was scheduled to reach on " + date_time)
        context.bot.send_message(chat_id=get_chat_id(update, context), text='Please select a date:',
                                 reply_markup=telegramcalendar.create_calendar(order_id))
    elif "reschedule-order-id-" in query.data:
        splitQuery = query.data.split(';')
        order_id = splitQuery[0][20:]
        reschedule_order(update, context, order_id)
    elif "upgrade-order-id-" in query.data:
        order_id = query.data[17:]
        upgrade_order(update, context, order_id)
    elif "_to_express_tier" in query.data:
        order_id = query.data[8:-16]
        upgrade_to_express(update, context, order_id)
    elif "_to_timeslot_tier" in query.data:
        order_id = query.data[8:-17]
        upgrade_to_timeslot(update, context, order_id)
    elif "9-12" in query.data:
        order_id = query.data[11:-19]
        date = query.data[-15:-5]
        reschedule_to_time(update, context, date, order_id, 9)
    elif "12-15" in query.data:
        order_id = query.data[11:-20]
        date = query.data[-16:-6]
        reschedule_to_time(update, context, date, order_id, 12)
    elif "15-18" in query.data:
        order_id = query.data[11:-20]
        date = query.data[-16:-6]
        reschedule_to_time(update, context, date, order_id, 15)
    elif "_to_18-20" in query.data:
        order_id = query.data[11:-20]
        date = query.data[-16:-6]
        reschedule_to_time(update, context, date, order_id, 18)
    elif "_to_14daystd" in query.data:
        order_id = query.data[8:-12]
        upgrade_to_14daystd(update, context, order_id)
    elif "_to_14dayts" in query.data:
        order_id = query.data[8:-11]
        upgrade_to_14dayts(update, context, order_id)
    return


START_INSTRUCTION = """Welcome to NinjaScheduler! I'm here to help you with your Ninja Van deliveries.\n
You can view all your orders, upgrade your orders or schedule your deliveries. How would you like to proceed?"""


# Define a few command handlers. These usually take the two arguments update and
# context. Error handlers also receive the raised TelegramError object in error.
def start(update, context):
    context.bot.send_message(chat_id=get_chat_id(update, context),
                             text=START_INSTRUCTION,
                             reply_markup=get_update_keyboard())
    # input from text message


def convert_order_to_button(order_id, action):
    return InlineKeyboardButton(text=str(order_id), callback_data=action + "-order-id-" + str(order_id))


def get_orders_keyboard(update, context, orders, action):
    options = list(map(convert_order_to_button, orders, (action,) * len(orders)))
    keyboard = InlineKeyboardMarkup([options])
    return keyboard


VIEW_ORDERS_INSTRUCTION = "You currently have {} orders scheduled for delivery. \n Which order do you wish to " \
                          "view? "


# Retrieves the orders
def view_orders(update, context):
    try:
        users_collection = firestore_db.collection(u'users')
        doc = users_collection.document(update.callback_query.message.chat.username).get()
        doc_dict = doc.to_dict()
        orders = doc_dict['orders']
        num_orders = len(orders)
        context.bot.send_chat_action(chat_id=get_chat_id(update, context), action=ChatAction.TYPING, timeout=1)
        time.sleep(1)
        context.bot.send_message(chat_id=get_chat_id(update, context),
                                 text=VIEW_ORDERS_INSTRUCTION.format(num_orders),
                                 reply_markup=get_orders_keyboard(update, context, orders, "view"))
    except Exception as e:
        print(e)
        context.bot.send_message(chat_id=get_chat_id(update, context),
                                 text="Sorry, unable to retrieve orders.")


def get_order_keyboard(order_id):
    options = [[InlineKeyboardButton(text='Upgrade Plan', callback_data='upgrade-order-id-' + order_id)],
               [InlineKeyboardButton(text='Reschedule Order', callback_data='reschedule_orders_action' + order_id)]]
    keyboard = InlineKeyboardMarkup(options)
    return keyboard


def get_order(update, context, order_id):
    try:
        context.bot.send_chat_action(chat_id=get_chat_id(update, context), action=ChatAction.TYPING, timeout=1)
        time.sleep(1)
        order = firestore_db.collection(u'orders').document(order_id).get()
        order_dict = order.to_dict()
        date_time = order_dict["deliveryDate"].strftime("%m/%d/%Y, %H:%M:%S")
        del_type = order_dict["deliveryType"]
        num_res = order_dict["numReschedules"]
        text = "Your order {} is due to arrive by {}. \n The current delivery type for this order is: " \
               "{}.\n You have {} reschedules left.\n What do you want to do? "
        formatted_text = text.format(order_id, date_time, del_type, str(num_res))
        context.bot.send_message(chat_id=get_chat_id(update, context),
                                 text=formatted_text,
                                 reply_markup=get_order_keyboard(order_id))
    except Exception as e:
        print(e)
        context.bot.send_message(chat_id=get_chat_id(update, context),
                                 text="Sorry, unable to retrieve order.")

def dateInRange(dateToCheck, minDate, maxDate):
    return minDate <= dateToCheck <= maxDate

def reschedule_order(update, context, order_id):
    selected, rescheduledDateTime = telegramcalendar.process_calendar_selection(update, context)
    order = firestore_db.collection(u'orders').document(order_id).get()
    order_dict = order.to_dict()
    deliveryDate = order_dict['deliveryDate'].replace(tzinfo=None)
    deliveryType = order_dict['deliveryType']
    numReschedules = int(order_dict['numReschedules'])
    pickUpDate = order_dict['pickUpDate'].replace(tzinfo=None)
    today = datetime.datetime.now().replace(hour=0, minute=0)
    back_button = InlineKeyboardButton(text='←', callback_data='reschedule_orders_action' + order_id)
    if numReschedules <= 0:
        options = [InlineKeyboardButton(text='Yes!', callback_data='reschedule-topup'),
                   InlineKeyboardButton(text='No...', callback_data=get_update_keyboard())]
        keyboard = InlineKeyboardMarkup([options])
        context.bot.send_message(chat_id=get_chat_id(update, context),
                                 text="Number of reschedules has already exceeded the limit! Would you like to pay to reschedule?"
                                    ,reply_markup=keyboard)
    else:
        if deliveryType == "standard" and selected:
            minDate = max([today, pickUpDate + datetime.timedelta(days=3)])
            maxDate = pickUpDate + datetime.timedelta(days=7)
        elif (deliveryType == "express" or deliveryType == "timeslot") and selected:
            minDate = max([today, pickUpDate + datetime.timedelta(days=1)])
            maxDate = pickUpDate + datetime.timedelta(days=7)
        elif deliveryType == "14day-standard" and selected:
            minDate = max([today, pickUpDate + datetime.timedelta(days=3)])
            maxDate = pickUpDate + datetime.timedelta(days=14)
        elif deliveryType == "14day-timeslot" and selected:
            minDate = max([today, pickUpDate + datetime.timedelta(days=1)])
            maxDate = pickUpDate + datetime.timedelta(days=14)

        print("minDate", minDate.strftime("%d/%m/%Y"))
        print("maxDate", maxDate.strftime("%d/%m/%Y"))
        if dateInRange(rescheduledDateTime, minDate, maxDate):
            if "timeslot" in deliveryType:
                context.bot.send_message(chat_id=get_chat_id(update, context),
                                        text=f"Please select a time slot",
                                        reply_markup=get_time_keyboard(update, context, rescheduledDateTime, order_id))
            else:
                numReschedules -= 1
                firestore_db.collection(u'orders').document(order_id).update({
                    "deliveryDate": rescheduledDateTime,
                    "numReschedules" : str(numReschedules)
                })
                context.bot.send_message(chat_id=get_chat_id(update, context),
                                         text=f"Your delivery has been rescheduled to " + rescheduledDateTime.strftime("%d/%m/%Y") +
                                         f"!\nYou now have {numReschedules} reschedules left.",
                                         reply_markup=get_update_keyboard())
        else:
            context.bot.send_message(chat_id=update.callback_query.from_user.id,
                                 text="Date is out of range",
                                 reply_markup=InlineKeyboardMarkup([[back_button]]))
    # if deliveryType == "timeslot":
    # choose timeslot


def top_up_reschedules(update, context):
    context.bot.send_invoice(chat_id=get_chat_id(update, context),
                             title="Pay to reschedule",
                             description="Pay to reschedule after 2 times rescheduled",
                             payload="ninja-scheduler/top-up",
                             provider_token="284685063:TEST:YTM1ZGYzNDlhMWI3",
                             currency="SGD",
                             prices=[LabeledPrice("Payment for top-up", 2 * 100)],
                             start_parameter="asdhjasdj")


# def reschedule(update, context):
#     if update.message.text.strip() == '/reschedule':
#         update.message.reply_text("Please specify the reschedule date! \n Usage:/reschedule [dd/mm/yyyy] \n eg. /reschedule 02/24/22")
#     else:
#         # update the deliveryDate and update the numReschedules
#         order = firestore_db.collection(u'orders').document(u'1').get()
#         order_dict = order.to_dict()
#         #check if rescheduling is allowed
#         numReschedules = order_dict['numReschedules']
#         if numReschedules == 0:
#             options = [InlineKeyboardButton(text='Yes!', callback_data='reschedule-topup'),
#                        InlineKeyboardButton(text='No...', callback_data=get_update_keyboard())]
#             keyboard = InlineKeyboardMarkup([options])
#             context.bot.send_message(chat_id=get_chat_id(update, context),
#                                      text="Number of reschedules has already exceeded the limit! Would you like to pay to reschedule?",
#                                      reply_markup=keyboard)
#         else:
#             deliveryType = order_dict['deliveryType']
#             pickUpDate = order_dict['pickUpDate'].date()
#             today = datetime.now().replace(hour=0, minute=0)
#             print(today)
#
#             userInput = update.message.text
#             #split date and time
#             splitInput = userInput.split(' ')
#             print(splitInput)
#             #split day/month/year
#             splitDate = splitInput.split('/')
#             rescheduleDateTime = datetime.datetime(splitDate[2], splitDate[1], splitDate[0], 0, 0)
#
#             if deliveryType=="standard":
#                 minDate = today + datetime.timedelta(days=3)
#                 maxDate = pickUpDate + datetime.timedelta(days=7)
#             elif deliveryType=="express" or deliveryType=="timeslot":
#                 minDate = today + datetime.timedelta(days=1)
#                 maxDate = pickUpDate + datetime.timedelta(days=7)
#             else:
#                 minDate = today + datetime.timedelta(days=1)
#                 maxDate = pickUpDate + datetime.timedelta(days=14)
#
#             if "timeslot" in deliveryType:
#                 time = userInput[1]
#                 rescheduleDateTime.replace(hour=int(time[:2]), minute=int(time[2:]))
#
#             if not dateInRange(rescheduleDateTime, minDate, maxDate):
#                 update.message.reply_text('Date out of range')
#             else:
#                 numReschedules -= 1
#                 order.update({ "numReschedules" : numReschedules })
#                 order.update({ "deliveryDate" : rescheduleDateTime })
#                 context.bot.send_message(chat_id=get_chat_id(update, context), text=f"Your delivery has been rescheduled to {rescheduleDateTime}")

def upgrade_orders(update, context):
    try:
        users_collection = firestore_db.collection(u'users')
        doc = users_collection.document(update.callback_query.message.chat.username).get()
        doc_dict = doc.to_dict()
        orders = doc_dict['orders']
        context.bot.send_chat_action(chat_id=get_chat_id(update, context), action=ChatAction.TYPING, timeout=1)
        time.sleep(1)
        context.bot.send_message(chat_id=get_chat_id(update, context),
                                 text='Which order do you want to upgrade?',
                                 reply_markup=get_orders_keyboard(update, context, orders, "upgrade"))
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
        formatted_text = text.format(order_id, date_time, del_type, str(num_res))
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
    options.append(
        InlineKeyboardButton(text='14 Day Standard Tier', callback_data="upgrade-" + order_id + "_to_14daystd"))
    options.append(InlineKeyboardButton(text='14 Day Timeslot Tier', callback_data="upgrade-" + order_id + "_to_14dayts"))
    keyboard = InlineKeyboardMarkup([options])
    return keyboard


ALREADY_AT_TIER_MESSAGE = """You are already at this tier. Do /reschedule if you wish to reschedule your package."""
ALREADY_AT_HIGHER_TIER_MESSAGE = """You are already at a higher tier. Do /reschedule if you wish to reschedule your package."""
UPGRADE_EXPRESS_SUCCESS_MESSAGE = """Successfully upgraded to express tier!"""
UPGRADE_TIMESLOT_SUCCESS_MESSAGE = """Successfully upgraded to timeslot tier!"""
UPGRADE_FAIL_MESSAGE = """Sorry, unable to upgrade order."""



def upgrade_to_express(update, context, order_id):
    try:
        context.bot.send_chat_action(chat_id=get_chat_id(update, context), action=ChatAction.TYPING, timeout=1)
        time.sleep(1)
        order = firestore_db.collection(u'orders').document(order_id).get()
        order_dict = order.to_dict()
        del_type = order_dict["deliveryType"]
        if "express" in del_type:
            context.bot.send_message(chat_id=get_chat_id(update, context),
                                     text=ALREADY_AT_TIER_MESSAGE,
                                     reply_markup=get_update_keyboard())
        elif "timeslot" in del_type:
            context.bot.send_message(chat_id=get_chat_id(update, context),
                                     text=ALREADY_AT_HIGHER_TIER_MESSAGE,
                                     reply_markup=get_update_keyboard())
        else:
            payment(update, context, del_type, "express", "Receive your package within 1 day of pickup!", order_id)
    except Exception as e:
        print(e)
        context.bot.send_message(chat_id=get_chat_id(update, context),
                                 text=UPGRADE_FAIL_MESSAGE)


def upgrade_to_timeslot(update, context, order_id):
    try:
        context.bot.send_chat_action(chat_id=get_chat_id(update, context), action=ChatAction.TYPING, timeout=1)
        time.sleep(1)
        order = firestore_db.collection(u'orders').document(order_id).get()
        order_dict = order.to_dict()
        del_type = order_dict["deliveryType"]
        if "timeslot" in del_type:
            context.bot.send_message(chat_id=get_chat_id(update, context),
                                     text=ALREADY_AT_TIER_MESSAGE,
                                     reply_markup=get_update_keyboard())
        else:
            payment(update, context, del_type, "timeslot",
                    "Choose the time slot which you want to receive your parcel (within 7 days)!", order_id)
    except Exception as e:
        print(e)
        context.bot.send_message(chat_id=get_chat_id(update, context),
                                 text=UPGRADE_FAIL_MESSAGE)


def upgrade_to_14dayts(update, context, order_id):
    try:
        context.bot.send_chat_action(chat_id=get_chat_id(update, context), action=ChatAction.TYPING, timeout=1)
        time.sleep(1)
        order = firestore_db.collection(u'orders').document(order_id).get()
        order_dict = order.to_dict()
        del_type = order_dict["deliveryType"]
        if "14day-timeslot" in del_type:
            context.bot.send_message(chat_id=get_chat_id(update, context),
                                     text=ALREADY_AT_TIER_MESSAGE,
                                     reply_markup=get_update_keyboard())
        else:
            payment(update, context, del_type, "14day-timeslot",
                    "Not at home in the coming week? Delay your delivery up to 14 days and choose a timeslot!", order_id)

    except Exception as e:
        print(e)
        context.bot.send_message(chat_id=get_chat_id(update, context),
                                 text=UPGRADE_FAIL_MESSAGE)


def upgrade_to_14daystd(update, context, order_id):
    try:
        context.bot.send_chat_action(chat_id=get_chat_id(update, context), action=ChatAction.TYPING, timeout=1)
        time.sleep(1)
        order = firestore_db.collection(u'orders').document(order_id).get()
        order_dict = order.to_dict()
        del_type = order_dict["deliveryType"]
        if "14day-standard" in del_type:
            context.bot.send_message(chat_id=get_chat_id(update, context),
                                     text=ALREADY_AT_TIER_MESSAGE,
                                     reply_markup=get_update_keyboard())
        else:
            payment(update, context, del_type, "14day-standard",
                    "Not at home in the coming week? Delay your delivery up to 14 days!", order_id)
    except Exception as e:
        print(e)
        context.bot.send_message(chat_id=get_chat_id(update, context),
                                 text=UPGRADE_FAIL_MESSAGE)

def get_time_keyboard(update, context, date, order_id):
    ReplyKeyboardRemove()
    print('reschedule-' + order_id + "-to-" + str(date)[:10] + '_9-12')
    print('reschedule-' + order_id + "-to-" + str(date)[:10] + '_12-15')
    options = [
                InlineKeyboardButton(text='9am-12pm', callback_data= 'reschedule-' + order_id + "-to-" + str(date)[:10] + '_9-12'),
               InlineKeyboardButton(text='12pm-3pm', callback_data= 'reschedule-' + order_id + "-to-" + str(date)[:10] + '_12-15'),
               InlineKeyboardButton(text='3pm-6pm', callback_data= 'reschedule-' + order_id + "-to-" + str(date)[:10] + '_15-18'),
               InlineKeyboardButton(text='6pm-10pm', callback_data= 'reschedule-' + order_id + "-to-" + str(date)[:10] +'_18-22')]
    back = InlineKeyboardButton(text='←', callback_data= 'reschedule_orders_action' + order_id),
    keyboard = InlineKeyboardMarkup([back, options])
    return keyboard

def reschedule_to_time(update, context, dateString, order_id, rescheduleTime):
    try:
        context.bot.send_chat_action(chat_id=get_chat_id(update, context), action=ChatAction.TYPING, timeout=1)
        time.sleep(1)
        date = datetime.datetime(int(dateString[0:4]), int(dateString[5:7]), int(dateString[8:10]))
        firestore_db.collection(u'orders').document(order_id).update({
            "deliveryDate": date.replace(hour=rescheduleTime)
        })
        if time == 9:
            time_string = " between 9am to 12pm"
        elif time == 12:
            time_string = " between 12pm to 3pm"
        elif time == 15:
            time_string = " between 3pm to 6pm"
        else:
            time_string = " between 6pm to 10pm"
        numReschedules = int(firestore_db.collection(u'orders').document(order_id).get().to_dict()['numReschedules']) - 1
        firestore_db.collection(u'orders').document(order_id).update({
            "numReschedules": str(numReschedules)
        })
        context.bot.send_message(chat_id=get_chat_id(update, context),
                                 text=f"Your delivery has been rescheduled to " + (
                                     date.strftime("%d/%m/%Y") + time_string + f"!\nYou now have {numReschedules} reschedules left.")
                                 , reply_markup=get_update_keyboard())
    except Exception as e:
        print(e)
        context.bot.send_message(chat_id=get_chat_id(update, context),
                                 text=UPGRADE_FAIL_MESSAGE)

def payment(update, context, current_type, new_type, type_description, order_id):
    def get_price():
        prices = {
            "standard": 3,
            "express": 5,
            "timeslot": 7,
            "14day-standard": 9,
            "14day-timeslot": 11
        }
        return prices[new_type] - prices[current_type]

    context.bot.send_invoice(chat_id=get_chat_id(update, context),
                             title=new_type,
                             description=type_description,
                             payload="ninja-scheduler/" + new_type + "/" + order_id,
                             provider_token="284685063:TEST:YTM1ZGYzNDlhMWI3",
                             currency="SGD",
                             prices=[LabeledPrice("Payment for " + new_type + " delivery", get_price() * 100)],
                             start_parameter="asdhjasdj")


# after (optional) shipping, it's the pre-checkout
def precheckout_callback(update, context):
    """Answers the PrecheckoutQuery"""
    query = update.pre_checkout_query
    # check the payload, is this from your bot?
    if 'ninja-scheduler' not in query.invoice_payload:
        # answer False pre_checkout_query
        query.answer(ok=False, error_message="Something went wrong...")
    elif 'top-up' in query.invoice_payload:
        user_id = update.callback_query.message.chat.username
        firestore_db.collection(u'users').document(user_id).update({
            "numReschedules": 2
        })
        query.answer(ok=True)
    else:
        payload_split = update.pre_checkout_query.invoice_payload.split('/')
        update_db_after_payment(payload_split[2], payload_split[1])
        query.answer(ok=True)


def update_db_after_payment(order_id, del_type):
    firestore_db.collection(u'orders').document(order_id).update({
        "deliveryType": del_type
    })


# finally, after contacting the payment provider...
def successful_payment_callback(update, context):
    """Confirms the successful payment."""
    # do something after successfully receiving payment?
    update.message.reply_text("Thank you for your payment!")


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
    dp.add_handler(CallbackQueryHandler(query_handler))

    dp.add_handler(PreCheckoutQueryHandler(precheckout_callback))
    dp.add_handler(MessageHandler(Filters.successful_payment, successful_payment_callback))

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
