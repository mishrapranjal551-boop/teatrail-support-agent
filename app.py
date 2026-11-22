"""TeaTrail Store Support: a Streamlit chat page for Tara.

Run on your laptop:  streamlit run app.py
"""

import asyncio
import csv
import os
import re
import threading
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import streamlit as st

IST = timezone(timedelta(hours=5, minutes=30))
from dotenv import load_dotenv

st.set_page_config(page_title="TeaTrail Store Support", page_icon="🍵")


def secret(name: str) -> str | None:
    """Reads a value from Streamlit secrets (when deployed) or .env (on my laptop)."""
    try:
        if st.secrets.get(name):
            return str(st.secrets[name])
    except Exception:  # no secrets.toml on this machine
        pass
    return os.getenv(name) or None


load_dotenv(Path(__file__).resolve().parent / ".env")
api_key = secret("GOOGLE_API_KEY")

if not api_key:
    st.error("GOOGLE_API_KEY is missing. Add it to .env on your laptop, or to the app's Secrets on Streamlit Cloud.")
    st.stop()
os.environ["GOOGLE_API_KEY"] = api_key  # Tara's Gemini client reads it from here
# Optional: where orders are saved permanently (the TeaTrail Orders Google Sheet).
for _name in ("ORDERS_WEBHOOK_URL", "ORDERS_WEBHOOK_SECRET"):
    if secret(_name):
        os.environ[_name] = secret(_name)

st.title("🍵 TeaTrail Store Support")


# ---- Store photos (free Unsplash photos, loaded from Unsplash's image CDN) ------------
def photo(photo_id: str, w: int, h: int) -> str:
    """A cropped Unsplash photo URL at the size we need, so pages load fast."""
    return f"https://images.unsplash.com/photo-{photo_id}?auto=format&fit=crop&w={w}&h={h}&q=75"


BANNER = photo("1491497895121-1334fc14d8c9", 1400, 420)  # tea gardens in Munnar, Kerala
SIDEBAR_CUP = photo("1491720731493-223f97d92c21", 600, 360)
CATEGORIES = [
    ("Tea", "1765153743332-949b8d623d92", "Loose tea and tea bags, cups of tea and tea leaves"),
    ("Coffee", "1447933601403-0c6688de566e", "Roasted coffee beans"),
    ("Snacks", "1576717585968-8ea8166b89b8", "Tea-time cookies"),
    ("Gift hampers", "1508899203029-1c9eb493c9bd", "A gift basket of treats"),
]

st.image(BANNER, width="stretch", alt="Green tea gardens on misty hills in Munnar, Kerala")
st.caption("Fresh from India’s tea gardens to your cup. Tara is here to help, day and night.")

# ---- Message limits (protect the Gemini quota on a public page) --------------------
# Anyone can open the page, so instead of a passcode we limit how much one visitor,
# and the whole site, can send per day. Change the numbers in Secrets if needed.
MAX_PER_VISITOR = int(secret("MAX_MESSAGES_PER_VISITOR") or 30)  # per visitor, per day
MAX_PER_DAY = int(secret("MAX_MESSAGES_PER_DAY") or 500)  # whole site, per day
MIN_SECONDS_BETWEEN = 3  # stops someone pasting messages in a fast loop


@st.cache_resource
def usage_counter() -> dict:
    """One shared counter for every visitor, reset each day (Indian time)."""
    return {"lock": threading.Lock(), "day": None, "total": 0, "visitors": {}}


def visitor_id() -> str:
    """The visitor's IP address, or this browser session if the IP is unknown."""
    try:
        ip = st.context.ip_address
    except Exception:
        ip = None
    return ip or f"session-{st.session_state.get('session_id', 'unknown')}"


def limit_message() -> str | None:
    """Counts one message. Returns a polite reason if this message is over a limit."""
    now = time.monotonic()
    last = st.session_state.get("last_sent", 0.0)
    if now - last < MIN_SECONDS_BETWEEN:
        return "You're typing fast! Please wait a few seconds before your next message."
    usage = usage_counter()
    today = datetime.now(IST).date()
    with usage["lock"]:
        if usage["day"] != today:
            usage.update(day=today, total=0, visitors={})
        who = visitor_id()
        if usage["total"] >= MAX_PER_DAY:
            return ("Tara has answered a lot of questions today and is taking a break. "
                    "Please try again tomorrow, or email our support team.")
        if usage["visitors"].get(who, 0) >= MAX_PER_VISITOR:
            return ("You've reached today's message limit. Please come back tomorrow, and Tara will be "
                    "happy to help. Any ticket she raised for you is still open.")
        usage["total"] += 1
        usage["visitors"][who] = usage["visitors"].get(who, 0) + 1
    st.session_state.last_sent = now
    return None

# ---- Tara (loaded once, on one long-running event loop) ---------------------------
def tara_version() -> str:
    """A fingerprint of Tara's code and menu. When a push changes them, it changes too."""
    import hashlib

    root = Path(__file__).resolve().parent
    h = hashlib.sha256()
    for f in sorted([*(root / "tara").glob("*.py"), root / "data" / "menu.csv"]):
        if f.exists():
            h.update(f.name.encode() + f.read_bytes())
    return h.hexdigest()[:12]


