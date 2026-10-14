#!/usr/bin/env python3
"""Write REPORT.md from the dashboard datasets.

Run after build_dashboard_data.py, from the repo root:
    python dashboard/build_dashboard_data.py && python dashboard/build_report.py

Every number in the report is read from dashboard/data/*.json or data/*.csv,
so the report and the dashboard always agree.
"""
import json
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
DD = ROOT / "dashboard" / "data"
DASHBOARD_URL = "https://claude.ai/artifact/LzSYs78dp5rZF2QESL3WWb"


def load(name):
    return pd.DataFrame(json.loads((DD / f"{name}.json").read_text()))


sc = load("branch_scorecard").set_index("branch")
ins = load("insights").set_index("id")
monthly = load("monthly")
funnel = load("funnel")
src = load("lead_sources")
bs = load("booking_status")
sp = load("salespeople")
ist = load("install_status")
pol = load("po_lines")
vend = load("vendors")
cal = load("service_calendar")
port = load("amc_portfolio")
rq = load("ro_quarterly")
rp = load("ro_priority")
rf = load("ro_faults")
rc = load("ro_coverage")
age = load("ro_age")
tech = load("technicians")
att = load("attainment")
inc = load("incentives")
dq = load("data_quality")

A = sc.loc["All"]
BR = [b for b in sc.index if b != "All"]
YTD = A.ytd_label
AS_OF = pd.Timestamp(A.as_of)


def cr(v):
    return f"₹{v / 1e7:,.2f} Cr"


def lakh(v):
    return f"₹{v / 1e5:,.1f} L"


def inr(v):
    return cr(v) if abs(v) >= 1e7 else lakh(v)


def pct(v, d=0):
    return "—" if v is None or pd.isna(v) else f"{v * 100:.{d}f}%"


def signed(v):
    return "—" if v is None or pd.isna(v) else f"{'+' if v >= 0 else '−'}{abs(v) * 100:.0f}%"


def n(v):
    return f"{int(round(v)):,}"


def table(headers, rows, align=None):
    align = align or ["l"] + ["r"] * (len(headers) - 1)
    sep = ["---:" if a == "r" else ":---" for a in align]
    out = ["| " + " | ".join(headers) + " |", "| " + " | ".join(sep) + " |"]
    out += ["| " + " | ".join(str(c) for c in r) + " |" for r in rows]
    return "\n".join(out)


def status_icon(s):
    return {"ok": "🟢", "warn": "🟡", "bad": "🔴"}.get(s, "")


def finding(i):
    return f"- **{ins.loc[i].headline}** {ins.loc[i].detail}"


# ---------------------------------------------------------------- source table profile
TABLES = [
    ("dim_branch", "Branch", "One branch", None),
    ("dim_department", "Department", "One department", None),
    ("dim_employee", "Employee", "One employee (role, branch, hire date)", "hire_date"),
    ("dim_customer", "Customer", "One customer (type, city)", None),
    ("dim_vendor", "Vendor", "One installation vendor", None),
    ("dim_calendar", "Calendar", "One day", "full_date"),
    ("fact_leads", "Sales", "One lead", "lead_date"),
    ("fact_inquiries", "Sales", "One inquiry", "inquiry_date"),
    ("fact_quotations", "Sales", "One quotation", "quotation_date"),
    ("fact_bookings", "Sales", "One agreement (booking)", "agreement_date"),
    ("fact_units", "Installation", "One lift unit", "installation_complete_date"),
    ("fact_installation_pos", "Installation", "One vendor PO line", "po_date"),
    ("fact_warranty", "Service", "One unit's warranty", "warranty_start_date"),
    ("fact_amc", "Service", "One AMC contract", "start_date"),
    ("fact_repair_orders", "Service", "One repair order", "open_date"),
    ("fact_incentives", "People", "One monthly incentive payment", None),
    ("fact_employee_targets", "People", "One target per employee, metric and period", None),
]
profile = []
for name, area, grain, dcol in TABLES:
    df = pd.read_csv(ROOT / "data" / f"{name}.csv")
    rng = "—"
    if dcol and dcol in df:
        d = pd.to_datetime(df[dcol], errors="coerce").dropna()
        rng = f"{d.min():%b %Y} – {d.max():%b %Y}"
    profile.append((f"`{name}`", area, grain, n(len(df)), rng))

