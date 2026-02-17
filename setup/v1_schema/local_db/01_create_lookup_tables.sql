PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS lkp_line_of_business (
    lob_id TEXT PRIMARY KEY,
    lob_code TEXT NOT NULL UNIQUE,
    lob_name TEXT NOT NULL,
    active_flag INTEGER NOT NULL DEFAULT 1,
    sort_order INTEGER NOT NULL DEFAULT 100,
    effective_from TEXT,
    effective_to TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS lkp_service_type (
    service_type_id TEXT PRIMARY KEY,
    service_type_code TEXT NOT NULL UNIQUE,
    service_type_name TEXT NOT NULL,
    active_flag INTEGER NOT NULL DEFAULT 1,
    sort_order INTEGER NOT NULL DEFAULT 100,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS lkp_owner_role (
    owner_role_id TEXT PRIMARY KEY,
    owner_role_code TEXT NOT NULL UNIQUE,
    owner_role_name TEXT NOT NULL,
    active_flag INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS lkp_contact_type (
    contact_type_id TEXT PRIMARY KEY,
    contact_type_code TEXT NOT NULL UNIQUE,
    contact_type_name TEXT NOT NULL,
    active_flag INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS lkp_lifecycle_state (
    lifecycle_state_id TEXT PRIMARY KEY,
    lifecycle_state_code TEXT NOT NULL UNIQUE,
    lifecycle_state_name TEXT NOT NULL,
    active_flag INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS lkp_risk_tier (
    risk_tier_id TEXT PRIMARY KEY,
    risk_tier_code TEXT NOT NULL UNIQUE,
    risk_tier_name TEXT NOT NULL,
    active_flag INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
