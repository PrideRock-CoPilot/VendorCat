from __future__ import annotations

from django.db import models


class UserDirectory(models.Model):
    user_principal = models.CharField(max_length=255, unique=True)
    display_name = models.CharField(max_length=255)
    email = models.CharField(max_length=255, blank=True, default="")
    active_flag = models.BooleanField(default=True)
    last_seen_at = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


class AccessRequest(models.Model):
    requested_by_principal = models.CharField(max_length=255)
    requested_role = models.CharField(max_length=128)
    justification = models.TextField(default="")
    status = models.CharField(max_length=32, default="pending")
    reviewed_by_principal = models.CharField(max_length=255, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


class TermsAcceptance(models.Model):
    user_principal = models.CharField(max_length=255)
    terms_version = models.CharField(max_length=64)
    ip_address = models.CharField(max_length=128, blank=True, default="")
    accepted_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["user_principal", "terms_version"],
                name="uq_terms_acceptance_principal_version",
            )
        ]


class RoleAssignment(models.Model):
    user_principal = models.CharField(max_length=255)
    role = models.CharField(max_length=128)
    granted_by_principal = models.CharField(max_length=255, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["user_principal", "role"],
                name="uq_role_assignment_principal_role",
            )
        ]


class GroupRoleAssignment(models.Model):
    group_principal = models.CharField(max_length=255)
    role = models.CharField(max_length=128)
    granted_by_principal = models.CharField(max_length=255, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["group_principal", "role"],
                name="uq_group_role_assignment_group_role",
            )
        ]


class ScopeGrant(models.Model):
    user_principal = models.CharField(max_length=255)
    org_id = models.CharField(max_length=128)
    scope_level = models.CharField(max_length=64)
    granted_by_principal = models.CharField(max_length=255, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["user_principal", "org_id", "scope_level"],
                name="uq_scope_grant_principal_org_scope",
            )
        ]
