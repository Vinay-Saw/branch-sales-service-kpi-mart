#!/usr/bin/env python3
"""Aggregate the KPI mart CSVs in data/ into the JSON datasets the dashboard reads.

Run from the repo root:  python dashboard/build_dashboard_data.py
Writes dashboard/data/*.json. Every insight sentence is generated from the
same numbers, so re-running after a data refresh keeps the text honest.

Conventions
- As-of date: latest lead / booking / repair-order date in the extract.
- YTD: 1 Jan to the end of the last complete month before the as-of date,
  compared with the same months of the prior year.
- Branch sales target = sum of Salesperson monthly targets (Sales Manager
  targets overlap and are not added). Installation target = sum of
  Installation Engineer "Units completed" targets.
- Each branch-level dataset carries an extra branch = "All" row for the
  company total, so the dashboard's branch picker only filters rows.
"""
import json
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
OUT = ROOT / "dashboard" / "data"
OUT.mkdir(parents=True, exist_ok=True)


def rd(name, dates=()):
    return pd.read_csv(DATA / f"{name}.csv", parse_dates=list(dates))


branch = rd("dim_branch")
BR = dict(zip(branch.branch_id, branch.branch_name))
ORDER = list(branch.sort_values("branch_id").branch_name)
emp = rd("dim_employee", ["hire_date"])
vendor = rd("dim_vendor")
leads = rd("fact_leads", ["lead_date"])
inq = rd("fact_inquiries", ["inquiry_date"])
quotes = rd("fact_quotations", ["quotation_date"])
book = rd("fact_bookings", ["agreement_date"])
units = rd("fact_units", ["installation_start_date", "installation_complete_date"])
pos = rd("fact_installation_pos", ["po_date"])
warr = rd("fact_warranty", ["warranty_start_date", "warranty_end_date"])
amc = rd("fact_amc", ["start_date", "end_date"])
ro = rd("fact_repair_orders", ["open_date", "close_date"])
inc = rd("fact_incentives")
tgt = rd("fact_employee_targets")

for df in (leads, inq, quotes, book, units, pos, warr, amc, ro, inc, tgt, emp):
    if "branch_id" in df:
        df["branch"] = df.branch_id.map(BR)

AS_OF = max(leads.lead_date.max(), book.agreement_date.max(), ro.open_date.max())
YEAR = AS_OF.year
YTD_M = AS_OF.month - 1  # last complete month
PREV = YEAR - 1
D90 = AS_OF + pd.Timedelta(days=90)
MONTH_NAMES = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
YTD_LABEL = f"Jan–{MONTH_NAMES[YTD_M - 1]} {YEAR}"


def in_ytd(s, year=YEAR):
    return (s.dt.year == year) & (s.dt.month <= YTD_M)


def with_all(df, keys, aggs):
    """Group by branch + keys and append an 'All' branch roll-up."""
    a = df.groupby(["branch"] + keys, dropna=False).agg(**aggs).reset_index()
    b = df.groupby(keys, dropna=False).agg(**aggs).reset_index() if keys else df.agg(
        **{k: (v[0], v[1]) for k, v in aggs.items()}).T.reset_index(drop=True)
    b["branch"] = "All"
    return pd.concat([a, b[a.columns]], ignore_index=True)


def r(x, n=4):
    if x is None or (isinstance(x, float) and np.isnan(x)):
        return None
    return round(float(x), n)


def write(name, rows):
    if isinstance(rows, pd.DataFrame):
        rows = rows.replace({np.nan: None}).to_dict("records")
    clean = []
    for row in rows:
        out = {}
        for k, v in row.items():
            if isinstance(v, (np.integer,)):
                v = int(v)
            elif isinstance(v, (np.floating,)):
                v = None if np.isnan(v) else round(float(v), 4)
            elif isinstance(v, (np.bool_,)):
                v = bool(v)
            elif isinstance(v, pd.Timestamp):
                v = v.strftime("%Y-%m-%d")
            out[k] = v
        clean.append(out)
    (OUT / f"{name}.json").write_text(json.dumps(clean, ensure_ascii=False, separators=(",", ":")))
    return clean


def cr(v):
    return f"₹{v / 1e7:,.2f} Cr"


def lakh(v):
    return f"₹{v / 1e5:,.1f} L"


def pct(v, d=0):
    return f"{v * 100:.{d}f}%"


BRANCHES = ORDER + ["All"]
conf = book[book.status == "Confirmed"].copy()

# ---------------------------------------------------------------- targets / attainment
tm = tgt[(tgt.period_type == "Month") & (tgt.year == YEAR) & (tgt.period_index <= YTD_M)]

acts = []


def add_act(df, date_col, emp_col, val, metric, role):
    x = df[in_ytd(df[date_col])]
    acts.append(pd.DataFrame({"employee_id": x[emp_col].astype(int), "branch": x.branch,
                              "v": val(x) if callable(val) else 1, "metric": metric, "role": role}))


add_act(conf, "agreement_date", "salesperson_id", lambda x: x.total_agreement_value_inr, "Agreement value", "Salesperson")
add_act(conf, "agreement_date", "sales_manager_id", lambda x: x.total_agreement_value_inr, "Agreement value", "Sales Manager")
add_act(leads, "lead_date", "lead_generator_id", None, "Leads", "Lead Generator")
done = units[units.installation_status == "Completed"]
add_act(done, "installation_complete_date", "installation_engineer_id", None, "Units completed", "Installation Engineer")
add_act(amc, "start_date", "service_salesperson_id", lambda x: x.annual_value_inr, "AMC value", "Service Sales Person")
closed = ro[ro.status == "Closed"]
add_act(closed, "close_date", "service_supervisor_id", None, "Repair orders closed", "Service Supervisor")
add_act(closed, "close_date", "technician_id", None, "Repair orders closed", "Service Technician")
A = pd.concat(acts)

ROLE_ORDER = ["Lead Generator", "Salesperson", "Sales Manager", "Installation Engineer",
              "Installation Manager", "Service Sales Person", "Service Supervisor", "Service Technician"]
