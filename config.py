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

# Public channel example:
# FORCE_SUB_CHANNEL=@llBADAL_UPDATEll
#
# Private channel example:
# FORCE_SUB_CHANNEL=-1001234567890

FORCE_SUB_CHANNEL = os.getenv(
    "FORCE_SUB_CHANNEL",
    "",
).strip()


# Channel join/invite link
# Example:
# https://t.me/llBADAL_UPDATEll

FORCE_SUB_CHANNEL_LINK = os.getenv(
    "FORCE_SUB_CHANNEL_LINK",
    "",
).strip()


# ============================================================
# ✅ ENVIRONMENT VALIDATION
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
