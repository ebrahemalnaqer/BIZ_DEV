"""Synthetic demo data (no real information)."""
import numpy as np, pandas as pd


def demo():
    rng = np.random.default_rng(7)
    days = pd.date_range("2026-07-06", "2026-09-27")
    rows = []
    for i, d in enumerate(days):
        orders = int(rng.integers(80, 120))
        rows.append((d, "activity", "Orders", orders, "Orders"))
        spike = 1.6 if d >= pd.Timestamp("2026-09-14") else 1.0
        rows.append((d, "expense", "Ingredients", round(orders * 4.2 * spike + rng.normal(0, 10), 2), "Expense"))
        rows.append((d, "income", "Income", round(orders * 18 + rng.normal(0, 30), 2), "Income"))
        if d.weekday() == 0:
            rows.append((d, "expense", "Packaging", round(rng.uniform(180, 220), 2), "Expense"))
    r = pd.DataFrame(rows, columns=["date", "kind", "category", "amount", "original_column"])
    r["source_row"], r["description"], r["original_value"] = range(1, len(r) + 1), "", r.amount.astype(str)
    budget = pd.DataFrame([("Ingredients", m, 14000.0) for m in ("2026-07", "2026-08", "2026-09")] + [("Packaging", "2026-09", 900.0)], columns=["category", "month", "budget"])
    return r, budget
