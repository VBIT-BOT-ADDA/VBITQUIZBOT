from pymongo import MongoClient
import config

client = MongoClient(config.MONGO_URI)
db = client['quiz_bot_db']

users_col = db['users']
chats_col = db['chats']
quizzes_col = db['quizzes']

# User Management
def add_user(user_id: int, username: str = None, first_name: str = None):
    users_col.update_one(
        {"_id": user_id},
        {"$set": {"username": username, "first_name": first_name}},
        upsert=True
    )

def get_all_users():
    return [user["_id"] for user in users_col.find({}, {"_id": 1})]

def count_users() -> int:
    return users_col.count_documents({})

# Chat/Group Management
def add_chat(chat_id: int, title: str = None, chat_type: str = None):
    chats_col.update_one(
        {"_id": chat_id},
        {"$set": {"title": title, "type": chat_type}},
        upsert=True
    )

def get_all_chats():
    return [chat["_id"] for chat in chats_col.find({}, {"_id": 1})]

def count_chats() -> int:
    return chats_col.count_documents({})

# Quiz Management
def save_quiz(user_id: int, quiz_data: dict) -> str:
    quiz_doc = {
        "owner_id": user_id,
        "title": quiz_data['title'],
        "description": quiz_data['description'],
        "questions": quiz_data['questions'],
        "timer": quiz_data['timer'],
        "shuffle": quiz_data['shuffle']
    }
    res = quizzes_col.insert_one(quiz_doc)
    return str(res.inserted_id)

def get_quiz_by_id(quiz_id: str) -> dict:
    from bson.objectid import ObjectId
    try:
        return quizzes_col.find_one({"_id": ObjectId(quiz_id)})
    except Exception:
        return None
      
