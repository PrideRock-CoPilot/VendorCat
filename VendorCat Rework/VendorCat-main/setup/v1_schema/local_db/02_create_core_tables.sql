PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS vendor (
    vendor_id TEXT PRIMARY KEY,
    legal_name TEXT NOT NULL,
    display_name TEXT NOT NULL,
    lifecycle_state_id TEXT NOT NULL,
    risk_tier_id TEXT NOT NULL,
    primary_business_unit_id TEXT,
    primary_owner_organization_id TEXT,
    vendor_category_id TEXT,
    compliance_category_id TEXT,
    gl_category_id TEXT,
    delegated_vendor_flag INTEGER NOT NULL DEFAULT 0,
    health_care_vendor_flag INTEGER NOT NULL DEFAULT 0,
    source_system TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_by TEXT,
    FOREIGN KEY (lifecycle_state_id) REFERENCES lkp_lifecycle_state(lifecycle_state_id),
    FOREIGN KEY (risk_tier_id) REFERENCES lkp_risk_tier(risk_tier_id),
    FOREIGN KEY (primary_business_unit_id) REFERENCES lkp_business_unit(business_unit_id),
    FOREIGN KEY (primary_owner_organization_id) REFERENCES lkp_owner_organization(owner_organization_id),
    FOREIGN KEY (vendor_category_id) REFERENCES lkp_vendor_category(vendor_category_id),
    FOREIGN KEY (compliance_category_id) REFERENCES lkp_compliance_category(compliance_category_id),
    FOREIGN KEY (gl_category_id) REFERENCES lkp_gl_category(gl_category_id)
);

CREATE TABLE IF NOT EXISTS offering (
    offering_id TEXT PRIMARY KEY,
    vendor_id TEXT NOT NULL,
    offering_name TEXT NOT NULL,
    lifecycle_state_id TEXT NOT NULL,
    primary_business_unit_id TEXT,
    primary_service_type_id TEXT,
    criticality_tier TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_by TEXT,
    FOREIGN KEY (vendor_id) REFERENCES vendor(vendor_id),
    FOREIGN KEY (lifecycle_state_id) REFERENCES lkp_lifecycle_state(lifecycle_state_id),
    FOREIGN KEY (primary_business_unit_id) REFERENCES lkp_business_unit(business_unit_id),
    FOREIGN KEY (primary_service_type_id) REFERENCES lkp_service_type(service_type_id)
);

CREATE TABLE IF NOT EXISTS contract (
    contract_id TEXT PRIMARY KEY,
    vendor_id TEXT NOT NULL,
    offering_id TEXT,
    contract_number TEXT,
    contract_status TEXT NOT NULL,
    start_date TEXT,
    end_date TEXT,
    cancelled_flag INTEGER NOT NULL DEFAULT 0,
    annual_value REAL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_by TEXT,
    FOREIGN KEY (vendor_id) REFERENCES vendor(vendor_id),
    FOREIGN KEY (offering_id) REFERENCES offering(offering_id)
);

CREATE TABLE IF NOT EXISTS contract_event (
    contract_event_id TEXT PRIMARY KEY,
    contract_id TEXT NOT NULL,
    event_type TEXT NOT NULL,
    event_ts TEXT NOT NULL,
    reason_code TEXT,
    notes TEXT,
    actor_user_principal TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (contract_id) REFERENCES contract(contract_id)
);

CREATE TABLE IF NOT EXISTS vendor_demo (
    demo_id TEXT PRIMARY KEY,
    vendor_id TEXT NOT NULL,
    offering_id TEXT,
    demo_date TEXT NOT NULL,
    overall_score REAL,
    selection_outcome TEXT NOT NULL,
    non_selection_reason_code TEXT,
    notes TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_by TEXT,
    FOREIGN KEY (vendor_id) REFERENCES vendor(vendor_id),
    FOREIGN KEY (offering_id) REFERENCES offering(offering_id)
);

CREATE TABLE IF NOT EXISTS vendor_demo_score (
    demo_score_id TEXT PRIMARY KEY,
    demo_id TEXT NOT NULL,
    score_category TEXT NOT NULL,
    score_value REAL NOT NULL,
    weight REAL,
    comments TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (demo_id) REFERENCES vendor_demo(demo_id)
);

CREATE TABLE IF NOT EXISTS vendor_demo_note (
    demo_note_id TEXT PRIMARY KEY,
    demo_id TEXT NOT NULL,
    note_type TEXT NOT NULL,
    note_text TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    created_by TEXT,
    FOREIGN KEY (demo_id) REFERENCES vendor_demo(demo_id)
);

CREATE TABLE IF NOT EXISTS vendor_identifier (
    vendor_identifier_id TEXT PRIMARY KEY,
    vendor_id TEXT NOT NULL,
    source_system_code TEXT NOT NULL,
    source_vendor_key TEXT NOT NULL,
    identifier_type TEXT NOT NULL DEFAULT 'vendor_key',
    is_primary_source INTEGER NOT NULL DEFAULT 0,
    verification_status TEXT NOT NULL DEFAULT 'pending',
    active_flag INTEGER NOT NULL DEFAULT 1,
    first_seen_at TEXT,
    last_seen_at TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (vendor_id) REFERENCES vendor(vendor_id),
    UNIQUE (source_system_code, source_vendor_key)
);

CREATE TABLE IF NOT EXISTS project (
    project_id TEXT PRIMARY KEY,
    project_name TEXT NOT NULL,
    lifecycle_state_id TEXT NOT NULL,
    primary_business_unit_id TEXT,
    target_date TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_by TEXT,
    FOREIGN KEY (lifecycle_state_id) REFERENCES lkp_lifecycle_state(lifecycle_state_id),
    FOREIGN KEY (primary_business_unit_id) REFERENCES lkp_business_unit(business_unit_id)
);

CREATE TABLE IF NOT EXISTS project_offering_map (
    project_offering_map_id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL,
    offering_id TEXT NOT NULL,
    active_flag INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    ended_at TEXT,
    FOREIGN KEY (project_id) REFERENCES project(project_id),
    FOREIGN KEY (offering_id) REFERENCES offering(offering_id)
);
