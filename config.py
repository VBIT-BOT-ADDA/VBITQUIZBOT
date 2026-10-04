import os
from dotenv import load_dotenv

load_dotenv()


# ============================================================
# 🤖 BOT CONFIGURATION
# ============================================================

BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
MONGO_URI = os.getenv("MONGO_URI", "").strip()

try:
    OWNER_ID = int(os.getenv("OWNER_ID", "0").strip())
except (TypeError, ValueError):
    OWNER_ID = 0


# ============================================================
# 🔐 FORCE SUBSCRIPTION / CHANNEL VERIFICATION
# ============================================================

# Public channel:
# FORCE_SUB_CHANNEL=@llBADAL_UPDATEll
#
# Private channel:
# FORCE_SUB_CHANNEL=-1004326227389

FORCE_SUB_CHANNEL = os.getenv("FORCE_SUB_CHANNEL", "").strip()

# Example:
# https://t.me/llBADAL_UPDATEll
# or private invite link:
# https://t.me/llBADAL_UPDATEll

FORCE_SUB_CHANNEL_LINK = os.getenv(
    "https://t.me/llBADAL_UPDATEll",
    "",
).strip()


# ============================================================
# ✅ REQUIRED ENVIRONMENT VARIABLES
# ============================================================

if not BOT_TOKEN:
    raise ValueError(
        "BOT_TOKEN missing in Environment Variables!"
    )

if not MONGO_URI:
    raise ValueError(
        "MONGO_URI missing in Environment Variables!"
    )

if not OWNER_ID:
    raise ValueError(
        "OWNER_ID missing or invalid in Environment Variables!"
    )

if not FORCE_SUB_CHANNEL:
    raise ValueError(
        "FORCE_SUB_CHANNEL missing in Environment Variables!"
    )

if not FORCE_SUB_CHANNEL_LINK:
    raise ValueError(
        "FORCE_SUB_CHANNEL_LINK missing in Environment Variables!"
    )
