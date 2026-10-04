import asyncio
import logging
import random
import time
from urllib.parse import quote

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    KeyboardButtonPollType,
    Poll,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
)
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    PollAnswerHandler,
    ConversationHandler,
    ContextTypes,
    filters,
)

import config
import database


logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

QUESTIONS, TIMER, SHUFFLE = range(3)
active_sessions = {}


# ============================================================
# FORCE SUBSCRIBE CONFIG
# ============================================================
def get_force_channel():
    """
    Supports the following config names so the next config.py
    can be adapted without changing the main quiz code:
      FORCE_SUB_CHANNEL_ID
      FORCE_SUB_CHANNEL
      CHANNEL_USERNAME
      UPDATE_CHANNEL
    """
    channel_id = getattr(config, "FORCE_SUB_CHANNEL_ID", None)
    channel = getattr(config, "FORCE_SUB_CHANNEL", None)

    if not channel:
        channel = getattr(config, "CHANNEL_USERNAME", None)

    if not channel:
        channel = getattr(config, "UPDATE_CHANNEL", None)

    return channel_id or channel


def get_force_channel_link():
    link = getattr(config, "FORCE_SUB_CHANNEL_LINK", None)
    if link:
        return link

    channel = get_force_channel()

    if isinstance(channel, int):
        # Private channel IDs cannot be converted to a public t.me link.
        # The next config.py can provide FORCE_SUB_CHANNEL_LINK.
        return ""

    channel = str(channel or "").strip()

    if channel.startswith("https://t.me/"):
        return channel

    if channel.startswith("@"):
        channel = channel[1:]

    if channel:
        return f"https://t.me/{channel}"

    return ""


async def is_user_joined_channel(bot, user_id):
    """
    Check whether the user has joined the force-subscription channel.

    IMPORTANT:
    For reliable channel-member verification, the bot should be an
    administrator of the channel.
    """
    channel = get_force_channel()

    if not channel:
        # If no channel is configured, don't lock the bot.
        return True

    try:
        member = await bot.get_chat_member(
            chat_id=channel,
            user_id=user_id,
        )

        return member.status in (
            "creator",
            "administrator",
            "member",
        )
    except Exception as e:
        logger.warning("Force-subscription check failed: %s", e)
        return False


def force_join_keyboard():
    channel_link = get_force_channel_link()

    rows = []

    if channel_link:
        rows.append(
            [
                InlineKeyboardButton(
                    "➜ ᴊᴏɪɴ ᴄʜᴀɴɴᴇʟ",
                    url=channel_link,
                )
            ]
        )

    rows.append(
        [
            InlineKeyboardButton(
                "✓ ᴠᴇʀɪꜰʏ",
                callback_data="verify_join",
            )
        ]
    )

    return InlineKeyboardMarkup(rows)


async def send_force_join(update, context):
    message = update.effective_message

    if not message:
        return

    text = (
        "╭━━━〔 🔐 ᴄʜᴀɴɴᴇʟ ᴠᴇʀɪꜰɪᴄᴀᴛɪᴏɴ 〕━━━╮\n"
        "┃\n"
        "┃ ᴡᴇʟᴄᴏᴍᴇ ᴛᴏ ᴛʜᴇ ǫᴜɪᴢ ʙᴏᴛ ✨\n"
        "┃\n"
        "┃ ᴛᴏ ᴜsᴇ ᴛʜɪs ʙᴏᴛ, ᴘʟᴇᴀsᴇ ᴊᴏɪɴ\n"
        "┃ ᴏᴜʀ ᴏғғɪᴄɪᴀʟ ᴄʜᴀɴɴᴇʟ ғɪʀsᴛ.\n"
        "┃\n"
        "┃ ① ᴛᴀᴘ <b>ᴊᴏɪɴ ᴄʜᴀɴɴᴇʟ</b>\n"
        "┃ ② ᴊᴏɪɴ ᴛʜᴇ ᴄʜᴀɴɴᴇʟ\n"
        "┃ ③ ᴛᴀᴘ <b>ᴠᴇʀɪꜰʏ</b>\n"
        "┃\n"
        "╰━━━━━━━━━━━━━━━━━━━━━━╯"
    )

    await message.reply_text(
        text,
        parse_mode="HTML",
        reply_markup=force_join_keyboard(),
    )