# ---------------------------------------------------------------- derived helpers
fc = funnel[(funnel.branch == "All")]
cur = fc[fc.period == "current"].set_index("step")
pri = fc[fc.period == "prior"].set_index("step")
prior_label = pri.iloc[0].period_label
m_all = monthly[monthly.branch == "All"].set_index("month")
rq_all = rq[rq.branch == "All"].sort_values("quarter").set_index("quarter")
rp_all = rp[rp.branch == "All"].sort_values("priority")
ist_all = ist[ist.branch == "All"]
pol_all = pol[pol.branch == "All"].sort_values("amount", ascending=False)
cal_all = cal[cal.branch == "All"].sort_values("month")
port_all = port[port.branch == "All"]
bs_all = bs[bs.branch == "All"].set_index("status")
sp_ok = sp.dropna(subset=["attainment"]).sort_values("attainment", ascending=False)
att_all = att[att.branch == "All"].set_index("role")
off = att_all[~att_all.calibrated]
rc_s = rc.set_index("coverage")
open_total = int(A.open_ros)
year = AS_OF.year

L = []
w = L.append

w("# Branch Sales, Installation & Service KPI Mart")
w("")
w("**Project report.** Portfolio project built on a fully synthetic dataset. Every company, customer, employee and rupee value is generated, and nothing here describes a real business.")
w("")
w(f"- **Dashboard:** [{DASHBOARD_URL}]({DASHBOARD_URL}) (six tabs, branch filter)")
w(f"- **Data as of:** {AS_OF:%-d %B %Y} · **Year to date (YTD):** {YTD}, compared with {prior_label}")
w("- **Rebuild:** `python dashboard/build_dashboard_data.py && python dashboard/build_report.py`")
w("")
w("---")
w("")
w("## Contents")
w("")
for i, t in enumerate(["Summary in numbers", "The business question", "Data", "Architecture", "KPI definitions",
                       "Dashboard tour", "Findings: branch scorecard", "Findings: sales", "Findings: installation",
                       "Findings: service", "Findings: people and targets", "Recommendations", "Data quality",
                       "Method and assumptions", "Limitations", "How to reproduce", "Skills demonstrated"], 1):
    w(f"{i}. [{t}](#{i}-{t.lower().replace(' ', '-').replace(':', '')})")
w("")

# 1 -----------------------------------------------------------------
w("## 1. Summary in numbers")
w("")
w(table(["Metric", "Value", "Context"], [
    [f"Agreement value, {YTD}", cr(A.agreement_value_ytd), f"{signed(A.agreement_value_yoy)} vs {prior_label}"],
    ["Sales vs target", pct(A.sales_attainment), f"Target {cr(A.sales_target_ytd)}"],
    ["Units installed vs target", pct(A.install_attainment), f"{n(A.units_completed_ytd)} of {n(A.install_target_ytd)} units"],
    ["Installation backlog", n(A.install_backlog), f"{n(A.units_delayed)} delayed, {cr(A.open_po_value)} open vendor POs"],
    ["Repair orders past SLA", pct(A.sla_breach_ytd), f"{pct(A.sla_breach_prev_ytd)} a year earlier"],
    ["Open repair orders", n(A.open_ros), f"{n(A.open_ros_p1)} P1-Critical, {n(A.open_ros_past_sla)} past SLA"],
    ["Active AMC portfolio", cr(A.active_amc_value), f"{n(A.active_amc)} contracts, {pct(A.post_warranty_amc_cover)} of post-warranty units covered"],
    ["AMC renewals due in 90 days", n(A.amc_due_90d), f"{cr(A.amc_due_90d_value)} annual value"],
], ["l", "r", "l"]))
w("")
w("**The answer in five lines**")
w("")
for i in ["ov-1", "ov-2", "ov-3", "ov-4", "ov-5"]:
    w(f"- {ins.loc[i].headline}")
w("")

