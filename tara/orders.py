"""Customer orders, saved in orders.csv. Prices and totals are worked out here, never by the AI."""

import csv
import re
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path

from .menu import load_menu

ORDERS_FILE = Path(__file__).resolve().parent.parent / "orders.csv"
FIELDS = ["order_id", "time", "customer_name", "phone", "address", "items", "subtotal",
          "delivery_fee", "total", "payment", "status"]
FIRST_ORDER_NUMBER = 1001
FREE_DELIVERY_ABOVE = 499  # from the FAQ: free above ₹499, else a flat ₹49
DELIVERY_FEE = 49
MAX_QTY = 20
IST = timezone(timedelta(hours=5, minutes=30))

_lock = threading.Lock()
_ITEM = re.compile(r"^\s*(\d+)\s*(?:x|×|\*|pcs?|packs?|nos?)?\s*(.+?)\s*$", re.I)


def _find_item(name: str, menu: list[dict]) -> dict | None:
    """Matches a customer's item name to the menu, ignoring case and small differences."""
    want = re.sub(r"[^a-z0-9 ]", "", name.lower()).strip()
    for m in menu:
        have = re.sub(r"[^a-z0-9 ]", "", m["Item"].lower())
        if want == have:
            return m
    matches = [m for m in menu if want and (want in re.sub(r"[^a-z0-9 ]", "", m["Item"].lower()))]
    return matches[0] if len(matches) == 1 else None


def _parse_items(items: str, menu: list[dict]) -> tuple[list[tuple[int, dict]], list[str]]:
    """'2 x Masala Chai Blend, 1 Coorg Filter Coffee' -> [(2, item), (1, item)], unknown names."""
    found, unknown = [], []
    for part in re.split(r"[,;\n]+|\band\b", items):
        if not part.strip():
            continue
        m = _ITEM.match(part)
        qty, name = (int(m.group(1)), m.group(2)) if m else (1, part.strip())
        item = _find_item(name, menu)
        if item is None or not 1 <= qty <= MAX_QTY:
            unknown.append(part.strip())
        else:
            found.append((qty, item))
    return found, unknown


def _next_order_number() -> int:
    if not ORDERS_FILE.exists():
        return FIRST_ORDER_NUMBER
    highest = FIRST_ORDER_NUMBER - 1
    with ORDERS_FILE.open(newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            try:
                highest = max(highest, int(row["order_id"].removeprefix("ORD-")))
            except (KeyError, ValueError, AttributeError):
                continue
    return highest + 1


def place_order(items: str, customer_name: str, phone: str, address: str) -> dict:
    """Places a Cash on Delivery order for items from the TeaTrail menu.

    Only call this AFTER the customer has confirmed the items, quantities, name, phone
    number and delivery address, and said yes to placing the order.

    Args:
        items: The items and quantities, using exact names from the MENU, separated by
            commas, e.g. "2 x Masala Chai Blend, 1 x Coorg Filter Coffee".
        customer_name: The customer's name for the delivery.
        phone: The customer's 10-digit mobile number.
        address: The full delivery address including the 6-digit PIN code.

    Returns:
        A dict with ok=True and the order_id, the order lines, subtotal, delivery_fee
        and total in rupees, or ok=False and a problem to fix with the customer.
    """
    menu = load_menu()
    found, unknown = _parse_items(str(items), menu)
    if unknown:
        return {"ok": False, "problem": f"These items are not on the menu or the quantity is wrong: {', '.join(unknown)}. "
                                       f"Quantities must be 1 to {MAX_QTY}. Ask the customer to choose from the MENU."}
    if not found:
        return {"ok": False, "problem": "No items were given. Ask the customer what they would like to order."}
    digits = re.sub(r"\D", "", str(phone))
    if len(digits) == 12 and digits.startswith("91"):
        digits = digits[2:]
    if not re.fullmatch(r"[6-9]\d{9}", digits):
        return {"ok": False, "problem": "The phone number must be a 10-digit Indian mobile number. Ask for it again."}
    name = str(customer_name).strip()[:80]
    if len(name) < 2:
        return {"ok": False, "problem": "The customer's name is missing. Ask for it."}
    addr = " ".join(str(address).split())[:300]
    if not re.search(r"\b\d{6}\b", addr):
        return {"ok": False, "problem": "The address needs a 6-digit PIN code. Ask for the full address with PIN code."}

    lines = [f"{qty} x {it['Item']} ({it['Pack']}) = ₹{qty * int(it['Price']):,}" for qty, it in found]
    subtotal = sum(qty * int(it["Price"]) for qty, it in found)
    delivery_fee = 0 if subtotal > FREE_DELIVERY_ABOVE else DELIVERY_FEE
    total = subtotal + delivery_fee
    row = {
        "time": datetime.now(IST).strftime("%Y-%m-%d %H:%M:%S"),
        "customer_name": name,
        "phone": digits,
        "address": addr,
        "items": "; ".join(lines),
        "subtotal": subtotal,
        "delivery_fee": delivery_fee,
        "total": total,
        "payment": "Cash on Delivery",
        "status": "placed",
    }
    with _lock:
        order_id = f"ORD-{_next_order_number()}"
        is_new_file = not ORDERS_FILE.exists()
        with ORDERS_FILE.open("a", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=FIELDS)
            if is_new_file:
                writer.writeheader()
            writer.writerow({"order_id": order_id, **row})
    return {
        "ok": True,
        "order_id": order_id,
        "lines": lines,
        "subtotal": f"₹{subtotal:,}",
        "delivery_fee": "Free" if delivery_fee == 0 else f"₹{delivery_fee}",
        "total": f"₹{total:,}",
        "payment": "Cash on Delivery",
        "delivery_time": "2 to 4 days in metro cities, 4 to 7 days elsewhere",
    }


def orders_by_id(order_ids: set[str]) -> list[dict]:
    """The saved orders with these IDs, newest first (used by the web page sidebar)."""
    if not ORDERS_FILE.exists() or not order_ids:
        return []
    with ORDERS_FILE.open(newline="", encoding="utf-8") as f:
        rows = [r for r in csv.DictReader(f) if r.get("order_id") in order_ids]
    return list(reversed(rows))