async def verify_join(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    user = update.effective_user

    if not await is_user_joined_channel(context.bot, user.id):
        await query.answer(
            "❌ Please join the channel first.",
            show_alert=True,
        )
        return

    bot_username = context.bot.username

    if not bot_username:
        me = await context.bot.get_me()
        bot_username = me.username

    restart_url = f"https://t.me/{bot_username}?start=verified"

    await query.message.reply_text(
        "╭━━━〔 ✅ ᴠᴇʀɪꜰɪᴇᴅ 〕━━━╮\n"
        "┃\n"
        "┃ ʏᴏᴜ ʜᴀᴠᴇ ʙᴇᴇɴ ᴠᴇʀɪꜰɪᴇᴅ sᴜᴄᴄᴇssғᴜʟʟʏ. 🎉\n"
        "┃\n"
        "┃ ᴘʟᴇᴀsᴇ sᴛᴀʀᴛ ᴛʜᴇ ʙᴏᴛ ᴀɢᴀɪɴ\n"
        "┃ ᴛᴏ ᴏᴘᴇɴ ᴛʜᴇ ǫᴜɪᴢ ʙᴏᴛ.\n"
        "┃\n"
        "╰━━━━━━━━━━━━━━━━━━━━━━╯",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton(
                        "↻ ʀᴇsᴛᴀʀᴛ ʙᴏᴛ",
                        url=restart_url,
                    )
                ]
            ]
        ),
    )


# ============================================================
# QUIZ HELPERS
# ============================================================
def quiz_share_url(bot_username, quiz_id, quiz_title):
    start_url = f"https://t.me/{bot_username}?start=quiz_{quiz_id}"
    share_text = (
        f"🎯 {quiz_title}\n\n"
        "ʙʏ ǫᴜɪᴢ ʙᴏᴛ — ᴛᴀᴘ ʙᴇʟᴏᴡ ᴛᴏ ᴘʟᴀʏ!"
    )
    return (
        "https://t.me/share/url?"
        f"url={quote(start_url, safe='')}"
        f"&text={quote(share_text, safe='')}"
    )


def quiz_creation_keyboard():
    return ReplyKeyboardMarkup(
        [
            [
                KeyboardButton(
                    "📝 ᴄʀᴇᴀᴛᴇ ǫᴜɪᴢ",
                    request_poll=KeyboardButtonPollType(type="quiz"),
                )
            ],
            [
                KeyboardButton("✅ ᴅᴏɴᴇ"),
                KeyboardButton("❌ ᴄᴀɴᴄᴇʟ"),
            ],
        ],
        resize_keyboard=True,
        is_persistent=True,
    )


