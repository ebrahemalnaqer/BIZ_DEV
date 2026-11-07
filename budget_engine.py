"""Monthly budget vs actual using ORIGINAL transaction dates, with guarded run-rate estimates."""
import pandas as pd


def monthly_budget(rec, budget):
    e = rec[rec.kind == "expense"].copy()
    e["month"] = e.date.dt.strftime("%Y-%m")
    as_of = rec.date.max()
    act = e.groupby(["category", "month"]).amount.sum()
    days = e.groupby(["category", "month"]).date.nunique()
    rows = []
    for _, b in budget.iterrows():
        key = (b.category, b.month)
        per = pd.Period(b.month)
        row = dict(category=b.category, month=b.month, budget=b.budget, actual=None, remaining=None, pct_consumed=None,
                   estimated_month_end=None, status="", note="")
        if key not in act.index:
            row.update(status="No actual data", note="No expense records for this category and month; not treated as zero.")
        else:
            a = float(act[key])
            row.update(actual=round(a, 2), remaining=round(b.budget - a, 2), pct_consumed=round(a / b.budget * 100, 1) if b.budget else None)
            row["status"] = "Over budget" if a > b.budget else "Within budget"
            if as_of >= per.end_time.normalize():
                row["note"] = "Month complete in the data."
            elif as_of < per.start_time:
                row["note"] = "Month not started in the data."
            else:
                el = as_of.day
                if el >= 14 and days[key] >= 0.7 * el:
                    est = a / el * per.days_in_month
                    row.update(estimated_month_end=round(est, 2), note="ESTIMATE: daily run-rate; actual and estimate are separate.")
                    if est > b.budget and a <= b.budget:
                        row["status"] = "Estimated to exceed budget"
                else:
                    row["note"] = "No forecast: too few days or too irregular records for a reliable estimate."
        rows.append(row)
    return pd.DataFrame(rows)
