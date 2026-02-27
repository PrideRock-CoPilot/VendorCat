PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS vendor_business_unit_assignment (
    assignment_id TEXT PRIMARY KEY,
    vendor_id TEXT NOT NULL,
    business_unit_id TEXT NOT NULL,
    source_system TEXT,
    source_key TEXT,
    effective_start_at TEXT,
    effective_end_at TEXT,
    is_primary INTEGER NOT NULL DEFAULT 0,
    active_flag INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    created_by TEXT,
    updated_at TEXT,
    updated_by TEXT,
    FOREIGN KEY (vendor_id) REFERENCES vendor(vendor_id),
    FOREIGN KEY (business_unit_id) REFERENCES lkp_business_unit(business_unit_id),
    UNIQUE (vendor_id, business_unit_id, active_flag)
);

CREATE TABLE IF NOT EXISTS offering_business_unit_assignment (
    assignment_id TEXT PRIMARY KEY,
    offering_id TEXT NOT NULL,
    business_unit_id TEXT NOT NULL,
    source_system TEXT,
    source_key TEXT,
    effective_start_at TEXT,
    effective_end_at TEXT,
    is_primary INTEGER NOT NULL DEFAULT 0,
    active_flag INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    created_by TEXT,
    updated_at TEXT,
    updated_by TEXT,
    FOREIGN KEY (offering_id) REFERENCES offering(offering_id),
    FOREIGN KEY (business_unit_id) REFERENCES lkp_business_unit(business_unit_id),
    UNIQUE (offering_id, business_unit_id, active_flag)
);

CREATE TABLE IF NOT EXISTS vendor_owner_assignment (
    assignment_id TEXT PRIMARY KEY,
    vendor_id TEXT NOT NULL,
    owner_role_id TEXT NOT NULL,
    user_principal TEXT NOT NULL,
    active_flag INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    ended_at TEXT,
    FOREIGN KEY (vendor_id) REFERENCES vendor(vendor_id),
    FOREIGN KEY (owner_role_id) REFERENCES lkp_owner_role(owner_role_id)
);

CREATE TABLE IF NOT EXISTS offering_owner_assignment (
    assignment_id TEXT PRIMARY KEY,
    offering_id TEXT NOT NULL,
    owner_role_id TEXT NOT NULL,
    user_principal TEXT NOT NULL,
    active_flag INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    ended_at TEXT,
    FOREIGN KEY (offering_id) REFERENCES offering(offering_id),
    FOREIGN KEY (owner_role_id) REFERENCES lkp_owner_role(owner_role_id)
);

CREATE TABLE IF NOT EXISTS project_owner_assignment (
    assignment_id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL,
    owner_role_id TEXT NOT NULL,
    user_principal TEXT NOT NULL,
    active_flag INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    ended_at TEXT,
    FOREIGN KEY (project_id) REFERENCES project(project_id),
    FOREIGN KEY (owner_role_id) REFERENCES lkp_owner_role(owner_role_id)
);

CREATE TABLE IF NOT EXISTS vendor_contact (
    vendor_contact_id TEXT PRIMARY KEY,
    vendor_id TEXT NOT NULL,
    contact_type_id TEXT NOT NULL,
    full_name TEXT,
    email TEXT,
    phone TEXT,
    active_flag INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    ended_at TEXT,
    FOREIGN KEY (vendor_id) REFERENCES vendor(vendor_id),
    FOREIGN KEY (contact_type_id) REFERENCES lkp_contact_type(contact_type_id)
);

CREATE TABLE IF NOT EXISTS offering_contact (
    offering_contact_id TEXT PRIMARY KEY,
    offering_id TEXT NOT NULL,
    contact_type_id TEXT NOT NULL,
    full_name TEXT,
    email TEXT,
    phone TEXT,
    active_flag INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    ended_at TEXT,
    FOREIGN KEY (offering_id) REFERENCES offering(offering_id),
    FOREIGN KEY (contact_type_id) REFERENCES lkp_contact_type(contact_type_id)
);
