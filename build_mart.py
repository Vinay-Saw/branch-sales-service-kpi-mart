#!/usr/bin/env python3
"""Build the desk mart from the simulated extracts."""
import json
from collections import defaultdict
from datetime import datetime, date
from pathlib import Path

import pandas as pd

DATA = Path("/workspace/artifacts/branch-kpi-mart/data")
OUT = Path("/workspace/src/data/mart.json")

def dparse(s):
    if s is None or (isinstance(s, float) and pd.isna(s)):
        return None
    s = str(s)
    if not s or s in ("None", "nan", "NaT"):
        return None
    return datetime.strptime(s[:10], "%Y-%m-%d").date()

def ym(d):
    return f"{d.year:04d}-{d.month:02d}"

branches = pd.read_csv(DATA / "dim_branch.csv")
depts = pd.read_csv(DATA / "dim_department.csv")
emps = pd.read_csv(DATA / "dim_employee.csv")
bookings = pd.read_csv(DATA / "fact_bookings.csv")
leads = pd.read_csv(DATA / "fact_leads.csv")
inquiries = pd.read_csv(DATA / "fact_inquiries.csv")
quotes = pd.read_csv(DATA / "fact_quotations.csv")
units = pd.read_csv(DATA / "fact_units.csv")
pos = pd.read_csv(DATA / "fact_installation_pos.csv")
amc = pd.read_csv(DATA / "fact_amc.csv")
warranty = pd.read_csv(DATA / "fact_warranty.csv")
ros = pd.read_csv(DATA / "fact_repair_orders.csv")
targets = pd.read_csv(DATA / "fact_employee_targets.csv")

dates = []
for df, col in (
    (bookings, "agreement_date"),
    (leads, "lead_date"),
    (units, "installation_complete_date"),
    (ros, "open_date"),
):
    for v in df[col].dropna():
        d = dparse(v)
        if d:
            dates.append(d)
as_of = max(dates)
as_ym = ym(as_of)

months = []
y, m = min(dates).year, min(dates).month
while (y, m) <= (as_of.year, as_of.month):
    months.append(f"{y:04d}-{m:02d}")
    m += 1
    if m == 13:
        y, m = y + 1, 1
idx = {k: i for i, k in enumerate(months)}
ids = [int(x) for x in branches.branch_id]
NM = len(months)

def zeros():
    return {str(i): [0] * NM for i in ids}

book_val, book_units, book_n = zeros(), zeros(), zeros()
lead_n, inq_n, quo_n, acc_n = zeros(), zeros(), zeros(), zeros()
comp_n, start_n, po_amt = zeros(), zeros(), zeros()
inc_amt, amc_new, sales_target = zeros(), zeros(), zeros()

confirmed = bookings[bookings.status == "Confirmed"]
for r in confirmed.itertuples(index=False):
    d = dparse(r.agreement_date)
    if not d or ym(d) not in idx:
        continue
    i = idx[ym(d)]
    b = str(int(r.branch_id))
    book_val[b][i] += int(r.total_agreement_value_inr or 0)
    book_units[b][i] += int(r.number_of_units or 0)
    book_n[b][i] += 1

for r in leads.itertuples(index=False):
    d = dparse(r.lead_date)
    if d and ym(d) in idx:
        lead_n[str(int(r.branch_id))][idx[ym(d)]] += 1
for r in inquiries.itertuples(index=False):
    d = dparse(r.inquiry_date)
    if d and ym(d) in idx:
        inq_n[str(int(r.branch_id))][idx[ym(d)]] += 1
for r in quotes.itertuples(index=False):
    d = dparse(r.quotation_date)
    if not d or ym(d) not in idx:
        continue
    b = str(int(r.branch_id))
    quo_n[b][idx[ym(d)]] += 1
    if r.status == "Accepted":
        acc_n[b][idx[ym(d)]] += 1
for r in units.itertuples(index=False):
    b = str(int(r.branch_id))
    sd = dparse(getattr(r, "installation_start_date", None))
    cd = dparse(getattr(r, "installation_complete_date", None))
    if sd and ym(sd) in idx:
        start_n[b][idx[ym(sd)]] += 1
    if r.installation_status == "Completed" and cd and ym(cd) in idx:
        comp_n[b][idx[ym(cd)]] += 1
for r in pos.itertuples(index=False):
    d = dparse(r.po_date)
    if d and ym(d) in idx:
        po_amt[str(int(r.branch_id))][idx[ym(d)]] += int(r.amount_inr or 0)

month_targets = targets[(targets.period_type == "Month") & (targets.role == "Salesperson")]
for r in month_targets.itertuples(index=False):
    key = f"{int(r.year):04d}-{int(r.period_index):02d}"
    if key in idx:
        sales_target[str(int(r.branch_id))][idx[key]] += int(r.target_value)

