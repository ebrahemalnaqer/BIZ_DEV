"""Weekly expense analysis, alerts, and activity-adjusted unit cost."""
import pandas as pd

NEXT_STEPS = ("Check invoices and supplier prices for this category and week, compare quantities with activity, "
              "and confirm any one-off purchases. This is an observed increase, not proof of waste or error.")


def week_of(dates, week_start=0):
    return dates - pd.to_timedelta((dates.dt.weekday - week_start) % 7, unit="D")


def weekly_totals(rec, week_start=0):
    e = rec[rec.kind == "expense"].copy()
    if e.empty:
        return pd.DataFrame(columns=["category", "week", "amount"])
    e["week"] = week_of(e.date, week_start)
    return e.groupby(["category", "week"], as_index=False).amount.sum()


def detect_alerts(weekly, threshold=0.25, n=3, min_base=2):
    alerts, warns = [], []
    for cat, g in weekly.groupby("category"):
        hist, prev, prev_flag = [], None, False
        for w, a in zip(*[g.sort_values("week")[c] for c in ("week", "amount")]):
            if prev is not None and (w - prev).days != 7:
                hist = []
                warns.append(f"{cat}: weeks are missing before {w.date()}; the baseline restarted (gaps are not filled with zero).")
            prev, base, flag = w, hist[-n:], False
            if len(base) >= min_base:
                m = sum(base) / len(base)
                if m > 0 and a > m * (1 + threshold):
                    flag = True
                    alerts.append(dict(alert_key=f"expense|{cat}|{w.date()}", category=cat, week=w, actual=a, baseline=round(m, 2),
                                       change_pct=round((a / m - 1) * 100, 1), status="repeated" if prev_flag else "new", next_steps=NEXT_STEPS))
            prev_flag = flag
            hist.append(a)
    cols = ["alert_key", "category", "week", "actual", "baseline", "change_pct", "status", "next_steps"]
    return pd.DataFrame(alerts, columns=cols), warns


def unit_costs(rec, weekly, category, unit_label, activity_col=None, threshold=0.25, week_start=0, n=3):
    empty = pd.DataFrame()
    if not str(unit_label).strip():
        return empty, ["The unit of the activity measure is unknown, so no unit cost was calculated."]
    a = rec[rec.kind == "activity"].copy()
    if activity_col:
        a = a[a.original_column == activity_col]
    if a.empty:
        return empty, ["No activity records are available."]
    a["week"] = week_of(a.date, week_start)
    aw = a.groupby("week", as_index=False).amount.sum().rename(columns={"amount": "units"})
    cw = weekly[weekly.category == category][["week", "amount"]]
    m = cw.merge(aw, on="week", how="outer", indicator=True).sort_values("week")
    warns = []
    if (m._merge != "both").any():
        warns.append(f"{int((m._merge != 'both').sum())} week(s) have spending without activity or activity without spending; they were excluded.")
    m = m[(m._merge == "both") & (m.units > 0)].drop(columns="_merge").reset_index(drop=True)
    m["unit_cost"] = m.amount / m.units
    base, chg, tot, flags, hist = [], [], [], [], []
    for i, r in m.iterrows():
        consecutive = i > 0 and (r.week - m.week[i - 1]).days == 7
        if not consecutive:
            if i > 0:
                warns.append(f"Weeks are missing before {r.week.date()}; the unit-cost baseline restarted.")
            hist = []
        b = hist[-n:]
        bl = sum(b) / len(b) if len(b) >= 2 else None
        base.append(bl)
        chg.append(round((r.unit_cost / bl - 1) * 100, 1) if bl else None)
        tot.append(round((r.amount / m.amount[i - 1] - 1) * 100, 1) if consecutive and m.amount[i - 1] else None)
        flags.append(bool(bl and r.unit_cost > bl * (1 + threshold)))
        hist.append(r.unit_cost)
    m["baseline_unit_cost"], m["unit_cost_change_pct"], m["total_change_pct"], m["flag"] = base, chg, tot, flags
    m["unit"] = unit_label
    return m, warns
