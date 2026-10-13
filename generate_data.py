#!/usr/bin/env python3
"""
Synthetic ERP extracts for Branch Sales & Service KPI Mart
Vertical transport company — Surat, Vadodara, Vapi branches.
Dataset is simulated. No real company or personal data.
"""

import pandas as pd
import numpy as np
from faker import Faker
from datetime import datetime, timedelta
import random
import os

fake = Faker("en_IN")
Faker.seed(42)
np.random.seed(42)
random.seed(42)

OUT = "/workspace/artifacts/branch-kpi-mart/data"
os.makedirs(OUT, exist_ok=True)

# ---------------------------------------------------------------------------
# Dimensions
# ---------------------------------------------------------------------------

branches = pd.DataFrame({
    "branch_id": [1, 2, 3],
    "branch_code": ["SUR", "VAD", "VAP"],
    "branch_name": ["Surat", "Vadodara", "Vapi"],
    "state": ["Gujarat", "Gujarat", "Gujarat"],
    "region": ["South Gujarat", "Central Gujarat", "South Gujarat"],
})

products = pd.DataFrame({
    "product_id": [1, 2, 3, 4, 5],
    "product_code": ["GL-08", "GL-13", "HY-06", "HY-10", "HL-04"],
    "product_name": [
        "Gearless Traction 8-person",
        "Gearless Traction 13-person",
        "Hydraulic 6-person",
        "Hydraulic 10-person",
        "Home Lift 4-person",
    ],
    "product_type": ["Gearless", "Gearless", "Hydraulic", "Hydraulic", "Home Lift"],
    "typical_value_inr": [850000, 1200000, 450000, 620000, 280000],
})

# Salespeople — generic Indian names
salespeople = []
for i in range(1, 13):
    salespeople.append({
        "salesperson_id": i,
        "salesperson_name": fake.name(),
        "branch_id": ((i - 1) % 3) + 1,
        "active": True,
        "hire_date": fake.date_between(start_date="-6y", end_date="-1y"),
    })
dim_salesperson = pd.DataFrame(salespeople)

# Customers — companies / building owners
customers = []
for i in range(1, 181):
    customers.append({
        "customer_id": i,
        "customer_name": fake.company(),
        "customer_type": random.choice(["Residential Society", "Commercial", "Hospital", "Hotel", "Industrial", "Government"]),
        "city": random.choice(["Surat", "Vadodara", "Vapi", "Navsari", "Bharuch", "Anand"]),
        "primary_branch_id": random.choice([1, 2, 3]),
    })
dim_customer = pd.DataFrame(customers)