# snapshots
snap = {}
for b in ids:
    snap[str(b)] = {
        "units": defaultdict(int),
        "poOpen": 0, "poTotal": 0,
        "amcActive": 0, "amcComp": 0, "amcNon": 0, "amcDue": 0, "amcValue": 0,
        "wActive": 0, "wExp90": 0,
        "roOpen": 0, "roOpenSla": 0, "roParts": 0, "roLabor": 0,
        "product": defaultdict(int),
    }
for r in units.itertuples(index=False):
    s = snap[str(int(r.branch_id))]
    s["units"][r.installation_status or "Pending"] += 1
    s["product"][r.product_type] += 1
for r in pos.itertuples(index=False):
    s = snap[str(int(r.branch_id))]
    amt = int(r.amount_inr or 0)
    s["poTotal"] += amt
    if r.status == "Open":
        s["poOpen"] += amt
for r in amc.itertuples(index=False):
    s = snap[str(int(r.branch_id))]
    if r.status == "Active":
        s["amcActive"] += 1
        s["amcValue"] += int(r.annual_value_inr or 0)
        if r.amc_type == "Comprehensive":
            s["amcComp"] += 1
        else:
            s["amcNon"] += 1
        end = dparse(r.end_date)
        if end and ym(end) == as_ym:
            s["amcDue"] += 1
for r in warranty.itertuples(index=False):
    s = snap[str(int(r.branch_id))]
    end = dparse(r.warranty_end_date)
    if r.status == "Active":
        s["wActive"] += 1
        if end and 0 <= (end - as_of).days <= 90:
            s["wExp90"] += 1
for r in ros.itertuples(index=False):
    s = snap[str(int(r.branch_id))]
    s["roParts"] += int(r.parts_cost_inr or 0)
    s["roLabor"] += int(r.labor_cost_inr or 0)
    if r.status in ("Open", "In Progress"):
        s["roOpen"] += 1
        if str(r.exceeded_sla).lower() == "true":
            s["roOpenSla"] += 1

def freeze(d):
    return {k: (dict(v) if isinstance(v, defaultdict) else v) for k, v in d.items()}

sp = defaultdict(lambda: {"value": 0, "n": 0, "units": 0, "branch": 0, "id": 0})
for r in confirmed.itertuples(index=False):
    sid = int(r.salesperson_id)
    sp[sid]["value"] += int(r.total_agreement_value_inr or 0)
    sp[sid]["n"] += 1
    sp[sid]["units"] += int(r.number_of_units or 0)
    sp[sid]["branch"] = int(r.branch_id)
    sp[sid]["id"] = sid
names = {int(r.employee_id): r.employee_name for r in emps.itertuples(index=False)}
salespeople = sorted(
    [
        {
            "id": v["id"],
            "name": names.get(v["id"], "Unassigned"),
            "branchId": v["branch"],
            "value": v["value"],
            "bookings": v["n"],
            "units": v["units"],
        }
        for v in sp.values()
    ],
    key=lambda x: -x["value"],
)[:24]

open_ros = []
for r in ros.itertuples(index=False):
    if r.status not in ("Open", "In Progress"):
        continue
    od = dparse(r.open_date)
    open_ros.append({
        "id": int(r.repair_order_id),
        "unit": r.unit_id,
        "branchId": int(r.branch_id),
        "priority": r.priority,
        "status": r.status,
        "days": (as_of - od).days if od else 0,
        "sla": str(r.exceeded_sla).lower() == "true",
        "desc": r.description,
        "amc": r.amc_type if isinstance(r.amc_type, str) and r.amc_type not in ("nan",) else (
            "Warranty" if str(r.is_under_warranty).lower() == "true" else "Out of portfolio"
        ),
        "parts": int(r.parts_cost_inr or 0),
    })
open_ros.sort(key=lambda x: (-int(x["sla"]), -x["days"]))
open_ros = open_ros[:40]

amc_due = []
for r in amc.itertuples(index=False):
    if r.status != "Active":
        continue
    end = dparse(r.end_date)
    if not end or ym(end) != as_ym:
        continue
    amc_due.append({
        "id": int(r.amc_id),
        "unit": r.unit_id,
        "branchId": int(r.branch_id),
        "type": r.amc_type,
        "end": end.isoformat(),
        "value": int(r.annual_value_inr or 0),
    })
amc_due = amc_due[:40]

backlog = []
order = {"Delayed": 0, "In Progress": 1, "Scheduled": 2, "Pending": 3}
for r in units.itertuples(index=False):
    if r.installation_status == "Completed":
        continue
    backlog.append({
        "unit": r.unit_id,
        "branchId": int(r.branch_id),
        "status": r.installation_status,
        "type": r.product_type,
        "floors": r.floors_description,
        "cost": int(r.equipment_cost_inr or 0),
        "grouping": r.grouping,
    })
