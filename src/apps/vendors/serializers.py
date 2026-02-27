"""Serializers for all Vendor Catalog models."""

from rest_framework import serializers
from django.utils import timezone
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


class VendorContactSerializer(serializers.ModelSerializer):
    """Serializer for VendorContact."""

    class Meta:
        model = VendorContact
        fields = [
            "id",
            "vendor",
            "full_name",
            "contact_type",
            "email",
            "phone",
            "title",
            "is_primary",
            "is_active",
            "notes",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

    def validate_email(self, value):
        """Ensure email is valid or empty."""
        if value:
            # Basic validation - more sophisticated validation happens at model level
            if "@" not in value:
                raise serializers.ValidationError("Invalid email format")
        return value


class VendorIdentifierSerializer(serializers.ModelSerializer):
    """Serializer for VendorIdentifier."""

    class Meta:
        model = VendorIdentifier
        fields = [
            "id",
            "vendor",
            "identifier_type",
            "identifier_value",
            "country_code",
            "is_primary",
            "is_verified",
            "verified_at",
            "verified_by",
            "notes",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

    def validate(self, data):
        """Validate identifier data."""
        vendor = data.get("vendor")
        identifier_type = data.get("identifier_type")
        identifier_value = data.get("identifier_value")

        if vendor and identifier_type and identifier_value:
            # Check for duplicate identifier (excluding self in updates)
            existing = VendorIdentifier.objects.filter(
                vendor=vendor,
                identifier_type=identifier_type,
                identifier_value=identifier_value,
            )
            if self.instance:
                existing = existing.exclude(id=self.instance.id)
            if existing.exists():
                raise serializers.ValidationError(
                    f"This {identifier_type} already exists for this vendor"
                )
        return data


class VendorDetailSerializer(serializers.ModelSerializer):
    """Extended Vendor serializer with nested contacts and identifiers."""

    contacts = VendorContactSerializer(many=True, read_only=True)
    identifiers = VendorIdentifierSerializer(many=True, read_only=True)
    primary_contact = serializers.SerializerMethodField()
    primary_identifier = serializers.SerializerMethodField()

    class Meta:
        model = Vendor
        fields = [
            "id",
            "vendor_id",
            "legal_name",
            "display_name",
            "lifecycle_state",
            "owner_org_id",
            "risk_tier",
            "contacts",
            "identifiers",
            "primary_contact",
            "primary_identifier",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

    def get_primary_contact(self, obj):
        """Get primary contact for vendor."""
        primary_contact = obj.contacts.filter(
            is_primary=True, is_active=True
        ).first()
        if primary_contact:
            return VendorContactSerializer(primary_contact).data
        return None

    def get_primary_identifier(self, obj):
        """Get primary identifier for vendor."""
        primary_identifier = obj.identifiers.filter(is_primary=True).first()
        if primary_identifier:
            return VendorIdentifierSerializer(primary_identifier).data
        return None


class VendorListSerializer(serializers.ModelSerializer):
    """Serializer for Vendor list view (lighter weight)."""

    contact_count = serializers.SerializerMethodField()
    identifier_count = serializers.SerializerMethodField()

    class Meta:
        model = Vendor
        fields = [
            "id",
            "vendor_id",
            "legal_name",
            "display_name",
            "lifecycle_state",
            "owner_org_id",
            "risk_tier",
            "contact_count",
            "identifier_count",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

    def get_contact_count(self, obj):
        """Count active contacts."""
        return obj.contacts.filter(is_active=True).count()

    def get_identifier_count(self, obj):
        """Count identifiers."""
        return obj.identifiers.count()


class OnboardingWorkflowSerializer(serializers.ModelSerializer):
    """Serializer for OnboardingWorkflow state machine."""

    current_state_display = serializers.CharField(
        source="get_current_state_display",
        read_only=True,
        help_text="Human-readable current state"
    )
    next_states = serializers.SerializerMethodField(
        read_only=True,
        help_text="Available state transitions from current state"
    )
    days_in_state = serializers.SerializerMethodField(
        read_only=True,
        help_text="Number of days in current state"
    )
    total_onboarding_days = serializers.SerializerMethodField(
        read_only=True,
        help_text="Total days from initiation to now"
    )

    class Meta:
        model = __import__('apps.vendors.models', fromlist=['OnboardingWorkflow']).OnboardingWorkflow
        fields = [
            "id",
            "vendor",
            "current_state",
            "current_state_display",
            "next_states",
            "initiated_by",
            "initiated_at",
            "updated_at",
            "last_state_change",
            "days_in_state",
            "total_onboarding_days",
            "status_change_reason",
            "status_change_notes",
            "assigned_reviewer",
            "assigned_date",
            "review_completed_date",
            "reviewed_by",
            "information_request_sent_at",
            "documents_received_at",
            "compliance_check_completed_at",
        ]
        read_only_fields = [
            "id",
            "initiated_at",
            "updated_at",
            "last_state_change",
            "current_state_display",
            "next_states",
            "days_in_state",
            "total_onboarding_days",
        ]

    def get_next_states(self, obj):
        """Get available state transitions."""
        return obj.get_next_states()

    def get_days_in_state(self, obj):
        """Get days in current state."""
        return obj.get_days_in_state()

    def get_total_onboarding_days(self, obj):
        """Get total onboarding duration."""
        return obj.get_total_onboarding_days()


class OnboardingWorkflowStateChangeSerializer(serializers.Serializer):
    """Serializer for state change operations."""

    action = serializers.CharField(
        max_length=50,
        required=True,
        help_text="Name of the state transition method to call"
    )
    reviewer = serializers.CharField(
        max_length=255,
        required=False,
        allow_blank=True,
        help_text="Reviewer email or name (for approval/rejection)"
    )
    reason = serializers.CharField(
        max_length=64,
        required=False,
        allow_blank=True,
        help_text="Reason for state change"
    )
    notes = serializers.CharField(
        required=False,
        allow_blank=True,
        help_text="Additional notes for state change"
    )

    def validate_action(self, value):
        """Validate action is a valid transition method."""
        from .models import OnboardingWorkflow

        valid_actions = [
            "request_information",
            "mark_information_received",
            "assign_for_review",
            "approve_vendor",
            "reject_vendor",
            "activate_vendor",
            "archive_workflow",
            "reopen_draft",
        ]

        if value not in valid_actions:
            raise serializers.ValidationError(
                f"Invalid action. Must be one of: {', '.join(valid_actions)}"
            )

        return value

# New Serializers for Additional Models

class VendorNoteSerializer(serializers.ModelSerializer):
    class Meta:
        model = VendorNote
        fields = [
            "id",
            "vendor",
            "note_type",
            "note_text",
            "created_by",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["created_at", "updated_at"]

    def validate_note_text(self, value):
        if not value or len(value.strip()) == 0:
            raise serializers.ValidationError("Note text cannot be empty.")
        return value.strip()


class VendorWarningSerializer(serializers.ModelSerializer):
    class Meta:
        model = VendorWarning
        fields = [
            "id",
            "vendor",
            "warning_category",
            "severity",
            "status",
            "title",
            "detail",
            "detected_at",
            "resolved_at",
            "created_by",
            "created_at",
        ]
        read_only_fields = ["created_at"]

    def validate(self, data):
        if data.get("status") == "resolved" and not data.get("resolved_at"):
            raise serializers.ValidationError(
                "resolved_at is required when status is 'resolved'."
            )
        return data


class VendorTicketSerializer(serializers.ModelSerializer):
    class Meta:
        model = VendorTicket
        fields = [
            "id",
            "vendor",
            "ticket_system",
            "external_ticket_id",
            "title",
            "description",
            "status",
            "priority",
            "opened_date",
            "closed_date",
            "notes",
            "created_by",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["created_at", "updated_at"]

    def validate(self, data):
        if data.get("status") == "closed" and not data.get("closed_date"):
            raise serializers.ValidationError(
                "closed_date is required when status is 'closed'."
            )
        return data


class OfferingNoteSerializer(serializers.ModelSerializer):
    class Meta:
        model = OfferingNote
        fields = [
            "id",
            "offering_id",
            "note_type",
            "note_text",
            "created_by",
            "created_at",
        ]
        read_only_fields = ["created_at"]

    def validate_note_text(self, value):
        if not value or len(value.strip()) == 0:
            raise serializers.ValidationError("Note text cannot be empty.")
        return value.strip()


class OfferingTicketSerializer(serializers.ModelSerializer):
    class Meta:
        model = OfferingTicket
        fields = [
            "id",
            "offering_id",
            "ticket_system",
            "external_ticket_id",
            "title",
            "status",
            "priority",
            "opened_date",
            "closed_date",
            "notes",
            "created_by",
            "created_at",
        ]
        read_only_fields = ["created_at"]

    def validate(self, data):
        if data.get("status") == "closed" and not data.get("closed_date"):
            raise serializers.ValidationError(
                "closed_date is required when status is 'closed'."
            )
        return data


class ContractEventSerializer(serializers.ModelSerializer):
    class Meta:
        model = ContractEvent
        fields = [
            "id",
            "contract_id",
            "event_type",
            "event_date",
            "notes",
            "actor_user_principal",
            "created_at",
        ]
        read_only_fields = ["created_at"]


class DemoScoreSerializer(serializers.ModelSerializer):
    class Meta:
        model = DemoScore
        fields = [
            "id",
            "demo",
            "score_category",
            "score_value",
            "weight",
            "comments",
            "created_at",
        ]
        read_only_fields = ["created_at"]

    def validate_score_value(self, value):
        if value < 0 or value > 100:
            raise serializers.ValidationError("Score must be between 0 and 100.")
        return value

    def validate_weight(self, value):
        if value and (value < 0 or value > 1):
            raise serializers.ValidationError("Weight must be between 0 and 1.")
        return value


class DemoNoteSerializer(serializers.ModelSerializer):
    class Meta:
        model = DemoNote
        fields = [
            "id",
            "demo",
            "note_type",
            "note_text",
            "created_by",
            "created_at",
        ]
        read_only_fields = ["created_at"]

    def validate_note_text(self, value):
        if not value or len(value.strip()) == 0:
            raise serializers.ValidationError("Note text cannot be empty.")
        return value.strip()


class VendorDemoSerializer(serializers.ModelSerializer):
    scores = DemoScoreSerializer(source="scores", many=True, read_only=True)
    notes = DemoNoteSerializer(source="demo_notes", many=True, read_only=True)

    class Meta:
        model = VendorDemo
        fields = [
            "id",
            "vendor",
            "offering_id",
            "demo_id",
            "demo_date",
            "overall_score",
            "selection_outcome",
            "attendees_internal",
            "attendees_vendor",
            "notes",
            "created_by",
            "created_at",
            "scores",
        ]
        read_only_fields = ["created_at"]

    def validate_overall_score(self, value):
        if value and (value < 0 or value > 100):
            raise serializers.ValidationError("Overall score must be between 0 and 100.")
        return value


class VendorBusinessOwnerSerializer(serializers.ModelSerializer):
    class Meta:
        model = VendorBusinessOwner
        fields = [
            "id",
            "vendor",
            "owner_user_principal",
            "owner_name",
            "owner_department",
            "is_primary",
            "assigned_date",
            "assigned_by",
        ]
        read_only_fields = ["assigned_date"]


class VendorOrgAssignmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = VendorOrgAssignment
        fields = [
            "id",
            "vendor",
            "org_id",
            "org_name",
            "is_primary",
            "assigned_date",
            "assigned_by",
        ]
        read_only_fields = ["assigned_date"]


class VendorDetailedSerializer(serializers.ModelSerializer):
    """Detailed vendor serializer with all nested relationships"""

    contacts = VendorContactSerializer(many=True, read_only=True)
    identifiers = VendorIdentifierSerializer(many=True, read_only=True)
    vendor_notes = VendorNoteSerializer(many=True, read_only=True)
    vendor_warnings = VendorWarningSerializer(many=True, read_only=True)
    vendor_tickets = VendorTicketSerializer(many=True, read_only=True)
    business_owners = VendorBusinessOwnerSerializer(many=True, read_only=True)
    org_assignments = VendorOrgAssignmentSerializer(many=True, read_only=True)
    onboarding_workflow = OnboardingWorkflowSerializer(read_only=True)

    class Meta:
        model = Vendor
        fields = [
            "id",
            "vendor_id",
            "legal_name",
            "display_name",
            "lifecycle_state",
            "owner_org_id",
            "risk_tier",
            "created_at",
            "updated_at",
            "contacts",
            "identifiers",
            "vendor_notes",
            "vendor_warnings",
            "vendor_tickets",
            "business_owners",
            "org_assignments",
            "onboarding_workflow",
        ]
        read_only_fields = ["created_at", "updated_at"]


class VendorCreateUpdateSerializer(serializers.ModelSerializer):
    """Serializer for creating and updating vendors"""

    class Meta:
        model = Vendor
        fields = [
            "vendor_id",
            "legal_name",
            "display_name",
            "lifecycle_state",
            "owner_org_id",
            "risk_tier",
        ]

    def validate_vendor_id(self, value):
        if not value or len(value.strip()) == 0:
            raise serializers.ValidationError("Vendor ID cannot be empty.")
        if self.instance and self.instance.vendor_id != value:
            raise serializers.ValidationError("Vendor ID cannot be changed.")
        return value.upper()

    def validate_legal_name(self, value):
        if not value or len(value.strip()) == 0:
            raise serializers.ValidationError("Legal name cannot be empty.")
        return value.strip()

    def validate_display_name(self, value):
        if not value or len(value.strip()) == 0:
            raise serializers.ValidationError("Display name cannot be empty.")
        return value.strip()