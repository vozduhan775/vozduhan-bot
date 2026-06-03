import os
import time
import threading
import requests

TOKEN = os.environ.get("BOT_TOKEN")
API = f"https://api.telegram.org/bot{TOKEN}"

timers = {}

def send(chat_id, text, reply_to=None, keyboard=None):
    data = {"chat_id": chat_id, "text": text, "parse_mode": "HTML"}
    if reply_to:
        data["reply_to_message_id"] = reply_to
    if keyboard:
        data["reply_markup"] = {"inline_keyboard": keyboard}
    r = requests.post(f"{API}/sendMessage", json=data)
    return r.json().get("result", {})

def edit(chat_id, msg_id, text, keyboard=None):
    data = {"chat_id": chat_id, "message_id": msg_id, "text": text, "parse_mode": "HTML"}
    if keyboard:
        data["reply_markup"] = {"inline_keyboard": keyboard}
    try:
        requests.post(f"{API}/editMessageText", json=data)
    except:
        pass

def mention(uid, name):
    return f'<a href="tg://user?id={uid}">{name}</a>'

def fmt(sec):
    sec = max(0, int(sec))
    m, s = divmod(sec, 60)
    return f"{m}:{s:02d}"

def timer_kb():
    return [
        [{"text": "⏱ 1 мин.", "callback_data": "ts:1"}, {"text": "⏱ 3 мин.", "callback_data": "ts:3"}],
        [{"text": "⏱ 5 мин.", "callback_data": "ts:5"}, {"text": "⏱ 10 мин.", "callback_data": "ts:10"}]
    ]

def done_kb():
    return [[{"text": "✅ Завершить", "callback_data": "td"}]]

def ticker(chat_id):
    state = timers.get(chat_id)
    if not state:
        return
    while True:
        time.sleep(15)
        state = timers.get(chat_id)
        if not state or state["finished"]:
            return
        remaining = state["end_time"] - time.time()
        if remaining <= 0:
            break
        edit(chat_id, state["msg_id"],
             f"⏱ Таймер идёт!\n\nЗапустил: {mention(state['sid'], state['sname'])}\n\n⏳ Осталось: {fmt(remaining)}\n\nНажми Завершить иначе воздухан! 💨",
             done_kb())
    state = timers.pop(chat_id, None)
    if state and not state["finished"]:
        edit(chat_id, state["msg_id"], "⏰ Время вышло!")
        send(chat_id,
             f"💨 ВОЗДУХАН!\n\n{mention(state['sid'], state['sname'])} не успел завершить таймер.\n\nПоздравляем с заслуженным званием воздухана чата! 🏆",
             reply_to=state["msg_id"])

def handle_message(msg):
    chat_id = msg["chat"]["id"]
    text = msg.get("text", "")
    if text.startswith("/start") or text.startswith("/timer"):
        if chat_id in timers:
            send(chat_id, "⏳ Таймер уже идёт!")
            return
        send(chat_id, "👋 Воздухан-бот!\n\nЗапусти таймер и успей нажать Завершить.\nНе успел — воздухан! 💨\n\nВыбери длительность:", keyboard=timer_kb())

def handle_callback(cb):
    chat_id = cb["message"]["chat"]["id"]
    msg_id = cb["message"]["message_id"]
    data = cb["data"]
    uid = cb["from"]["id"]
    uname = cb["from"].get("first_name", "") + " " + cb["from"].get("last_name", "")
    uname = uname.strip()
    cb_id = cb["id"]
    requests.post(f"{API}/answerCallbackQuery", json={"callback_query_id": cb_id})

    if data == "td":
        state = timers.get(chat_id)
        if not state:
            edit(chat_id, msg_id, "❌ Таймер уже не активен.")
            return
        if uid != state["sid"]:
            requests.post(f"{API}/answerCallbackQuery", json={"callback_query_id": cb_id, "text": "Только тот кто запустил может завершить!", "show_alert": True})
            return
        state["finished"] = True
        timers.pop(chat_id, None)
        edit(chat_id, msg_id, f"✅ {mention(uid, uname)} успел вовремя. Красавчик! 💪")
        return

    if data.startswith("ts:"):
        if chat_id in timers:
            requests.post(f"{API}/answerCallbackQuery", json={"callback_query_id": cb_id, "text": "Таймер уже запущен!", "show_alert": True})
            return
        minutes = int(data[3:])
        total = minutes * 60
        end_time = time.time() + total
        edit(chat_id, msg_id,
             f"⏱ Таймер на {minutes} мин!\n\nЗапустил: {mention(uid, uname)}\n\n⏳ Осталось: {fmt(total)}\n\nНажми Завершить иначе воздухан! 💨",
             done_kb())
        timers[chat_id] = {"sid": uid, "sname": uname, "msg_id": msg_id, "end_time": end_time, "finished": False}
        t = threading.Thread(target=ticker, args=(chat_id,), daemon=True)
        t.start()

def main():
    print("Бот запущен")
    offset = 0
    while True:
        try:
            r = requests.get(f"{API}/getUpdates", params={"timeout": 30, "offset": offset}, timeout=35)
            updates = r.json().get("result", [])
            for u in updates:
                offset = u["update_id"] + 1
                if "message" in u:
                    handle_message(u["message"])
                elif "callback_query" in u:
                    handle_callback(u["callback_query"])
        except Exception as e:
            print(f"Ошибка: {e}")
            time.sleep(5)

if __name__ == "__main__":
    main()