DEPT = {"Lead Generator": "Sales", "Salesperson": "Sales", "Sales Manager": "Sales",
        "Installation Engineer": "Installation", "Installation Manager": "Installation",
        "Service Sales Person": "Service", "Service Supervisor": "Service", "Service Technician": "Service"}

att_rows = []
for role in ROLE_ORDER:
    if role == "Installation Manager":
        # Units carry no manager id: credit the branch's completed units to its manager.
        x = done[in_ytd(done.installation_complete_date)]
        act_b = x.groupby("branch").size()
    else:
        act_b = A[A.role == role].groupby("branch").v.sum()
    t = tm[tm.role == role]
    tg_b = t.groupby("branch").target_value.sum()
    metric = t.metric.iloc[0]
    for b in BRANCHES:
        a = act_b.sum() if b == "All" else act_b.get(b, 0)
        g = tg_b.sum() if b == "All" else tg_b.get(b, 0)
        p = a / g if g else None
        att_rows.append({"role": role, "department": DEPT[role], "metric": metric, "branch": b,
                         "actual": a, "target": g, "attainment": p,
                         "headcount": int(((emp.role == role) & emp.active & ((emp.branch == b) | (b == "All"))).sum())})
att = pd.DataFrame(att_rows)
# A target is "out of scale" when company-wide attainment sits outside 50%–200%: a whole role that far off
# plan points at the plan, not the people.
company = att[att.branch == "All"].set_index("role").attainment
att["calibrated"] = att.role.map(lambda ro_: bool(0.5 <= company[ro_] <= 2))
write("attainment", att)

# ---------------------------------------------------------------- monthly series
months = pd.period_range("2024-01", AS_OF.to_period("M"), freq="M")


def monthly(df, date_col, val=None, name="v"):
    x = df.dropna(subset=[date_col]).copy()
    x["month"] = x[date_col].dt.to_period("M")
    x["_v"] = 1 if val is None else x[val]
    g = x.groupby(["branch", "month"])._v.sum()
    out = {}
    for b in ORDER:
        for m in months:
            out[(b, m)] = g.get((b, m), 0)
    for m in months:
        out[("All", m)] = sum(out[(b, m)] for b in ORDER)
    return pd.Series(out, name=name)


sp_t = tgt[(tgt.role == "Salesperson") & (tgt.period_type == "Month")].copy()
sp_t["month"] = [pd.Period(f"{y}-{m:02d}", "M") for y, m in zip(sp_t.year, sp_t.period_index)]
sp_t["_v"] = sp_t.target_value
st = sp_t.groupby(["branch", "month"])._v.sum()

ro_m = ro.copy()
series = pd.concat([
    monthly(conf, "agreement_date", "total_agreement_value_inr", "agreement_value"),
    monthly(conf, "agreement_date", None, "bookings"),
    monthly(conf, "agreement_date", "number_of_units", "units_booked"),
    monthly(leads, "lead_date", None, "leads"),
    monthly(done, "installation_complete_date", None, "units_completed"),
    monthly(pos, "po_date", "amount_inr", "po_value"),
    monthly(ro, "open_date", None, "ros_opened"),
    monthly(ro[ro.exceeded_sla], "open_date", None, "ros_breached"),
    monthly(amc, "start_date", "annual_value_inr", "new_amc_value"),
    monthly(inc.assign(paid=pd.to_datetime(dict(year=inc.year, month=inc.month, day=1))), "paid", "incentive_amount_inr", "incentives"),
], axis=1)
series["sales_target"] = [st.get(k, 0) if k[0] != "All" else sum(st.get((b, k[1]), 0) for b in ORDER)
                          for k in series.index]
series = series.reset_index().rename(columns={"level_0": "branch", "level_1": "month"})
series["month"] = series.month.astype(str)
series["partial"] = series.month == str(AS_OF.to_period("M"))
write("monthly", series)

# ---------------------------------------------------------------- funnel
fun = []
for label, yr in ((f"{YTD_LABEL}", YEAR), (f"Jan–{MONTH_NAMES[YTD_M - 1]} {PREV}", PREV)):
    stages = [
        ("Leads", leads[in_ytd(leads.lead_date, yr)]),
        ("Inquiries", inq[in_ytd(inq.inquiry_date, yr)]),
        ("Quotations", quotes[in_ytd(quotes.quotation_date, yr)]),
        ("Agreements won", conf[in_ytd(conf.agreement_date, yr)]),
    ]
    for i, (s, df) in enumerate(stages):
        c = df.groupby("branch").size()
        for b in BRANCHES:
            fun.append({"period": "current" if yr == YEAR else "prior", "period_label": label,
                        "step": i + 1, "stage": s, "branch": b,
                        "count": int(c.sum() if b == "All" else c.get(b, 0))})
fun = pd.DataFrame(fun)
fun["of_first"] = fun.apply(lambda x: x["count"] / fun[(fun.period == x.period) & (fun.branch == x.branch) & (fun.step == 1)]["count"].iloc[0], axis=1)
fun["from_prev"] = fun.apply(lambda x: None if x.step == 1 else x["count"] / fun[(fun.period == x.period) & (fun.branch == x.branch) & (fun.step == x.step - 1)]["count"].iloc[0], axis=1)
write("funnel", fun)

# ---------------------------------------------------------------- lead sources (all history)
bl = conf.merge(leads[["lead_id", "source"]], on="lead_id")
src = pd.DataFrame({"leads": leads.groupby("source").size(), "agreements": bl.groupby("source").size(),
                    "agreement_value": bl.groupby("source").total_agreement_value_inr.sum()}).reset_index()
src["lead_to_agreement"] = src.agreements / src.leads
src["avg_deal"] = src.agreement_value / src.agreements
write("lead_sources", src.sort_values("lead_to_agreement", ascending=False))

# ---------------------------------------------------------------- booking status / leakage (all history)
bs = with_all(book, ["status"], {"agreements": ("booking_id", "size"), "value": ("total_agreement_value_inr", "sum"),
                                  "units": ("number_of_units", "sum")})
tot = bs.groupby("branch").value.transform("sum")
bs["share_of_value"] = bs.value / tot
write("booking_status", bs)

