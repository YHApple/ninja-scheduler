# What it is:
Telegram bot to send you quotes. @iqotd_bot on Telegram.
# Commands: 
/start - Gives you a hearty welcome!
/help - Shows all available commands.
/inspireme - Inspires you with a quote!
/addquote (insert quote here) - Adds a quote to the database.


# Creation & Deployment: 
Based off a tutorial: https://www.codementor.io/@karandeepbatra/part-1-how-to-create-a-telegram-bot-in-python-in-under-10-minutes-19yfdv4wrq
The above tutorial is for an echo bot. I used the concepts shown inside to create the quotes bot by retrieving data from a Cloud Firestore database. The bot is deployed on Heroku, and implements webhooks.


# Source of quotes: 
The quotes are sourced from my orientation group's telegram group. One of my peers used to send quotes of the day, with a hashtag. I wrote data_reader.py to parse through the raw JSON data that I downloaded from the Telegram group (not uploaded onto GitHub) and wrote some conditions to filter out only messages with quotes. I then added the valid quote text to Cloud Firestore using an automatically generated key.