async def send_main_menu(update, context):
    """
    Main menu is shown ONLY after channel verification.

    The old welcome image + Owner + Updates + Help buttons are
    intentionally removed as requested.
    """
    user = update.effective_user
    chat = update.effective_chat

    if not user or not chat:
        return

    database.add_user(
        user.id,
        user.username,
        user.first_name,
    )

    if chat.type in ("group", "supergroup"):
        database.add_chat(
            chat.id,
            chat.title,
            chat.type,
        )

    if chat.type != "private":
        await chat.send_message(
            "🔐 <b>Please verify yourself in the bot's private chat first.</b>\n\n"
            "Open the bot in DM, join the required channel and press Verify.",
            parse_mode="HTML",
        )
        return

    text = (
        "╭━━━〔 🎯 ǫᴜɪᴢ ᴢᴏɴᴇ 〕━━━╮\n"
        "┃\n"
        f"┃ ᴡᴇʟᴄᴏᴍᴇ, <b>{user.first_name}</b>! ✨\n"
        "┃\n"
        "┃ ᴄʀᴇᴀᴛᴇ ʏᴏᴜʀ ᴏᴡɴ ʟɪᴠᴇ ǫᴜɪᴢ\n"
        "┃ ᴜsɪɴɢ ᴛᴇʟᴇɢʀᴀᴍ'ꜱ ɴᴀᴛɪᴠᴇ ǫᴜɪᴢ ᴘᴏʟʟs.\n"
        "┃\n"
        "┃ ʙᴜɪʟᴅ • sʜᴀʀᴇ • ᴘʟᴀʏ • ᴡɪɴ 🏆\n"
        "┃\n"
        "╰━━━━━━━━━━━━━━━━━━━━━━╯\n\n"
        "⚡ <b>ᴛᴀᴘ ᴄʀᴇᴀᴛᴇ ǫᴜɪᴢ ᴛᴏ ʙᴇɢɪɴ.</b>"
    )

    await chat.send_message(
        text,
        parse_mode="HTML",
        reply_markup=quiz_creation_keyboard(),
    )


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user

    if not user:
        return

    # Always require channel membership on /start.
    if not await is_user_joined_channel(context.bot, user.id):
        await send_force_join(update, context)
        return

    # Support /start quiz_<id> from shared quizzes.
    if context.args:
        payload = context.args[0]

        if payload.startswith("quiz_"):
            quiz_id = payload[len("quiz_"):]
            quiz = database.get_quiz_by_id(quiz_id)

            if not quiz:
                await update.effective_message.reply_text(
                    "❌ <b>Quiz not found or expired.</b>",
                    parse_mode="HTML",
                )
                return

            await send_quiz_ready_message(
                update.effective_message,
                quiz,
                quiz_id,
            )
            return

    await send_main_menu(update, context)


async def stats_command(update, context):
    if update.effective_user.id != config.OWNER_ID:
        await update.message.reply_text(
            "❌ Only bot owner can view stats."
        )
        return

    users_cnt = database.count_users()
    chats_cnt = database.count_chats()

    await update.message.reply_text(
        f"📊 <b>Bot Live Statistics</b>\n\n"
        f"👤 <b>Total Users:</b> {users_cnt}\n"
        f"👥 <b>Total Groups/Chats:</b> {chats_cnt}\n"
        f"🌐 <b>Total Active Endpoints:</b> {users_cnt + chats_cnt}",
        parse_mode="HTML",
    )


async def broadcast_command(update, context):
    if update.effective_user.id != config.OWNER_ID:
        await update.message.reply_text(
            "❌ Only owner can use broadcast."
        )
        return

    if not update.message.reply_to_message:
        await update.message.reply_text(
            "⚠️ Reply to a message with /broadcast "
            "to send it to all users and groups."
        )
        return

    msg = update.message.reply_to_message

    all_users = database.get_all_users()
    all_chats = database.get_all_chats()
    targets = list(set(all_users + all_chats))

    status_msg = await update.message.reply_text(
        f"🚀 Broadcast started to {len(targets)} targets..."
    )

    success = 0
    failed = 0

    for target_id in targets:
        try:
            await context.bot.forward_message(
                chat_id=target_id,
                from_chat_id=msg.chat_id,
                message_id=msg.message_id,
            )
            success += 1
            await asyncio.sleep(0.05)
        except Exception:
            failed += 1

    await status_msg.edit_text(
        f"✅ <b>Broadcast Completed!</b>\n\n"
        f"🎯 <b>Total Targets:</b> {len(targets)}\n"
        f"✅ <b>Success:</b> {success}\n"
        f"❌ <b>Failed:</b> {failed}",
        parse_mode="HTML",
    )


async def button_click(update, context):
    query = update.callback_query
    await query.answer()

    if query.data == "main_menu":
        await send_main_menu(update, context)


async def create_quiz_start(update, context):
    context.user_data.pop("current_quiz", None)

    if update.effective_chat.type != "private":
        await update.message.reply_text(
            "⚠️ Create Quiz is available in private chat only."
        )
        return ConversationHandler.END

    await update.message.reply_text(
        "🎯 <b>Quiz creation started.</b>\n\n"
        "Tap <b>📝 Create Quiz</b> below.\n"
        "Telegram's native <b>New Poll → Quiz</b> screen will open.",
        parse_mode="HTML",
        reply_markup=quiz_creation_keyboard(),
    )

    return QUESTIONS