# 2 -----------------------------------------------------------------
w("## 2. The business question")
w("")
w("Branch leadership at a vertical-transport (lift) company asks one question every month:")
w("")
w("> *Which branch is off target, and is it a sales problem, an installation problem, or a service problem?*")
w("")
w("The business runs in three hand-offs. **Sales** turns leads into signed agreements. **Installation** puts each unit in, using third-party vendors on purchase orders. **Service** covers the unit under warranty, sells an annual maintenance contract (AMC), and handles repair orders. A miss in one department shows up in the next, so the dashboard follows the same chain and keeps all five branches side by side: Surat, Vadodara, Vapi, Ahmedabad and Pune.")
w("")

# 3 -----------------------------------------------------------------
w("## 3. Data")
w("")
w("A star schema of 6 dimensions and 11 fact tables, exported as CSV in `data/`. It is generated by `generate_data.py`.")
w("")
w(table(["Table", "Area", "Grain", "Rows", "Date range"], profile, ["l", "l", "l", "r", "l"]))
w("")
w("Units carry an ID of the form `BK-YYYY-NNNNNL001`: the booking ID plus the unit's line number. That key links an agreement to its units, their vendor POs, warranty, AMC contracts and repair orders.")
w("")

# 4 -----------------------------------------------------------------
w("## 4. Architecture")
w("")
w("```mermaid")
w("flowchart LR")
w("  G[generate_data.py] --> C[(data/*.csv)]")
w("  C --> P[load_postgres.py] --> DB[(PostgreSQL star schema)] --> PBI[Power BI / DAX]")
w("  C --> B[dashboard/build_dashboard_data.py] --> J[(dashboard/data/*.json<br/>23 aggregated datasets)]")
w("  J --> D[Web dashboard<br/>dashboard/index.html, d3]")
w("  J --> R[dashboard/build_report.py] --> M[REPORT.md]")
w("```")
w("")
w("- The **SQL path** (`sql/schema.sql`, `load_postgres.py`, `docs/dax_measures.md`) is the warehouse version for Power BI.")
w("- The **dashboard path** aggregates with pandas into small JSON files, one per visual family. Each figure on the page is tagged with the dataset and field it came from.")
w("- **Signals and findings are generated, not typed.** The build script writes the short signals on the dashboard and the sentences in this report from the same aggregates, so they stay correct after a data refresh.")
w("")

# 5 -----------------------------------------------------------------
w("## 5. KPI definitions")
w("")
w(table(["KPI", "Definition", "Source"], [
    ["Agreement value", "Total agreement value of **Confirmed** agreements, by signing date", "`fact_bookings`"],
    ["Sales target", "Sum of Salesperson monthly targets (Sales Manager targets overlap and are not added)", "`fact_employee_targets`"],
    ["Sales vs target", "Agreement value ÷ sales target, YTD", "both"],
    ["Lead → agreement", "Confirmed agreements signed in the period ÷ leads created in the period", "`fact_leads`, `fact_bookings`"],
    ["Units installed", "Units with status Completed, by completion date", "`fact_units`"],
    ["Installs vs target", "Units installed ÷ sum of Installation Engineer *Units completed* targets", "`fact_units`, targets"],
    ["Installation backlog", "Confirmed-agreement units that are Scheduled, In Progress or Delayed", "`fact_units`"],
    ["Parked units", "Units on Cancelled or On Hold agreements (shown as Pending in the source)", "`fact_units`, `fact_bookings`"],
    ["Open vendor POs", "PO lines with status Open", "`fact_installation_pos`"],
    ["Repairs past SLA", "Share of repair orders opened in the period with `exceeded_sla = true`", "`fact_repair_orders`"],
    ["Open repair orders", "Status Open or In Progress at the as-of date", "`fact_repair_orders`"],
    ["Active AMC value", "Annual value of contracts with status Active", "`fact_amc`"],
    ["AMC renewals due", "Active contracts whose end date falls in the next 90 days", "`fact_amc`"],
    ["Post-warranty AMC cover", "Units out of warranty that have an Active AMC ÷ units out of warranty", "`fact_warranty`, `fact_amc`"],
    ["Lapsed AMC", "Expired contract with no later contract on the same unit", "`fact_amc`"],
    ["Out-of-scale target", "A role whose company-wide attainment is below 50% or above 200%", "targets + actuals"],
], ["l", "l", "l"]))
w("")
w("**Status thresholds used for colour:** sales 🟢 ≥ 85% of target, 🟡 ≥ 70%, otherwise 🔴. Installation 🟢 ≥ 85%, 🟡 ≥ 60%. Repairs past SLA 🟢 ≤ 25%, 🟡 ≤ 32%.")
w("")

