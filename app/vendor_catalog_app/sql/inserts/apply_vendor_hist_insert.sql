INSERT INTO {hist_vendor}
  (vendor_hist_id, vendor_id, version_no, valid_from_ts, valid_to_ts, is_current, snapshot_json, changed_by, change_reason)
VALUES
  (%s, %s, %s, %s, %s, %s, %s, %s, %s)