# ---------------------------------------------------------------- salespeople (YTD)
cy = conf[in_ytd(conf.agreement_date)]
qy = quotes[in_ytd(quotes.quotation_date)]
sp = emp[emp.role == "Salesperson"][["employee_id", "employee_name", "branch", "active"]].copy()
sp["agreement_value"] = sp.employee_id.map(cy.groupby("salesperson_id").total_agreement_value_inr.sum()).fillna(0)
sp["agreements"] = sp.employee_id.map(cy.groupby("salesperson_id").size()).fillna(0).astype(int)
sp["target"] = sp.employee_id.map(tm[tm.role == "Salesperson"].groupby("employee_id").target_value.sum()).fillna(0)
sp["attainment"] = np.where(sp.target > 0, sp.agreement_value / sp.target, np.nan)
sp["quotes"] = sp.employee_id.map(qy.groupby("salesperson_id").size()).fillna(0).astype(int)
sp["quote_win_rate"] = sp.employee_id.map(qy[qy.status == "Accepted"].groupby("salesperson_id").size()).fillna(0) / sp.quotes.replace(0, np.nan)
sp = sp.rename(columns={"employee_name": "salesperson"}).drop(columns=["employee_id"])
write("salespeople", sp.sort_values("attainment", ascending=False))

# ---------------------------------------------------------------- installation status (snapshot)
u = units.merge(book[["booking_id", "status", "agreement_date"]], on="booking_id")
u["bucket"] = np.where(u.status == "Confirmed", u.installation_status, "Parked (" + u.status + " agreement)")
ist = with_all(u, ["bucket"], {"units": ("unit_id", "size")})
ist["share"] = ist.units / ist.groupby("branch").units.transform("sum")
write("install_status", ist)

# ---------------------------------------------------------------- PO cost by line item
pl = with_all(pos, ["line_item"], {"pos": ("po_id", "size"), "amount": ("amount_inr", "sum"),
                                    "open_amount": ("amount_inr", lambda s: s[pos.loc[s.index, "status"] == "Open"].sum())})
write("po_lines", pl)

v = pos.merge(vendor, on="vendor_id")
vend = v.groupby(["vendor_name", "specialty"]).agg(pos=("po_id", "size"), amount=("amount_inr", "sum"),
                                                     open_amount=("amount_inr", lambda s: s[v.loc[s.index, "status"] == "Open"].sum()),
                                                     units=("unit_id", "nunique"), branches=("branch_id", "nunique")).reset_index()
vend["open_share"] = vend.open_amount / vend.amount
dl = u[u.installation_status == "Delayed"].unit_id
vend["delayed_units"] = vend.vendor_name.map(v[v.unit_id.isin(dl)].groupby("vendor_name").unit_id.nunique()).fillna(0).astype(int)
write("vendors", vend.sort_values("amount", ascending=False))

# ---------------------------------------------------------------- service calendar (next 12 months)
act = amc[amc.status == "Active"]
fut = pd.period_range(AS_OF.to_period("M"), periods=12, freq="M")
cal = []
for b in BRANCHES:
    ab = act if b == "All" else act[act.branch == b]
    wb = warr if b == "All" else warr[warr.branch == b]
    for m in fut:
        am = ab[ab.end_date.dt.to_period("M") == m]
        wm = wb[wb.warranty_end_date.dt.to_period("M") == m]
        cal.append({"branch": b, "month": str(m), "amc_renewals": len(am),
                    "amc_renewal_value": int(am.annual_value_inr.sum()),
                    "comprehensive": int((am.amc_type == "Comprehensive").sum()),
                    "non_comprehensive": int((am.amc_type == "Non-comprehensive").sum()),
                    "warranty_expiring": len(wm)})
write("service_calendar", cal)

# ---------------------------------------------------------------- AMC portfolio
port = with_all(act, ["amc_type"], {"contracts": ("amc_id", "size"), "units": ("unit_id", "nunique"),
                                     "annual_value": ("annual_value_inr", "sum")})
port["avg_value"] = port.annual_value / port.contracts
write("amc_portfolio", port)

# ---------------------------------------------------------------- repair orders
ro["coverage"] = np.select(
    [ro.is_under_warranty & ~ro.is_under_amc, ro.is_under_warranty & ro.is_under_amc,
     ~ro.is_under_warranty & ro.is_under_amc],
    ["Warranty only", "Warranty + AMC", "AMC only (post-warranty)"], "No cover")
ro["cost"] = ro.parts_cost_inr + ro.labor_cost_inr
ro["quarter"] = ro.open_date.dt.to_period("Q").astype(str)

rq = with_all(ro, ["quarter"], {"ros": ("repair_order_id", "size"), "breached": ("exceeded_sla", "sum"),
                                 "median_resolution_h": ("resolution_hours", "median")})
rq["breach_rate"] = rq.breached / rq.ros
rq["partial"] = rq.quarter == str(AS_OF.to_period("Q"))
write("ro_quarterly", rq)

rp = with_all(ro, ["priority"], {"ros": ("repair_order_id", "size"), "breached": ("exceeded_sla", "sum"),
                                  "sla_hours": ("sla_hours", "max"), "median_resolution_h": ("resolution_hours", "median"),
                                  "open": ("status", lambda s: int((s != "Closed").sum()))})
rp["breach_rate"] = rp.breached / rp.ros
write("ro_priority", rp)

op = ro[ro.status != "Closed"].copy()
op["age_days"] = (AS_OF - op.open_date).dt.days
op = op.merge(emp[["employee_id", "employee_name"]].rename(columns={"employee_id": "service_supervisor_id", "employee_name": "supervisor"}), on="service_supervisor_id")
op["ro"] = "RO-" + op.repair_order_id.astype(str).str.zfill(4)
AGE_BUCKETS = [(0, 30, "0–30 days"), (31, 90, "31–90 days"), (91, 180, "91–180 days"), (181, 365, "181–365 days"), (366, 10 ** 6, "Over a year")]
age_rows = []
for b in BRANCHES:
    ob = op if b == "All" else op[op.branch == b]
    for i, (lo, hi, lab) in enumerate(AGE_BUCKETS):
        for pr in sorted(ro.priority.unique()):
            age_rows.append({"branch": b, "step": i + 1, "age_bucket": lab, "priority": pr,
                             "open_ros": int(((ob.age_days >= lo) & (ob.age_days <= hi) & (ob.priority == pr)).sum())})
