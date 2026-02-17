PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS vendor_lob_assignment (
    assignment_id TEXT PRIMARY KEY,
    vendor_id TEXT NOT NULL,
    lob_id TEXT NOT NULL,
    is_primary INTEGER NOT NULL DEFAULT 0,
    active_flag INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    ended_at TEXT,
    FOREIGN KEY (vendor_id) REFERENCES vendor(vendor_id),
    FOREIGN KEY (lob_id) REFERENCES lkp_line_of_business(lob_id)
);

CREATE TABLE IF NOT EXISTS offering_lob_assignment (
    assignment_id TEXT PRIMARY KEY,
    offering_id TEXT NOT NULL,
    lob_id TEXT NOT NULL,
    is_primary INTEGER NOT NULL DEFAULT 0,
    active_flag INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    ended_at TEXT,
    FOREIGN KEY (offering_id) REFERENCES offering(offering_id),
    FOREIGN KEY (lob_id) REFERENCES lkp_line_of_business(lob_id)
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
