import logging
import time
import asyncio
import io
import urllib.request
import json

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    WebAppInfo,
    Poll
)

from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    PollAnswerHandler,
    ConversationHandler,
    ContextTypes,
    filters
)

import config
import database


logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)


# ==========================================================
# STATES
# ==========================================================

QUESTIONS, TIMER, SHUFFLE = range(3)

active_sessions = {}


# ==========================================================
# PHOTO
# ==========================================================

def get_photo_bytes(url):
    """Image URL ko download karke Telegram photo compatible byte stream me convert karta hai."""
    try:
        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
            }
        )

        with urllib.request.urlopen(req, timeout=10) as response:
            return io.BytesIO(response.read())

    except Exception as e:
        logging.error(f"Error downloading image: {e}")
        return None


# ==========================================================
# START
# ==========================================================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):

    user = update.effective_user
    chat = update.effective_chat

    database.add_user(
        user.id,
        user.username,
        user.first_name
    )

    if chat.type in ["group", "supergroup"]:
        database.add_chat(
            chat.id,
            chat.title,
            chat.type
        )

    caption_text = (
        "<b>This bot will help you create a quiz with a series "
        "of multiple choice questions.</b>\n\n"
        f"Welcome, {user.first_name}! "
        "Tap the buttons below to create and manage your quizzes."
    )

    # ======================================================
    # CREATE QUIZ -> EXISTING WEB FORM
    # ======================================================

    keyboard = [
        [
            InlineKeyboardButton(
                "📝 Create New Quiz",
                web_app=WebAppInfo(
                    url=config.WEBAPP_URL
                )
            )
        ],
        [
            InlineKeyboardButton(
                "Owner",
                url=f"https://t.me/{config.OWNER_USERNAME}"
            ),
            InlineKeyboardButton(
                "Update Channel",
                url=f"https://t.me/{config.UPDATE_CHANNEL}"
            )
        ],
        [
            InlineKeyboardButton(
                "Help & Commands",
                callback_data="help_commands"
            )
        ]
    ]

    reply_markup = InlineKeyboardMarkup(keyboard)

    photo_stream = get_photo_bytes(
        config.WELCOME_IMAGE_URL
    )

    try:

        if photo_stream:

            if update.message:

                await update.message.reply_photo(
                    photo=photo_stream,
                    caption=caption_text,
                    parse_mode="HTML",
                    reply_markup=reply_markup
                )

            elif update.callback_query:

                await update.callback_query.message.reply_photo(
                    photo=photo_stream,
                    caption=caption_text,
                    parse_mode="HTML",
                    reply_markup=reply_markup
                )

        else:
            raise Exception("Photo stream unavailable")

    except Exception as e:

        logging.error(
            f"Fallback to text welcome: {e}"
        )

        if update.message:

            await update.message.reply_text(
                text=caption_text,
                parse_mode="HTML",
                reply_markup=reply_markup
            )

        elif update.callback_query:

            await update.callback_query.message.reply_text(
                text=caption_text,
                parse_mode="HTML",
                reply_markup=reply_markup
            )


# ==========================================================
# STATS
# ==========================================================

async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):

    if update.effective_user.id != config.OWNER_ID:

        await update.message.reply_text(
            "❌ Only bot owner can view stats."
        )
        return

    users_cnt = database.count_users()
    chats_cnt = database.count_chats()

    msg = (
        "📊 <b>Bot Live Statistics</b>\n\n"
        f"👤 <b>Total Users:</b> {users_cnt}\n"
        f"👥 <b>Total Groups/Chats:</b> {chats_cnt}\n"
        f"🌐 <b>Total Active Endpoints:</b> "
        f"{users_cnt + chats_cnt}"
    )

    await update.message.reply_text(
        msg,
        parse_mode="HTML"
    )


# ==========================================================
# BROADCAST
# ==========================================================

async def broadcast_command(update: Update, context: ContextTypes.DEFAULT_TYPE):

    if update.effective_user.id != config.OWNER_ID:

        await update.message.reply_text(
            "❌ Only owner can use broadcast."
        )
        return

    if not update.message.reply_to_message:

        await update.message.reply_text(
            "⚠️ Please reply to a message with "
            "`/broadcast` to send it to all users and groups."
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
                message_id=msg.message_id
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
        parse_mode="HTML"
    )


# ==========================================================
# BUTTON HANDLER
# ==========================================================