# 6 -----------------------------------------------------------------
w("## 6. Dashboard tour")
w("")
w("Each tab follows the same pattern: **KPI tiles** with a 12-month micro-chart or a target meter, a strip of **four number signals**, then the **charts**. A branch picker in the header, or a click on any branch, filters every tab.")
w("")
w(table(["Tab", "Tiles", "Charts"], [
    ["Overview", "Agreement value, sales vs target, units installed, backlog, repairs past SLA, AMC renewals due", "Branch scorecard heatmap · sales vs installs dumbbell · value by branch vs last year · monthly value vs target"],
    ["Sales", "Agreement value, vs target, agreements, leads, conversion", "Monthly value vs target · funnel vs last year · signed value by outcome (donut) · leads and conversion by branch · conversion by source · every salesperson vs target"],
    ["Installation", "Units installed, vs target, backlog, delayed, open POs", "Units booked vs installed · unit status (donut) · installs vs target by branch · PO cost by line item · spend by vendor"],
    ["Service", "Repair orders, past SLA, open past SLA, AMC value, renewals due, post-warranty cover", "Repair orders and breaches by quarter · breach by priority · open ROs by age · renewals and warranty expiries ahead · AMC by branch · repair cost by cover (donut) · faults · technician scatter"],
    ["People", "Headcount, incentives, salespeople at target, roles out of scale", "Attainment by role · incentives by year and role · role × branch attainment heatmap"],
    ["Data quality", "One card per issue", "Rows and money affected"],
], ["l", "l", "l"]))
w("")

# 7 -----------------------------------------------------------------
w("## 7. Findings: branch scorecard")
w("")
w(f"{YTD}. 🟢 on target · 🟡 watch · 🔴 off target.")
w("")
rows = []
for b in BR + ["All"]:
    r = sc.loc[b]
    rows.append([f"**{b}**" if b != "All" else "Company", cr(r.agreement_value_ytd),
                 f"{status_icon(r.sales_status)} {pct(r.sales_attainment)}", signed(r.agreement_value_yoy),
                 f"{status_icon(r.install_status)} {pct(r.install_attainment)}", n(r.units_delayed),
                 f"{status_icon(r.service_status)} {pct(r.sla_breach_ytd)}", n(r.open_ros), n(r.amc_due_90d),
                 r.problem_areas])
w(table(["Branch", "Agreement value", "Sales vs target", "vs last year", "Installs vs target", "Units delayed",
         "Past SLA", "Open ROs", "AMC due 90 d", "Off target in"], rows,
        ["l", "r", "r", "r", "r", "r", "r", "r", "r", "l"]))
w("")
for i in ["ov-1", "ov-2", "ov-3", "ov-4", "ov-5"]:
    w(finding(i))
w("")

# 8 -----------------------------------------------------------------
w("## 8. Findings: sales")
w("")
for i in ["sa-1", "sa-2", "sa-3", "sa-4", "sa-5"]:
    w(finding(i))
w("")
w(f"**Funnel, company, {YTD} vs {prior_label}**")
w("")
w(table(["Stage", "This year", "Last year", "Kept from step before", "Share of leads"],
        [[cur.loc[s].stage, n(cur.loc[s]["count"]), n(pri.loc[s]["count"]),
          pct(cur.loc[s].from_prev) if s > 1 else "—", pct(cur.loc[s].of_first, 1)] for s in cur.index]))
w("")
w(f"**Leads and conversion by branch, {YTD}**")
w("")
fb = funnel[(funnel.period == "current") & (funnel.branch != "All")]
w(table(["Branch", "Leads", "Leads last year", "Agreements", "Lead → agreement", "Quotation → agreement"],
        [[b, n(sc.loc[b].leads_ytd), n(sc.loc[b].leads_prev_ytd), n(sc.loc[b].agreements_ytd),
          pct(sc.loc[b].lead_to_agreement, 1),
          pct(fb[(fb.branch == b) & (fb.step == 4)].from_prev.iloc[0])] for b in BR]))
