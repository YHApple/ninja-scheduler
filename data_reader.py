import json

import firebase_admin
from firebase_admin import credentials
from firebase_admin import firestore
cred = credentials.Certificate("./key.json")
firebase_admin.initialize_app(cred)

db = firestore.client()

f = open('result.json')

data = json.load(f)
messages = data.get("messages")

test = [1,2,3,4]

for msg in messages:
    if msg.get('type') == 'message' and msg.get('from') == 'izzuddin mawar' and isinstance(msg.get('text'), list):
        text = msg.get('text')
        if isinstance(text[0], dict) and text[0].get('type') == 'hashtag' and text[0].get('text') == "#izzusquoteoftheday":
            db.collection(u'quotes').add({'quotetext': text[1].lstrip()})
