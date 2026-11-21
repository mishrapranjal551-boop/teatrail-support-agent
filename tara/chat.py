"""A small helper to chat with Tara from Python (used by test_tricky.py and app.py)."""

import uuid

from google.adk.runners import InMemoryRunner
from google.genai import types

from .agent import root_agent

APP_NAME = "teatrail_support"
MAX_MESSAGE_CHARS = 1000  # very long messages are cut, a simple guard against abuse

_runner = InMemoryRunner(agent=root_agent, app_name=APP_NAME)


async def new_session(user_id: str = "customer") -> str:
    """Starts a fresh conversation and returns its session ID."""
    session = await _runner.session_service.create_session(
        app_name=APP_NAME, user_id=user_id, session_id=str(uuid.uuid4())
    )
    return session.id


async def ask_tara(session_id: str, message: str, user_id: str = "customer") -> str:
    """Sends one customer message and returns Tara's reply."""
    message = message.strip()[:MAX_MESSAGE_CHARS]
    content = types.Content(role="user", parts=[types.Part(text=message)])
    reply = ""
    async for event in _runner.run_async(
        user_id=user_id, session_id=session_id, new_message=content
    ):
        if event.is_final_response() and event.content and event.content.parts:
            reply = "".join(p.text or "" for p in event.content.parts).strip()
    return reply or "Sorry, I couldn't answer that just now. Please try again."