write("ro_age", age_rows)

write("ro_open", op[["ro", "branch", "priority", "status", "open_date", "age_days", "sla_hours", "description",
                     "coverage", "supervisor", "unit_id"]].sort_values(["priority", "age_days"], ascending=[True, False]))

rf = ro.groupby("description").agg(ros=("repair_order_id", "size"), breach_rate=("exceeded_sla", "mean"),
                                    avg_parts=("parts_cost_inr", "mean"), avg_cost=("cost", "mean"),
                                    total_cost=("cost", "sum"),
                                    median_resolution_h=("resolution_hours", "median")).reset_index()
write("ro_faults", rf.sort_values("ros", ascending=False))

rc = ro.groupby("coverage").agg(ros=("repair_order_id", "size"), parts=("parts_cost_inr", "sum"),
                                labor=("labor_cost_inr", "sum"), breach_rate=("exceeded_sla", "mean")).reset_index()
rc["cost"] = rc.parts + rc.labor
rc["share_of_cost"] = rc.cost / rc.cost.sum()
write("ro_coverage", rc.sort_values("cost", ascending=False))

tech = ro.groupby("technician_id").agg(ros=("repair_order_id", "size"), breach_rate=("exceeded_sla", "mean"),
                                       median_resolution_h=("resolution_hours", "median"),
                                       open=("status", lambda s: int((s != "Closed").sum()))).reset_index()
tech = tech.merge(emp[["employee_id", "employee_name", "branch", "active"]], left_on="technician_id", right_on="employee_id")
tech = tech.rename(columns={"employee_name": "technician"})[["technician", "branch", "active", "ros", "breach_rate", "median_resolution_h", "open"]]
write("technicians", tech.sort_values("breach_rate", ascending=False))

# ---------------------------------------------------------------- incentives
ic = inc.groupby(["branch", "role", "year"]).agg(amount=("incentive_amount_inr", "sum"), payments=("incentive_id", "size"),
                                                 employees=("employee_id", "nunique")).reset_index()
ica = inc.groupby(["role", "year"]).agg(amount=("incentive_amount_inr", "sum"), payments=("incentive_id", "size"),
                                        employees=("employee_id", "nunique")).reset_index()
ica["branch"] = "All"
ic = pd.concat([ic, ica[ic.columns]], ignore_index=True)
ic["department"] = ic.role.map(DEPT)
ic["year_label"] = np.where(ic.year == YEAR, ic.year.astype(str) + " (to " + MONTH_NAMES[AS_OF.month - 1] + ")", ic.year.astype(str))
write("incentives", ic)

# ---------------------------------------------------------------- data quality
x = inc.merge(emp[["employee_id", "hire_date"]], on="employee_id")
x["paid_month"] = pd.to_datetime(dict(year=x.year, month=x.month, day=1))
pre_hire = x[x.paid_month < x.hire_date.dt.to_period("M").dt.start_time]
a_sorted = amc.sort_values(["unit_id", "start_date"]).copy()
a_sorted["next_start"] = a_sorted.groupby("unit_id").start_date.shift(-1)
overl = a_sorted[a_sorted.next_start < a_sorted.end_date]
multi_active = act.groupby("unit_id").size()
open_stale = op[op.age_days > 30]
dq = [
    {"check": "Incentives paid before the employee's hire month", "table": "fact_incentives",
     "rows": len(pre_hire), "amount": int(pre_hire.incentive_amount_inr.sum()),
     "impact": f"{pre_hire.employee_id.nunique()} employees. Incentive totals by person overstate their tenure."},
    {"check": "AMC contracts that overlap the next contract on the same unit", "table": "fact_amc",
     "rows": len(overl), "amount": int(overl.annual_value_inr.sum()),
     "impact": f"{int((multi_active > 1).sum())} units carry more than one Active contract, which inflates active AMC value."},
    {"check": "Open repair orders older than 30 days", "table": "fact_repair_orders",
     "rows": len(open_stale), "amount": int(open_stale.cost.sum()),
     "impact": "Likely closed in the field but not in the system. Open-RO and SLA counts include them."},
    {"check": "Units on cancelled or on-hold agreements shown as Pending", "table": "fact_units",
     "rows": int((u.status != "Confirmed").sum()), "amount": int(u[u.status != "Confirmed"].equipment_cost_inr.sum()),
     "impact": "Every Pending unit belongs to a cancelled or on-hold agreement. This dashboard parks them outside the backlog."},
    {"check": "Repair orders flagged as under warranty", "table": "fact_repair_orders",
     "rows": int(ro.is_under_warranty.sum()), "amount": int(ro[ro.is_under_warranty].cost.sum()),
     "impact": "The metric dictionary scopes ROs to non-comprehensive AMC and uncovered units, yet most are warranty jobs. Confirm the flag's meaning."},
    {"check": "Incentives on the 'New AMC' basis paid to non-service roles", "table": "fact_incentives",
     "rows": int(((inc.basis == "New AMC") & (inc.role != "Service Sales Person")).sum()),
     "amount": int(inc[(inc.basis == "New AMC") & (inc.role != "Service Sales Person")].incentive_amount_inr.sum()),
     "impact": "Basis labels look assigned at random across roles; basis-level analysis is not reliable."},
]
write("data_quality", dq)

