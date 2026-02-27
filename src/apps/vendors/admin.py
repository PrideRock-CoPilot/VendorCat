from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.db.models import Count
from .models import (
    Vendor,
    VendorContact,
    VendorIdentifier,
    OnboardingWorkflow,
    VendorNote,
    VendorWarning,
    VendorTicket,
    OfferingNote,
    OfferingTicket,
    ContractEvent,
    VendorDemo,
    DemoScore,
    DemoNote,
    VendorBusinessOwner,
    VendorOrgAssignment,
)


@admin.register(Vendor)
class VendorAdmin(admin.ModelAdmin):
    list_display = (
        "vendor_id",
        "display_name",
        "legal_name",
        "lifecycle_state_badge",
        "risk_tier_badge",
        "contact_count",
        "created_at",
    )
    list_filter = ("lifecycle_state", "risk_tier", "owner_org_id", "created_at")
    search_fields = ("vendor_id", "legal_name", "display_name")
    readonly_fields = ("created_at", "updated_at")
    fieldsets = (
        ("Basic Information", {
            "fields": ("vendor_id", "legal_name", "display_name")
        }),
        ("Organization & Status", {
            "fields": ("lifecycle_state", "risk_tier", "owner_org_id")
        }),
        ("Timestamps", {
            "fields": ("created_at", "updated_at"),
            "classes": ("collapse",)
        }),
    )
    ordering = ("-created_at",)

    def lifecycle_state_badge(self, obj):
        colors = {"active": "green", "inactive": "red", "pending": "orange"}
        color = colors.get(obj.lifecycle_state, "gray")
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 10px; '
            'border-radius: 3px;">{}</span>',
            color,
            obj.lifecycle_state.upper(),
        )
    lifecycle_state_badge.short_description = "Lifecycle State"

    def risk_tier_badge(self, obj):
        colors = {"low": "green", "medium": "orange", "high": "red", "critical": "darkred"}
        color = colors.get(obj.risk_tier, "gray")
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 10px; '
            'border-radius: 3px;">{}</span>',
            color,
            obj.risk_tier.upper(),
        )
    risk_tier_badge.short_description = "Risk Tier"

    def contact_count(self, obj):
        return obj.contacts.count()
    contact_count.short_description = "Contacts"


@admin.register(VendorContact)
class VendorContactAdmin(admin.ModelAdmin):
    list_display = (
        "full_name",
        "vendor",
        "contact_type",
        "email",
        "phone",
        "is_primary_badge",
        "is_active_badge",
    )
    list_filter = ("contact_type", "is_primary", "is_active", "vendor")
    search_fields = ("full_name", "email", "vendor__vendor_id")
    readonly_fields = ("created_at", "updated_at")
    fieldsets = (
        ("Contact Info", {
            "fields": ("vendor", "full_name", "email", "phone", "title")
        }),
        ("Type & Status", {
            "fields": ("contact_type", "is_primary", "is_active")
        }),
        ("Additional Info", {
            "fields": ("notes",),
            "classes": ("collapse",)
        }),
        ("Timestamps", {
            "fields": ("created_at", "updated_at"),
            "classes": ("collapse",)
        }),
    )

    def is_primary_badge(self, obj):
        return format_html(
            '<span style="color: {};">{}</span>',
            "green" if obj.is_primary else "gray",
            "★" if obj.is_primary else "○",
        )
    is_primary_badge.short_description = "Primary"

    def is_active_badge(self, obj):
        color = "green" if obj.is_active else "red"
        text = "Active" if obj.is_active else "Inactive"
        return format_html(
            '<span style="color: {};">{}</span>', color, text
        )
    is_active_badge.short_description = "Status"


