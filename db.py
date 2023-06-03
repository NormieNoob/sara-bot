import time
import os
from dotenv import load_dotenv
from pymongo.mongo_client import MongoClient

if os.path.exists('.env'):
    load_dotenv()
    db_user = os.getenv('DB_USER')
    db_pass = os.getenv('DB_PASS')
    db_uri = os.getenv('DB_URI')
    db_name = os.getenv('DB_NAME')
else:
    db_user = os.getenv('DB_USER')
    db_pass = os.getenv('DB_PASS')
    db_uri = os.getenv('DB_URI')
    db_name = os.getenv('DB_NAME')


def db_connection():
    uri = f"mongodb+srv://{db_user}:{db_pass}@{db_uri}"
    client = MongoClient(uri)
    db = client[db_name]
    collection = db['users']
    return collection


def create_user(chat_id, user_id, firstname, username, collection):
    user_data = {
        '_id': chat_id,
        'user_id': user_id,
        'firstname': firstname,
        'username': username,
        'message_counter': 0,
        'last_message': time.time(),
        'balance': 0,
        'voiceMode': False,
        'payments': []
    }
    collection.insert_one(user_data)


def get_user_details(chat_id, collection, Users):
    user_data = collection.find_one({'_id': chat_id})
    if user_data:
        user = Users(
            chat_id=user_data['_id'],
            user_id=user_data['user_id'],
            firstname=user_data['firstname'],
            username=user_data['username'],
        )
        user.set_balance(user_data['balance'])
        user.set_voiceMode(user_data['voiceMode'])
        return user
    else:
        return None


def get_voice_mode(chat_id, collection):
    user_data = collection.find_one({'_id': chat_id})
    if user_data:
        voice_mode = user_data.get('voiceMode')
        return voice_mode
    else:
        return None


def set_voice_mode(chat_id, voice_mode, collection):
    result = collection.update_one(
        {'_id': chat_id},
        {'$set': {'voiceMode': voice_mode}}
    )
    if result.modified_count > 0:
        return True
    else:
        return False
