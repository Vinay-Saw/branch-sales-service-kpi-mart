-- Branch Sales, Installation & Service KPI Mart
-- PostgreSQL star schema reflecting departmental flow
-- Sales → Installation → Service (Warranty → AMC + Repair Orders)
-- Dataset is simulated.

CREATE SCHEMA IF NOT EXISTS kpi_mart;

-- Dimensions
CREATE TABLE kpi_mart.dim_branch (
    branch_id       INT PRIMARY KEY,
    branch_code     VARCHAR(10) NOT NULL,
    branch_name     VARCHAR(50) NOT NULL,
    state           VARCHAR(50),
    region          VARCHAR(50)
);

CREATE TABLE kpi_mart.dim_employee (
    employee_id         INT PRIMARY KEY,
    employee_name       VARCHAR(100),
    role                VARCHAR(50),  -- Lead Generator, Salesperson, Sales Manager, Installation Engineer, Installation Manager, Service Sales Person, Service Supervisor, Service Technician
    branch_id           INT REFERENCES kpi_mart.dim_branch(branch_id),
    active              BOOLEAN,
    hire_date           DATE,
    incentive_eligible  BOOLEAN
);

CREATE TABLE kpi_mart.dim_customer (
    customer_id         INT PRIMARY KEY,
    customer_name       VARCHAR(200),
    customer_type       VARCHAR(50),
    city                VARCHAR(100),
    primary_branch_id   INT REFERENCES kpi_mart.dim_branch(branch_id)
);

CREATE TABLE kpi_mart.dim_vendor (
    vendor_id           INT PRIMARY KEY,
    vendor_name         VARCHAR(200),
    specialty           VARCHAR(50),
    branch_coverage     INT
);

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

-- Sales facts
CREATE TABLE kpi_mart.fact_leads (
    lead_id             INT PRIMARY KEY,
    lead_date           DATE,
    branch_id           INT REFERENCES kpi_mart.dim_branch(branch_id),
    lead_generator_id   INT REFERENCES kpi_mart.dim_employee(employee_id),
    customer_id         INT REFERENCES kpi_mart.dim_customer(customer_id),
    prospect_name       VARCHAR(200),
    source              VARCHAR(50),
    status              VARCHAR(20)
);

CREATE TABLE kpi_mart.fact_inquiries (
    inquiry_id          INT PRIMARY KEY,
    lead_id             INT,
    inquiry_date        DATE,
    customer_id         INT REFERENCES kpi_mart.dim_customer(customer_id),
    branch_id           INT REFERENCES kpi_mart.dim_branch(branch_id),
    salesperson_id      INT REFERENCES kpi_mart.dim_employee(employee_id),
    product_interest    VARCHAR(50),
    status              VARCHAR(20)
);

CREATE TABLE kpi_mart.fact_quotations (
    quotation_id        INT PRIMARY KEY,
    inquiry_id          INT,
    quotation_date      DATE,
    salesperson_id      INT REFERENCES kpi_mart.dim_employee(employee_id),
    branch_id           INT REFERENCES kpi_mart.dim_branch(branch_id),
    total_value_inr     INT,
    status              VARCHAR(20)
);

-- Grain: one won agreement (booking)
CREATE TABLE kpi_mart.fact_bookings (
    booking_id                  VARCHAR(30) PRIMARY KEY,
    agreement_date              DATE,
    quotation_id                INT,
    inquiry_id                  INT,
    lead_id                     INT,
    customer_id                 INT REFERENCES kpi_mart.dim_customer(customer_id),
    branch_id                   INT REFERENCES kpi_mart.dim_branch(branch_id),
    salesperson_id              INT REFERENCES kpi_mart.dim_employee(employee_id),
    sales_manager_id            INT REFERENCES kpi_mart.dim_employee(employee_id),
    number_of_units             INT,
    total_equipment_cost_inr    INT,
    total_agreement_value_inr   INT,
    status                      VARCHAR(20)
);

