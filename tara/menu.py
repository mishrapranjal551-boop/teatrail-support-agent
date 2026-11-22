"""TeaTrail's product menu (Category, Item, Pack, Price, Description) from data/menu.csv."""

import csv
from pathlib import Path

MENU_FILE = Path(__file__).resolve().parent.parent / "data" / "menu.csv"
CATEGORIES = ["Tea", "Coffee", "Snacks", "Gift Hampers"]


def load_menu() -> list[dict]:
    """Reads the menu. Returns an empty list if the file is missing, so Tara still starts."""
    if not MENU_FILE.exists():
        return []
    with MENU_FILE.open(newline="", encoding="utf-8") as f:
        rows = []
        for row in csv.DictReader(f):
            item = {k: (v or "").strip() for k, v in row.items()}
            if item.get("Category") and item.get("Item") and item.get("Price", "").isdigit():
                rows.append(item)
        return rows


def menu_as_text(menu: list[dict]) -> str:
    """The menu grouped by category, one line per item, for Tara's instructions."""
    if not menu:
        return "(The menu is not available right now.)"
    lines = []
    for category in CATEGORIES + sorted({m["Category"] for m in menu} - set(CATEGORIES)):
        items = [m for m in menu if m["Category"] == category]
        if not items:
            continue
        lines.append(f"### {category}")
        for m in items:
            price = f"₹{int(m['Price']):,}"
            lines.append(f"- {m['Item']} ({m['Pack']}): {price}. {m['Description']}")
    return "\n".join(lines)
