PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS change_request (
    request_id TEXT PRIMARY KEY,
    entity_type TEXT NOT NULL,
    entity_id TEXT NOT NULL,
    change_type TEXT NOT NULL,
    payload_json TEXT,
    request_status TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    created_by TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS vendor_merge_event (
    merge_id TEXT PRIMARY KEY,
    survivor_vendor_id TEXT NOT NULL,
    merge_status TEXT NOT NULL DEFAULT 'completed',
    merge_reason TEXT,
    merge_method TEXT NOT NULL DEFAULT 'manual',
    confidence_score REAL,
    request_id TEXT,
    merged_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    merged_by TEXT NOT NULL,
    FOREIGN KEY (survivor_vendor_id) REFERENCES vendor(vendor_id),
    FOREIGN KEY (request_id) REFERENCES change_request(request_id)
);

CREATE TABLE IF NOT EXISTS vendor_merge_member (
    merge_member_id TEXT PRIMARY KEY,
    merge_id TEXT NOT NULL,
    vendor_id TEXT NOT NULL,
    member_role TEXT NOT NULL,
    source_system_code TEXT,
    source_vendor_key TEXT,
    pre_merge_display_name TEXT,
    active_flag INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (merge_id) REFERENCES vendor_merge_event(merge_id),
    FOREIGN KEY (vendor_id) REFERENCES vendor(vendor_id),
    UNIQUE (merge_id, vendor_id)
);

CREATE TABLE IF NOT EXISTS vendor_merge_snapshot (
    snapshot_id TEXT PRIMARY KEY,
    merge_id TEXT NOT NULL,
    vendor_id TEXT NOT NULL,
    snapshot_json TEXT NOT NULL,
    captured_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    captured_by TEXT,
    FOREIGN KEY (merge_id) REFERENCES vendor_merge_event(merge_id),
    FOREIGN KEY (vendor_id) REFERENCES vendor(vendor_id)
);

CREATE TABLE IF NOT EXISTS vendor_survivorship_decision (
    decision_id TEXT PRIMARY KEY,
    merge_id TEXT NOT NULL,
    field_name TEXT NOT NULL,
    chosen_vendor_id TEXT,
    chosen_value_text TEXT,
    decision_method TEXT NOT NULL DEFAULT 'manual',
    decision_note TEXT,
    decided_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    decided_by TEXT,
    FOREIGN KEY (merge_id) REFERENCES vendor_merge_event(merge_id),
    FOREIGN KEY (chosen_vendor_id) REFERENCES vendor(vendor_id)
);

CREATE TABLE IF NOT EXISTS change_event (
    event_id TEXT PRIMARY KEY,
    request_id TEXT,
    entity_type TEXT NOT NULL,
    entity_id TEXT NOT NULL,
    action TEXT NOT NULL,
    payload_json TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    created_by TEXT NOT NULL,
    FOREIGN KEY (request_id) REFERENCES change_request(request_id)
);

CREATE TABLE IF NOT EXISTS schema_version (
    version_num INTEGER PRIMARY KEY,
    description TEXT NOT NULL,
    applied_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    applied_by TEXT NOT NULL
);
