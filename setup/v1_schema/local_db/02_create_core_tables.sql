PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS vendor (
    vendor_id TEXT PRIMARY KEY,
    legal_name TEXT NOT NULL,
    display_name TEXT NOT NULL,
    lifecycle_state_id TEXT NOT NULL,
    risk_tier_id TEXT NOT NULL,
    primary_lob_id TEXT,
    source_system TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_by TEXT,
    FOREIGN KEY (lifecycle_state_id) REFERENCES lkp_lifecycle_state(lifecycle_state_id),
    FOREIGN KEY (risk_tier_id) REFERENCES lkp_risk_tier(risk_tier_id),
    FOREIGN KEY (primary_lob_id) REFERENCES lkp_line_of_business(lob_id)
);

CREATE TABLE IF NOT EXISTS offering (
    offering_id TEXT PRIMARY KEY,
    vendor_id TEXT NOT NULL,
    offering_name TEXT NOT NULL,
    lifecycle_state_id TEXT NOT NULL,
    primary_lob_id TEXT,
    primary_service_type_id TEXT,
    criticality_tier TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_by TEXT,
    FOREIGN KEY (vendor_id) REFERENCES vendor(vendor_id),
    FOREIGN KEY (lifecycle_state_id) REFERENCES lkp_lifecycle_state(lifecycle_state_id),
    FOREIGN KEY (primary_lob_id) REFERENCES lkp_line_of_business(lob_id),
    FOREIGN KEY (primary_service_type_id) REFERENCES lkp_service_type(service_type_id)
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
    primary_lob_id TEXT,
    target_date TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_by TEXT,
    FOREIGN KEY (lifecycle_state_id) REFERENCES lkp_lifecycle_state(lifecycle_state_id),
    FOREIGN KEY (primary_lob_id) REFERENCES lkp_line_of_business(lob_id)
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
