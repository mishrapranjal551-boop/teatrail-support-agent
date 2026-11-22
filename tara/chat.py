"""A small helper to chat with Tara from Python (used by test_tricky.py and app.py)."""

import asyncio
import re
import uuid

from google.adk.runners import InMemoryRunner
from google.genai import types

from .agent import root_agent
from .tickets import create_ticket

APP_NAME = "teatrail_support"
MAX_MESSAGE_CHARS = 1000  # very long messages are cut, a simple guard against abuse

_runner = InMemoryRunner(agent=root_agent, app_name=APP_NAME)


async def new_session(user_id: str = "customer") -> str:
    """Starts a fresh conversation and returns its session ID."""
    session = await _runner.session_service.create_session(
        app_name=APP_NAME, user_id=user_id, session_id=str(uuid.uuid4())
    )
    return session.id


# Safety net for ticket hand-offs. Gemini Flash-Lite sometimes writes the tool call
# as text ("call:default_api:create_ticket{...}") instead of calling it, or mentions
# an old ticket ID without raising a new one. The code below makes sure a real
# ticket is always saved and the customer only ever sees a real, new ticket ID.
_TEXT_CALL = re.compile(r"call:\s*[\w:.]*create_ticket\s*\{(.*?)\}", re.DOTALL)
_ARG_KEY = re.compile(r"(message|reason|priority)\s*:")
_TICKET_ID = re.compile(r"TKT-\d+")
_HANDOFF_LINE = "I've raised ticket {id} for you, and a person from TeaTrail will reply within 24 hours."


def _parse_text_call(args_text: str) -> dict:
    """Turns 'message:...,priority:high,reason:...' into a dict of arguments."""
    keys = list(_ARG_KEY.finditer(args_text))
    args = {}
    for i, key in enumerate(keys):
        end = keys[i + 1].start() if i + 1 < len(keys) else len(args_text)
        args[key.group(1)] = args_text[key.end():end].strip().strip(",").strip().strip("\"'")
    return args


def _check_ticket_reply(message: str, reply: str, created_ids: list[str]) -> str:
    """Fixes replies where Tara faked or skipped the create_ticket call."""
    text_call = _TEXT_CALL.search(reply)
    if text_call and not created_ids:
        args = _parse_text_call(text_call.group(1))
        ticket = create_ticket(
            message=args.get("message") or message,
            reason=args.get("reason") or "hand-off",
            priority=args.get("priority") or "normal",
        )
        before = reply[: text_call.start()].strip()
        line = _HANDOFF_LINE.format(id=ticket["ticket_id"])
        return f"{before} {line}".strip() if before else f"Thanks for your patience! {line}"

    mentioned = set(_TICKET_ID.findall(reply))
    if mentioned and not created_ids:
        # Tara named a ticket she never raised (often an old ID). Raise a real one.
        ticket = create_ticket(message=message, reason="hand-off (agent skipped the tool)", priority="high")
        created_ids = [ticket["ticket_id"]]
    if mentioned and created_ids:
        for old_id in mentioned - set(created_ids):
            reply = reply.replace(old_id, created_ids[-1])
    return reply


def _is_rate_limit(err: Exception) -> bool:
    text = f"{type(err).__name__} {err}"
    return "429" in text or "RESOURCE_EXHAUSTED" in text or "ResourceExhausted" in text


async def ask_tara(session_id: str, message: str, user_id: str = "customer") -> str:
    """Sends one customer message and returns Tara's reply.

    The free Gemini plan allows about 15 requests a minute. If Tara hits that
    limit, wait and try again (up to 2 times) instead of failing.
    """
    message = message.strip()[:MAX_MESSAGE_CHARS]
    content = types.Content(role="user", parts=[types.Part(text=message)])
    for attempt in range(3):
        try:
            reply = ""
            created_ids = []  # ticket IDs the create_ticket tool really returned this turn
            async for event in _runner.run_async(
                user_id=user_id, session_id=session_id, new_message=content
            ):
                for resp in event.get_function_responses() or []:
                    if resp.name == "create_ticket" and isinstance(resp.response, dict):
                        if resp.response.get("ticket_id"):
                            created_ids.append(resp.response["ticket_id"])
                if event.is_final_response() and event.content and event.content.parts:
                    reply = "".join(p.text or "" for p in event.content.parts).strip()
            reply = _check_ticket_reply(message, reply, created_ids)
            return reply or "Sorry, I couldn't answer that just now. Please try again."
        except Exception as err:
            if not _is_rate_limit(err) or attempt == 2:
                raise
            await asyncio.sleep(20)  # the free quota refills every minute
    raise RuntimeError("unreachable")