@admin.register(VendorIdentifier)
class VendorIdentifierAdmin(admin.ModelAdmin):
    list_display = (
        "identifier_type",
        "identifier_value",
        "vendor",
        "country_code",
        "is_primary_badge",
        "is_verified_badge",
    )
    list_filter = ("identifier_type", "is_primary", "is_verified", "country_code")
    search_fields = ("identifier_value", "vendor__vendor_id")
    readonly_fields = ("created_at", "updated_at")
    fieldsets = (
        ("Identifier Info", {
            "fields": ("vendor", "identifier_type", "identifier_value", "country_code")
        }),
        ("Verification", {
            "fields": ("is_primary", "is_verified", "verified_at", "verified_by")
        }),
        ("Notes", {
            "fields": ("notes",),
            "classes": ("collapse",)
        }),
        ("Timestamps", {
            "fields": ("created_at", "updated_at"),
            "classes": ("collapse",)
        }),
    )

    def is_primary_badge(self, obj):
        return "★" if obj.is_primary else "○"
    is_primary_badge.short_description = "Primary"

    def is_verified_badge(self, obj):
        color = "green" if obj.is_verified else "red"
        text = "✓" if obj.is_verified else "✗"
        return format_html('<span style="color: {}; font-weight: bold;">{}</span>', color, text)
    is_verified_badge.short_description = "Verified"


@admin.register(OnboardingWorkflow)
class OnboardingWorkflowAdmin(admin.ModelAdmin):
    list_display = (
        "vendor",
        "current_state_badge",
        "initiated_by",
        "assigned_reviewer",
        "days_in_state",
        "initiated_at",
    )
    list_filter = ("current_state", "status_change_reason", "initiated_at")
    search_fields = ("vendor__vendor_id", "assigned_reviewer", "reviewed_by")
    readonly_fields = ("initiated_at", "updated_at", "last_state_change")
    fieldsets = (
        ("Vendor & State", {
            "fields": ("vendor", "current_state", "status_change_reason", "status_change_notes")
        }),
        ("Initiation", {
            "fields": ("initiated_by", "initiated_at")
        }),
        ("Review Assignment", {
            "fields": ("assigned_reviewer", "assigned_date", "reviewed_by", "review_completed_date"),
            "classes": ("collapse",)
        }),
        ("Timeline", {
            "fields": ("information_request_sent_at", "documents_received_at", "compliance_check_completed_at"),
            "classes": ("collapse",)
        }),
        ("Timestamps", {
            "fields": ("updated_at", "last_state_change"),
            "classes": ("collapse",)
        }),
    )

    def current_state_badge(self, obj):
        colors = {
            "draft": "#9d9d9d",
            "pending_information": "#ffa500",
            "under_review": "#0066cc",
            "compliance_check": "#ff6600",
            "approved": "#00cc66",
            "rejected": "#cc0000",
            "active": "#339933",
            "archived": "#666666",
        }
        color = colors.get(obj.current_state, "#999999")
        return format_html(
            '<span style="background-color: {}; color: white; padding: 4px 8px; '
            'border-radius: 4px; font-weight: bold;">{}</span>',
            color,
            obj.get_current_state_display(),
        )
    current_state_badge.short_description = "State"

    def days_in_state(self, obj):
        return obj.get_days_in_state()
    days_in_state.short_description = "Days in State"


class VendorContactInline(admin.TabularInline):
    model = VendorContact
    extra = 1
    fields = ("full_name", "contact_type", "email", "phone", "is_primary", "is_active")


class VendorIdentifierInline(admin.TabularInline):
    model = VendorIdentifier
    extra = 1
    fields = ("identifier_type", "identifier_value", "country_code", "is_primary", "is_verified")


class VendorNoteInline(admin.TabularInline):
    model = VendorNote
    extra = 0
    readonly_fields = ("created_by", "created_at")
    fields = ("note_type", "note_text", "created_by", "created_at")


@admin.register(VendorNote)
class VendorNoteAdmin(admin.ModelAdmin):
    list_display = ("vendor", "note_type", "note_text_preview", "created_by", "created_at")
    list_filter = ("note_type", "vendor", "created_at")
    search_fields = ("vendor__vendor_id", "note_text")
    readonly_fields = ("created_at", "updated_at")
    fieldsets = (
        ("Note Info", {
            "fields": ("vendor", "note_type", "note_text")
        }),
        ("Metadata", {
            "fields": ("created_by", "created_at", "updated_at"),
            "classes": ("collapse",)
        }),
    )

    def note_text_preview(self, obj):
        return obj.note_text[:50] + "..." if len(obj.note_text) > 50 else obj.note_text
    note_text_preview.short_description = "Note"


