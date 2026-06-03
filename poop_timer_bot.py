"""
💩 Воздухан-бот v2
"""

import asyncio
import logging
import os
from typing import Optional

from telegram import Update, Message, InlineKeyboardButton, InlineKeyboardMarkup, User
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes
from telegram.constants import ParseMode

logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

TIMER_OPTIONS   = [1, 3, 5, 10]
CALLBACK_PREFIX = "timer_start:"
CALLBACK_DONE   = "timer_done"

class TimerState:
    def __init__(self, timer_message: Message, minutes: int, starter: User):
        self.timer_message = timer_message
        self.minutes       = minutes
        self.starter       = starter
        self.task: Optional[asyncio.Task] = None
        self.finished      = False

active_timers: dict[int, TimerState] = {}

def fmt_time(seconds: int) -> str:
    m, s = divmod(max(0, seconds), 60)
    return f"{m}:{s:02d}"

def mention(user: User) -> str:
    return f'<a href="tg://user?id={user.id}">{user.full_name}</a>'

def timer_keyboard() -> InlineKeyboardMarkup:
    buttons = [
        InlineKeyboardButton(f"⏱ {m} мин.", callback_data=f"{CALLBACK_PREFIX}{m}")
        for m in TIMER_OPTIONS
    ]
    rows = [buttons[i:i+2] for i in range(0, len(buttons), 2)]
    return InlineKeyboardMarkup(rows)

def done_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [[InlineKeyboardButton("✅ Завершить", callback_data=CALLBACK_DONE)]]
    )

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 Привет! Я Воздухан-бот.\n\n"
        "Запусти таймер и успей нажать <b>«Завершить»</b> до конца.\n"
        "Не успел — бот напишет в чат <b>воздухан</b> и тегнет тебя 😈\n\n"
        "Выбери длительность:",
        parse_mode=ParseMode.HTML,
        reply_markup=timer_keyboard(),
    )

async def cmd_timer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    if chat_id in active_timers:
        await update.message.reply_text("⏳ Таймер уже идёт! Дождись окончания.")
        return
    await update.message.reply_text(
        "⏱ Выбери длительность таймера:",
        reply_markup=timer_keyboard(),
    )

async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    chat_id = update.effective_chat.id
    data    = query.data

    if data == CALLBACK_DONE:
        state = active_timers.get(chat_id)
        if not state:
            await query.edit_message_text("❌ Таймер уже не активен.")
            return

        if query.from_user.id != state.starter.id:
            await query.answer(
                "Только тот, кто запустил таймер, может его завершить!",
                show_alert=True,
            )
            return

        state.finished = True
        if state.task:
            state.task.cancel()
        active_timers.pop(chat_id, None)

        await query.edit_message_text(
            f"✅ <b>Таймер завершён!</b>\n\n"
            f"{mention(state.starter)} успел вовремя. Красавчик! 💪",
            parse_mode=ParseMode.HTML,
        )
        return

    if data.startswith(CALLBACK_PREFIX):
        if chat_id in active_timers:
            await query.answer("⏳ Таймер уже запущен!", show_alert=True)
            return

        minutes   = int(data.removeprefix(CALLBACK_PREFIX))
        total_sec = minutes * 60
        starter   = query.from_user

        await query.edit_message_text(
            f"⏱ <b>Таймер запущен на {minutes} мин.!</b>\n\n"
            f"Запустил: {mention(starter)}\n\n"
            f"⏳ Осталось: <b>{fmt_time(total_sec)}</b>\n\n"
            f"Нажми <b>«Завершить»</b> до истечения времени,\n"
            f"иначе получишь звание <b>воздухан</b> 💨",
            parse_mode=ParseMode.HTML,
            reply_markup=done_keyboard(),
        )

        state = TimerState(
            timer_message=query.message,
            minutes=minutes,
            starter=starter,
        )
        active_timers[chat_id] = state
        state.task = asyncio.create_task(
            countdown_task(chat_id, total_sec, context.application)
        )

async def countdown_task(chat_id: int, total_sec: int, app: Application):
    state = active_timers.get(chat_id)
    if not state:
        return

    UPDATE_INTERVAL = 15
    elapsed = 0

    try:
        while elapsed < total_sec:
            await asyncio.sleep(UPDATE_INTERVAL)
            elapsed += UPDATE_INTERVAL

            if state.finished or chat_id not in active_timers:
                return

            remaining = total_sec - elapsed
            try:
                await state.timer_message.edit_text(
                    f"⏱ <b>Таймер идёт!</b>\n\n"
                    f"Запустил: {mention(state.starter)}\n\n"
                    f"⏳ Осталось: <b>{fmt_time(remaining)}</b>\n\n"
                    f"Нажми <b>«Завершить»</b> до истечения времени,\n"
                    f"иначе получишь звание <b>воздухан</b> 💨",
                    parse_mode=ParseMode.HTML,
                    reply_markup=done_keyboard(),
                )
            except Exception as e:
                logger.warning("edit_text failed: %s", e)

    except asyncio.CancelledError:
        return

    if not state.finished and chat_id in active_timers:
        await expire_timer(chat_id, app)

async def expire_timer(chat_id: int, app: Application):
    state = active_timers.pop(chat_id, None)
    if not state:
        return

    try:
        await state.timer_message.edit_text(
            "⏰ <b>Время вышло!</b>",
            parse_mode=ParseMode.HTML,
        )
    except Exception:
        pass

    await app.bot.send_message(
        chat_id=chat_id,
        text=(
            f"💨 <b>ВОЗДУХАН!</b>\n\n"
            f"{mention(state.starter)} не успел завершить таймер.\n\n"
            f"Поздравляем с заслуженным званием <b>воздухана чата</b>! 🏆"
        ),
        parse_mode=ParseMode.HTML,
        reply_to_message_id=state.timer_message.message_id,
    )

def main():
    token = os.environ.get("BOT_TOKEN")
    if not token:
        raise RuntimeError("Укажи BOT_TOKEN через переменную окружения.")

    app = Application.builder().token(token).build()
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("timer", cmd_timer))
    app.add_handler(CallbackQueryHandler(callback_handler))

    logger.info("🚀 Воздухан-бот запущен")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