backlog.sort(key=lambda x: (order.get(x["status"], 9), -x["cost"]))
backlog = backlog[:40]

# Employee scorecard for the extract month, quarter, and year
year = as_of.year
month = as_of.month
quarter = (month - 1) // 3 + 1
q_start = date(year, (quarter - 1) * 3 + 1, 1)
y_start = date(year, 1, 1)
m_start = date(year, month, 1)

def in_window(d, start):
    return d is not None and start <= d <= as_of

lead_m = defaultdict(int)
lead_q = defaultdict(int)
lead_y = defaultdict(int)
for r in leads.itertuples(index=False):
    d = dparse(r.lead_date)
    eid = int(r.lead_generator_id)
    if in_window(d, m_start):
        lead_m[eid] += 1
    if in_window(d, q_start):
        lead_q[eid] += 1
    if in_window(d, y_start):
        lead_y[eid] += 1

sale_m, sale_q, sale_y = defaultdict(int), defaultdict(int), defaultdict(int)
mgr_m, mgr_q, mgr_y = defaultdict(int), defaultdict(int), defaultdict(int)
for r in confirmed.itertuples(index=False):
    d = dparse(r.agreement_date)
    val = int(r.total_agreement_value_inr or 0)
    sid, mid = int(r.salesperson_id), int(r.sales_manager_id)
    if in_window(d, m_start):
        sale_m[sid] += val
        mgr_m[mid] += val
    if in_window(d, q_start):
        sale_q[sid] += val
        mgr_q[mid] += val
    if in_window(d, y_start):
        sale_y[sid] += val
        mgr_y[mid] += val

eng_m, eng_q, eng_y = defaultdict(int), defaultdict(int), defaultdict(int)
br_m, br_q, br_y = defaultdict(int), defaultdict(int), defaultdict(int)
for r in units.itertuples(index=False):
    if r.installation_status != "Completed":
        continue
    d = dparse(getattr(r, "installation_complete_date", None))
    b = int(r.branch_id)
    eid = getattr(r, "installation_engineer_id", None)
    if in_window(d, m_start):
        br_m[b] += 1
        if pd.notna(eid):
            eng_m[int(eid)] += 1
    if in_window(d, q_start):
        br_q[b] += 1
        if pd.notna(eid):
            eng_q[int(eid)] += 1
    if in_window(d, y_start):
        br_y[b] += 1
        if pd.notna(eid):
            eng_y[int(eid)] += 1

amc_m, amc_q, amc_y = defaultdict(int), defaultdict(int), defaultdict(int)
for r in amc.itertuples(index=False):
    d = dparse(r.start_date)
    eid = int(r.service_salesperson_id)
    val = int(r.annual_value_inr or 0)
    if in_window(d, m_start):
        amc_m[eid] += val
    if in_window(d, q_start):
        amc_q[eid] += val
    if in_window(d, y_start):
        amc_y[eid] += val

sup_m, sup_q, sup_y = defaultdict(int), defaultdict(int), defaultdict(int)
tech_m, tech_q, tech_y = defaultdict(int), defaultdict(int), defaultdict(int)
closed = ros[ros.status == "Closed"]
for r in closed.itertuples(index=False):
    d = dparse(r.close_date)
    if pd.notna(r.service_supervisor_id):
        sid = int(r.service_supervisor_id)
        if in_window(d, m_start):
            sup_m[sid] += 1
        if in_window(d, q_start):
            sup_q[sid] += 1
        if in_window(d, y_start):
            sup_y[sid] += 1
    if pd.notna(r.technician_id):
        tid = int(r.technician_id)
        if in_window(d, m_start):
            tech_m[tid] += 1
        if in_window(d, q_start):
            tech_q[tid] += 1
        if in_window(d, y_start):
            tech_y[tid] += 1

def lookup(df, eid, ptype, pindex):
    hit = df[(df.employee_id == eid) & (df.year == year) & (df.period_type == ptype) & (df.period_index == pindex)]
    if hit.empty:
        return 0
    return int(hit.iloc[0].target_value)