def initialize_quiz(user):
    return {
        "title": f"Quiz by {user.first_name}",
        "description": "No description provided.",
        "questions": [],
        "timer": 15,
        "shuffle": "ɴᴏ sʜᴜꜰꜰʟᴇ",
    }


async def process_question(update, context):
    if not update.message or not update.message.poll:
        return QUESTIONS

    if update.effective_chat.type != "private":
        await update.message.reply_text(
            "⚠️ <b>Quiz creation is available in private chat only.</b>",
            parse_mode="HTML",
        )
        return ConversationHandler.END

    poll = update.message.poll

    if poll.type != Poll.QUIZ:
        await update.message.reply_text(
            "❌ Please create a <b>Quiz</b> poll.",
            parse_mode="HTML",
        )
        return QUESTIONS

    if not context.user_data.get("current_quiz"):
        context.user_data["current_quiz"] = initialize_quiz(
            update.effective_user
        )

    current_quiz = context.user_data["current_quiz"]

    current_quiz["questions"].append(
        {
            "question": poll.question,
            "options": [option.text for option in poll.options],
            "correct_option_id": poll.correct_option_id,
            "explanation": poll.explanation or "",
        }
    )

    count = len(current_quiz["questions"])

    await update.message.reply_text(
        f"✅ <b>Question #{count} added!</b>\n\n"
        "📝 Create another question or tap <b>Done</b>.\n\n"
        "Optional:\n"
        "<code>/title My Quiz</code>\n"
        "<code>/description Your description</code>",
        parse_mode="HTML",
        reply_markup=quiz_creation_keyboard(),
    )

    return QUESTIONS


async def set_title(update, context):
    current_quiz = context.user_data.get("current_quiz")

    if not current_quiz:
        await update.message.reply_text(
            "Start quiz creation first."
        )
        return QUESTIONS

    title = " ".join(context.args).strip()

    if not title:
        await update.message.reply_text(
            "Usage:\n<code>/title My Quiz Title</code>",
            parse_mode="HTML",
        )
        return QUESTIONS

    current_quiz["title"] = title

    await update.message.reply_text(
        f"✅ Quiz title changed to:\n<b>{title}</b>",
        parse_mode="HTML",
        reply_markup=quiz_creation_keyboard(),
    )

    return QUESTIONS


async def set_description(update, context):
    current_quiz = context.user_data.get("current_quiz")

    if not current_quiz:
        await update.message.reply_text(
            "Start quiz creation first."
        )
        return QUESTIONS

    description = " ".join(context.args).strip()

    if not description:
        await update.message.reply_text(
            "Usage:\n<code>/description Your quiz description</code>",
            parse_mode="HTML",
        )
        return QUESTIONS

    current_quiz["description"] = description

    await update.message.reply_text(
        "✅ Quiz description updated.",
        reply_markup=quiz_creation_keyboard(),
    )

    return QUESTIONS


async def finish_questions(update, context):
    current_quiz = context.user_data.get("current_quiz")

    if not current_quiz or not current_quiz.get("questions"):
        await update.message.reply_text(
            "❌ Add at least one Quiz Poll first.",
            reply_markup=quiz_creation_keyboard(),
        )
        return QUESTIONS

    keyboard = [
        [
            InlineKeyboardButton("𝟷𝟶 sᴇᴄ", callback_data="time_10"),
            InlineKeyboardButton("𝟷𝟻 sᴇᴄ", callback_data="time_15"),
            InlineKeyboardButton("𝟹𝟶 sᴇᴄ", callback_data="time_30"),
        ],
        [
            InlineKeyboardButton("𝟺𝟻 sᴇᴄ", callback_data="time_45"),
            InlineKeyboardButton("𝟷 ᴍɪɴ", callback_data="time_60"),
        ],
    ]

    await update.message.reply_text(
        "⏱ <b>Select timer per question:</b>",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )

    await update.message.reply_text(
        "Quiz questions are complete.",
        reply_markup=ReplyKeyboardRemove(),
    )

    return TIMER


