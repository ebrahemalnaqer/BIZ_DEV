import os
import pandas as pd
import streamlit as st
from smart_import import load_file, normalize, describe, BUDGET_TEMPLATE
from expense_engine import weekly_totals, detect_alerts, unit_costs
from budget_engine import monthly_budget
from investigation_store import Store, DuplicateInvestigation
from export_reports import build_workbook
from demo_data import demo

T = {
 "ar": dict(nav=["نظرة عامة", "التكاليف", "الميزانية", "التحقيقات", "التقارير والبيانات"], demo="تستخدم الآن بيانات تجريبية (وهمية)",
            pend="ملف مرفوع غير معتمد — لن يُستخدم قبل التأكيد", conf="بيانات مؤكدة من ملفك", up="ارفع ملف عملك", confirm="أؤكد استخدام هذه السجلات",
            thr="حد التنبيه %", ws="بداية الأسبوع", none="لا توجد نتائج", dayq="هل التواريخ مثل 03/04/2026 تعني: ", d1="يوم/شهر", d2="شهر/يوم",
            nob="لا توجد ميزانية. نزّل القالب وارفعه لمتابعة الإنفاق مقابل الميزانية.", tpl="تنزيل قالب الميزانية", inv="ابدأ تحقيقًا", dup="يوجد تحقيق لهذا التنبيه بالفعل",
            note="التنبيه زيادة ملحوظة وليس دليلًا على هدر أو احتيال.", unit="ما وحدة النشاط (مثال: طلب)؟", dl="تنزيل تقرير Excel", ref="تحقق من الفواتير والأسعار والكميات."),
 "en": dict(nav=["Overview", "Costs", "Budget", "Investigations", "Reports & Data"], demo="Using DEMO data (synthetic)",
            pend="Uploaded file NOT confirmed — it is not used until you confirm", conf="Confirmed data from your file", up="Upload your business file",
            confirm="Confirm and use these records", thr="Alert threshold %", ws="Week starts on", none="Nothing to show", dayq="Do dates like 03/04/2026 mean: ",
            d1="day/month", d2="month/day", nob="No budget yet. Download the template, fill it and upload it to track actual vs budget.", tpl="Download budget template",
            inv="Start investigation", dup="An investigation already exists for this alert", note="An alert is an observed increase, not proof of waste or fraud.",
            unit="What unit is the activity measured in (e.g. order)?", dl="Download Excel report", ref="Check invoices, prices and quantities."),
}
st.set_page_config(page_title="BizPilot AI", layout="wide")
lang = st.sidebar.radio("Language / اللغة", ["ar", "en"], format_func=lambda x: "العربية" if x == "ar" else "English")
t = T[lang]
if lang == "ar":
    st.markdown("<style>.stApp{direction:rtl;text-align:right}</style>", unsafe_allow_html=True)
thr = st.sidebar.slider(t["thr"], 5, 100, 25) / 100
days = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
ws = st.sidebar.selectbox(t["ws"], range(7), format_func=lambda i: days[i], index=0)
st.sidebar.caption("Default: Monday. Monthly budgets use each transaction's own date.")
store = Store(os.path.join("data", "investigations.db"))
S = st.session_state
tabs = st.tabs(t["nav"])

if "confirmed" in S:
    C = S.confirmed
    label, rec, budget, rej, warns = t["conf"], C["rec"], C["budget"], C["rej"], C["warns"]
else:
    rec, budget = demo(); rej, warns = [], []; label = t["demo"]

