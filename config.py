import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN", "")
MONGO_URI = os.getenv("MONGO_URI", "")
OWNER_ID = int(os.getenv("OWNER_ID", "0"))
WELCOME_IMAGE_URL = os.getenv("WELCOME_IMAGE_URL", "https://files.catbox.moe/zzpmhu.jpg")
OWNER_USERNAME = os.getenv("OWNER_USERNAME", "Telegram")
UPDATE_CHANNEL = os.getenv("UPDATE_CHANNEL", "Telegram")

if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN missing in Environment Variables!")
if not MONGO_URI:
    raise ValueError("MONGO_URI missing in Environment Variables!")
  
