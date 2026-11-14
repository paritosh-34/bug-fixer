"""
buggy.py — the patient. Has two bugs on purpose.

Run it:  uv run buggy.py
Fix it:  uv run buggy.py 2>&1 | uv run python agent.py
Expected output once fixed:
    Subtotal: 1150.0
    Total after 10% discount: 1035.0

Bug 1 crashes first. Bug 2 only shows up after bug 1 is fixed,
which is why the agent needs to re-run the file, not just patch once.
"""

cart = [
    {"name": "notebook", "price": 150.0, "quantity": 3},
    {"name": "pen", "price": 20.0, "quantity": 10},
    {"name": "backpack", "price": 500.0, "quantity": 1},
]


def subtotal(items):
    return sum(item["price"] * item["qty"] for item in items)


def apply_discount(amount, percent):
    return amount * (1 - percent / 100)


if __name__ == "__main__":
    sub = subtotal(cart)
    print("Subtotal: " + str(sub))
    print("Total after 10% discount: " + apply_discount(sub, 10))