# ---------------------------------------------------------------- branch scorecard
def branch_metrics(b):
    sel = (lambda df: df) if b == "All" else (lambda df: df[df.branch == b])
    c = sel(conf)
    val = c[in_ytd(c.agreement_date)].total_agreement_value_inr.sum()
    val_p = c[in_ytd(c.agreement_date, PREV)].total_agreement_value_inr.sum()
    a = att[(att.branch == b)].set_index("role")
    uu = sel(u)
    backlog = uu[uu.bucket.isin(["Delayed", "In Progress", "Scheduled"])]
    rr = sel(ro)
    rr_y = rr[in_ytd(rr.open_date)]
    rr_p = rr[in_ytd(rr.open_date, PREV)]
    oo = sel(op)
    aa = sel(act)
    ww = sel(warr)
    ex = sel(amc)[sel(amc).status == "Expired"]
    later = ex.apply(lambda e: bool(((amc.unit_id == e.unit_id) & (amc.start_date > e.start_date)).any()), axis=1) if len(ex) else pd.Series(dtype=bool)
    post = ww[ww.warranty_end_date < AS_OF]
    l = sel(leads)
    return {
        "branch": b,
        "agreement_value_ytd": int(val), "agreement_value_prev_ytd": int(val_p),
        "agreement_value_yoy": (val / val_p - 1) if val_p else None,
        "sales_target_ytd": int(a.loc["Salesperson", "target"]),
        "sales_attainment": a.loc["Salesperson", "attainment"],
        "agreements_ytd": int(in_ytd(c.agreement_date).sum()),
        "leads_ytd": int(in_ytd(l.lead_date).sum()),
        "leads_prev_ytd": int(in_ytd(l.lead_date, PREV).sum()),
        "lead_to_agreement": in_ytd(c.agreement_date).sum() / max(1, in_ytd(l.lead_date).sum()),
        "units_completed_ytd": int(a.loc["Installation Engineer", "actual"]),
        "install_target_ytd": int(a.loc["Installation Engineer", "target"]),
        "install_attainment": a.loc["Installation Engineer", "attainment"],
        "install_backlog": len(backlog),
        "units_delayed": int((uu.bucket == "Delayed").sum()),
        "delayed_share": (uu.bucket == "Delayed").sum() / max(1, (uu.status == "Confirmed").sum()),
        "open_po_value": int(sel(pos)[sel(pos).status == "Open"].amount_inr.sum()),
        "ros_ytd": len(rr_y),
        "sla_breach_ytd": rr_y.exceeded_sla.mean() if len(rr_y) else None,
        "sla_breach_prev_ytd": rr_p.exceeded_sla.mean() if len(rr_p) else None,
        "open_ros": len(oo), "open_ros_p1": int((oo.priority == "P1-Critical").sum()),
        "open_ros_past_sla": int(oo.exceeded_sla.sum()),
        "active_amc": len(aa), "active_amc_value": int(aa.annual_value_inr.sum()),
        "amc_due_90d": int(((aa.end_date >= AS_OF) & (aa.end_date < D90)).sum()),
        "amc_due_90d_value": int(aa[(aa.end_date >= AS_OF) & (aa.end_date < D90)].annual_value_inr.sum()),
        "warranty_expiring_90d": int(((ww.warranty_end_date >= AS_OF) & (ww.warranty_end_date < D90)).sum()),
        "post_warranty_amc_cover": post.unit_id.isin(set(aa.unit_id)).mean() if len(post) else None,
        "expired_amc_lapsed": int((~later).sum()) if len(ex) else 0,
        "expired_amc_lapse_rate": float((~later).mean()) if len(ex) else None,
        "repair_cost_ytd": int(rr_y.cost.sum()),
        "incentives_ytd": int(sel(inc)[(sel(inc).year == YEAR) & (sel(inc).month <= YTD_M)].incentive_amount_inr.sum()),
        "headcount": int((sel(emp).active).sum()),
        "salespeople_at_target": int(((sel(sp).attainment >= 1) & (sel(sp).target > 0)).sum()),
        "salespeople": int((sel(sp).target > 0).sum()),
        "roles_out_of_scale": int((~att[att.branch == "All"].calibrated).sum()),
        "roles": int(att[att.branch == "All"].role.nunique()),
        "new_amc_value_ytd": int(sel(amc)[in_ytd(sel(amc).start_date)].annual_value_inr.sum()),
        "po_value_ytd": int(sel(pos)[in_ytd(sel(pos).po_date)].amount_inr.sum()),
    }


sc = pd.DataFrame([branch_metrics(b) for b in BRANCHES])


def status(v, good, warn, higher_better=True):
    if v is None or (isinstance(v, float) and np.isnan(v)):
        return "none"
    if higher_better:
        return "ok" if v >= good else "warn" if v >= warn else "bad"
    return "ok" if v <= good else "warn" if v <= warn else "bad"


sc["sales_status"] = sc.sales_attainment.map(lambda v: status(v, 0.85, 0.7))
sc["install_status"] = sc.install_attainment.map(lambda v: status(v, 0.85, 0.6))
sc["service_status"] = sc.sla_breach_ytd.map(lambda v: status(v, 0.25, 0.32, False))


def diagnose(row):
    issues = []
    if row.sales_status != "ok":
        issues.append("sales")
    if row.install_status != "ok":
        issues.append("installation")
    if row.service_status != "ok":
        issues.append("service")
    return issues


sc["problem_areas"] = sc.apply(lambda r_: ", ".join(diagnose(r_)) or "none", axis=1)
sc["as_of"] = AS_OF.strftime("%Y-%m-%d")
sc["ytd_label"] = YTD_LABEL
write("branch_scorecard", sc)