@st.cache_resource
def get_tara(version: str):
    """Imports Tara and starts one background event loop that all chats share.

    The cache is keyed on Tara's version, so after a push that changes her code or menu,
    Streamlit Cloud loads the NEW Tara instead of keeping the old one in memory.
    """
    import importlib
    import sys

    # Reload Tara's modules in order, so the new code is used (not an old cached copy).
    for name in ("tara.menu", "tara.faq", "tara.tickets", "tara.orders", "tara.agent", "tara.chat"):
        if name in sys.modules:
            importlib.reload(sys.modules[name])
    from tara import chat, tickets

    loop = asyncio.new_event_loop()
    threading.Thread(target=loop.run_forever, daemon=True).start()
    print(f"[app] Tara loaded (version {version})")
    return chat, tickets, loop


TARA_VERSION = tara_version()
chat, tickets, loop = get_tara(TARA_VERSION)


def run(coro):
    return asyncio.run_coroutine_threadsafe(coro, loop).result(timeout=120)


from tara.agent import GREETING  # noqa: E402

if "session_id" in st.session_state and st.session_state.get("tara_version") != TARA_VERSION:
    # Tara was updated while this chat was open: start a fresh conversation with the new Tara.
    st.session_state.session_id = run(chat.new_session())
    st.session_state.tara_version = TARA_VERSION
if "session_id" not in st.session_state:
    st.session_state.tara_version = TARA_VERSION
    st.session_state.session_id = run(chat.new_session())
    st.session_state.messages = [{"role": "assistant", "content": GREETING}]
    st.session_state.my_tickets = []  # ticket IDs raised in THIS visitor's chat
    st.session_state.my_orders = []  # order IDs placed in THIS visitor's chat

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
            datetime.now(IST).strftime("%Y-%m-%d %H:%M:%S"),
            question,
            st.session_state.messages[index]["content"],
            helpful,
        ])
    st.session_state.messages[index]["feedback"] = helpful


# ---- Sidebar: this customer's own tickets only -------------------------------------
# A public page must never show other customers' tickets or messages.
with st.sidebar:
    st.image(SIDEBAR_CUP, width="stretch", alt="A cup of tea with a tea bag")
    st.markdown("**TeaTrail Store**  \nTea, coffee, snacks and gift hampers, delivered across India.")
    st.caption("🚚 Free delivery on orders above ₹499 · Photos: Unsplash")
    st.divider()
    st.header("🧾 Your orders")
    from tara.orders import orders_by_id  # noqa: E402 (Tara is already loaded above)

    my_orders = orders_by_id(set(st.session_state.my_orders))
    if not my_orders:
        st.caption("No orders yet. Ask Tara for the menu and tell her what you'd like.")
    for o in my_orders:
        with st.container(border=True):
            st.markdown(f"**{o['order_id']}** · ₹{int(o['total']):,} · Cash on Delivery")
            st.caption(o["time"])
            for line in o["items"].split("; "):
                st.write(line)
    st.divider()
    st.header("🎫 Your tickets")
    mine = set(st.session_state.my_tickets)
    open_list = [t for t in tickets.open_tickets() if t["ticket_id"] in mine]
    if not open_list:
        st.caption("No tickets in this chat. If Tara raises one, it shows here.")
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
    st.markdown("##### Shop by category")
    for col, (label, pid, alt) in zip(st.columns(4), CATEGORIES):
        with col:
            st.image(photo(pid, 400, 300), width="stretch", alt=alt)
            if st.button(f"{label} menu", key=f"menu-{label}", use_container_width=True):
                suggested = f"Show me your {label} menu"
    st.markdown("##### Ask Tara")
    cols = st.columns(3)
    for col, q in zip(cols, ["Show me the full menu", "How much does delivery cost?", "What is your return policy?"]):
        if col.button(q, use_container_width=True):
            suggested = q

prompt = st.chat_input("Ask for the menu, place an order, or ask about delivery…", max_chars=1000) or suggested
if prompt:
    st.session_state.messages.append({"role": "user", "content": prompt})
    reply = limit_message()
    if reply is None:
        with st.spinner("Tara is typing…"):
            try:
                reply = run(chat.ask_tara(st.session_state.session_id, prompt))
            except Exception as err:  # quota, network, bad key…
                print(f"[app] Tara failed: {err!r}")
                if "429" in str(err) or "RESOURCE_EXHAUSTED" in str(err):
                    reply = "I'm getting a lot of questions right now. Please try again in a minute."
                else:
                    reply = "Sorry, something went wrong on my side. Please try again."
        for ticket_id in re.findall(r"TKT-\d+", reply):
            if ticket_id not in st.session_state.my_tickets:
                st.session_state.my_tickets.append(ticket_id)
        for order_id in re.findall(r"ORD-\d+", reply):
            if order_id not in st.session_state.my_orders:
                st.session_state.my_orders.append(order_id)
    st.session_state.messages.append({"role": "assistant", "content": reply})
    st.rerun()