async def process_timer(update, context):
    query = update.callback_query
    await query.answer()

    current_quiz = context.user_data.get("current_quiz")

    if not current_quiz:
        await query.message.reply_text(
            "❌ Quiz session expired."
        )
        return ConversationHandler.END

    current_quiz["timer"] = int(
        query.data.split("_", 1)[1]
    )

    keyboard = [
        [
            InlineKeyboardButton(
                "sʜᴜꜰꜰʟᴇ ᴀʟʟ",
                callback_data="shuf_all",
            ),
            InlineKeyboardButton(
                "ɴᴏ sʜᴜꜰꜰʟᴇ",
                callback_data="shuf_none",
            ),
        ]
    ]

    await query.message.reply_text(
        "🔀 <b>Shuffle options?</b>",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )

    return SHUFFLE


async def process_shuffle(update, context):
    query = update.callback_query
    await query.answer()

    current_quiz = context.user_data.get("current_quiz")

    if not current_quiz:
        await query.message.reply_text(
            "❌ Quiz session expired."
        )
        return ConversationHandler.END

    user_id = update.effective_user.id
    creator = update.effective_user

    current_quiz["shuffle"] = (
        "sʜᴜꜰꜰʟᴇ ᴀʟʟ"
        if query.data == "shuf_all"
        else "ɴᴏ sʜᴜꜰꜰʟᴇ"
    )
    current_quiz["creator_username"] = creator.username or ""

    quiz_id = database.save_quiz(
        user_id,
        current_quiz,
    )

    creator_display = (
        f"@{creator.username}"
        if creator.username
        else creator.first_name
    )

    bot_username = context.bot.username
    if not bot_username:
        me = await context.bot.get_me()
        bot_username = me.username

    share_url = quiz_share_url(
        bot_username,
        quiz_id,
        current_quiz["title"],
    )

    summary_msg = (
        "╭━━━〔 🎉 ǫᴜɪᴢ ᴄʀᴇᴀᴛᴇᴅ 〕━━━╮\n"
        "┃\n"
        f"┃ 🎯 <b>{current_quiz['title']}</b>\n"
        f"┃ ❓ {len(current_quiz['questions'])} question(s)\n"
        f"┃ ⏱ {current_quiz['timer']} sec/question\n"
        f"┃ 🔀 {current_quiz['shuffle']}\n"
        f"┃ 👤 ʙʏ {creator_display}\n"
        "┃\n"
        "╰━━━━━━━━━━━━━━━━━━━━━━╯\n\n"
        "📤 Share the quiz anywhere and let others play!"
    )

    keyboard = [
        [
            InlineKeyboardButton(
                "▶️ sᴛᴀʀᴛ ǫᴜɪᴢ",
                callback_data=f"startquiz_{quiz_id}",
            )
        ],
        [
            InlineKeyboardButton(
                "👥 sᴛᴀʀᴛ ɪɴ ɢʀᴏᴜᴘ",
                url=f"https://t.me/{bot_username}?startgroup=quiz_{quiz_id}",
            )
        ],
        [
            InlineKeyboardButton(
                "📤 sʜᴀʀᴇ ǫᴜɪᴢ",
                url=share_url,
            )
        ],
    ]

    await query.message.reply_text(
        summary_msg,
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )

    context.user_data.pop("current_quiz", None)

    return ConversationHandler.END