# ---------------------------------------------------------------- insights (text generated from the numbers above)
S = sc.set_index("branch")
br_only = S.drop(index="All")
allr = S.loc["All"]
worst_sales = br_only.sales_attainment.idxmin()
best_sales = br_only.sales_attainment.idxmax()
yoy_drop = br_only.agreement_value_yoy.idxmin()
w = br_only.loc[worst_sales]
fun_c = fun[(fun.period == "current")]
l2a = fun_c[fun_c.step == 4].set_index("branch").of_first
lead_share = w.leads_ytd / br_only.leads_ytd.mean()
worst_inst = br_only.install_attainment.idxmin()
best_inst = br_only.install_attainment.idxmax()
mon = series[(series.branch == "All")].set_index("month")
h1 = mon.loc[f"{YEAR}-01":f"{YEAR}-06"].units_completed.mean()
q3 = mon.loc[f"{YEAR}-07":f"{YEAR}-09"].units_completed.mean()
booked_9 = mon.loc[f"{YEAR}-01":f"{YEAR}-{YTD_M:02d}"].units_booked.mean()
dur_done = (done.installation_complete_date - done.installation_start_date).dt.days.median()
dly = u[u.bucket == "Delayed"]
dur_dly = (dly.installation_complete_date - dly.installation_start_date).dt.days.median()
pending_parked = int((u.status != "Confirmed").sum())
worst_sla = br_only.sla_breach_ytd.idxmax()
best_sla = br_only.sla_breach_ytd.idxmin()
rq_all = rq[rq.branch == "All"].set_index("quarter")
warranty_cost_share = rc.set_index("coverage").share_of_cost.reindex(["Warranty only", "Warranty + AMC"]).sum()
rep = ro.groupby("unit_id").size()
amc_due_top = br_only.amc_due_90d.idxmax()
top_fault = rf.sort_values("ros", ascending=False).iloc[0]
src_s = src.set_index("source")
calib = att[(att.branch == "All")].set_index("role")
off = calib[~calib.calibrated]
sp_ok = sp[sp.target > 0]
all3 = [k for k, v in br_only.problem_areas.items() if v == "sales, installation, service"]
inc_ytd = inc[(inc.year == YEAR) & (inc.month <= YTD_M)]
inc_y = inc_ytd.incentive_amount_inr.sum()
inc_b = inc_ytd.groupby("branch").incentive_amount_inr.sum()
fc = fun_c.pivot(index="branch", columns="stage", values="from_prev").drop(index="All")
q2a = fc["Agreements won"]
last24 = mon.loc[:f"{YEAR}-{YTD_M:02d}"].agreement_value.tail(24)

