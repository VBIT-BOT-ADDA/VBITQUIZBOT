import logging
import time
import asyncio
from telegram import (
    Update, 
    InlineKeyboardButton, 
    InlineKeyboardMarkup, 
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
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

TITLE, DESCRIPTION, QUESTIONS, TIMER, SHUFFLE = range(5)
active_sessions = {}

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    chat = update.effective_chat
    
    database.add_user(user.id, user.username, user.first_name)
    if chat.type in ['group', 'supergroup']:
        database.add_chat(chat.id, chat.title, chat.type)

    caption_text = (
        f"<b>This bot will help you create a quiz with a series of multiple choice questions.</b>\n\n"
        f"Welcome, {user.first_name}! Tap the buttons below to create and manage your quizzes."
    )
    
    keyboard = [
        [InlineKeyboardButton("Create New Quiz", callback_data="create_quiz")],
        [
            InlineKeyboardButton("Owner", url=f"https://t.me/{config.OWNER_USERNAME}"),
            InlineKeyboardButton("Update Channel", url=f"https://t.me/{config.UPDATE_CHANNEL}")
        ],
        [InlineKeyboardButton("Help & Commands", callback_data="help_commands")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    # Safe handling if image URL fails to load
    try:
        if update.message:
            await update.message.reply_photo(
                photo=config.WELCOME_IMAGE_URL,
                caption=caption_text,
                parse_mode="HTML",
                reply_markup=reply_markup
            )
        elif update.callback_query:
            await update.callback_query.message.reply_photo(
                photo=config.WELCOME_IMAGE_URL,
                caption=caption_text,
                parse_mode="HTML",
                reply_markup=reply_markup
            )
    except Exception as e:
        logging.error(f"Failed to send welcome image: {e}")
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
        await update.message.reply_text("⚠️ Please reply to a message with `/broadcast` to send it to all users and groups.")
        return

    msg = update.message.reply_to_message
    all_users = database.get_all_users()
    all_chats = database.get_all_chats()
    targets = list(set(all_users + all_chats))

    status_msg = await update.message.reply_text(f"🚀 Broadcast started to {len(targets)} targets...")

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

async def button_click(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "help_commands":
        help_text = (
            "<b>Help & Commands:</b>\n\n"
            "/start - Start the bot\n"
            "/newquiz - Create a new quiz\n"
            "/stop - Stop active session\n"
            "/stats - Check bot user & group statistics (Owner Only)\n"
            "/broadcast - Broadcast a message to all users and groups (Owner Only)"
        )
        keyboard = [[InlineKeyboardButton("Back to Main Menu", callback_data="main_menu")]]
        await query.message.reply_text(help_text, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(keyboard))
    
    elif query.data == "main_menu":
        await start(update, context)

async def create_quiz_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.message.reply_text("Let's create a new quiz. Send me the title of your quiz.")
    elif update.message:
        await update.message.reply_text("Let's create a new quiz. Send me the title of your quiz.")
    return TITLE

async def process_title(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['current_quiz'] = {
        'title': update.message.text,
        'description': 'No description provided.',
        'questions': [],
        'timer': 15,
        'shuffle': 'No Shuffle'
    }
    await update.message.reply_text("Good. Now send me a description (or send /skip).")
    return DESCRIPTION

async def process_description(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['current_quiz']['description'] = update.message.text
    await update.message.reply_text("Now send me Quiz Polls. When finished, send /done.")
    return QUESTIONS

async def skip_description(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Now send me Quiz Polls. When finished, send /done.")
    return QUESTIONS

async def process_question(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.poll:
        poll = update.message.poll
        if poll.type != Poll.QUIZ:
            await update.message.reply_text("Please send a poll of type Quiz.")
            return QUESTIONS
        
        context.user_data['current_quiz']['questions'].append({
            'question': poll.question,
            'options': [opt.text for opt in poll.options],
            'correct_option_id': poll.correct_option_id,
            'explanation': poll.explanation
        })
        count = len(context.user_data['current_quiz']['questions'])
        await update.message.reply_text(f"Question #{count} added! Send another or /done.")
        return QUESTIONS

async def finish_questions(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.user_data.get('current_quiz', {}).get('questions'):
        await update.message.reply_text("Add at least one question poll before sending /done.")
        return QUESTIONS

    keyboard = [
        [InlineKeyboardButton("10 sec", callback_data="time_10"), InlineKeyboardButton("15 sec", callback_data="time_15"), InlineKeyboardButton("30 sec", callback_data="time_30")],
        [InlineKeyboardButton("45 sec", callback_data="time_45"), InlineKeyboardButton("1 min", callback_data="time_60")]
    ]
    await update.message.reply_text("Select timer per question:", reply_markup=InlineKeyboardMarkup(keyboard))
    return TIMER

async def process_timer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data['current_quiz']['timer'] = int(query.data.split("_")[1])

    keyboard = [
        [InlineKeyboardButton("Shuffle All", callback_data="shuf_all"), InlineKeyboardButton("No Shuffle", callback_data="shuf_none")]
    ]
    await query.message.reply_text("Shuffle options?", reply_markup=InlineKeyboardMarkup(keyboard))
    return SHUFFLE

async def process_shuffle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    
    context.user_data['current_quiz']['shuffle'] = "Shuffle All" if query.data == "shuf_all" else "No Shuffle"
    quiz_id = database.save_quiz(user_id, context.user_data['current_quiz'])

    quiz_info = context.user_data['current_quiz']
    summary_msg = (
        f"👍 <b>Quiz Created in Database!</b>\n\n"
        f"<b>{quiz_info['title']}</b>\n"
        f"<i>{len(quiz_info['questions'])} question(s) · {quiz_info['timer']} sec</i>\n\n"
        f"Start Link:\n<code>t.me/{context.bot.username}?start=quiz_{quiz_id}</code>"
    )

    keyboard = [
        [InlineKeyboardButton("Start this quiz", callback_data=f"startquiz_{quiz_id}")],
        [InlineKeyboardButton("Start quiz in group", url=f"https://t.me/{context.bot.username}?startgroup=true")]
    ]

    await query.message.reply_text(summary_msg, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(keyboard))
    return ConversationHandler.END

async def start_quiz_session(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    quiz_id = query.data.split("_")[1]
    quiz = database.get_quiz_by_id(quiz_id)
    if not quiz:
        await query.message.reply_text("Quiz not found!")
        return

    ready_msg = (
        f"🎲 <b>Get ready for '{quiz['title']}'</b>\n\n"
        f"📌 Questions: {len(quiz['questions'])}\n"
        f"⏱ Timer: {quiz['timer']}s per question\n\n"
        f"Press Ready when prepared."
    )
    keyboard = [[InlineKeyboardButton("I'm ready", callback_data=f"runquiz_{quiz_id}_0")]]
    await query.message.reply_text(ready_msg, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(keyboard))

async def run_next_question(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    _, quiz_id, q_idx = query.data.split("_")
    q_idx = int(q_idx)

    quiz = database.get_quiz_by_id(quiz_id)
    questions = quiz['questions']
    user_id = update.effective_user.id

    if user_id not in active_sessions:
        active_sessions[user_id] = {'start_time': time.time(), 'correct': 0, 'wrong': 0}

    if q_idx < len(questions):
        q = questions[q_idx]
        poll_msg = await query.message.reply_poll(
            question=f"[{q_idx + 1}/{len(questions)}] {q['question']}",
            options=q['options'],
            type=Poll.QUIZ,
            correct_option_id=q['correct_option_id'],
            explanation=q['explanation'],
            is_anonymous=False,
            open_period=quiz['timer']
        )
        context.bot_data[poll_msg.poll.id] = {
            'user_id': user_id,
            'quiz_id': quiz_id,
            'q_idx': q_idx,
            'correct_id': q['correct_option_id']
        }
    else:
        await finish_quiz_results(update, context, user_id, quiz)

async def handle_poll_answer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    answer = update.poll_answer
    poll_id = answer.poll_id
    
    if poll_id in context.bot_data:
        p_info = context.bot_data[poll_id]
        user_id = p_info['user_id']
        selected = answer.option_ids[0] if answer.option_ids else -1
        
        if user_id in active_sessions:
            if selected == p_info['correct_id']:
                active_sessions[user_id]['correct'] += 1
            else:
                active_sessions[user_id]['wrong'] += 1

async def finish_quiz_results(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: int, quiz: dict):
    session = active_sessions.get(user_id, {'correct': 0, 'wrong': 0, 'start_time': time.time()})
    time_taken = int(time.time() - session['start_time'])
    total_q = len(quiz['questions'])
    correct = session['correct']
    wrong = session['wrong']
    missed = total_q - (correct + wrong)

    results_text = (
        f"🏁 <b>The quiz '{quiz['title']}' has finished!</b>\n\n"
        f"<i>You answered {total_q} question(s):</i>\n\n"
        f"✅ <b>Correct</b> – {correct}\n"
        f"❌ <b>Wrong</b> – {wrong}\n"
        f"⏳ <b>Missed</b> – {missed}\n"
        f"⏱ <b>{time_taken} sec</b>\n\n"
        f"🏆 <b>1st</b> place out of 1."
    )

    if update.callback_query:
        await update.callback_query.message.reply_text(results_text, parse_mode="HTML")
    
    if user_id in active_sessions:
        del active_sessions[user_id]

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Cancelled.")
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
            CommandHandler('newquiz', create_quiz_start),
            CallbackQueryHandler(create_quiz_start, pattern="^create_quiz$")
        ],
        states={
            TITLE: [MessageHandler(filters.TEXT & ~filters.COMMAND, process_title)],
            DESCRIPTION: [
                CommandHandler('skip', skip_description),
                MessageHandler(filters.TEXT & ~filters.COMMAND, process_description)
            ],
            QUESTIONS: [
                CommandHandler('done', finish_questions),
                MessageHandler(filters.POLL | filters.TEXT, process_question)
            ],
            TIMER: [CallbackQueryHandler(process_timer, pattern="^time_")],
            SHUFFLE: [CallbackQueryHandler(process_shuffle, pattern="^shuf_")]
        },
        fallbacks=[CommandHandler('cancel', cancel)],
        per_message=False
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("stats", stats_command))
    app.add_handler(CommandHandler("broadcast", broadcast_command))
    app.add_handler(conv_handler)
    app.add_handler(CallbackQueryHandler(start_quiz_session, pattern="^startquiz_"))
    app.add_handler(CallbackQueryHandler(run_next_question, pattern="^runquiz_"))
    app.add_handler(PollAnswerHandler(handle_poll_answer))
    app.add_handler(CallbackQueryHandler(button_click))

    print("Quiz Bot with MongoDB, Broadcast, and Stats is running...")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