async def send_quiz_ready_message(message, quiz, quiz_id):
    description = (
        quiz.get("description") or
        "No description provided."
    ).strip()

    if message.chat.type in ("group", "supergroup"):
        ready_msg = (
            "╭━━━〔 🎯 ǫᴜɪᴢ ᴀʀᴇɴᴀ 〕━━━╮\n"
            "┃\n"
            "┃ 🔥 <b>ARE YOU READY FOR THE QUIZ?</b>\n"
            "┃\n"
            f"┃ 📚 <b>{quiz['title']}</b>\n"
            "┃\n"
            f"┃ 📝 <b>Description:</b>\n┃ {description}\n"
            "┃\n"
            f"┃ ❓ <b>Questions:</b> {len(quiz['questions'])}\n"
            f"┃ ⏱ <b>Time:</b> {quiz['timer']} sec/question\n"
            f"┃ 🔀 <b>Mode:</b> {quiz.get('shuffle', 'No Shuffle')}\n"
            "┃\n"
            "┃ 🏆 Questions will appear one by one.\n"
            "┃ ⚡ Beat the timer and get the highest score!\n"
            "┃\n"
            "╰━━━━━━━━━━━━━━━━━━━━━━╯"
        )
        button_text = "✅ ʏᴇs, ɪ ᴀᴍ ʀᴇᴀᴅʏ ғᴏʀ ǫᴜɪᴢ"
    else:
        ready_msg = (
            f"🎯 <b>{quiz['title']}</b>\n\n"
            f"📝 {description}\n\n"
            f"❓ Questions: {len(quiz['questions'])}\n"
            f"⏱ {quiz['timer']} sec/question\n"
            f"🔀 {quiz.get('shuffle', 'No Shuffle')}\n\n"
            "Press the button below when you're ready."
        )
        button_text = "✅ ɪ'ᴍ ʀᴇᴀᴅʏ"

    await message.reply_text(
        ready_msg,
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton(
                        button_text,
                        callback_data=f"runquiz_{quiz_id}_0",
                    )
                ]
            ]
        ),
    )


async def start_quiz_session(update, context):
    query = update.callback_query
    await query.answer()

    try:
        quiz_id = query.data.split("_", 1)[1]
    except (IndexError, ValueError):
        await query.message.reply_text("❌ Invalid quiz ID.")
        return

    quiz = database.get_quiz_by_id(quiz_id)

    if not quiz:
        await query.message.reply_text(
            "❌ Quiz not found!"
        )
        return

    await send_quiz_ready_message(
        query.message,
        quiz,
        quiz_id,
    )


async def run_next_question(update, context):
    query = update.callback_query

    try:
        _, quiz_id, q_idx_text = query.data.split("_", 2)
        q_idx = int(q_idx_text)
    except (ValueError, IndexError):
        await query.answer(
            "Invalid quiz session.",
            show_alert=True,
        )
        return

    quiz = database.get_quiz_by_id(quiz_id)

    if not quiz:
        await query.answer(
            "Quiz not found!",
            show_alert=True,
        )
        return

    user_id = update.effective_user.id

    if user_id in active_sessions:
        await query.answer(
            "A quiz is already running for you.",
            show_alert=True,
        )
        return

    await query.answer()

    active_sessions[user_id] = {
        "start_time": time.time(),
        "correct": 0,
        "wrong": 0,
        "current_q": -1,
        "quiz_id": str(quiz_id),
        "chat_id": query.message.chat_id,
        "answered_polls": set(),
    }

    await send_question(
        context,
        user_id,
        query.message.chat_id,
        quiz_id,
        q_idx,
    )


async def send_question(
    context,
    user_id,
    chat_id,
    quiz_id,
    q_idx,
):
    quiz = database.get_quiz_by_id(quiz_id)

    if not quiz:
        active_sessions.pop(user_id, None)
        await context.bot.send_message(
            chat_id=chat_id,
            text="❌ Quiz not found.",
        )
        return

    session = active_sessions.get(user_id)

    if not session:
        return

    if "questions" not in session:
        session["questions"] = list(
            quiz.get("questions", [])
        )

        if quiz.get("shuffle") in (
            "Shuffle All",
            "sʜᴜꜰꜰʟᴇ ᴀʟʟ",
        ):
            random.shuffle(session["questions"])

    questions = session["questions"]

    if q_idx >= len(questions):
        await finish_quiz_results(
            context,
            user_id,
            chat_id,
            quiz,
        )
        return

    q = questions[q_idx]

    poll_msg = await context.bot.send_poll(
        chat_id=chat_id,
        question=(
            f"[{q_idx + 1}/{len(questions)}] "
            f"{q['question']}"
        ),
        options=q["options"],
        type=Poll.QUIZ,
        correct_option_id=q["correct_option_id"],
        explanation=q.get("explanation") or None,
        is_anonymous=False,
        open_period=int(quiz["timer"]),
        allows_multiple_answers=False,
    )

    poll_id = poll_msg.poll.id

    context.bot_data[poll_id] = {
        "user_id": user_id,
        "quiz_id": str(quiz_id),
        "q_idx": q_idx,
        "correct_id": q["correct_option_id"],
        "chat_id": chat_id,
    }

    session["current_q"] = q_idx
    session["current_poll_id"] = poll_id

    asyncio.create_task(
        auto_advance_question(
            context,
            user_id,
            chat_id,
            quiz_id,
            q_idx,
            int(quiz["timer"]),
            poll_id,
        )
    )


