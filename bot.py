import asyncio
import io
import logging
import random
import time
import urllib.request
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

# Conversation states
QUESTIONS, TIMER, SHUFFLE = range(3)

# Running quiz sessions
active_sessions = {}


def get_photo_bytes(url):
    """Download the configured welcome image and reject empty responses."""
    if not url:
        return None

    try:
        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
            },
        )
        with urllib.request.urlopen(req, timeout=15) as response:
            data = response.read()

        if not data:
            logger.warning("Welcome image URL returned empty data.")
            return None

        return io.BytesIO(data)
    except Exception as e:
        logger.warning("Welcome image download failed: %s", e)
        return None


def quiz_share_url(bot_username, quiz_id, quiz_title):
    """Build Telegram's native Share dialog URL for a saved quiz."""
    start_url = f"https://t.me/{bot_username}?start=quiz_{quiz_id}"
    share_text = f"🎯 {quiz_title}\n\nʙʏ ǫᴜɪᴢ ʙᴏᴛ — ᴛᴀᴘ ʙᴇʟᴏᴡ ᴛᴏ ᴘʟᴀʏ!"
    return (
        "https://t.me/share/url?"
        f"url={quote(start_url, safe='')}"
        f"&text={quote(share_text, safe='')}"
    )


def quiz_creation_keyboard():
    """
    Telegram native Quiz button.

    Pressing 'Create Quiz' opens Telegram's own New Poll composer
    directly in QUIZ mode. No website/webapp is used.
    """
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