insights = [
    # overview
    {"id": "ov-1", "tab": "overview", "severity": "bad",
     "headline": f"{worst_sales} is the branch furthest off target, and the gap starts with sales.",
     "detail": f"{worst_sales} booked {cr(w.agreement_value_ytd)} in {YTD_LABEL}, {pct(w.sales_attainment)} of its {cr(w.sales_target_ytd)} target, against {pct(allr.sales_attainment)} company-wide. It is also last on installation ({pct(w.install_attainment)} of target) and has the fewest leads of any branch."},
    {"id": "ov-2", "tab": "overview", "severity": "warn",
     "headline": f"{yoy_drop} is the branch going backwards: agreement value is down {pct(-br_only.loc[yoy_drop].agreement_value_yoy)} on last year.",
     "detail": f"{yoy_drop} booked {cr(br_only.loc[yoy_drop].agreement_value_ytd)} in {YTD_LABEL} against {cr(br_only.loc[yoy_drop].agreement_value_prev_ytd)} a year earlier, and it has the most AMC renewals due in the next 90 days ({int(br_only.loc[amc_due_top].amc_due_90d)})." if yoy_drop == amc_due_top else
     f"{yoy_drop} booked {cr(br_only.loc[yoy_drop].agreement_value_ytd)} in {YTD_LABEL} against {cr(br_only.loc[yoy_drop].agreement_value_prev_ytd)} a year earlier."},
    {"id": "ov-3", "tab": "overview", "severity": "ok",
     "headline": (f"{best_sales} leads on both sales ({pct(br_only.loc[best_sales].sales_attainment)} of target) and installation ({pct(br_only.loc[best_inst].install_attainment)})." if best_sales == best_inst else
                  f"{best_sales} leads on sales ({pct(br_only.loc[best_sales].sales_attainment)} of target) and {best_inst} on installation ({pct(br_only.loc[best_inst].install_attainment)})."),
     "detail": f"Company-wide, {YTD_LABEL} agreement value is {cr(allr.agreement_value_ytd)}, {'up' if allr.agreement_value_yoy >= 0 else 'down'} {pct(abs(allr.agreement_value_yoy))} on the same months of {PREV}, and {pct(allr.sales_attainment)} of the {cr(allr.sales_target_ytd)} target."},
    {"id": "ov-4", "tab": "overview", "severity": "bad",
     "headline": f"Service is a company-wide problem, not one branch's: {pct(allr.sla_breach_ytd)} of {YEAR} repair orders missed SLA.",
     "detail": f"Every branch breaches on more than one job in four ({worst_sla} worst at {pct(br_only.loc[worst_sla].sla_breach_ytd)}, {best_sla} best at {pct(br_only.loc[best_sla].sla_breach_ytd)}). {int(allr.open_ros)} repair orders are still open, {int(allr.open_ros_past_sla)} of them past SLA and {int(allr.open_ros_p1)} of them P1-Critical."},
    {"id": "ov-5", "tab": "overview", "severity": "warn",
     "headline": "Every branch misses somewhere: " + "; ".join(
         f"{k} on {' and '.join(v.rsplit(', ', 1))}" for k, v in br_only.problem_areas.items() if v != "none") + ".",
     "detail": f"A branch is off target on sales below {pct(0.85)} of target, on installation below {pct(0.85)}, and on service above {pct(0.25)} of repair orders past SLA. "
               + (f"{' and '.join(', '.join(all3).rsplit(', ', 1))} miss on all three, so their gap is not one department's problem." if all3 else "No branch misses on all three.")},
    # sales
    {"id": "sa-1", "tab": "sales", "severity": "bad",
     "headline": f"{worst_sales}'s shortfall is lead volume, not conversion.",
     "detail": f"{worst_sales} generated {int(w.leads_ytd)} leads in {YTD_LABEL}, {pct(lead_share)} of the branch average, yet converts {pct(l2a[worst_sales], 1)} of leads into agreements, close to the company's {pct(l2a['All'], 1)}. More leads, not better closing, is the fix."},
    {"id": "sa-2", "tab": "sales", "severity": "ok",
     "headline": f"{l2a.drop('All').idxmax()} converts best because it wins more of its quotations.",
     "detail": f"Lead-to-agreement conversion runs from {pct(l2a.drop('All').min(), 1)} ({l2a.drop('All').idxmin()}) to {pct(l2a.drop('All').max(), 1)} ({l2a.drop('All').idxmax()}). {pct(q2a.max())} of {q2a.idxmax()}'s quotations become agreements, against {pct(q2a.min())} at {' and '.join(q2a[q2a.round(2) == q2a.min().round(2)].index)}."},
    {"id": "sa-3", "tab": "sales", "severity": "warn",
     "headline": f"Cancelled and on-hold agreements hold {cr(bs[(bs.branch == 'All') & (bs.status != 'Confirmed')].value.sum())} of value.",
     "detail": f"That is {pct(bs[(bs.branch == 'All') & (bs.status != 'Confirmed')].share_of_value.sum())} of everything signed since {book.agreement_date.min().year}. On-hold deals ({cr(bs[(bs.branch == 'All') & (bs.status == 'On Hold')].value.sum())}) are the recoverable part and worth a monthly review."},
    {"id": "sa-4", "tab": "sales", "severity": "info",
     "headline": f"Architect referrals convert best ({pct(src_s.loc['Architect'].lead_to_agreement, 1)}); cold calls convert worst ({pct(src_s.loc['Cold Call'].lead_to_agreement, 1)}).",
     "detail": f"The spread across sources is narrow. Source mix is not what separates strong and weak branches."},
    {"id": "sa-5", "tab": "sales", "severity": "warn",
     "headline": f"Monthly bookings dipped from April to July {YEAR}.",
     "detail": f"April {YEAR} was {'the weakest of the last 24 complete months' if last24.idxmin() == f'{YEAR}-04' else 'a low month'} at {cr(mon.loc[f'{YEAR}-04'].agreement_value)}. August and September recovered to {cr(mon.loc[f'{YEAR}-08'].agreement_value)} and {cr(mon.loc[f'{YEAR}-09'].agreement_value)}."},
    # installation
    {"id": "in-1", "tab": "installation", "severity": "bad",
     "headline": f"Completions slowed in the second half while bookings held up, so the backlog is growing.",
     "detail": f"Units completed fell from {h1:.0f} a month in January–June to {q3:.0f} a month in July–September, while new agreements added {booked_9:.0f} units a month. {int(allr.install_backlog)} units on confirmed agreements are waiting or in work."},
    {"id": "in-2", "tab": "installation", "severity": "bad",
     "headline": f"{int(allr.units_delayed)} units are Delayed, and they tie up {cr(allr.open_po_value)} of open vendor POs.",
     "detail": f"Delayed jobs take {dur_dly:.0f} days from start to finish against {dur_done:.0f} for on-time jobs. Every open PO sits on a delayed or in-progress unit, so clearing delays also releases vendor cost."},
    {"id": "in-3", "tab": "installation", "severity": "info",
     "headline": f"{pending_parked} 'Pending' units belong to cancelled or on-hold agreements.",
     "detail": "They are not installation backlog. The dashboard shows them as parked so they do not inflate the backlog figure."},
    {"id": "in-4", "tab": "installation", "severity": "info",
     "headline": f"{worst_inst}'s installation gap is mostly its sales gap carried forward.",
     "detail": f"{worst_inst} completed {int(br_only.loc[worst_inst].units_completed_ytd)} units against a target of {int(br_only.loc[worst_inst].install_target_ytd)}, with as many engineers as larger branches. Fewer agreements means fewer units to install. Its delayed share is {pct(br_only.loc[worst_inst].delayed_share)}" + (", the highest of any branch." if br_only.delayed_share.idxmax() == worst_inst else f", against {pct(br_only.delayed_share.max())} at {br_only.delayed_share.idxmax()}.")},
    {"id": "in-5", "tab": "installation", "severity": "info",
     "headline": f"Third-party cost is spread evenly: {len(vend)} vendors each take {pct(vend.amount.min() / vend.amount.sum(), 0)}–{pct(vend.amount.max() / vend.amount.sum(), 0)} of PO value.",
     "detail": f"No single vendor is a concentration risk. Total PO value to date is {cr(pos.amount_inr.sum())}, about {lakh(pos.groupby('unit_id').amount_inr.sum().mean())} per unit across four line items."},
    # service
    {"id": "se-1", "tab": "service", "severity": "bad",
     "headline": f"SLA breaches rose to {pct(rq_all.loc[f'{YEAR}Q3'].breach_rate)} in Q3 {YEAR}, from {pct(rq_all.loc[f'{PREV}Q4'].breach_rate)} in Q4 {PREV}.",
     "detail": f"Repair volume is up as the installed base grows ({int(rq_all.loc[f'{PREV}Q3'].ros)} ROs in Q3 {PREV}, {int(rq_all.loc[f'{YEAR}Q3'].ros)} in Q3 {YEAR}) without a matching gain in on-time closure. P1-Critical jobs breach as often as normal ones."},
    {"id": "se-2", "tab": "service", "severity": "bad",
     "headline": f"{int(allr.open_ros)} repair orders are still open, most of them for months.",
     "detail": f"The median open RO is {op.age_days.median():.0f} days old and {int(allr.open_ros_p1)} are P1-Critical. Either the work is done and not closed in the system, or customers are waiting; both need a ticket-by-ticket review."},
    {"id": "se-3", "tab": "service", "severity": "warn",
     "headline": f"{int(allr.amc_due_90d)} AMC contracts worth {cr(allr.amc_due_90d_value)} a year come up for renewal in the next 90 days.",
     "detail": f"{amc_due_top} has the most ({int(br_only.loc[amc_due_top].amc_due_90d)}). Of contracts that have already expired, {pct(allr.expired_amc_lapse_rate)} were not followed by a new contract on the same unit."},
    {"id": "se-4", "tab": "service", "severity": "ok",
     "headline": f"AMC capture after warranty is strong: {pct(allr.post_warranty_amc_cover)} of out-of-warranty units have an active AMC.",
     "detail": f"The active portfolio is {int(allr.active_amc):,} contracts worth {cr(allr.active_amc_value)} a year, split almost evenly between comprehensive and non-comprehensive. {int(allr.warranty_expiring_90d)} more units leave warranty in the next 90 days."},
    {"id": "se-5", "tab": "service", "severity": "warn",
     "headline": f"Warranty jobs carry {pct(warranty_cost_share)} of repair cost.",
     "detail": f"{int(ro.is_under_warranty.sum())} of {len(ro)} repair orders were on units under warranty, so the company absorbs most parts and labour cost. {top_fault.description} is the most common fault ({int(top_fault.ros)} ROs). {int((rep >= 2).sum())} units have needed two or more repairs."},
    # people
    {"id": "pe-1", "tab": "people", "severity": "warn",
     "headline": f"Targets for {len(off)} of {len(calib)} roles are out of scale with the business.",
     "detail": "Company-wide attainment: " + "; ".join(f"{r_} {pct(off.loc[r_].attainment)}" for r_ in off.index) + f". Attainment this far from 100% says the target was not built from the volume these teams handle. Reset them before tying incentives to them."},
    {"id": "pe-2", "tab": "people", "severity": "info",
     "headline": f"{int((sp_ok.attainment >= 1).sum())} of {len(sp_ok)} salespeople are at or above their {YTD_LABEL} target.",
     "detail": f"Individual attainment runs from {pct(sp_ok.attainment.min())} to {pct(sp_ok.attainment.max())}. The bottom five are a coaching list; the top five show what the plan allows."},
    {"id": "pe-3", "tab": "people", "severity": "info",
     "headline": f"Incentives paid in {YTD_LABEL} totalled {lakh(inc_y)}, spread across all eight roles.",
     "detail": f"Salespeople take the largest share. Payouts follow headcount more than results: branch totals ranged only from {lakh(inc_b.min())} ({inc_b.idxmin()}) to {lakh(inc_b.max())} ({inc_b.idxmax()}), although sales attainment ranged from {pct(br_only.sales_attainment.min())} to {pct(br_only.sales_attainment.max())}."},
    {"id": "pe-4", "tab": "people", "severity": "warn",
     "headline": f"{len(pre_hire)} incentive payments ({lakh(pre_hire.incentive_amount_inr.sum())}) are dated before the employee was hired.",
     "detail": "Listed with the other data issues below. Fix the source before using incentive history for pay decisions."},
]
write("insights", insights)