async def button_click(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    query = update.callback_query

    await query.answer()

    if query.data == "help_commands":

        help_text = (
            "<b>Help & Commands:</b>\n\n"
            "/start - Start the bot\n"
            "/newquiz - Create a new quiz\n"
            "/stop - Stop active session\n"
            "/stats - Check bot user & group statistics "
            "(Owner Only)\n"
            "/broadcast - Broadcast a message to all users "
            "and groups (Owner Only)"
        )

        keyboard = [
            [
                InlineKeyboardButton(
                    "Back to Main Menu",
                    callback_data="main_menu"
                )
            ]
        ]

        await query.message.reply_text(
            help_text,
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    elif query.data == "main_menu":

        await start(
            update,
            context
        )


# ==========================================================
# OPTIONAL /newquiz COMMAND
# ==========================================================

async def create_quiz_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    keyboard = [
        [
            InlineKeyboardButton(
                "📝 Open Quiz Form",
                web_app=WebAppInfo(
                    url=config.WEBAPP_URL
                )
            )
        ]
    ]

    await update.message.reply_text(
        "📝 <b>Create your quiz using the form below.</b>",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


# ==========================================================
# WEB APP FORM DATA
# ==========================================================

async def handle_web_app_data(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    if not update.message:
        return

    if not update.message.web_app_data:
        return

    user = update.effective_user

    raw_data = update.message.web_app_data.data

    logging.info(
        f"Web App data received from {user.id}: {raw_data}"
    )

    # ------------------------------------------------------
    # JSON DATA READ
    # ------------------------------------------------------

    try:

        form_data = json.loads(raw_data)

    except json.JSONDecodeError:

        await update.message.reply_text(
            "❌ Invalid form data received."
        )
        return

    # ------------------------------------------------------
    # SUPPORT COMMON FIELD NAMES
    # ------------------------------------------------------

    title = (
        form_data.get("title")
        or form_data.get("quiz_title")
        or form_data.get("name")
        or ""
    ).strip()

    description = (
        form_data.get("description")
        or form_data.get("quiz_description")
        or ""
    ).strip()

    # ------------------------------------------------------
    # VALIDATION
    # ------------------------------------------------------

    if not title:

        await update.message.reply_text(
            "❌ Quiz title is required."
        )
        return

    # ------------------------------------------------------
    # CREATE CURRENT QUIZ
    # ------------------------------------------------------

    context.user_data["current_quiz"] = {
        "title": title,
        "description": description
        if description
        else "No description provided.",
        "questions": [],
        "timer": 15,
        "shuffle": "No Shuffle"
    }

    # ------------------------------------------------------
    # FORM SUCCESS
    # ------------------------------------------------------

    await update.message.reply_text(
        "✅ <b>Quiz Form Submitted Successfully!</b>\n\n"
        f"📝 <b>Title:</b> {title}\n"
        f"📄 <b>Description:</b> "
        f"{description if description else 'No description'}\n\n"
        "Now send your <b>Quiz Polls</b> one by one.\n\n"
        "When all questions are added, send /done.",
        parse_mode="HTML"
    )

    # ------------------------------------------------------
    # START EXISTING QUESTION FLOW
    # ------------------------------------------------------

    return QUESTIONS


# ==========================================================
# START QUESTIONS
# ==========================================================

async def start_questions_callback(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    query = update.callback_query

    await query.answer()

    await query.message.reply_text(
        "Now send me Quiz Polls. "
        "When finished, send /done."
    )

    return QUESTIONS


# ==========================================================
# PROCESS QUESTIONS
# ==========================================================

async def process_question(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    if not context.user_data.get("current_quiz"):

        await update.message.reply_text(
            "❌ No active quiz found. "
            "Please open the quiz form first."
        )

        return QUESTIONS

    if update.message.poll:

        poll = update.message.poll

        if poll.type != Poll.QUIZ:

            await update.message.reply_text(
                "❌ Please send a poll of type Quiz."
            )

            return QUESTIONS

        context.user_data["current_quiz"]["questions"].append(
            {
                "question": poll.question,
                "options": [
                    opt.text
                    for opt in poll.options
                ],
                "correct_option_id": poll.correct_option_id,
                "explanation": poll.explanation
            }
        )

        count = len(
            context.user_data["current_quiz"]["questions"]
        )

        await update.message.reply_text(
            f"✅ Question #{count} added!\n\n"
            "Send another question or /done."
        )

        return QUESTIONS

    await update.message.reply_text(
        "⚠️ Please send a Telegram Quiz Poll.\n"
        "When finished, use /done."
    )

    return QUESTIONS


# ==========================================================
# FINISH QUESTIONS
# ==========================================================

async def finish_questions(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    quiz = context.user_data.get(
        "current_quiz",
        {}
    )

    if not quiz.get("questions"):

        await update.message.reply_text(
            "❌ Add at least one question poll "
            "before sending /done."
        )

        return QUESTIONS

    keyboard = [
        [
            InlineKeyboardButton(
                "10 sec",
                callback_data="time_10"
            ),
            InlineKeyboardButton(
                "15 sec",
                callback_data="time_15"
            ),
            InlineKeyboardButton(
                "30 sec",
                callback_data="time_30"
            )
        ],
        [
            InlineKeyboardButton(
                "45 sec",
                callback_data="time_45"
            ),
            InlineKeyboardButton(
                "1 min",
                callback_data="time_60"
            )
        ]
    ]

    await update.message.reply_text(
        "⏱ <b>Select timer per question:</b>",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

    return TIMER


# ==========================================================
# TIMER
# ==========================================================

async def process_timer(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    query = update.callback_query

    await query.answer()

    timer = int(
        query.data.split("_")[1]
    )

    context.user_data[
        "current_quiz"
    ]["timer"] = timer

    keyboard = [
        [
            InlineKeyboardButton(
                "🔀 Shuffle All",
                callback_data="shuf_all"
            ),
            InlineKeyboardButton(
                "➡️ No Shuffle",
                callback_data="shuf_none"
            )
        ]
    ]

    await query.message.reply_text(
        "🔀 <b>Shuffle options?</b>",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

    return SHUFFLE


# ==========================================================
# SHUFFLE + SAVE QUIZ
# ==========================================================

async def process_shuffle(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    query = update.callback_query

    await query.answer()

    user_id = update.effective_user.id

    context.user_data[
        "current_quiz"
    ]["shuffle"] = (
        "Shuffle All"
        if query.data == "shuf_all"
        else "No Shuffle"
    )

    quiz_info = context.user_data[
        "current_quiz"
    ]

    # ------------------------------------------------------
    # SAVE DATABASE
    # ------------------------------------------------------

    quiz_id = database.save_quiz(
        user_id,
        quiz_info
    )

    summary_msg = (
        "👍 <b>Quiz Created in Database!</b>\n\n"
        f"<b>{quiz_info['title']}</b>\n"
        f"<i>{len(quiz_info['questions'])} "
        f"question(s) · {quiz_info['timer']} sec</i>\n\n"
        "Start Link:\n"
        f"<code>t.me/{context.bot.username}"
        f"?start=quiz_{quiz_id}</code>"
    )

    keyboard = [
        [
            InlineKeyboardButton(
                "▶️ Start this quiz",
                callback_data=f"startquiz_{quiz_id}"
            )
        ],
        [
            InlineKeyboardButton(
                "👥 Start quiz in group",
                url=(
                    f"https://t.me/{context.bot.username}"
                    "?startgroup=true"
                )
            )
        ]
    ]

    await query.message.reply_text(
        summary_msg,
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

    # ------------------------------------------------------
    # CLEAR TEMP QUIZ DATA
    # ------------------------------------------------------

    context.user_data.pop(
        "current_quiz",
        None
    )

    return ConversationHandler.END


# ==========================================================
# START QUIZ SESSION
# ==========================================================

async def start_quiz_session(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    query = update.callback_query

    await query.answer()

    quiz_id = query.data.split("_")[1]

    quiz = database.get_quiz_by_id(
        quiz_id
    )

    if not quiz:

        await query.message.reply_text(
            "❌ Quiz not found!"
        )
        return

    ready_msg = (
        f"🎲 <b>Get ready for "
        f"'{quiz['title']}'</b>\n\n"
        f"📌 Questions: {len(quiz['questions'])}\n"
        f"⏱ Timer: {quiz['timer']}s per question\n\n"
        "Press <b>Ready</b> when prepared."
    )

    keyboard = [
        [
            InlineKeyboardButton(
                "I'm ready",
                callback_data=f"runquiz_{quiz_id}_0"
            )
        ]
    ]

    await query.message.reply_text(
        ready_msg,
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


# ==========================================================
# NEXT QUESTION
# ==========================================================

async def run_next_question(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    query = update.callback_query

    await query.answer()

    _, quiz_id, q_idx = query.data.split("_")

    q_idx = int(q_idx)

    quiz = database.get_quiz_by_id(
        quiz_id
    )

    if not quiz:
        await query.message.reply_text(
            "❌ Quiz not found."
        )
        return

    questions = quiz["questions"]

    user_id = update.effective_user.id

    if user_id not in active_sessions:

        active_sessions[user_id] = {
            "start_time": time.time(),
            "correct": 0,
            "wrong": 0
        }

    if q_idx < len(questions):

        q = questions[q_idx]

        poll_msg = await query.message.reply_poll(
            question=(
                f"[{q_idx + 1}/{len(questions)}] "
                f"{q['question']}"
            ),
            options=q["options"],
            type=Poll.QUIZ,
            correct_option_id=q["correct_option_id"],
            explanation=q["explanation"],
            is_anonymous=False,
            open_period=quiz["timer"]
        )

        context.bot_data[
            poll_msg.poll.id
        ] = {
            "user_id": user_id,
            "quiz_id": quiz_id,
            "q_idx": q_idx,
            "correct_id": q["correct_option_id"]
        }

    else:

        await finish_quiz_results(
            update,
            context,
            user_id,
            quiz
        )


# ==========================================================
# POLL ANSWER
# ==========================================================

async def handle_poll_answer(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    answer = update.poll_answer

    poll_id = answer.poll_id

    if poll_id not in context.bot_data:
        return

    p_info = context.bot_data[poll_id]

    user_id = p_info["user_id"]

    selected = (
        answer.option_ids[0]
        if answer.option_ids
        else -1
    )

    if user_id in active_sessions:

        if selected == p_info["correct_id"]:

            active_sessions[user_id]["correct"] += 1

        else:

            active_sessions[user_id]["wrong"] += 1


# ==========================================================
# RESULTS
# ==========================================================

async def finish_quiz_results(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    user_id: int,
    quiz: dict
):

    session = active_sessions.get(
        user_id,
        {
            "correct": 0,
            "wrong": 0,
            "start_time": time.time()
        }
    )

    time_taken = int(
        time.time() -
        session["start_time"]
    )

    total_q = len(
        quiz["questions"]
    )

    correct = session["correct"]
    wrong = session["wrong"]

    missed = total_q - (
        correct + wrong
    )

    results_text = (
        f"🏁 <b>The quiz '{quiz['title']}' "
        f"has finished!</b>\n\n"
        f"<i>You answered {total_q} question(s):</i>\n\n"
        f"✅ <b>Correct</b> – {correct}\n"
        f"❌ <b>Wrong</b> – {wrong}\n"
        f"⏳ <b>Missed</b> – {missed}\n"
        f"⏱ <b>{time_taken} sec</b>\n\n"
        f"🏆 <b>1st</b> place out of 1."
    )

    if update.callback_query:

        await update.callback_query.message.reply_text(
            results_text,
            parse_mode="HTML"
        )

    if user_id in active_sessions:

        del active_sessions[user_id]


# ==========================================================
# CANCEL
# ==========================================================

async def cancel(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    context.user_data.pop(
        "current_quiz",
        None
    )

    await update.message.reply_text(
        "❌ Cancelled."
    )

    return ConversationHandler.END


# ==========================================================
# MAIN
# ==========================================================

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

    # ======================================================
    # QUIZ CONVERSATION
    # ======================================================

    conv_handler = ConversationHandler(

        entry_points=[
            CommandHandler(
                "newquiz",
                create_quiz_command
            )
        ],

        states={

            QUESTIONS: [

                CommandHandler(
                    "done",
                    finish_questions
                ),

                MessageHandler(
                    filters.POLL,
                    process_question
                )
            ],

            TIMER: [

                CallbackQueryHandler(
                    process_timer,
                    pattern=r"^time_"
                )
            ],

            SHUFFLE: [

                CallbackQueryHandler(
                    process_shuffle,
                    pattern=r"^shuf_"
                )
            ]
        },

        fallbacks=[
            CommandHandler(
                "cancel",
                cancel
            )
        ],

        allow_reentry=True
    )

    # ======================================================
    # BASIC COMMANDS
    # ======================================================

    app.add_handler(
        CommandHandler(
            "start",
            start
        )
    )

    app.add_handler(
        CommandHandler(
            "stats",
            stats_command
        )
    )

    app.add_handler(
        CommandHandler(
            "broadcast",
            broadcast_command
        )
    )

    # ======================================================
    # WEB APP DATA
    # IMPORTANT: THIS MUST BE BEFORE NORMAL TEXT HANDLERS
    # ======================================================

    app.add_handler(
        MessageHandler(
            filters.StatusUpdate.WEB_APP_DATA,
            handle_web_app_data
        )
    )

    # ======================================================
    # QUIZ CONVERSATION
    # ======================================================

    app.add_handler(
        conv_handler
    )

    # ======================================================
    # QUIZ BUTTONS
    # ======================================================

    app.add_handler(
        CallbackQueryHandler(
            start_quiz_session,
            pattern=r"^startquiz_"
        )
    )

    app.add_handler(
        CallbackQueryHandler(
            run_next_question,
            pattern=r"^runquiz_"
        )
    )

    # ======================================================
    # POLL ANSWERS
    # ======================================================

    app.add_handler(
        PollAnswerHandler(
            handle_poll_answer
        )
    )

    # ======================================================
    # OTHER BUTTONS
    # ======================================================

    app.add_handler(
        CallbackQueryHandler(
            button_click
        )
    )

    print(
        "Quiz Bot with Web Form, MongoDB, "
        "Broadcast and Stats is running..."
    )

    app.run_polling(
        drop_pending_updates=True
    )


# ==========================================================
# RUN
# ==========================================================

if __name__ == "__main__":
    main()