ty = targets[targets.year == year]
scorecard = []
MANAGERS = {"Sales Manager", "Installation Manager", "Service Supervisor"}
for e in emps.itertuples(index=False):
    eid = int(e.employee_id)
    role = e.role
    if role == "Lead Generator":
        actuals = (lead_m[eid], lead_q[eid], lead_y[eid])
    elif role == "Salesperson":
        actuals = (sale_m[eid], sale_q[eid], sale_y[eid])
    elif role == "Sales Manager":
        actuals = (mgr_m[eid], mgr_q[eid], mgr_y[eid])
    elif role == "Installation Engineer":
        actuals = (eng_m[eid], eng_q[eid], eng_y[eid])
    elif role == "Installation Manager":
        b = int(e.branch_id)
        actuals = (br_m[b], br_q[b], br_y[b])
    elif role == "Service Sales Person":
        actuals = (amc_m[eid], amc_q[eid], amc_y[eid])
    elif role == "Service Supervisor":
        actuals = (sup_m[eid], sup_q[eid], sup_y[eid])
    else:
        actuals = (tech_m[eid], tech_q[eid], tech_y[eid])
    scorecard.append({
        "employeeId": eid,
        "name": e.employee_name,
        "role": role,
        "departmentId": int(e.department_id),
        "branchId": int(e.branch_id),
        "metric": ROLE_METRIC[role] if False else None,
        "contributor": role not in MANAGERS,
        "monthTarget": lookup(ty, eid, "Month", month),
        "quarterTarget": lookup(ty, eid, "Quarter", quarter),
        "yearTarget": lookup(ty, eid, "Year", year),
        "monthActual": int(actuals[0]),
        "quarterActual": int(actuals[1]),
        "yearActual": int(actuals[2]),
    })

# fill metric from targets
metric_of = {int(r.employee_id): r.metric for r in targets.drop_duplicates("employee_id").itertuples(index=False)}
for row in scorecard:
    row["metric"] = metric_of.get(row["employeeId"], "")

ROLE_METRIC = {}  # silence if referenced; metric comes from file

mart = {
    "asOf": as_of.isoformat(),
    "company": "Simulated vertical-transport extracts",
    "question": "Which branch is off target, and is it a sales problem, an installation problem, or a service problem?",
    "branches": [
        {"id": int(r.branch_id), "code": r.branch_code, "name": r.branch_name, "state": r.state, "region": r.region}
        for r in branches.itertuples(index=False)
    ],
    "departments": [
        {"id": int(r.department_id), "code": r.department_code, "name": r.department_name}
        for r in depts.itertuples(index=False)
    ],
    "months": months,
    "period": {"year": year, "month": month, "quarter": quarter},
    "series": {
        "bookValue": book_val,
        "bookUnits": book_units,
        "bookCount": book_n,
        "leads": lead_n,
        "inquiries": inq_n,
        "quotations": quo_n,
        "accepted": acc_n,
        "installStarted": start_n,
        "installCompleted": comp_n,
        "poAmount": po_amt,
        "incentives": inc_amt,
        "amcStarts": amc_new,
        "salesTarget": sales_target,
    },
    "snapshot": {k: freeze(v) for k, v in snap.items()},
    "salespeople": salespeople,
    "openRepairOrders": open_ros,
    "amcDue": amc_due,
    "installBacklog": backlog,
    "scorecard": scorecard,
    "reconciliation": {
        "confirmedBookings": int((bookings.status == "Confirmed").sum()),
        "confirmedAgreementValue": int(confirmed.total_agreement_value_inr.sum()),
        "bookingRows": int(len(bookings)),
        "units": int(len(units)),
        "amcRows": int(len(amc)),
        "repairOrders": int(len(ros)),
        "purchaseOrders": int(len(pos)),
        "leads": int(len(leads)),
        "inquiries": int(len(inquiries)),
        "quotations": int(len(quotes)),
        "warranty": int(len(warranty)),
        "employees": int(len(emps)),
        "departments": int(len(depts)),
        "targets": int(len(targets)),
    },
    "definitions": {
        "booking": "Confirmed agreements only. Cancelled and On Hold stay in the pipeline counts but are excluded from booked value.",
        "target": "Each employee has a monthly plan. The quarter target is the sum of its three months, and the year target is the sum of twelve. Sales gap on the desk uses salesperson agreement-value targets only, so a booking is not counted twice through the manager.",
        "grain": "One booking is one agreement. One unit row is one lift. Departments are Sales, Installation, and Service.",
        "amc": "Comprehensive covers parts. Non-comprehensive does not. Repair orders cover non-comprehensive and units outside the AMC portfolio.",
    },
}
# incentives and amc starts were left zero — fill them so the service page still has numbers
for r in amc.itertuples(index=False):
    d = dparse(r.start_date)
    if d and ym(d) in idx:
        amc_new[str(int(r.branch_id))][idx[ym(d)]] += 1
# incentives file
incentives = pd.read_csv(DATA / "fact_incentives.csv")
for r in incentives.itertuples(index=False):
    key = f"{int(r.year):04d}-{int(r.month):02d}"
    if key in idx:
        inc_amt[str(int(r.branch_id))][idx[key]] += int(r.incentive_amount_inr or 0)

OUT.write_text(json.dumps(mart, separators=(",", ":")))
print("asOf", as_of, "branches", len(ids), "scorecard", len(scorecard), "bytes", OUT.stat().st_size)
print("targets file", len(targets))