# ---------------------------------------------------------------- callouts: one number + a short label, for the page
vy = br_only.loc[worst_sales]
callouts = [
    ("overview", "ov-c1", "bad", w.sales_attainment, "pct", f"{worst_sales} · sales vs target", f"Company {pct(allr.sales_attainment)}"),
    ("overview", "ov-c2", "bad", br_only.loc[yoy_drop].agreement_value_yoy, "signed", f"{yoy_drop} · value vs last year", f"{cr(br_only.loc[yoy_drop].agreement_value_ytd)} this year"),
    ("overview", "ov-c3", "bad", allr.sla_breach_ytd, "pct", "Repairs past SLA", f"{YEAR}, all branches"),
    ("overview", "ov-c4", "ok", br_only.loc[best_sales].sales_attainment, "pct", f"{best_sales} · sales vs target", "Best branch"),
    ("sales", "sa-c1", "bad", lead_share, "pct", f"{worst_sales} leads vs branch average", f"{int(w.leads_ytd)} leads"),
    ("sales", "sa-c2", "ok", q2a.max(), "pct", f"{q2a.idxmax()} · quotations won", f"Lowest {pct(q2a.min())}"),
    ("sales", "sa-c3", "warn", bs[(bs.branch == "All") & (bs.status != "Confirmed")].value.sum(), "inr", "Cancelled + on-hold value", f"{pct(bs[(bs.branch == 'All') & (bs.status != 'Confirmed')].share_of_value.sum())} of signed"),
    ("sales", "sa-c4", "warn", mon.loc[f"{YEAR}-04"].agreement_value, "inr", f"Apr {YEAR} bookings", "Weakest month"),
    ("installation", "in-c1", "bad", q3 / h1 - 1, "signed", "Installs per month, Q3 vs H1", f"{q3:.0f} vs {h1:.0f} units"),
    ("installation", "in-c2", "bad", int(allr.units_delayed), "int", "Units delayed", f"{cr(allr.open_po_value)} open POs"),
    ("installation", "in-c3", "warn", dur_dly, "days", "Delayed job duration", f"On-time jobs {dur_done:.0f} days"),
    ("installation", "in-c4", "info", pending_parked, "int", "Units parked on dead deals", "Not backlog"),
    ("service", "se-c1", "bad", rq_all.loc[f"{YEAR}Q3"].breach_rate, "pct", f"SLA breach, Q3 {YEAR}", f"{pct(rq_all.loc[f'{PREV}Q4'].breach_rate)} in Q4 {PREV}"),
    ("service", "se-c2", "bad", op.age_days.median(), "days", "Median open RO age", f"{int(allr.open_ros)} open ROs"),
    ("service", "se-c3", "warn", warranty_cost_share, "pct", "Repair cost on warranty jobs", "Absorbed by company"),
    ("service", "se-c4", "ok", allr.post_warranty_amc_cover, "pct", "Post-warranty AMC cover", f"{int(allr.active_amc):,} active contracts"),
    ("people", "pe-c1", "warn", len(off), "int", f"of {len(calib)} roles with out-of-scale targets", "Below 50% or above 200%"),
    ("people", "pe-c2", "info", int((sp_ok.attainment >= 1).sum()), "int", f"of {len(sp_ok)} salespeople at target", f"Range {pct(sp_ok.attainment.min())}–{pct(sp_ok.attainment.max())}"),
    ("people", "pe-c3", "warn", pre_hire.incentive_amount_inr.sum(), "inr", "Incentives dated before hire", f"{len(pre_hire)} payments"),
    ("people", "pe-c4", "info", inc_b.max() / inc_b.min(), "x", "Incentive spread, top vs bottom branch", f"Sales spread {br_only.sales_attainment.max() / br_only.sales_attainment.min():.1f}×"),
]
write("callouts", [{"tab": t, "id": i, "severity": sv, "value": float(v), "fmt": f, "label": l, "context": c}
                   for t, i, sv, v, f, l, c in callouts])

print(f"As of {AS_OF:%Y-%m-%d}; YTD = {YTD_LABEL}. Wrote {len(list(OUT.glob('*.json')))} files to {OUT.relative_to(ROOT)}")
for i in insights:
    print(f"[{i['tab']}] {i['headline']}\n    {i['detail']}")