with tabs[0]:
    st.title("BizPilot AI")
    up = st.file_uploader(t["up"], type=["csv", "xlsx", "xls"])
    pending_msg = False
    if up:
        key = (up.name, up.size)
        if S.get("pkey") != key:
            S.pkey = key
            try: S.pending = dict(sheets=load_file(up.name, up.getvalue()))
            except ValueError as e: S.pending = dict(error=str(e))
        p = S.pending
        if "error" in p: st.error(p["error"])
        else:
            sheet = st.selectbox("Sheet", list(p["sheets"])) if len(p["sheets"]) > 1 else list(p["sheets"])[0]
            raw = p["sheets"][sheet]
            st.dataframe(raw.head(8))
            res = normalize(raw)
            if "date_format" in res["needs"]:
                c = st.radio(t["dayq"], [t["d1"], t["d2"]], index=None)
                if c: res = normalize(raw, dayfirst=(c == t["d1"]))
            if res["needs"]: st.warning("Waiting for a clarification / need a clearer header row: " + ", ".join(res["needs"]))
            else:
                pending_msg = True
                st.info(describe(res)); st.warning(t["pend"])
                if res["budget"] is not None: st.dataframe(res["budget"])
                else: st.dataframe(res["records"].head(20))
                if res["rejected"]: st.dataframe(pd.DataFrame(res["rejected"]))
                for w in res["warnings"]: st.caption(w)
                if st.button(t["confirm"]) and (len(res["records"]) or res["budget"] is not None):
                    old = S.get("confirmed", dict(rec=None, budget=None, rej=[], warns=[]))
                    if res["budget"] is not None:  # budget file: keep confirmed expense records
                        S.confirmed = dict(old, rec=old["rec"] if old["rec"] is not None else rec, budget=res["budget"], rej=old["rej"], warns=old["warns"])
                    else:
                        S.confirmed = dict(rec=res["records"], budget=None, rej=res["rejected"], warns=res["warnings"])
                    st.rerun()
    st.subheader(label if not pending_msg else f"{label}  |  {t['pend']}")
    exp = rec[rec.kind == "expense"]
    c1, c2 = st.columns(2)
    c1.metric("Expenses", f"{exp.amount.sum():,.0f}"); c2.metric("Income", f"{rec[rec.kind == 'income'].amount.sum():,.0f}")

weekly = weekly_totals(rec, ws)
alerts, awarns = detect_alerts(weekly, thr)
with tabs[1]:
    st.caption(t["note"])
    st.dataframe(weekly.pivot(index="week", columns="category", values="amount"))
    for w in awarns + warns: st.caption(w)
    st.dataframe(alerts.drop(columns=["alert_key"]) if len(alerts) else pd.DataFrame())
    for _, a in alerts.iterrows():
        if st.button(f"{t['inv']}: {a.category} {a.week.date()}", key=a.alert_key):
            try: store.create(a.alert_key, "expense", a.drop("next_steps").to_dict()); st.success("OK")
            except DuplicateInvestigation: st.info(t["dup"])
    udf = None
    if (rec.kind == "activity").any():
        cats = sorted(weekly.category.unique())
        cat = st.selectbox("Category", cats); unit = st.text_input(t["unit"])
        udf, uw = unit_costs(rec, weekly, cat, unit, threshold=thr, week_start=ws)
        for w in uw: st.caption(w)
        if len(udf): st.dataframe(udf)
bdf = None
with tabs[2]:
    if budget is None or budget.empty:
        st.info(t["nob"])
    else:
        bdf = monthly_budget(rec, budget); st.dataframe(bdf)
    st.download_button(t["tpl"], BUDGET_TEMPLATE, "budget_template.csv")
with tabs[3]:
    for r in store.list():
        with st.expander(f"#{r['id']} {r['alert_key']} — {r['status']}"):
            pr = st.selectbox("Priority", ["High", "Medium", "Low"], ["High", "Medium", "Low"].index(r["priority"]), key=f"p{r['id']}")
            f = {k: st.text_input(k, r[k] or "", key=f"{k}{r['id']}") for k in ("assignee", "suspected_cause", "notes", "next_action")}
            stt = st.selectbox("Status", ["Open", "In progress"], 0 if r["status"] != "In progress" else 1, key=f"s{r['id']}") if r["status"] != "Resolved" else None
            if r["status"] != "Resolved":
                if st.button("Save", key=f"sv{r['id']}"): store.update(r["id"], priority=pr, status=stt, **f); st.rerun()
                fin = st.text_area("Final findings (required to resolve)", key=f"f{r['id']}")
                imp = st.text_input("Verified financial impact (optional, enter only if verified)", key=f"i{r['id']}")
                if st.button("Resolve", key=f"r{r['id']}"):
                    try: store.resolve(r["id"], fin, float(imp) if imp.strip() else None); st.rerun()
                    except ValueError as e: st.error(str(e))
            else: st.write(r["final_findings"], r["verified_impact"])
with tabs[4]:
    st.write(label)
    data = build_workbook(label, rec, weekly, alerts, rej, awarns + warns, bdf, udf, store.list())
    st.download_button(t["dl"], data, "bizpilot_report.xlsx")
    with st.expander("Advanced"):
        st.dataframe(rec)
