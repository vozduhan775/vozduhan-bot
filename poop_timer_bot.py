import asyncio
import logging
import os
from typing import Optional

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

TIMER_OPTIONS = [1, 3, 5, 10]
CALLBACK_PREFIX = "ts:"
CALLBACK_DONE = "td"

class TimerState:
    def __init__(self, msg, minutes, starter_id, starter_name):
        self.msg = msg
        self.minutes = minutes
        self.starter_id = starter_id
        self.starter_name = starter_name
        self.task = None
        self.finished = False

active_timers = {}

def fmt(sec):
    m, s = divmod(max(0, sec), 60)
    return f"{m}:{s:02d}"

def mention(uid, name):
    return f'<a href="tg://user?id={uid}">{name}</a>'

def timer_kb():
    btns = [InlineKeyboardButton(f"⏱ {m} мин.", callback_data=f"{CALLBACK_PREFIX}{m}") for m in TIMER_OPTIONS]
    return InlineKeyboardMarkup([btns[:2], btns[2:]])

def done_kb():
    return InlineKeyboardMarkup([[InlineKeyboardButton("✅ Завершить", callback_data=CALLBACK_DONE)]])

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 Воздухан-бот!\n\nЗапусти таймер и успей нажать Завершить.\nНе успел — получишь звание воздухан!\n\nВыбери длительность:",
        reply_markup=timer_kb()
    )

async def cmd_timer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.id in active_timers:
        await update.message.reply_text("Таймер уже идёт!")
        return
    await update.message.reply_text("Выбери длительность:", reply_markup=timer_kb())

async def on_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    chat_id = update.effective_chat.id

    if q.data == CALLBACK_DONE:
        state = active_timers.get(chat_id)
        if not state:
            await q.edit_message_text("Таймер уже не активен.")
            return
        if q.from_user.id != state.starter_id:
            await q.answer("Только тот кто запустил может завершить!", show_alert=True)
            return
        state.finished = True
        if state.task:
            state.task.cancel()
        active_timers.pop(chat_id, None)
        await q.edit_message_text(
            f"✅ {mention(state.starter_id, state.starter_name)} успел вовремя. Красавчик! 💪",
            parse_mode="HTML"
        )
        return

    if q.data.startswith(CALLBACK_PREFIX):
        if chat_id in active_timers:
            await q.answer("Таймер уже запущен!", show_alert=True)
            return
        minutes = int(q.data[len(CALLBACK_PREFIX):])
        total = minutes * 60
        sid = q.from_user.id
        sname = q.from_user.full_name
        await q.edit_message_text(
            f"⏱ Таймер на {minutes} мин!\n\nЗапустил: {mention(sid, sname)}\n\n⏳ Осталось: {fmt(total)}\n\nНажми Завершить иначе воздухан!",
            parse_mode="HTML",
            reply_markup=done_kb()
        )
        state = TimerState(q.message, minutes, sid, sname)
        active_timers[chat_id] = state
        state.task = asyncio.create_task(tick(chat_id, total, context.application))

async def tick(chat_id, total, app):
    state = active_timers.get(chat_id)
    if not state:
        return
    elapsed = 0
    try:
        while elapsed < total:
            await asyncio.sleep(15)
            elapsed += 15
            if state.finished or chat_id not in active_timers:
                return
            rem = total - elapsed
            try:
                await state.msg.edit_text(
                    f"⏱ Таймер идёт!\n\nЗапустил: {mention(state.starter_id, state.starter_name)}\n\n⏳ Осталось: {fmt(rem)}\n\nНажми Завершить иначе воздухан!",
                    parse_mode="HTML",
                    reply_markup=done_kb()
                )
            except Exception as e:
                logger.warning(e)
    except asyncio.CancelledError:
        return
    if not state.finished and chat_id in active_timers:
        await shame(chat_id, app)

async def shame(chat_id, app):
    state = active_timers.pop(chat_id, None)
    if not state:
        return
    try:
        await state.msg.edit_text("⏰ Время вышло!")
    except Exception:
        pass
    await app.bot.send_message(
        chat_id=chat_id,
        text=f"💨 ВОЗДУХАН!\n\n{mention(state.starter_id, state.starter_name)} не успел завершить таймер.\n\nПоздравляем с заслуженным званием воздухана чата! 🏆",
        parse_mode="HTML",
        reply_to_message_id=state.msg.message_id
    )

def main():
    token = os.environ.get("BOT_TOKEN")
    if not token:
        raise RuntimeError("Нет BOT_TOKEN")
    app = Application.builder().token(token).build()
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("timer", cmd_timer))
    app.add_handler(CallbackQueryHandler(on_button))
    logger.info("Бот запущен")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
