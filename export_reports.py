"""Excel report built from the same validated frames the app shows."""
import io
import pandas as pd
from openpyxl.styles import Font, PatternFill


def build_workbook(label, rec, weekly, alerts, rejected, warnings, budget_df=None, unit_df=None, investigations=None):
    exp = rec[rec.kind == "expense"]
    summary = pd.DataFrame([
        ("Dataset", label), ("Date range", f"{rec.date.min().date()} to {rec.date.max().date()}" if len(rec) else "n/a"),
        ("Total expenses (accepted records)", round(exp.amount.sum(), 2)), ("Alerts", len(alerts)),
        ("Rejected/unresolved rows", len(rejected)),
        ("Note", "Alerts are observed increases, not proof of waste. Estimates are labelled and separate from actuals."),
    ], columns=["Item", "Value"])
    sheets = {"Executive Summary": summary, "Expense Analysis": weekly.assign(week=weekly.week.dt.date),
              "Alerts": alerts.assign(week=alerts.week.dt.date) if len(alerts) else alerts,
              "Data Quality": pd.DataFrame(list(rejected) + [dict(status="warning", reason=w) for w in warnings])}
    if unit_df is not None and len(unit_df):
        sheets["Activity Analysis"] = unit_df.assign(week=unit_df.week.dt.date)
    if budget_df is not None and len(budget_df):
        sheets["Budget Monitoring"] = budget_df
    sheets["Investigations"] = pd.DataFrame(investigations or [], columns=["id", "alert_key", "priority", "assignee", "status", "suspected_cause", "next_action", "final_findings", "verified_impact"]) if not investigations else pd.DataFrame(investigations).drop(columns=["snapshot"], errors="ignore")
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as w:
        for name, df in sheets.items():
            df.to_excel(w, sheet_name=name, index=False)
            ws = w.sheets[name]
            for c in ws[1]:
                c.font, c.fill = Font(bold=True, color="FFFFFF"), PatternFill("solid", fgColor="1F4E78")
            for col in ws.columns:
                ws.column_dimensions[col[0].column_letter].width = min(60, max(12, max(len(str(c.value or "")) for c in col) + 2))
    return buf.getvalue()
