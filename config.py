import os
from dotenv import load_dotenv

load_dotenv()


# ==========================================================
# BOT CONFIGURATION
# ==========================================================

BOT_TOKEN = os.getenv("BOT_TOKEN", "")

MONGO_URI = os.getenv("MONGO_URI", "")

OWNER_ID = int(os.getenv("OWNER_ID", "0"))


# ==========================================================
# WEB QUIZ FORM
# ==========================================================
# Yahan apne EXISTING quiz form ka URL lagao.
# Form ko change/rebuild karne ki zarurat nahi hai.

WEBAPP_URL = os.getenv(
    "WEBAPP_URL",
    "https://YOUR-EXISTING-FORM-URL.com"
)


# ==========================================================
# BOT BRANDING
# ==========================================================

WELCOME_IMAGE_URL = os.getenv(
    "WELCOME_IMAGE_URL",
    "https://files.catbox.moe/zzpmhu.jpg"
)

OWNER_USERNAME = os.getenv(
    "OWNER_USERNAME",
    "Telegram"
)

UPDATE_CHANNEL = os.getenv(
    "UPDATE_CHANNEL",
    "Telegram"
)


# ==========================================================
# REQUIRED ENVIRONMENT VARIABLES
# ==========================================================

if not BOT_TOKEN:
    raise ValueError(
        "BOT_TOKEN missing in Environment Variables!"
    )

if not MONGO_URI:
    raise ValueError(
        "MONGO_URI missing in Environment Variables!"
    )

if not WEBAPP_URL:
    raise ValueError(
        "WEBAPP_URL missing in Environment Variables!"
    )
