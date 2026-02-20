# Admin Portal UX

## Goals
- Keep admin operations usable at 100 to 1000+ users.
- Separate browsing, searching, and write actions into focused pages.
- Keep role + scope governance understandable with plain language.

## Navigation
- `/admin/access`: Access landing for Users, Groups, and recent grants.
- `/admin/users/{principal}`: User access detail with role grants and Line of Business access.
- `/admin/groups/{principal}`: Group role grants detail.
- `/admin/roles`: Role catalog with pagination and role editor.
- `/admin/roles/{role_code}`: Role detail and grant summaries.
- `/admin/ownership`: Ownership reassignment workflow.
- `/admin/defaults`: Defaults catalog with paging and filters.

Legacy `/admin?section=...` links are still supported and route to equivalent page content.

## Search-first design
- User operations rely on server-side typeahead via `/admin/users/search`.
- Group operations rely on server-side typeahead via `/admin/groups/search`.
- All grant lists support filter query + page size + page navigation.

## Line of Business scope model
The UI uses "Line of Business Access" terminology:
- `None`
- `View`
- `Edit`
- `Full`

This represents scope-level permissions for an org/LOB and combines with role grants for effective access.

## Scalability controls
- Grant queries are paginated with `LIMIT/OFFSET`.
- Hard-coded list caps are removed from list grant SQL.
- Summary pages load only one page per grant table and expose total counts.