w("")
w("**Signed value by outcome, all history**")
w("")
w(table(["Status", "Agreements", "Units", "Value", "Share of value"],
        [[s, n(bs_all.loc[s].agreements), n(bs_all.loc[s].units), cr(bs_all.loc[s].value), pct(bs_all.loc[s].share_of_value, 1)]
         for s in ["Confirmed", "On Hold", "Cancelled"]]))
w("")
w("**Lead sources, all history**")
w("")
w(table(["Source", "Leads", "Agreements", "Conversion", "Average deal"],
        [[r.source, n(r.leads), n(r.agreements), pct(r.lead_to_agreement, 1), lakh(r.avg_deal)] for r in src.itertuples()]))
w("")
w(f"**Salespeople, {YTD}: top five and bottom five by attainment**")
w("")
sel = pd.concat([sp_ok.head(5), sp_ok.tail(5)])
w(table(["Salesperson", "Branch", "Agreement value", "Target", "Attainment", "Quote win rate"],
        [[r.salesperson, r.branch, inr(r.agreement_value), inr(r.target), pct(r.attainment), pct(r.quote_win_rate)]
         for r in sel.itertuples()], ["l", "l", "r", "r", "r", "r"]))
w("")

# 9 -----------------------------------------------------------------
w("## 9. Findings: installation")
w("")
for i in ["in-1", "in-2", "in-3", "in-4", "in-5"]:
    w(finding(i))
w("")
w("**Where every unit stands, now**")
w("")
order = ["Completed", "In Progress", "Scheduled", "Delayed", "Parked (On Hold agreement)", "Parked (Cancelled agreement)"]
ia = ist_all.set_index("bucket")
w(table(["Status", "Units", "Share"], [[b, n(ia.loc[b].units), pct(ia.loc[b].share, 1)] for b in order if b in ia.index]))
w("")
w("**Units booked vs installed, last six complete months**")
w("")
last6 = m_all[~m_all.partial].tail(6)
w(table(["Month", "Units booked", "Units installed", "Gap"],
        [[pd.Period(mo).strftime("%b %Y"), n(r.units_booked), n(r.units_completed), f"{int(r.units_booked - r.units_completed):+d}"]
         for mo, r in last6.iterrows()]))
w("")
w("**Vendor PO cost by line item, all history**")
w("")
w(table(["Line item", "PO lines", "Value", "Still open"],
        [[r.line_item, n(r.pos), cr(r.amount), cr(r.open_amount)] for r in pol_all.itertuples()]))
w("")
w(f"Fifteen vendors share the PO value. The largest takes {pct(vend.amount.max() / vend.amount.sum(), 1)} and the smallest {pct(vend.amount.min() / vend.amount.sum(), 1)}.")
w("")

# 10 ----------------------------------------------------------------
w("## 10. Findings: service")
w("")
for i in ["se-1", "se-2", "se-3", "se-4", "se-5"]:
    w(finding(i))
w("")
w("**Repair orders by quarter (company)**")
w("")
w(table(["Quarter", "Repair orders", "Breached SLA", "Breach rate", "Median resolution"],
        [[f"{q[4:]} {q[:4]}" + (" (partial)" if r.partial else ""), n(r.ros), n(r.breached), pct(r.breach_rate), f"{r.median_resolution_h:g} h"]
         for q, r in rq_all.iterrows()]))
w("")
w("**By priority, all history**")
w("")
w(table(["Priority", "SLA", "Repair orders", "Breach rate", "Median resolution", "Open now"],
        [[r.priority, f"{r.sla_hours:g} h", n(r.ros), pct(r.breach_rate), f"{r.median_resolution_h:g} h", n(r.open)] for r in rp_all.itertuples()]))
w("")
ag = age[age.branch == "All"].groupby(["step", "age_bucket"]).open_ros.sum().reset_index()
w(f"**Open repair orders by age ({open_total} total)**")
w("")
w(table(["Age", "Open ROs"], [[r.age_bucket, n(r.open_ros)] for r in ag.itertuples()]))
w("")
w("**Who carries repair cost, all history**")
w("")
w(table(["Cover when opened", "Repair orders", "Parts", "Labour", "Share of cost"],
        [[c, n(r.ros), lakh(r.parts), lakh(r.labor), pct(r.share_of_cost, 1)] for c, r in rc_s.iterrows()]))
