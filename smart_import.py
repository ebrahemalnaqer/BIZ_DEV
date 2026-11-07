"""Rule-based import: header detection, Arabic/English field recognition, mixed values, provenance."""
import csv, io, re
import pandas as pd

AR = str.maketrans("٠١٢٣٤٥٦٧٨٩٫٬", "0123456789.,")
ALIASES = {
    "date": ["date", "day", "التاريخ", "اليوم"],
    "expense": ["expense", "expenses", "cost", "amount", "المصروف", "المصروفات", "مصروفات", "التكلفة", "المبلغ"],
    "income": ["income", "revenue", "sales", "الدخل", "الإيرادات", "ايرادات", "المبيعات"],
    "category": ["category", "type", "item", "الفئة", "التصنيف", "البند", "النوع"],
    "activity": ["orders", "order count", "quantity", "units", "عدد الطلبات", "الطلبات", "الكمية", "الإنتاج"],
    "budget": ["budget", "الميزانية", "ميزانية"],
    "month": ["month", "الشهر"],
    "description": ["description", "details", "الوصف", "التفاصيل"],
    "notes": ["notes", "note", "ملاحظات"],
}
COLS = ["source_row", "date", "kind", "category", "amount", "description", "original_value", "original_column"]


def _s(v):
    return "" if v is None or (isinstance(v, float) and pd.isna(v)) else str(v).strip().translate(AR)


def _blank(v):
    return _s(v) in ("", "-", "--", "...", "nan", "None")


def _frame(rows):
    w = max((len(r) for r in rows), default=0)
    return pd.DataFrame([list(r) + [None] * (w - len(r)) for r in rows], dtype=object)


def load_file(name, data):
    ext = name.lower().rsplit(".", 1)[-1] if "." in name else ""
    if ext == "xls":
        raise ValueError("Legacy .xls files are not supported (no reader installed). Save as .xlsx or .csv and upload again.")
    if ext == "csv":
        for enc in ("utf-8-sig", "cp1256"):
            try:
                text = data.decode(enc)
                break
            except UnicodeDecodeError:
                continue
        else:
            raise ValueError("Could not read the CSV text encoding.")
        return {"csv": _frame(list(csv.reader(io.StringIO(text))))}
    if ext == "xlsx":
        from openpyxl import load_workbook
        try:
            wb = load_workbook(io.BytesIO(data), data_only=True)
        except Exception as e:
            raise ValueError(f"Could not read the Excel file: {e}")
        return {ws.title: _frame([list(r) for r in ws.iter_rows(values_only=True)]) for ws in wb.worksheets}
    raise ValueError("Unsupported file type. Please upload .csv or .xlsx.")


def _role(h):
    h = _s(h).lower()
    if not h:
        return None
    for role, al in ALIASES.items():
        if h in al:
            return role
    for role, al in ALIASES.items():
        if any(a in h for a in al):
            return role
    return None


def find_header(raw):
    best = (0, None, {})
    for i in range(min(15, len(raw))):
        mp = {}
        for c, v in enumerate(raw.iloc[i]):
            r = _role(v)
            if r and r not in mp:
                mp[r] = c
        if len(mp) > best[0]:
            best = (len(mp), i, mp)
    return (best[1], best[2]) if best[0] >= 2 else (None, {})


def parse_amount(v):
    """-> (number, leftover text, status) ; status ok | mixed | missing | unparseable."""
    s = _s(v)
    if s in ("", "-", "nan", "None"):
        return None, None, "missing"
    try:
        return float(s.replace(",", "")), "", "ok"
    except ValueError:
        pass
    m = re.findall(r"-?\d[\d,]*\.?\d*", s)
    if len(m) == 1:
        return float(m[0].replace(",", "")), s.replace(m[0], "", 1).strip(), "mixed"
    return None, None, "unparseable"


def parse_dates(vals, dayfirst):
    pats = []
    for v in vals:
        m = re.match(r"^(\d{1,2})[/.-](\d{1,2})[/.-](\d{4})$", _s(v))
        pats.append(tuple(map(int, m.groups())) if m else None)
    p = [x for x in pats if x]
    if dayfirst is None and p:
        if any(a > 12 for a, b, y in p):
            dayfirst = True
        elif any(b > 12 for a, b, y in p):
            dayfirst = False
        elif any(a != b for a, b, y in p):
            return None, True  # genuinely ambiguous: ask the user
        else:
            dayfirst = True
    out = []
    for v, pt in zip(vals, pats):
        s = _s(v)
        try:
            if pt:
                a, b, y = pt
                d, mo = (a, b) if dayfirst else (b, a)
                out.append(pd.Timestamp(y, mo, d))
            elif re.match(r"^\d{4}-\d{1,2}-\d{1,2}", s):
                out.append(pd.to_datetime(s[:10], errors="coerce"))
            else:
                out.append(pd.NaT)
        except ValueError:
            out.append(pd.NaT)
    return out, False


