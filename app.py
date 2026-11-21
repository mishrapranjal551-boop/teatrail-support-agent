"""TeaTrail Store Support: a Streamlit chat page for Tara.

Run on your laptop:  streamlit run app.py
"""

import asyncio
import csv
import hmac
import os
import threading
from datetime import datetime
from pathlib import Path

import streamlit as st
from dotenv import load_dotenv

st.set_page_config(page_title="TeaTrail Store Support", page_icon="🍵")


def secret(name: str) -> str | None:
    """Reads a value from Streamlit secrets (when deployed) or .env (on my laptop)."""
    try:
        if name in st.secrets:
            return str(st.secrets[name])
    except Exception:  # no secrets.toml on this machine
        pass
    return os.getenv(name)


load_dotenv(Path(__file__).resolve().parent / ".env")
api_key = secret("GOOGLE_API_KEY")
passcode = secret("APP_PASSCODE")

if not api_key:
    st.error("GOOGLE_API_KEY is missing. Add it to .env on your laptop, or to the app's Secrets on Streamlit Cloud.")
    st.stop()
if not passcode:
    st.error("APP_PASSCODE is missing. Add it to .streamlit/secrets.toml, or to the app's Secrets on Streamlit Cloud.")
    st.stop()
os.environ["GOOGLE_API_KEY"] = api_key  # Tara's Gemini client reads it from here

# ---- Passcode gate --------------------------------------------------------------
MAX_ATTEMPTS = 5
st.session_state.setdefault("unlocked", False)
st.session_state.setdefault("attempts", 0)

st.title("🍵 TeaTrail Store Support")

if not st.session_state.unlocked:
    st.write("Please enter the passcode to chat with Tara.")
    if st.session_state.attempts >= MAX_ATTEMPTS:
        st.error("Too many wrong attempts. Please refresh the page and try again later.")
        st.stop()
    with st.form("passcode"):
        entered = st.text_input("Passcode", type="password")
        if st.form_submit_button("Open chat"):
            if hmac.compare_digest(entered.encode(), passcode.encode()):
                st.session_state.unlocked = True
                st.rerun()
            else:
                st.session_state.attempts += 1
                st.error("That passcode is not right. The chat stays locked.")
    st.stop()

# ---- Tara (loaded once, on one long-running event loop) ---------------------------
@st.cache_resource
def get_tara():
    """Imports Tara and starts one background event loop that all chats share."""
    from tara import chat, tickets

    loop = asyncio.new_event_loop()
    threading.Thread(target=loop.run_forever, daemon=True).start()
    return chat, tickets, loop


chat, tickets, loop = get_tara()


def run(coro):
    return asyncio.run_coroutine_threadsafe(coro, loop).result(timeout=120)


from tara.agent import GREETING  # noqa: E402

if "session_id" not in st.session_state:
    st.session_state.session_id = run(chat.new_session())
    st.session_state.messages = [{"role": "assistant", "content": GREETING}]

# ---- Feedback (extra) ---------------------------------------------------------------
FEEDBACK_FILE = Path(__file__).resolve().parent / "feedback.csv"


def save_feedback(index: int, helpful: str) -> None:
    question = st.session_state.messages[index - 1]["content"] if index > 0 else ""
    is_new = not FEEDBACK_FILE.exists()
    with FEEDBACK_FILE.open("a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        if is_new:
            writer.writerow(["time", "question", "reply", "helpful"])
        writer.writerow([
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            question,
            st.session_state.messages[index]["content"],
            helpful,
        ])
    st.session_state.messages[index]["feedback"] = helpful


# ---- Sidebar: open tickets ------------------------------------------------------------
with st.sidebar:
    st.header("🎫 Open tickets")
    open_list = tickets.open_tickets()
    if not open_list:
        st.caption("No open tickets yet.")
    for t in open_list:
        badge = "🔴 high" if t["priority"] == "high" else "🟢 normal"
        with st.container(border=True):
            st.markdown(f"**{t['ticket_id']}** · {badge}")
            st.caption(f"{t['time']} · {t['reason']}")
            st.write(t["customer_message"])

# ---- Chat -------------------------------------------------------------------------------
for i, msg in enumerate(st.session_state.messages):
    with st.chat_message(msg["role"], avatar="🍵" if msg["role"] == "assistant" else None):
        st.markdown(msg["content"])
        if msg["role"] == "assistant" and i > 0:
            if "feedback" in msg:
                st.caption("Thanks for your feedback!")
            else:
                st.caption("Was this helpful?")
                c1, c2, _ = st.columns([1, 1, 6])
                c1.button("👍 Yes", key=f"yes{i}", on_click=save_feedback, args=(i, "yes"))
                c2.button("👎 No", key=f"no{i}", on_click=save_feedback, args=(i, "no"))

# Suggested questions (extra) show until the customer asks something.
suggested = None
if len(st.session_state.messages) == 1:
    cols = st.columns(3)
    for col, q in zip(cols, ["How much does delivery cost?", "What is your return policy?", "How do I track my order?"]):
        if col.button(q, use_container_width=True):
            suggested = q

prompt = st.chat_input("Ask Tara about orders, delivery, returns…", max_chars=1000) or suggested
if prompt:
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.spinner("Tara is typing…"):
        try:
            reply = run(chat.ask_tara(st.session_state.session_id, prompt))
        except Exception as err:  # quota, network, bad key…
            print(f"[app] Tara failed: {err!r}")
            if "429" in str(err) or "RESOURCE_EXHAUSTED" in str(err):
                reply = "I'm getting a lot of questions right now. Please try again in a minute."
            else:
                reply = "Sorry, something went wrong on my side. Please try again."
    st.session_state.messages.append({"role": "assistant", "content": reply})
    st.rerun()