w("")
w("**Most common faults**")
w("")
w(table(["Fault", "Repair orders", "Breach rate", "Average cost"],
        [[r.description, n(r.ros), pct(r.breach_rate), lakh(r.avg_cost)] for r in rf.itertuples()]))
w("")
w("**AMC renewals and warranty expiries, next six months**")
w("")
w(table(["Month", "AMC renewals", "Comprehensive", "Non-comprehensive", "Annual value", "Warranties expiring"],
        [[pd.Period(r.month).strftime("%b %Y"), n(r.amc_renewals), n(r.comprehensive), n(r.non_comprehensive),
          lakh(r.amc_renewal_value), n(r.warranty_expiring)] for r in cal_all.head(6).itertuples()]))
w("")
w("**Active AMC portfolio by branch**")
w("")
pb = port[port.branch != "All"].pivot(index="branch", columns="amc_type", values="contracts").reindex(BR)
w(table(["Branch", "Comprehensive", "Non-comprehensive", "Annual value", "Expired AMCs lapsed"],
        [[b, n(pb.loc[b, "Comprehensive"]), n(pb.loc[b, "Non-comprehensive"]), cr(sc.loc[b].active_amc_value),
          pct(sc.loc[b].expired_amc_lapse_rate)] for b in BR]))
w("")
worst_t = tech.sort_values("breach_rate", ascending=False).head(5)
w("**Technicians with the highest breach rate**")
w("")
w(table(["Technician", "Branch", "Repair orders", "Breach rate", "Median resolution"],
        [[r.technician, r.branch, n(r.ros), pct(r.breach_rate), f"{r.median_resolution_h:g} h"] for r in worst_t.itertuples()],
        ["l", "l", "r", "r", "r"]))
w("")

# 11 ----------------------------------------------------------------
w("## 11. Findings: people and targets")
w("")
for i in ["pe-1", "pe-2", "pe-3", "pe-4"]:
    w(finding(i))
w("")
w(f"**Target attainment, {YTD}** (✱ = target out of scale with volume)")
w("")
roles = list(dict.fromkeys(att.role))
mat = att.pivot(index="role", columns="branch", values="attainment").reindex(roles)
cal_flag = att_all.calibrated
w(table(["Role", "Measured on"] + BR + ["Company"],
        [[r + ("" if cal_flag[r] else " ✱"), att_all.loc[r].metric] + [pct(mat.loc[r, b]) for b in BR] + [pct(mat.loc[r, "All"])] for r in roles],
        ["l", "l"] + ["r"] * (len(BR) + 1)))
w("")
w("**Incentives paid by year (company)**")
w("")
iy = inc[inc.branch == "All"].groupby(["year", "year_label"]).agg(amount=("amount", "sum"), payments=("payments", "sum")).reset_index()
w(table(["Year", "Amount", "Payments"], [[r.year_label, lakh(r.amount), n(r.payments)] for r in iy.itertuples()]))
w("")

# 12 ----------------------------------------------------------------
w("## 12. Recommendations")
w("")
w(table(["#", "Action", "Owner", "Why (from the data)", "Track"], [
    ["1", "Rebuild the lead engine in the weakest branch: field lead generators, architect and referral programmes", "Sales",
     ins.loc["sa-1"].headline, "Leads per month, lead → agreement"],
    ["2", "Run a quotation win-loss review in branches below the company quote-to-agreement rate", "Sales", ins.loc["sa-2"].detail, "Quotation → agreement"],
    ["3", "Monthly review of on-hold agreements", "Sales", ins.loc["sa-3"].headline, "On-hold value, revived deals"],
    ["4", "Clear delayed installations: vendor-by-vendor recovery plan, close open POs", "Installation", ins.loc["in-2"].headline, "Delayed units, open PO value"],
    ["5", "Restore installation throughput to the booking rate", "Installation", ins.loc["in-1"].detail.split('.')[0] + ".", "Units installed vs booked per month"],
    ["6", "Ticket-by-ticket review of open repair orders; close or escalate everything older than 30 days", "Service", ins.loc["se-2"].headline, "Open ROs by age"],
    ["7", "Dispatch rule that puts P1-Critical first, plus technician coaching on the highest breach rates", "Service", ins.loc["se-1"].headline, "Breach rate by priority"],
    ["8", "Renewal desk for the next 90 days of AMC expiries", "Service", ins.loc["se-3"].headline, "Renewal rate, lapsed units"],
    ["9", "Root-cause the top warranty faults with engineering and vendors", "Service / Installation", ins.loc["se-5"].headline, "Warranty repair cost, repeat ROs"],
    ["10", "Rebase targets from actual volume before tying incentives to them", "Leadership / HR", ins.loc["pe-1"].headline, "Share of roles in scale"],
    ["11", "Fix the data issues below at source", "Data / ERP", f"{len(dq)} issues found", "Issue counts to zero"],
], ["r", "l", "l", "l", "l"]))
w("")