async def auto_advance_question(
    context,
    user_id,
    chat_id,
    quiz_id,
    q_idx,
    timer_value,
    poll_id,
):
    try:
        await asyncio.sleep(timer_value + 1)
    except asyncio.CancelledError:
        return

    session = active_sessions.get(user_id)

    if not session:
        return

    if session.get("current_poll_id") != poll_id:
        return

    quiz = database.get_quiz_by_id(quiz_id)

    if not quiz:
        active_sessions.pop(user_id, None)
        return

    next_q_idx = q_idx + 1

    if next_q_idx < len(quiz.get("questions", [])):
        await context.bot.send_message(
            chat_id=chat_id,
            text=(
                f"➡️ <b>Question {next_q_idx + 1} "
                "coming up...</b>"
            ),
            parse_mode="HTML",
        )

        await send_question(
            context,
            user_id,
            chat_id,
            quiz_id,
            next_q_idx,
        )
    else:
        await finish_quiz_results(
            context,
            user_id,
            chat_id,
            quiz,
        )


async def handle_poll_answer(update, context):
    answer = update.poll_answer
    poll_id = answer.poll_id
    poll_info = context.bot_data.get(poll_id)

    if not poll_info:
        return

    user_id = poll_info["user_id"]

    if answer.user.id != user_id:
        return

    session = active_sessions.get(user_id)

    if not session:
        return

    answered_polls = session.setdefault(
        "answered_polls",
        set(),
    )

    if poll_id in answered_polls:
        return

    answered_polls.add(poll_id)

    selected = (
        answer.option_ids[0]
        if answer.option_ids
        else -1
    )

    if selected == poll_info["correct_id"]:
        session["correct"] += 1
    else:
        session["wrong"] += 1


async def finish_quiz_results(
    context,
    user_id,
    chat_id,
    quiz,
):
    session = active_sessions.get(user_id)

    if not session:
        return

    time_taken = int(
        time.time() - session["start_time"]
    )

    total_q = len(
        quiz.get("questions", [])
    )

    correct = session["correct"]
    wrong = session["wrong"]
    missed = max(
        0,
        total_q - (correct + wrong),
    )

    creator_username = (
        quiz.get("creator_username") or ""
    )

    creator_line = (
        f"👤 <b>Created by:</b> @{creator_username}\n\n"
        if creator_username
        else ""
    )

    bot_username = context.bot.username

    if not bot_username:
        me = await context.bot.get_me()
        bot_username = me.username

    share_url = quiz_share_url(
        bot_username,
        session["quiz_id"],
        quiz["title"],
    )

    results_text = (
        "╭━━━〔 🏁 ǫᴜɪᴢ ғɪɴɪsʜᴇᴅ 〕━━━╮\n"
        "┃\n"
        f"┃ 🎯 <b>{quiz['title']}</b>\n"
        f"┃ {creator_line}"
        f"┃ 📊 <b>ʏᴏᴜʀ ᴀɴsᴡᴇʀs</b>\n"
        "┃\n"
        f"┃ ✅ ᴄᴏʀʀᴇᴄᴛ — <b>{correct}</b>\n"
        f"┃ ❌ ᴡʀᴏɴɢ — <b>{wrong}</b>\n"
        f"┃ ⏳ ᴍɪssᴇᴅ — <b>{missed}</b>\n"
        f"┃ ⏱ ᴛɪᴍᴇ — <b>{time_taken} sec</b>\n"
        "┃\n"
        "╰━━━━━━━━━━━━━━━━━━━━━━╯\n\n"
        "🏆 <b>Qᴜɪᴢ ᴄᴏᴍᴘʟᴇᴛᴇᴅ!</b>"
    )

    await context.bot.send_message(
        chat_id=chat_id,
        text=results_text,
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton(
                        "📤 sʜᴀʀᴇ ǫᴜɪᴢ",
                        url=share_url,
                    )
                ]
            ]
        ),
    )

    active_sessions.pop(
        user_id,
        None,
    )