@admin.register(VendorWarning)
class VendorWarningAdmin(admin.ModelAdmin):
    list_display = (
        "title",
        "vendor",
        "severity_badge",
        "status_badge",
        "detected_at",
    )
    list_filter = ("severity", "status", "warning_category", "detected_at")
    search_fields = ("vendor__vendor_id", "title")
    readonly_fields = ("created_at", "detected_at")
    fieldsets = (
        ("Warning Info", {
            "fields": ("vendor", "title", "detail", "warning_category")
        }),
        ("Status", {
            "fields": ("severity", "status", "detected_at", "resolved_at")
        }),
        ("Metadata", {
            "fields": ("created_by", "created_at"),
            "classes": ("collapse",)
        }),
    )

    def severity_badge(self, obj):
        colors = {"info": "blue", "warning": "orange", "critical": "red"}
        color = colors.get(obj.severity, "gray")
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 8px; '
            'border-radius: 3px;">{}</span>',
            color,
            obj.get_severity_display(),
        )
    severity_badge.short_description = "Severity"

    def status_badge(self, obj):
        colors = {"active": "red", "acknowledged": "orange", "resolved": "green"}
        color = colors.get(obj.status, "gray")
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 8px; '
            'border-radius: 3px;">{}</span>',
            color,
            obj.get_status_display(),
        )
    status_badge.short_description = "Status"


@admin.register(VendorTicket)
class VendorTicketAdmin(admin.ModelAdmin):
    list_display = (
        "title",
        "vendor",
        "status_badge",
        "priority_badge",
        "opened_date",
    )
    list_filter = ("status", "priority", "vendor", "opened_date")
    search_fields = ("vendor__vendor_id", "title", "external_ticket_id")
    readonly_fields = ("created_at", "updated_at")
    fieldsets = (
        ("Ticket Info", {
            "fields": ("vendor", "title", "description")
        }),
        ("External Reference", {
            "fields": ("ticket_system", "external_ticket_id"),
            "classes": ("collapse",)
        }),
        ("Status", {
            "fields": ("status", "priority", "opened_date", "closed_date")
        }),
        ("Notes", {
            "fields": ("notes",),
            "classes": ("collapse",)
        }),
        ("Metadata", {
            "fields": ("created_by", "created_at", "updated_at"),
            "classes": ("collapse",)
        }),
    )

    def status_badge(self, obj):
        colors = {"open": "red", "in_progress": "orange", "closed": "green"}
        color = colors.get(obj.status, "gray")
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 8px; '
            'border-radius: 3px;">{}</span>',
            color,
            obj.get_status_display(),
        )
    status_badge.short_description = "Status"

    def priority_badge(self, obj):
        colors = {"low": "blue", "medium": "orange", "high": "red", "critical": "darkred"}
        color = colors.get(obj.priority, "gray")
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 8px; '
            'border-radius: 3px;">{}</span>',
            color,
            obj.get_priority_display(),
        )
    priority_badge.short_description = "Priority"


@admin.register(OfferingNote)
class OfferingNoteAdmin(admin.ModelAdmin):
    list_display = ("offering_id", "note_type", "note_text_preview", "created_by", "created_at")
    list_filter = ("note_type", "created_at")
    search_fields = ("offering_id", "note_text")
    readonly_fields = ("created_at",)

    def note_text_preview(self, obj):
        return obj.note_text[:50] + "..." if len(obj.note_text) > 50 else obj.note_text
    note_text_preview.short_description = "Note"


@admin.register(OfferingTicket)
class OfferingTicketAdmin(admin.ModelAdmin):
    list_display = ("title", "offering_id", "status_badge", "priority_badge", "opened_date")
    list_filter = ("status", "priority", "opened_date")
    search_fields = ("offering_id", "title", "external_ticket_id")
    readonly_fields = ("created_at",)

    def status_badge(self, obj):
        colors = {"open": "red", "in_progress": "orange", "closed": "green"}
        color = colors.get(obj.status, "gray")
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 8px; '
            'border-radius: 3px;">{}</span>',
            color,
            obj.get_status_display(),
        )
    status_badge.short_description = "Status"

    def priority_badge(self, obj):
        colors = {"low": "blue", "medium": "orange", "high": "red"}
        color = colors.get(obj.priority, "gray")
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 8px; '
            'border-radius: 3px;">{}</span>',
            color,
            obj.get_priority_display(),
        )
    priority_badge.short_description = "Priority"