# 13 ----------------------------------------------------------------
w("## 13. Data quality")
w("")
w("Issues found while building the mart. Each one changes how a number should be read, and the dashboard handles them as described.")
w("")
w(table(["Issue", "Table", "Rows", "Money affected", "What it means"],
        [[r.check, f"`{r.table}`", n(r.rows), inr(r.amount), r.impact] for r in dq.itertuples()],
        ["l", "l", "r", "r", "l"]))
w("")

# 14 ----------------------------------------------------------------
w("## 14. Method and assumptions")
w("")
w(f"- **As-of date** is the latest lead, booking or repair-order date in the extract: {AS_OF:%-d %b %Y}.")
w(f"- **YTD** runs from 1 January to the last complete month ({YTD}) and is compared with the same months of the prior year. The latest month is shown as partial in monthly charts.")
w("- **Attribution.** Agreements go to their salesperson and sales manager, leads to their lead generator, completed units to their installation engineer, AMC value to its service salesperson, and closed repair orders to their supervisor and technician. Installation managers are credited with their branch's completed units, because units carry no manager ID.")
w("- **Branch totals** come from the fact table's own `branch_id`. Every employee's attributed activity sits in their home branch.")
w("- **Each branch dataset carries an *All* row**, so the dashboard's branch filter only selects rows and never recomputes totals in the browser.")
w("- **Renewal and lapse.** Because contracts on the same unit overlap (see Data quality), a contract counts as renewed when any later contract exists on the same unit.")
w("")

# 15 ----------------------------------------------------------------
w("## 15. Limitations")
w("")
w("- The dataset is synthetic: distributions are generated, and many rates are close to uniform. Use the findings to show method, not to make claims about any real company.")
w("- Targets for several roles do not match the generated volumes. Their attainment is reported but flagged rather than judged.")
w("- No cost of sales or margin data beyond equipment cost, so profitability is out of scope.")
w("- Repair-order SLA is a flag in the source. Resolution hours are not recomputed from timestamps.")
w("")

# 16 ----------------------------------------------------------------
w("## 16. How to reproduce")
w("")
w("```bash")
w("pip install pandas numpy")
w("python generate_data.py                      # optional: regenerate data/*.csv")
w("python dashboard/build_dashboard_data.py     # data/*.csv -> dashboard/data/*.json")
w("python dashboard/build_report.py             # dashboard/data/*.json -> REPORT.md")
w("```")
w("")
w("For the warehouse path, run `sql/schema.sql` and then `python load_postgres.py --db yourdb`, and connect Power BI with the measures in `docs/dax_measures.md`. The checks in `sql/reconciliation.sql` should match the dashboard totals.")
w("")

# 17 ----------------------------------------------------------------
w("## 17. Skills demonstrated")
w("")
w("- **Data modelling:** star schema across three departments, a unit-level key that links sales, installation and service.")
w("- **KPI design:** definitions agreed in business language, a target framework, status thresholds and a north-star metric per department.")
w("- **Analytics engineering:** a reproducible pandas pipeline, pre-aggregated datasets, and a report generated from code.")
w("- **Root-cause analysis:** separating volume from conversion problems, and backlog from parked units.")
w("- **Data quality:** six issues found and quantified, with the dashboard designed around each.")
w("- **Visualisation:** a multi-tab d3 dashboard with KPI tiles, micro-charts, heatmaps, a funnel, donuts, a dumbbell and a scatter, plus a branch filter and tooltips.")
w("- **Communication:** findings and recommendations tied to a metric to track.")
w("")

(ROOT / "REPORT.md").write_text("\n".join(L) + "\n")
print(f"Wrote REPORT.md ({len(L)} lines)")
