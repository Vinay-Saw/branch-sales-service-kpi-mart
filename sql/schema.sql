-- Branch Sales & Service KPI Mart
-- PostgreSQL schema (star schema)
-- Nightly ERP extracts loaded into these tables.
-- Grain documented in each fact comment.

CREATE SCHEMA IF NOT EXISTS kpi_mart;

-- Dimensions
CREATE TABLE kpi_mart.dim_branch (
    branch_id       INT PRIMARY KEY,
    branch_code     VARCHAR(10) NOT NULL,
    branch_name     VARCHAR(50) NOT NULL,
    state           VARCHAR(50),
    region          VARCHAR(50)
);

CREATE TABLE kpi_mart.dim_product (
    product_id          INT PRIMARY KEY,
    product_code        VARCHAR(20),
    product_name        VARCHAR(100),
    product_type        VARCHAR(30),   -- Gearless, Hydraulic, Home Lift
    typical_value_inr   INT
);

CREATE TABLE kpi_mart.dim_salesperson (
    salesperson_id  INT PRIMARY KEY,
    salesperson_name VARCHAR(100),
    branch_id       INT REFERENCES kpi_mart.dim_branch(branch_id),
    active          BOOLEAN,
    hire_date       DATE
);

CREATE TABLE kpi_mart.dim_customer (
    customer_id         INT PRIMARY KEY,
    customer_name       VARCHAR(200),
    customer_type       VARCHAR(50),
    city                VARCHAR(100),
    primary_branch_id   INT REFERENCES kpi_mart.dim_branch(branch_id)
);

-- Role-playing calendar (one table, multiple relationships in Power BI)
CREATE TABLE kpi_mart.dim_calendar (
    date_key        INT PRIMARY KEY,
    full_date       DATE NOT NULL,
    year            INT,
    quarter         INT,
    month           INT,
    month_name      VARCHAR(20),
    year_month      VARCHAR(7),
    day_of_week     INT,
    is_weekend      BOOLEAN,
    fiscal_year     INT,
    fiscal_quarter  INT
);

-- Facts
-- Grain: one booking line (one product quantity on one booking)
CREATE TABLE kpi_mart.fact_bookings (
    booking_line_id     INT PRIMARY KEY,
    booking_id          VARCHAR(30),
    booking_date        DATE,
    branch_id           INT REFERENCES kpi_mart.dim_branch(branch_id),
    salesperson_id      INT REFERENCES kpi_mart.dim_salesperson(salesperson_id),
    customer_id         INT REFERENCES kpi_mart.dim_customer(customer_id),
    product_id          INT REFERENCES kpi_mart.dim_product(product_id),
    quantity            INT,
    list_value_inr      INT,
    net_value_inr       INT,
    status              VARCHAR(20),   -- Confirmed, Cancelled, On Hold, Delivered
    cancel_reason       VARCHAR(100),
    expected_install_month VARCHAR(7)
);

-- Grain: one installation job (linked to a booking line)
CREATE TABLE kpi_mart.fact_installations (
    installation_id         INT PRIMARY KEY,
    booking_line_id         INT,
    booking_id              VARCHAR(30),
    branch_id               INT REFERENCES kpi_mart.dim_branch(branch_id),
    customer_id             INT REFERENCES kpi_mart.dim_customer(customer_id),
    product_id              INT REFERENCES kpi_mart.dim_product(product_id),
    quantity                INT,
    scheduled_date          DATE,
    actual_completion_date  DATE,
    status                  VARCHAR(20),  -- Completed, Delayed, Scheduled, Cancelled
    value_inr               INT,
    days_from_booking       INT
);

-- Grain: one service call
CREATE TABLE kpi_mart.fact_service_calls (
    service_call_id     INT PRIMARY KEY,
    open_date           DATE,
    close_date          DATE,
    open_branch_id      INT REFERENCES kpi_mart.dim_branch(branch_id),
    close_branch_id     INT REFERENCES kpi_mart.dim_branch(branch_id),
    customer_id         INT REFERENCES kpi_mart.dim_customer(customer_id),
    product_id          INT REFERENCES kpi_mart.dim_product(product_id),
    call_type           VARCHAR(50),
    priority            VARCHAR(20),
    sla_hours           INT,
    resolution_hours    INT,
    status              VARCHAR(20),
    amc_related         BOOLEAN,
    exceeded_sla        BOOLEAN
);

-- Grain: one monthly target by branch + product type
CREATE TABLE kpi_mart.fact_targets (
    target_id           INT PRIMARY KEY,
    branch_id           INT REFERENCES kpi_mart.dim_branch(branch_id),
    product_type        VARCHAR(30),
    year                INT,
    month               INT,
    target_units        INT,
    target_value_inr    INT,
    revised_mid_period  BOOLEAN,
    revision_date       DATE
);

-- Grain: one AMC contract
CREATE TABLE kpi_mart.fact_amc (
    amc_id              INT PRIMARY KEY,
    customer_id         INT REFERENCES kpi_mart.dim_customer(customer_id),
    branch_id           INT REFERENCES kpi_mart.dim_branch(branch_id),
    product_type        VARCHAR(30),
    start_date          DATE,
    end_date            DATE,
    annual_value_inr    INT,
    status              VARCHAR(20),
    renewal_due_month   VARCHAR(7)
);

-- Indexes for common filters
CREATE INDEX idx_bookings_date ON kpi_mart.fact_bookings(booking_date);
CREATE INDEX idx_bookings_branch ON kpi_mart.fact_bookings(branch_id);
CREATE INDEX idx_service_open ON kpi_mart.fact_service_calls(open_date);
CREATE INDEX idx_service_status ON kpi_mart.fact_service_calls(status);
CREATE INDEX idx_amc_end ON kpi_mart.fact_amc(end_date);