async def send_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    chat = update.effective_chat

    if not user or not chat:
        return

    database.add_user(user.id, user.username, user.first_name)

    if chat.type in ("group", "supergroup"):
        database.add_chat(chat.id, chat.title, chat.type)

    is_private = chat.type == "private"

    if is_private:
        caption_text = (
            "<b>╭━━━〔 🎯 ǫᴜɪᴢ ᴢᴏɴᴇ 〕━━━╮</b>\n"
            "<b>┃</b> ᴡᴇʟᴄᴏᴍᴇ, " + f"<b>{user.first_name}</b>" + "! ✨\n"
            "<b>┃</b> ᴛᴜʀɴ ʏᴏᴜʀ ɪᴅᴇᴀs ɪɴᴛᴏ ᴀ ʟɪᴠᴇ ǫᴜɪᴢ.\n"
            "<b>┃</b> ᴄʀᴇᴀᴛᴇ ᴘᴏʟʟs ᴅɪʀᴇᴄᴛʟʏ ᴜsɪɴɢ ᴛᴇʟᴇɢʀᴀᴍ'ꜱ ɴᴀᴛɪᴠᴇ ǫᴜɪᴢ ᴍᴏᴅᴇ.\n"
            "<b>┃</b> ᴄʜᴏᴏsᴇ ᴛɪᴍᴇʀ • sʜᴜꜰꜰʟᴇ • sᴛᴀʀᴛ • sʜᴀʀᴇ.\n"
            "<b>┃</b> ᴍᴀᴋᴇ ɪᴛ. sʜᴀʀᴇ ɪᴛ. ᴘʟᴀʏ ɪᴛ. 🏆\n"
            "<b>╰━━━━━━━━━━━━━━━━━━━━╯</b>\n\n"
            "<b>⚡ ᴛᴀᴘ ʙᴇʟᴏᴡ ᴛᴏ ᴄʀᴇᴀᴛᴇ ʏᴏᴜʀ ǫᴜɪᴢ.</b>"
        )
    else:
        caption_text = (
            "<b>╭━━━〔 🎯 ǫᴜɪᴢ ᴀʀᴇɴᴀ 〕━━━╮</b>\n"
            "<b>┃</b> ᴀ ɴᴇᴡ ǫᴜɪᴢ ʜᴀs ʟᴀɴᴅᴇᴅ ʜᴇʀᴇ. 🔥\n"
            "<b>┃</b> ᴄʀᴇᴀᴛᴇ ɪᴛ ɪɴ ᴘʀɪᴠᴀᴛᴇ ᴄʜᴀᴛ, ᴛʜᴇɴ sʜᴀʀᴇ ɪᴛ ʜᴇʀᴇ.\n"
            "<b>┃</b> ǫᴜᴇsᴛɪᴏɴs ᴀᴘᴘᴇᴀʀ ᴏɴᴇ-ʙʏ-ᴏɴᴇ ᴀғᴛᴇʀ ʏᴏᴜ ᴀʀᴇ ʀᴇᴀᴅʏ.\n"
            "<b>╰━━━━━━━━━━━━━━━━━━━━╯</b>"
        )

    keyboard = [
        [
            InlineKeyboardButton(
                "ᴏᴡɴᴇʀ",
                url=f"https://t.me/{config.OWNER_USERNAME.lstrip('@')}",
            ),
            InlineKeyboardButton(
                "ᴜᴘᴅᴀᴛᴇs",
                url=f"https://t.me/{config.UPDATE_CHANNEL.lstrip('@')}",
            ),
        ],
        [
            InlineKeyboardButton(
                "ʜᴇʟᴘ & ᴄᴏᴍᴍᴀɴᴅs",
                callback_data="help_commands",
            )
        ],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    target_message = update.message
    if update.callback_query:
        target_message = update.callback_query.message

    # Send the configured welcome image directly to Telegram.
    # This avoids the "File must be non-empty" error caused by an
    # empty/failed urllib download stream.
    image_sent = False
    if config.WELCOME_IMAGE_URL:
        try:
            await target_message.reply_photo(
                photo=config.WELCOME_IMAGE_URL,
                caption=caption_text,
                parse_mode="HTML",
                reply_markup=reply_markup,
            )
            image_sent = True
        except Exception as e:
            logger.warning("Direct welcome image failed: %s", e)

            # Second attempt: download the image ourselves and verify that
            # Telegram receives non-empty bytes.
            photo_stream = get_photo_bytes(config.WELCOME_IMAGE_URL)
            if photo_stream is not None:
                try:
                    await target_message.reply_photo(
                        photo=photo_stream,
                        caption=caption_text,
                        parse_mode="HTML",
                        reply_markup=reply_markup,
                    )
                    image_sent = True
                except Exception as fallback_error:
                    logger.warning(
                        "Downloaded welcome image also failed: %s",
                        fallback_error,
                    )

    if not image_sent:
        await target_message.reply_text(
            caption_text,
            parse_mode="HTML",
            reply_markup=reply_markup,
        )

    # Telegram only allows request_poll buttons in private chats.
    # Never attach a request_poll keyboard to a group/supergroup.
    if is_private:
        await target_message.reply_text(
            "✨ <b>ᴄʀᴇᴀᴛᴇ ʏᴏᴜʀ ǫᴜɪᴢ ʀɪɢʜᴛ ɪɴ ᴛᴇʟᴇɢʀᴀᴍ</b>\n\n"
            "📝 ᴛᴀᴘ <b>ᴄʀᴇᴀᴛᴇ ǫᴜɪᴢ</b> → ɴᴀᴛɪᴠᴇ ǫᴜɪᴢ ᴘᴏʟʟ.\n"
            "➕ ᴀᴅᴅ ᴀs ᴍᴀɴʏ ǫᴜᴇsᴛɪᴏɴs ᴀs ʏᴏᴜ ᴡᴀɴᴛ.\n"
            "✅ ᴡʜᴇɴ ᴅᴏɴᴇ, ᴛᴀᴘ <b>ᴅᴏɴᴇ</b>.",
            parse_mode="HTML",
            reply_markup=quiz_creation_keyboard(),
        )
    else:
        await target_message.reply_text(
            "📌 <b>ǫᴜɪᴢ ᴄᴏɴᴛʀᴏʟ</b>\n\n"
            "ᴄʀᴇᴀᴛᴇ ᴛʜᴇ ǫᴜɪᴢ ɪɴ ᴘʀɪᴠᴀᴛᴇ ᴄʜᴀᴛ, ᴛʜᴇɴ sʜᴀʀᴇ ᴛʜᴇ ǫᴜɪᴢ ᴛᴏ ᴛʜɪs ɢʀᴏᴜᴘ.",
            parse_mode="HTML",
        )


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Support both private and group deep links:
    # /start quiz_<id>
    if context.args:
        payload = context.args[0]
        if payload.startswith("quiz_"):
            quiz_id = payload[len("quiz_") :]
            quiz = database.get_quiz_by_id(quiz_id)

            if not quiz:
                await update.effective_message.reply_text(
                    "❌ Quiz not found or expired."
                )
                return

            await send_quiz_ready_message(
                update.effective_message,
                quiz,
                quiz_id,
            )
            return

    await send_main_menu(update, context)


async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != config.OWNER_ID:
        await update.message.reply_text("❌ Only bot owner can view stats.")
        return

    users_cnt = database.count_users()
    chats_cnt = database.count_chats()

    msg = (
        f"📊 <b>Bot Live Statistics</b>\n\n"
        f"👤 <b>Total Users:</b> {users_cnt}\n"
        f"👥 <b>Total Groups/Chats:</b> {chats_cnt}\n"
        f"🌐 <b>Total Active Endpoints:</b> {users_cnt + chats_cnt}"
    )

    await update.message.reply_text(msg, parse_mode="HTML")


async def broadcast_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != config.OWNER_ID:
        await update.message.reply_text("❌ Only owner can use broadcast.")
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


async def button_click(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "help_commands":
        help_text = (
            "<b>Help & Commands</b>\n\n"
            "/start - Start the bot\n"
            "/newquiz - Start quiz creation\n"
            "/title My Quiz - Change quiz title\n"
            "/description Text - Change quiz description\n"
            "/done - Finish adding questions\n"
            "/cancel - Cancel quiz creation\n"
            "/stop - Stop active quiz session\n"
            "/stats - Bot statistics (Owner Only)\n"
            "/broadcast - Broadcast (Owner Only)\n\n"
            "<b>Quiz creation:</b>\n"
            "Press 📝 Create Quiz to open Telegram's native "
            "New Poll → Quiz screen."
        )

        keyboard = [
            [
                InlineKeyboardButton(
                    "ʙᴀᴄᴋ ᴛᴏ ᴍᴀɪɴ ᴍᴇɴᴜ",
                    callback_data="main_menu",
                )
            ]
        ]

        await query.message.reply_text(
            help_text,
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(keyboard),
        )

    elif query.data == "main_menu":
        await send_main_menu(update, context)


async def create_quiz_start(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    context.user_data.pop("current_quiz", None)

    message = update.message

    if update.callback_query:
        await update.callback_query.answer()
        message = update.callback_query.message

    await message.reply_text(
        "🎯 <b>Quiz creation started.</b>\n\n"
        "Press <b>📝 Create Quiz</b> below.\n"
        "Telegram's native <b>New Poll → Quiz</b> screen will open.\n\n"
        "Create your first quiz poll there and send it to me.",
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


async def process_question(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    """
    Receives the native Telegram quiz poll created by the user.

    This function also acts as the ConversationHandler entry point,
    so the first native poll can start the quiz creation flow directly.
    """
    if not update.message or not update.message.poll:
        return QUESTIONS

    if update.effective_chat.type != "private":
        await update.message.reply_text(
            "⚠️ <b>Quiz creation is available in private chat only.</b>\n\n"
            "Open the bot in private chat and press 📝 Create Quiz.",
            parse_mode="HTML",
        )
        return QUESTIONS

    poll = update.message.poll

    if poll.type != Poll.QUIZ:
        await update.message.reply_text(
            "❌ Please create a <b>Quiz</b> poll, not a regular poll.",
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
        "Press <b>📝 Create Quiz</b> for another question.\n"
        "When all questions are added, press <b>✅ Done</b>.\n\n"
        "Optional:\n"
        "<code>/title My Quiz</code>\n"
        "<code>/description Your description</code>",
        parse_mode="HTML",
        reply_markup=quiz_creation_keyboard(),
    )

    return QUESTIONS


async def set_title(update: Update, context: ContextTypes.DEFAULT_TYPE):
    current_quiz = context.user_data.get("current_quiz")

    if not current_quiz:
        await update.message.reply_text(
            "Start quiz creation first with 📝 Create Quiz."
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


async def set_description(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    current_quiz = context.user_data.get("current_quiz")

    if not current_quiz:
        await update.message.reply_text(
            "Start quiz creation first with 📝 Create Quiz."
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


async def finish_questions(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    current_quiz = context.user_data.get("current_quiz")

    if not current_quiz or not current_quiz.get("questions"):
        await update.message.reply_text(
            "❌ Add at least one Quiz Poll before pressing Done.",
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

    # Remove native-poll creation keyboard while choosing settings.
    await update.message.reply_text(
        "Quiz questions are complete. Choose the timer above.",
        reply_markup=ReplyKeyboardRemove(),
    )

    return TIMER


async def process_timer(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    query = update.callback_query
    await query.answer()

    current_quiz = context.user_data.get("current_quiz")

    if not current_quiz:
        await query.message.reply_text("❌ Quiz session expired. Start again.")
        return ConversationHandler.END

    timer_value = int(query.data.split("_", 1)[1])
    current_quiz["timer"] = timer_value

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


async def process_shuffle(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    query = update.callback_query
    await query.answer()

    current_quiz = context.user_data.get("current_quiz")

    if not current_quiz:
        await query.message.reply_text("❌ Quiz session expired. Start again.")
        return ConversationHandler.END

    user_id = update.effective_user.id

    current_quiz["shuffle"] = (
        "sʜᴜꜰꜰʟᴇ ᴀʟʟ"
        if query.data == "shuf_all"
        else "ɴᴏ sʜᴜꜰꜰʟᴇ"
    )

    creator = update.effective_user
    current_quiz["creator_username"] = creator.username or ""

    quiz_id = database.save_quiz(user_id, current_quiz)

    quiz_info = current_quiz
    creator_display = (
        f"@{quiz_info['creator_username']}"
        if quiz_info.get("creator_username")
        else f"{creator.first_name}"
    )

    bot_username = context.bot.username

    if not bot_username:
        me = await context.bot.get_me()
        bot_username = me.username

    share_url = quiz_share_url(
        bot_username,
        quiz_id,
        quiz_info["title"],
    )

    summary_msg = (
        "👍 <b>Quiz Created Successfully!</b>\n\n"
        f"<b>{quiz_info['title']}</b>\n"
        f"<i>{len(quiz_info['questions'])} question(s) · "
        f"{quiz_info['timer']} sec/question</i>\n"
        f"🔀 <b>{quiz_info['shuffle']}</b>\n"
        f"👤 <b>Created by:</b> {creator_display}\n\n"
        f"<b>Private Start Link:</b>\n"
        f"<code>https://t.me/{bot_username}?start=quiz_{quiz_id}</code>\n\n"
        f"<b>Group Start:</b> Use the <b>Start quiz in group</b> button below."
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


async def send_quiz_ready_message(
    message,
    quiz,
    quiz_id,
):
    chat_type = message.chat.type

    description = (quiz.get("description") or "No description provided.").strip()

    if chat_type in ("group", "supergroup"):
        ready_msg = (
            "🎯 <b>QUIZ TIME — ARE YOU READY?</b>\n\n"
            f"📚 <b>{quiz['title']}</b>\n\n"
            f"📝 <b>Description:</b>\n{description}\n\n"
            f"❓ <b>Total Questions:</b> {len(quiz['questions'])}\n"
            f"⏱ <b>Time Per Question:</b> {quiz['timer']} seconds\n"
            f"🔀 <b>Mode:</b> {quiz.get('shuffle', 'No Shuffle')}\n\n"
            "🔥 <b>Get ready!</b>\n"
            "Questions will appear <b>one by one</b> after you press "
            "<b>YES, I AM READY FOR QUIZ</b>.\n\n"
            "🏆 Answer each question before the timer ends."
        )
        button_text = "✅ ʏᴇs, ɪ ᴀᴍ ʀᴇᴀᴅʏ ғᴏʀ ǫᴜɪᴢ"
    else:
        ready_msg = (
            f"🎲 <b>Get ready for '{quiz['title']}'</b>\n\n"
            f"📚 <b>Description:</b> {description}\n"
            f"📌 Questions: {len(quiz['questions'])}\n"
            f"⏱ Timer: {quiz['timer']}s per question\n"
            f"🔀 {quiz.get('shuffle', 'No Shuffle')}\n\n"
            "Press <b>I'm ready</b> when prepared."
        )
        button_text = "✅ ɪ'ᴍ ʀᴇᴀᴅʏ"

    keyboard = [
        [
            InlineKeyboardButton(
                button_text,
                callback_data=f"runquiz_{quiz_id}_0",
            )
        ]
    ]

    await message.reply_text(
        ready_msg,
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


async def start_quiz_session(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    query = update.callback_query
    await query.answer()

    try:
        quiz_id = query.data.split("_", 1)[1]
    except (IndexError, ValueError):
        await query.message.reply_text("❌ Invalid quiz ID.")
        return

    quiz = database.get_quiz_by_id(quiz_id)

    if not quiz:
        await query.message.reply_text("❌ Quiz not found!")
        return

    await send_quiz_ready_message(
        query.message,
        quiz,
        quiz_id,
    )


async def run_next_question(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    query = update.callback_query

    try:
        _, quiz_id, q_idx_text = query.data.split("_", 2)
        q_idx = int(q_idx_text)
    except (ValueError, IndexError):
        await query.answer("Invalid quiz session.", show_alert=True)
        return

    quiz = database.get_quiz_by_id(quiz_id)

    if not quiz:
        await query.answer("Quiz not found!", show_alert=True)
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
    context: ContextTypes.DEFAULT_TYPE,
    user_id: int,
    chat_id: int,
    quiz_id,
    q_idx: int,
):
    """Send one quiz question and automatically continue after its timer."""
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

    # Prepare a per-session question order once.
    if "questions" not in session:
        session["questions"] = list(quiz.get("questions", []))

        if quiz.get("shuffle") in ("Shuffle All", "sʜᴜꜰꜰʟᴇ ᴀʟʟ"):
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
        question=f"[{q_idx + 1}/{len(questions)}] {q['question']}",
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
    context: ContextTypes.DEFAULT_TYPE,
    user_id: int,
    chat_id: int,
    quiz_id,
    q_idx: int,
    timer_value: int,
    poll_id: str,
):
    try:
        await asyncio.sleep(timer_value + 1)
    except asyncio.CancelledError:
        return

    session = active_sessions.get(user_id)

    if not session:
        return

    # Ignore an old scheduled task if another question has already started.
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
            text=f"➡️ <b>Question {next_q_idx + 1} coming up...</b>",
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


async def handle_poll_answer(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    answer = update.poll_answer
    poll_id = answer.poll_id

    poll_info = context.bot_data.get(poll_id)

    if not poll_info:
        return

    user_id = poll_info["user_id"]

    # Only count the player who started this quiz.
    if answer.user.id != user_id:
        return

    session = active_sessions.get(user_id)

    if not session:
        return

    # Prevent duplicate counting if Telegram ever sends repeated updates.
    answered_polls = session.setdefault("answered_polls", set())

    if poll_id in answered_polls:
        return

    answered_polls.add(poll_id)

    selected = answer.option_ids[0] if answer.option_ids else -1

    if selected == poll_info["correct_id"]:
        session["correct"] += 1
    else:
        session["wrong"] += 1


async def finish_quiz_results(
    context: ContextTypes.DEFAULT_TYPE,
    user_id: int,
    chat_id: int,
    quiz: dict,
):
    session = active_sessions.get(user_id)

    if not session:
        return

    time_taken = int(time.time() - session["start_time"])

    total_q = len(quiz.get("questions", []))
    correct = session["correct"]
    wrong = session["wrong"]
    missed = max(0, total_q - (correct + wrong))

    creator_username = quiz.get("creator_username") or ""
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
        f"🏁 <b>Qᴜɪᴢ Fɪɴɪsʜᴇᴅ</b>\n\n"
        f"🎯 <b>{quiz['title']}</b>\n"
        f"{creator_line}"
        f"<i>ʏᴏᴜ ᴀɴsᴡᴇʀᴇᴅ {total_q} ǫᴜᴇsᴛɪᴏɴ(s):</i>\n\n"
        f"✅ <b>Correct</b> – {correct}\n"
        f"❌ <b>Wrong</b> – {wrong}\n"
        f"⏳ <b>Missed</b> – {missed}\n"
        f"⏱ <b>{time_taken} sec</b>\n\n"
        f"🏆 <b>Quiz completed!</b>"
    )

    keyboard = [
        [
            InlineKeyboardButton(
                "📤 sʜᴀʀᴇ ǫᴜɪᴢ",
                url=share_url,
            )
        ]
    ]

    try:
        await context.bot.send_message(
            chat_id=chat_id,
            text=results_text,
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(keyboard),
        )
    finally:
        active_sessions.pop(user_id, None)


async def stop_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    user_id = update.effective_user.id

    if user_id in active_sessions:
        active_sessions.pop(user_id, None)
        await update.message.reply_text(
            "🛑 <b>Active quiz session stopped.</b>\n"
            "No further questions will be sent.",
            parse_mode="HTML",
        )
    else:
        await update.message.reply_text(
            "ℹ️ No active quiz session."
        )


async def cancel(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    context.user_data.pop("current_quiz", None)

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
            CommandHandler("newquiz", create_quiz_start),

            # IMPORTANT:
            # A native Telegram Quiz Poll can directly start the
            # conversation without any web form.
            MessageHandler(
                filters.POLL,
                process_question,
            ),
        ],
        states={
            QUESTIONS: [
                CommandHandler("done", finish_questions),
                CommandHandler("title", set_title),
                CommandHandler("description", set_description),
                CommandHandler("cancel", cancel),

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
            CommandHandler("cancel", cancel),
        ],

        allow_reentry=True,
    )

    # Normal bot commands
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("stats", stats_command))
    app.add_handler(CommandHandler("broadcast", broadcast_command))
    app.add_handler(CommandHandler("stop", stop_command))

    # Quiz creation conversation
    app.add_handler(conv_handler)

    # Quiz execution
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

    # Answers from quiz polls sent by the bot
    app.add_handler(
        PollAnswerHandler(handle_poll_answer)
    )

    # Remaining inline buttons: Help / Main Menu
    app.add_handler(
        CallbackQueryHandler(button_click)
    )

    logger.info(
        "Quiz Bot with MongoDB, native Telegram Quiz Polls, "
        "broadcast, stats and auto-next questions is running..."
    )

    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