@admin.register(ContractEvent)
class ContractEventAdmin(admin.ModelAdmin):
    list_display = ("contract_id", "event_type", "event_date", "actor_user_principal")
    list_filter = ("event_type", "event_date")
    search_fields = ("contract_id", "actor_user_principal")
    readonly_fields = ("created_at",)


class DemoScoreInline(admin.TabularInline):
    model = DemoScore
    extra = 1
    fields = ("score_category", "score_value", "weight", "comments")


class DemoNoteInline(admin.TabularInline):
    model = DemoNote
    extra = 0
    readonly_fields = ("created_by", "created_at")
    fields = ("note_type", "note_text", "created_by", "created_at")


@admin.register(VendorDemo)
class VendorDemoAdmin(admin.ModelAdmin):
    list_display = (
        "demo_id",
        "vendor",
        "offering_id",
        "overall_score",
        "selection_outcome_badge",
        "demo_date",
    )
    list_filter = ("selection_outcome", "demo_date", "vendor")
    search_fields = ("demo_id", "vendor__vendor_id", "offering_id")
    readonly_fields = ("created_at",)
    inlines = [DemoScoreInline, DemoNoteInline]
    fieldsets = (
        ("Demo Info", {
            "fields": ("vendor", "offering_id", "demo_id", "demo_date")
        }),
        ("Scoring", {
            "fields": ("overall_score", "selection_outcome")
        }),
        ("Attendees", {
            "fields": ("attendees_internal", "attendees_vendor"),
            "classes": ("collapse",)
        }),
        ("Notes", {
            "fields": ("notes",),
            "classes": ("collapse",)
        }),
        ("Metadata", {
            "fields": ("created_by", "created_at"),
            "classes": ("collapse",)
        }),
    )

    def selection_outcome_badge(self, obj):
        colors = {"selected": "green", "not_selected": "red", "pending": "orange"}
        color = colors.get(obj.selection_outcome, "gray")
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 8px; '
            'border-radius: 3px;">{}</span>',
            color,
            obj.get_selection_outcome_display(),
        )
    selection_outcome_badge.short_description = "Outcome"


@admin.register(DemoScore)
class DemoScoreAdmin(admin.ModelAdmin):
    list_display = ("demo", "score_category", "score_value", "weight")
    list_filter = ("score_category", "demo__demo_date")
    search_fields = ("demo__demo_id", "score_category")
    readonly_fields = ("created_at",)


@admin.register(DemoNote)
class DemoNoteAdmin(admin.ModelAdmin):
    list_display = ("demo", "note_type", "note_text_preview", "created_by", "created_at")
    list_filter = ("note_type", "demo__demo_date")
    search_fields = ("demo__demo_id", "note_text")
    readonly_fields = ("created_at",)

    def note_text_preview(self, obj):
        return obj.note_text[:50] + "..." if len(obj.note_text) > 50 else obj.note_text
    note_text_preview.short_description = "Note"


@admin.register(VendorBusinessOwner)
class VendorBusinessOwnerAdmin(admin.ModelAdmin):
    list_display = ("owner_user_principal", "vendor", "owner_department", "is_primary_badge", "assigned_date")
    list_filter = ("is_primary", "vendor", "assigned_date")
    search_fields = ("owner_user_principal", "vendor__vendor_id", "owner_name")
    readonly_fields = ("assigned_date",)

    def is_primary_badge(self, obj):
        return "★" if obj.is_primary else "○"
    is_primary_badge.short_description = "Primary"


@admin.register(VendorOrgAssignment)
class VendorOrgAssignmentAdmin(admin.ModelAdmin):
    list_display = ("vendor", "org_id", "org_name", "is_primary_badge", "assigned_date")
    list_filter = ("is_primary", "vendor", "assigned_date")
    search_fields = ("vendor__vendor_id", "org_id", "org_name")
    readonly_fields = ("assigned_date",)

    def is_primary_badge(self, obj):
        return "★" if obj.is_primary else "○"
    is_primary_badge.short_description = "Primary"