async def stop_command(update, context):
    user_id = update.effective_user.id

    if user_id in active_sessions:
        active_sessions.pop(user_id, None)

        await update.message.reply_text(
            "🛑 <b>Active quiz session stopped.</b>",
            parse_mode="HTML",
        )
    else:
        await update.message.reply_text(
            "ℹ️ No active quiz session."
        )


async def cancel(update, context):
    context.user_data.pop(
        "current_quiz",
        None,
    )

    await update.message.reply_text(
        "❌ Quiz creation cancelled.",
        reply_markup=ReplyKeyboardRemove(),
    )

    return ConversationHandler.END


def main():
    app = (
        Application.builder()
        .token(config.BOT_TOKEN)
        .read_timeout(30)
        .write_timeout(30)
        .connect_timeout(30)
        .pool_timeout(30)
        .build()
    )

    conv_handler = ConversationHandler(
        entry_points=[
            CommandHandler(
                "newquiz",
                create_quiz_start,
            ),
            MessageHandler(
                filters.POLL,
                process_question,
            ),
        ],
        states={
            QUESTIONS: [
                CommandHandler(
                    "done",
                    finish_questions,
                ),
                CommandHandler(
                    "title",
                    set_title,
                ),
                CommandHandler(
                    "description",
                    set_description,
                ),
                CommandHandler(
                    "cancel",
                    cancel,
                ),
                MessageHandler(
                    filters.Regex(r"^✅ ᴅᴏɴᴇ$"),
                    finish_questions,
                ),
                MessageHandler(
                    filters.Regex(r"^❌ ᴄᴀɴᴄᴇʟ$"),
                    cancel,
                ),
                MessageHandler(
                    filters.POLL,
                    process_question,
                ),
            ],
            TIMER: [
                CallbackQueryHandler(
                    process_timer,
                    pattern=r"^time_",
                )
            ],
            SHUFFLE: [
                CallbackQueryHandler(
                    process_shuffle,
                    pattern=r"^shuf_",
                )
            ],
        },
        fallbacks=[
            CommandHandler(
                "cancel",
                cancel,
            )
        ],
        allow_reentry=True,
    )

    # /start performs force-subscription verification first.
    app.add_handler(
        CommandHandler(
            "start",
            start,
        )
    )

    app.add_handler(
        CommandHandler(
            "stats",
            stats_command,
        )
    )

    app.add_handler(
        CommandHandler(
            "broadcast",
            broadcast_command,
        )
    )

    app.add_handler(
        CommandHandler(
            "stop",
            stop_command,
        )
    )

    # Force-subscription Verify button.
    app.add_handler(
        CallbackQueryHandler(
            verify_join,
            pattern=r"^verify_join$",
        )
    )

    # Quiz creation.
    app.add_handler(conv_handler)

    # Quiz execution.
    app.add_handler(
        CallbackQueryHandler(
            start_quiz_session,
            pattern=r"^startquiz_",
        )
    )

    app.add_handler(
        CallbackQueryHandler(
            run_next_question,
            pattern=r"^runquiz_",
        )
    )

    # Quiz poll answers.
    app.add_handler(
        PollAnswerHandler(
            handle_poll_answer,
        )
    )

    # Remaining callback handlers.
    app.add_handler(
        CallbackQueryHandler(
            button_click,
        )
    )

    logger.info(
        "Quiz Bot started with force-subscription made by @llMR_BADALll, "
        "native Quiz Polls, MongoDB and auto-next questions."
    )

    app.run_polling(
        drop_pending_updates=True
    )


if __name__ == "__main__":
    main()