def _month(v, dayfirst=True):
    s = _s(v)
    m = re.match(r"^(\d{4})-(\d{1,2})", s)
    return f"{int(m[1])}-{int(m[2]):02d}" if m else None


def normalize(raw, dayfirst=None):
    res = dict(records=pd.DataFrame(columns=COLS), budget=None, rejected=[], warnings=[], needs=[], mapping={}, header_row=None)
    h, mp = find_header(raw)
    if h is None:
        res["needs"].append("header")
        res["warnings"].append("No header row could be recognised.")
        return res
    res["header_row"], res["mapping"] = h, mp
    hdr, body = raw.iloc[h], raw.iloc[h + 1:]
    if "budget" in mp and "category" in mp and ("month" in mp or "date" in mp):
        rows = []
        for i, row in body.iterrows():
            mo = _month(row[mp.get("month", mp.get("date"))])
            amt, _, st = parse_amount(row[mp["budget"]])
            cat = _s(row[mp["category"]])
            if _blank(cat) and st == "missing":
                continue
            if mo and cat and st in ("ok", "mixed") and amt >= 0:
                rows.append(dict(category=cat, month=mo, budget=amt))
            else:
                res["rejected"].append(dict(source_row=i + 1, status="rejected", reason="Budget row needs category, month (YYYY-MM) and amount", original=" | ".join(map(_s, row))))
        res["budget"] = pd.DataFrame(rows, columns=["category", "month", "budget"])
        return res
    if "date" not in mp:
        res["needs"].append("date_column")
        res["warnings"].append("No date column found.")
        return res
    dates, amb = parse_dates(list(body[mp["date"]]), dayfirst)
    if amb:
        res["needs"].append("date_format")
        return res
    recs, ign = [], 0
    for k, (i, row) in enumerate(body.iterrows()):
        vals = {r: row[c] for r, c in mp.items()}
        if all(_blank(v) for v in vals.values()):
            ign += 1
            continue
        orig = " | ".join(map(_s, row))
        if pd.isna(dates[k]):
            res["rejected"].append(dict(source_row=i + 1, status="rejected", reason="Date could not be read", original=orig))
            continue
        cat, desc, done = _s(vals.get("category")), _s(vals.get("description")), False
        for role in ("expense", "income", "activity"):
            if role not in mp:
                continue
            amt, rest, st = parse_amount(vals[role])
            if st == "missing":
                continue
            done = True
            if st == "unparseable" or amt < 0:
                res["rejected"].append(dict(source_row=i + 1, status="rejected", reason=f"'{_s(vals[role])}' in the {role} column is not a clear positive number", original=orig))
                continue
            col = _s(hdr[mp[role]])
            c = cat or (rest if role == "expense" and rest else {"income": "Income", "activity": col}.get(role, "Uncategorized"))
            recs.append(dict(source_row=i + 1, date=dates[k], kind=role, category=c, amount=amt,
                             description=rest or desc, original_value=_s(vals[role]), original_column=col))
        if not done:
            res["rejected"].append(dict(source_row=i + 1, status="unresolved", reason="No amount in this row (missing values are never treated as zero)", original=orig))
    if ign:
        res["warnings"].append(f"{ign} empty or placeholder rows were ignored.")
    r = pd.DataFrame(recs, columns=COLS)
    r["date"] = pd.to_datetime(r["date"])
    res["records"] = r
    return res


def describe(res):
    r = res["records"]
    if r.empty:
        return "No usable records were found yet."
    k = r.kind.value_counts().to_dict()
    return (f"I found a table starting at row {res['header_row'] + 1} with {k.get('expense', 0)} expense entries, "
            f"{k.get('income', 0)} income entries and {k.get('activity', 0)} activity entries, "
            f"from {r.date.min().date()} to {r.date.max().date()}. {len(res['rejected'])} rows need attention.")


BUDGET_TEMPLATE = "category,month,budget\nIngredients,2026-09,5000\nUtilities,2026-09,1200\n"
