from __future__ import annotations

from django.urls import path

from apps.admin_portal import views

urlpatterns = [
    path("", views.index, name="admin-home"),
    path("roles/assign", views.assign_user_role_endpoint, name="admin-assign-user-role"),
    path("roles/revoke", views.revoke_user_role_endpoint, name="admin-revoke-user-role"),
    path("groups/assign", views.assign_group_role_endpoint, name="admin-assign-group-role"),
    path("groups/revoke", views.revoke_group_role_endpoint, name="admin-revoke-group-role"),
    path("scopes/grant", views.grant_scope_endpoint, name="admin-grant-scope"),
    path("scopes/revoke", views.revoke_scope_endpoint, name="admin-revoke-scope"),
    path("api/assignments", views.list_admin_assignments_endpoint, name="admin-list-assignments"),
]
