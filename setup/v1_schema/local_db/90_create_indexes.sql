PRAGMA foreign_keys = ON;

CREATE INDEX IF NOT EXISTS idx_vendor_primary_lob_id ON vendor(primary_lob_id);
CREATE INDEX IF NOT EXISTS idx_vendor_identifier_vendor_id ON vendor_identifier(vendor_id, active_flag);
CREATE INDEX IF NOT EXISTS idx_vendor_identifier_source ON vendor_identifier(source_system_code, source_vendor_key);
CREATE INDEX IF NOT EXISTS idx_offering_vendor_id ON offering(vendor_id);
CREATE INDEX IF NOT EXISTS idx_offering_primary_lob_id ON offering(primary_lob_id);
CREATE INDEX IF NOT EXISTS idx_project_primary_lob_id ON project(primary_lob_id);

CREATE INDEX IF NOT EXISTS idx_vendor_lob_assignment_vendor ON vendor_lob_assignment(vendor_id, active_flag);
CREATE INDEX IF NOT EXISTS idx_vendor_lob_assignment_lob ON vendor_lob_assignment(lob_id, active_flag);
CREATE INDEX IF NOT EXISTS idx_offering_lob_assignment_offering ON offering_lob_assignment(offering_id, active_flag);
CREATE INDEX IF NOT EXISTS idx_offering_lob_assignment_lob ON offering_lob_assignment(lob_id, active_flag);

CREATE INDEX IF NOT EXISTS idx_vendor_owner_assignment_vendor ON vendor_owner_assignment(vendor_id, active_flag);
CREATE INDEX IF NOT EXISTS idx_offering_owner_assignment_offering ON offering_owner_assignment(offering_id, active_flag);
CREATE INDEX IF NOT EXISTS idx_project_owner_assignment_project ON project_owner_assignment(project_id, active_flag);

CREATE INDEX IF NOT EXISTS idx_vendor_contact_vendor ON vendor_contact(vendor_id, active_flag);
CREATE INDEX IF NOT EXISTS idx_offering_contact_offering ON offering_contact(offering_id, active_flag);

CREATE INDEX IF NOT EXISTS idx_change_request_entity ON change_request(entity_type, entity_id);
CREATE INDEX IF NOT EXISTS idx_change_event_entity ON change_event(entity_type, entity_id);
CREATE INDEX IF NOT EXISTS idx_vendor_merge_event_survivor ON vendor_merge_event(survivor_vendor_id, merged_at);
CREATE INDEX IF NOT EXISTS idx_vendor_merge_member_merge ON vendor_merge_member(merge_id, member_role);
CREATE INDEX IF NOT EXISTS idx_vendor_merge_member_vendor ON vendor_merge_member(vendor_id, merge_id);
CREATE INDEX IF NOT EXISTS idx_vendor_merge_snapshot_merge ON vendor_merge_snapshot(merge_id, captured_at);
CREATE INDEX IF NOT EXISTS idx_vendor_survivorship_decision_merge ON vendor_survivorship_decision(merge_id, field_name);

CREATE INDEX IF NOT EXISTS idx_app_user_directory_login ON app_user_directory(login_identifier, active_flag);
CREATE INDEX IF NOT EXISTS idx_app_user_settings_user_key ON app_user_settings(user_principal, setting_key);
CREATE INDEX IF NOT EXISTS idx_app_usage_log_user_ts ON app_usage_log(user_principal, event_ts);

CREATE INDEX IF NOT EXISTS idx_sec_user_role_map_user_active ON sec_user_role_map(user_principal, active_flag);
CREATE INDEX IF NOT EXISTS idx_sec_group_role_map_group_active ON sec_group_role_map(group_principal, active_flag);
CREATE INDEX IF NOT EXISTS idx_sec_role_permission_role_object ON sec_role_permission(role_code, object_name, action_code);
CREATE INDEX IF NOT EXISTS idx_sec_user_org_scope_user_active ON sec_user_org_scope(user_principal, active_flag);