-- Grain: one unit (core grain for installation and service)
CREATE TABLE kpi_mart.fact_units (
    unit_id                     VARCHAR(40) PRIMARY KEY,
    booking_id                  VARCHAR(30) REFERENCES kpi_mart.fact_bookings(booking_id),
    unit_number                 INT,
    customer_id                 INT REFERENCES kpi_mart.dim_customer(customer_id),
    branch_id                   INT REFERENCES kpi_mart.dim_branch(branch_id),
    product_type                VARCHAR(20),  -- Passenger, Goods, Home
    capacity_kg                 INT,
    capacity_passengers         INT,
    speed_mps                   DECIMAL(4,2),
    floors_description          VARCHAR(30),
    no_of_stops                 INT,
    front_openings              INT,
    rear_openings               INT,
    door_opening_type           VARCHAR(20),  -- Center, Telescopic
    grouping                    VARCHAR(20),  -- Simplex, Duplex, Triplex
    door_type                   VARCHAR(40),
    material_finish             VARCHAR(30),
    license_scope               VARCHAR(30),
    equipment_cost_inr          INT,
    installation_status         VARCHAR(20),
    installation_start_date     DATE,
    installation_complete_date  DATE,
    installation_engineer_id    INT REFERENCES kpi_mart.dim_employee(employee_id)
);

-- Third-party installation POs (grain: one line item per unit)
CREATE TABLE kpi_mart.fact_installation_pos (
    po_id           INT PRIMARY KEY,
    unit_id         VARCHAR(40),
    booking_id      VARCHAR(30),
    branch_id       INT REFERENCES kpi_mart.dim_branch(branch_id),
    vendor_id       INT REFERENCES kpi_mart.dim_vendor(vendor_id),
    line_item       VARCHAR(80),  -- Erection & Installation, Scaffolding, Wiring, Misc
    amount_inr      INT,
    po_date         DATE,
    status          VARCHAR(20)
);

-- Service
CREATE TABLE kpi_mart.fact_warranty (
    unit_id                 VARCHAR(40) PRIMARY KEY,
    booking_id              VARCHAR(30),
    customer_id             INT,
    branch_id               INT,
    warranty_start_date     DATE,
    warranty_months         INT,
    warranty_end_date       DATE,
    status                  VARCHAR(20)
);

CREATE TABLE kpi_mart.fact_amc (
    amc_id                  INT PRIMARY KEY,
    unit_id                 VARCHAR(40),
    booking_id              VARCHAR(30),
    customer_id             INT REFERENCES kpi_mart.dim_customer(customer_id),
    branch_id               INT REFERENCES kpi_mart.dim_branch(branch_id),
    service_salesperson_id  INT REFERENCES kpi_mart.dim_employee(employee_id),
    amc_type                VARCHAR(30),  -- Comprehensive, Non-comprehensive
    start_date              DATE,
    end_date                DATE,
    annual_value_inr        INT,
    status                  VARCHAR(20),
    renewal_due_month       VARCHAR(7)
);

CREATE TABLE kpi_mart.fact_repair_orders (
    repair_order_id         INT PRIMARY KEY,
    unit_id                 VARCHAR(40),
    booking_id              VARCHAR(30),
    customer_id             INT REFERENCES kpi_mart.dim_customer(customer_id),
    branch_id               INT REFERENCES kpi_mart.dim_branch(branch_id),
    open_date               DATE,
    close_date              DATE,
    service_supervisor_id   INT REFERENCES kpi_mart.dim_employee(employee_id),
    technician_id           INT REFERENCES kpi_mart.dim_employee(employee_id),
    priority                VARCHAR(20),
    sla_hours               INT,
    resolution_hours        INT,
    status                  VARCHAR(20),
    is_under_warranty       BOOLEAN,
    is_under_amc            BOOLEAN,
    amc_type                VARCHAR(30),
    parts_cost_inr          INT,
    labor_cost_inr          INT,
    exceeded_sla            BOOLEAN,
    description             VARCHAR(200)
);

CREATE TABLE kpi_mart.fact_incentives (
    incentive_id            INT PRIMARY KEY,
    employee_id             INT REFERENCES kpi_mart.dim_employee(employee_id),
    branch_id               INT REFERENCES kpi_mart.dim_branch(branch_id),
    year                    INT,
    month                   INT,
    role                    VARCHAR(50),
    incentive_amount_inr    INT,
    basis                   VARCHAR(50)
);

-- Indexes
CREATE INDEX idx_units_booking ON kpi_mart.fact_units(booking_id);
CREATE INDEX idx_units_status ON kpi_mart.fact_units(installation_status);
CREATE INDEX idx_amc_end ON kpi_mart.fact_amc(end_date);
CREATE INDEX idx_ro_open ON kpi_mart.fact_repair_orders(open_date);
CREATE INDEX idx_ro_status ON kpi_mart.fact_repair_orders(status);
