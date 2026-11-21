"""Support tickets for hand-off to a person, saved in tickets.csv."""

import csv
import threading
from datetime import datetime
from pathlib import Path

TICKETS_FILE = Path(__file__).resolve().parent.parent / "tickets.csv"
FIELDS = ["ticket_id", "time", "customer_message", "reason", "priority", "status"]
FIRST_TICKET_NUMBER = 1001

_lock = threading.Lock()  # two chats at once can't get the same ID


def _next_ticket_number() -> int:
    """Highest ticket number in the file + 1, so IDs are never repeated."""
    if not TICKETS_FILE.exists():
        return FIRST_TICKET_NUMBER
    highest = FIRST_TICKET_NUMBER - 1
    with TICKETS_FILE.open(newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            try:
                highest = max(highest, int(row["ticket_id"].removeprefix("TKT-")))
            except (KeyError, ValueError, AttributeError):
                continue
    return highest + 1


def create_ticket(message: str, reason: str, priority: str) -> dict:
    """Creates a support ticket so a person from TeaTrail follows up with the customer.

    Use this when the answer is not in the FAQ, for a refund or return worth more
    than ₹2,000, for a damaged or wrong item, when the customer is angry or upset,
    or when the customer asks for a person.

    Args:
        message: The customer's message, in their own words.
        reason: A short reason, e.g. "damaged item", "refund over ₹2,000",
            "angry customer", "asked for a person", "not in FAQ".
        priority: "high" for damaged or wrong items, refunds or returns over
            ₹2,000, and angry or upset customers. "normal" for everything else.

    Returns:
        A dict with the new ticket_id to share with the customer.
    """
    priority = priority.strip().lower() if isinstance(priority, str) else "normal"
    if priority not in ("normal", "high"):
        priority = "normal"
    row = {
        "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "customer_message": str(message)[:1000],
        "reason": str(reason)[:200],
        "priority": priority,
        "status": "open",
    }
    with _lock:
        ticket_id = f"TKT-{_next_ticket_number()}"
        is_new_file = not TICKETS_FILE.exists()
        with TICKETS_FILE.open("a", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=FIELDS)
            if is_new_file:
                writer.writeheader()
            writer.writerow({"ticket_id": ticket_id, **row})
    return {
        "ticket_id": ticket_id,
        "status": "open",
        "next_step": "A person from TeaTrail will reply within 24 hours.",
    }


def open_tickets() -> list[dict]:
    """All tickets with status 'open', newest first (used by the web page)."""
    if not TICKETS_FILE.exists():
        return []
    with TICKETS_FILE.open(newline="", encoding="utf-8") as f:
        rows = [r for r in csv.DictReader(f) if r.get("status") == "open"]
    return list(reversed(rows))