CREATE INDEX IF NOT EXISTS idx_audit_entity_change_entity_ts ON audit_entity_change(entity_name, entity_id, event_ts);
CREATE INDEX IF NOT EXISTS idx_audit_workflow_event_wf_ts ON audit_workflow_event(workflow_type, workflow_id, event_ts);
CREATE INDEX IF NOT EXISTS idx_audit_access_event_actor_ts ON audit_access_event(actor_user_principal, event_ts);

CREATE INDEX IF NOT EXISTS idx_vendor_help_article_slug ON vendor_help_article(slug);
CREATE INDEX IF NOT EXISTS idx_vendor_help_feedback_slug_ts ON vendor_help_feedback(article_slug, created_at);
CREATE INDEX IF NOT EXISTS idx_vendor_help_issue_slug_ts ON vendor_help_issue(article_slug, created_at);

CREATE INDEX IF NOT EXISTS idx_src_peoplesoft_batch_record ON src_peoplesoft_vendor_raw(batch_id, source_record_id);
CREATE INDEX IF NOT EXISTS idx_src_zycus_batch_record ON src_zycus_vendor_raw(batch_id, source_record_id);
CREATE INDEX IF NOT EXISTS idx_src_spreadsheet_batch_record ON src_spreadsheet_vendor_raw(batch_id, source_record_id);

CREATE INDEX IF NOT EXISTS idx_core_vendor_lifecycle ON core_vendor(lifecycle_state, updated_at);
CREATE INDEX IF NOT EXISTS idx_core_vendor_owner_org ON core_vendor(owner_org_id, lifecycle_state);
CREATE INDEX IF NOT EXISTS idx_core_vendor_offering_vendor ON core_vendor_offering(vendor_id, lifecycle_state);
CREATE INDEX IF NOT EXISTS idx_core_contract_vendor_status ON core_contract(vendor_id, contract_status);
CREATE INDEX IF NOT EXISTS idx_core_contract_offering ON core_contract(offering_id, contract_status);
CREATE INDEX IF NOT EXISTS idx_core_vendor_demo_vendor_date ON core_vendor_demo(vendor_id, demo_date);

CREATE INDEX IF NOT EXISTS idx_hist_vendor_vendor_current ON hist_vendor(vendor_id, is_current, version_no);
CREATE INDEX IF NOT EXISTS idx_hist_vendor_offering_current ON hist_vendor_offering(offering_id, is_current, version_no);
CREATE INDEX IF NOT EXISTS idx_hist_contract_current ON hist_contract(contract_id, is_current, version_no);

CREATE INDEX IF NOT EXISTS idx_app_project_vendor_status ON app_project(vendor_id, status, active_flag);
CREATE INDEX IF NOT EXISTS idx_app_project_vendor_map_project ON app_project_vendor_map(project_id, active_flag);
CREATE INDEX IF NOT EXISTS idx_app_project_vendor_map_vendor ON app_project_vendor_map(vendor_id, active_flag);
CREATE INDEX IF NOT EXISTS idx_app_project_offering_map_project ON app_project_offering_map(project_id, active_flag);
CREATE INDEX IF NOT EXISTS idx_app_project_offering_map_offering ON app_project_offering_map(offering_id, active_flag);
CREATE INDEX IF NOT EXISTS idx_app_project_demo_project ON app_project_demo(project_id, active_flag);
CREATE INDEX IF NOT EXISTS idx_app_project_note_project ON app_project_note(project_id, active_flag);

CREATE INDEX IF NOT EXISTS idx_app_document_link_entity ON app_document_link(entity_type, entity_id, active_flag);
CREATE INDEX IF NOT EXISTS idx_app_vendor_change_request_vendor ON app_vendor_change_request(vendor_id, status, submitted_at);
CREATE INDEX IF NOT EXISTS idx_app_offering_profile_vendor ON app_offering_profile(vendor_id);
CREATE INDEX IF NOT EXISTS idx_app_offering_ticket_offering ON app_offering_ticket(offering_id, status, active_flag);
CREATE INDEX IF NOT EXISTS idx_app_offering_invoice_offering ON app_offering_invoice(offering_id, invoice_date, active_flag);
CREATE INDEX IF NOT EXISTS idx_app_offering_data_flow_offering ON app_offering_data_flow(offering_id, direction, active_flag);