# Calendar — 2023-01-01 to 2026-12-31 (role-playing ready)
start = datetime(2023, 1, 1)
end = datetime(2026, 12, 31)
dates = pd.date_range(start, end, freq="D")
dim_calendar = pd.DataFrame({
    "date_key": dates.strftime("%Y%m%d").astype(int),
    "full_date": dates,
    "year": dates.year,
    "quarter": dates.quarter,
    "month": dates.month,
    "month_name": dates.strftime("%B"),
    "year_month": dates.strftime("%Y-%m"),
    "day_of_week": dates.dayofweek + 1,
    "is_weekend": dates.dayofweek >= 5,
    "fiscal_year": dates.year + (dates.month >= 4).astype(int),  # Apr-Mar fiscal
    "fiscal_quarter": ((dates.month - 4) % 12 // 3) + 1,
})

# ---------------------------------------------------------------------------
# Targets (can change mid-quarter)
# ---------------------------------------------------------------------------
# Monthly targets by branch, product type, for bookings value and units
target_rows = []
tid = 1
for year in [2024, 2025, 2026]:
    for month in range(1, 13):
        for b in [1, 2, 3]:
            for ptype in ["Gearless", "Hydraulic", "Home Lift"]:
                base_units = {"Gearless": 4, "Hydraulic": 6, "Home Lift": 8}[ptype]
                base_value = {"Gearless": 4_200_000, "Hydraulic": 2_800_000, "Home Lift": 1_800_000}[ptype]
                # Seasonal and branch variation
                seasonal = 1.0 + 0.15 * np.sin((month - 3) * np.pi / 6)
                branch_factor = {1: 1.15, 2: 1.0, 3: 0.85}[b]
                units = max(1, int(base_units * seasonal * branch_factor * np.random.uniform(0.85, 1.15)))
                value = int(base_value * seasonal * branch_factor * np.random.uniform(0.9, 1.1))
                # Occasional mid-quarter revision (flag)
                revised = random.random() < 0.08
                target_rows.append({
                    "target_id": tid,
                    "branch_id": b,
                    "product_type": ptype,
                    "year": year,
                    "month": month,
                    "target_units": units,
                    "target_value_inr": value,
                    "revised_mid_period": revised,
                    "revision_date": None if not revised else fake.date_between(
                        start_date=datetime(year, month, 1),
                        end_date=datetime(year, month, 28) if month != 12 else datetime(year, 12, 28)
                    ),
                })
                tid += 1
fact_targets = pd.DataFrame(target_rows)

# ---------------------------------------------------------------------------
# Fact: Bookings (order lines — grain = one booking line)
# ---------------------------------------------------------------------------
booking_rows = []
bid = 1
for _ in range(2400):  # ~800 bookings / year over 3 years
    booking_date = fake.date_between(start_date="-3y", end_date="today")
    branch_id = random.choices([1, 2, 3], weights=[0.40, 0.35, 0.25])[0]
    salesperson = dim_salesperson[dim_salesperson.branch_id == branch_id].sample(1).iloc[0]
    customer = dim_customer.sample(1).iloc[0]
    product = products.sample(1).iloc[0]
    qty = random.choices([1, 2, 3, 4], weights=[0.7, 0.2, 0.07, 0.03])[0]
    list_value = product.typical_value_inr * qty
    discount = random.uniform(0.0, 0.12)
    net_value = int(list_value * (1 - discount))
    status = random.choices(
        ["Confirmed", "Cancelled", "On Hold", "Delivered"],
        weights=[0.72, 0.08, 0.05, 0.15]
    )[0]
    cancel_reason = None
    if status == "Cancelled":
        cancel_reason = random.choice(["Customer cancelled", "Financing failed", "Site not ready", "Price renegotiation"])
    booking_rows.append({
        "booking_line_id": bid,
        "booking_id": f"BK-{booking_date.year}-{bid:05d}",
        "booking_date": booking_date,
        "branch_id": branch_id,
        "salesperson_id": salesperson.salesperson_id,
        "customer_id": customer.customer_id,
        "product_id": product.product_id,
        "quantity": qty,
        "list_value_inr": list_value,
        "net_value_inr": net_value,
        "status": status,
        "cancel_reason": cancel_reason,
        "expected_install_month": (booking_date + timedelta(days=random.randint(45, 120))).strftime("%Y-%m"),
    })
    bid += 1
fact_bookings = pd.DataFrame(booking_rows)

# ---------------------------------------------------------------------------
# Fact: Installations (one row per installation job)
# ---------------------------------------------------------------------------
install_rows = []
iid = 1
confirmed = fact_bookings[fact_bookings.status.isin(["Confirmed", "Delivered"])]
for _, bk in confirmed.sample(frac=0.65, random_state=42).iterrows():
    install_date = bk.booking_date + timedelta(days=random.randint(40, 150))
    if install_date > datetime.now().date():
        status = "Scheduled"
        actual_date = None
    else:
        status = random.choices(["Completed", "Delayed", "Cancelled"], weights=[0.82, 0.12, 0.06])[0]
        actual_date = install_date if status == "Completed" else install_date + timedelta(days=random.randint(10, 45))
    # Cross-branch possible for service later, but installation usually same
    install_rows.append({
        "installation_id": iid,
        "booking_line_id": bk.booking_line_id,
        "booking_id": bk.booking_id,
        "branch_id": bk.branch_id,
        "customer_id": bk.customer_id,
        "product_id": bk.product_id,
        "quantity": bk.quantity,
        "scheduled_date": install_date,
        "actual_completion_date": actual_date,
        "status": status,
        "value_inr": bk.net_value_inr,
        "days_from_booking": (install_date - bk.booking_date).days if status != "Scheduled" else None,
    })
    iid += 1
fact_installations = pd.DataFrame(install_rows)

# ---------------------------------------------------------------------------
# Fact: Service Calls (including AMC-related)
# ---------------------------------------------------------------------------
service_rows = []
sid = 1
for _ in range(3200):
    open_date = fake.date_between(start_date="-3y", end_date="today")
    open_branch = random.choices([1, 2, 3], weights=[0.38, 0.35, 0.27])[0]
    # 8% opened in one branch, closed in another
    close_branch = open_branch if random.random() > 0.08 else random.choice([b for b in [1, 2, 3] if b != open_branch])
    customer = dim_customer.sample(1).iloc[0]
    product = products.sample(1).iloc[0]
    call_type = random.choices(
        ["Breakdown", "AMC Visit", "Callback", "Inspection", "Modernization Quote"],
        weights=[0.35, 0.30, 0.15, 0.12, 0.08]
    )[0]
    priority = random.choices(["P1-Critical", "P2-High", "P3-Normal", "P4-Low"], weights=[0.12, 0.25, 0.45, 0.18])[0]
    sla_hours = {"P1-Critical": 4, "P2-High": 8, "P3-Normal": 24, "P4-Low": 72}[priority]
    # Status
    if open_date > datetime.now().date() - timedelta(days=5):
        status = random.choice(["Open", "In Progress"])
        close_date = None
        resolution_hours = None
        exceeded = False
    else:
        status = random.choices(["Closed", "Open", "Cancelled"], weights=[0.88, 0.07, 0.05])[0]
        if status == "Closed":
            resolution_hours = max(1, int(np.random.lognormal(mean=np.log(sla_hours * 0.7), sigma=0.5)))
            close_date = open_date + timedelta(hours=resolution_hours)
            # Some exceed SLA
            if random.random() < 0.18:
                resolution_hours = int(sla_hours * random.uniform(1.1, 2.5))
                close_date = open_date + timedelta(hours=resolution_hours)
            exceeded = resolution_hours > sla_hours
        else:
            # Still open — check if already past SLA
            hours_open = (datetime.now().date() - open_date).days * 24
            close_date = None
            resolution_hours = None
            exceeded = hours_open > sla_hours
    amc_related = call_type in ["AMC Visit", "Inspection"] or random.random() < 0.15
    service_rows.append({
        "service_call_id": sid,
        "open_date": open_date,
        "close_date": close_date,
        "open_branch_id": open_branch,
        "close_branch_id": close_branch if status == "Closed" else None,
        "customer_id": customer.customer_id,
        "product_id": product.product_id,
        "call_type": call_type,
        "priority": priority,
        "sla_hours": sla_hours,
        "resolution_hours": resolution_hours,
        "status": status,
        "amc_related": amc_related,
        "exceeded_sla": exceeded,
    })
    sid += 1
fact_service = pd.DataFrame(service_rows)

# ---------------------------------------------------------------------------
# AMC contracts (for renewal due this month)
# ---------------------------------------------------------------------------
amc_rows = []
aid = 1
for cust in dim_customer.sample(frac=0.55, random_state=7).itertuples():
    start = fake.date_between(start_date="-4y", end_date="-6m")
    # Annual or multi-year
    term_years = random.choice([1, 1, 1, 2, 3])
    end = start + timedelta(days=365 * term_years - 5)
    # Some renewed
    renewed = end < datetime.now().date() and random.random() < 0.72
    if renewed:
        start = end + timedelta(days=random.randint(1, 20))
        end = start + timedelta(days=365 * random.choice([1, 2]) - 5)
    amc_rows.append({
        "amc_id": aid,
        "customer_id": cust.customer_id,
        "branch_id": cust.primary_branch_id,
        "product_type": random.choice(["Gearless", "Hydraulic", "Home Lift"]),
        "start_date": start,
        "end_date": end,
        "annual_value_inr": random.randint(45000, 180000),
        "status": "Active" if end >= datetime.now().date() else "Expired",
        "renewal_due_month": end.strftime("%Y-%m"),
    })
    aid += 1
fact_amc = pd.DataFrame(amc_rows)

# ---------------------------------------------------------------------------
# Save
# ---------------------------------------------------------------------------
branches.to_csv(f"{OUT}/dim_branch.csv", index=False)
products.to_csv(f"{OUT}/dim_product.csv", index=False)
dim_salesperson.to_csv(f"{OUT}/dim_salesperson.csv", index=False)
dim_customer.to_csv(f"{OUT}/dim_customer.csv", index=False)
dim_calendar.to_csv(f"{OUT}/dim_calendar.csv", index=False)
fact_targets.to_csv(f"{OUT}/fact_targets.csv", index=False)
fact_bookings.to_csv(f"{OUT}/fact_bookings.csv", index=False)
fact_installations.to_csv(f"{OUT}/fact_installations.csv", index=False)
fact_service.to_csv(f"{OUT}/fact_service_calls.csv", index=False)
fact_amc.to_csv(f"{OUT}/fact_amc.csv", index=False)

print("Generated files:")
for f in os.listdir(OUT):
    df = pd.read_csv(f"{OUT}/{f}")
    print(f"  {f}: {len(df):,} rows")
print("Done.")
