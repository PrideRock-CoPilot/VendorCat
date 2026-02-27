"""Comprehensive tests for Vendor Catalog application."""

import pytest
from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth.models import User
from django.utils import timezone
from rest_framework.test import APITestCase, APIClient
from rest_framework import status

from .models import (
    Vendor,
    VendorContact,
    VendorIdentifier,
    OnboardingWorkflow,
    VendorNote,
    VendorWarning,
    VendorTicket,
    VendorBusinessOwner,
    VendorOrgAssignment,
    VendorDemo,
    DemoScore,
)


class VendorModelTestCase(TestCase):
    """Tests for Vendor model."""

    def setUp(self):
        """Set up test fixtures."""
        self.vendor = Vendor.objects.create(
            vendor_id="TEST-001",
            legal_name="Test Vendor Inc",
            display_name="Test Vendor",
            lifecycle_state="active",
            risk_tier="medium",
        )

    def test_vendor_creation(self):
        """Test basic vendor creation."""
        vendor = Vendor.objects.create(
            vendor_id="TEST-002",
            legal_name="Another Test Vendor",
            display_name="Another Vendor",
        )
        self.assertIsNotNone(vendor.id)
        self.assertEqual(vendor.vendor_id, "TEST-002")
        self.assertEqual(vendor.legal_name, "Another Test Vendor")

    def test_vendor_str_representation(self):
        """Test vendor __str__ method."""
        expected = f"{self.vendor.display_name} ({self.vendor.vendor_id})"
        self.assertEqual(str(self.vendor), expected)

    def test_vendor_get_contacts(self):
        """Test get_contacts method."""
        # Create contacts
        VendorContact.objects.create(
            vendor=self.vendor,
            full_name="John Doe",
            contact_type="primary",
            email="john@example.com",
            is_active=True,
        )
        VendorContact.objects.create(
            vendor=self.vendor,
            full_name="Jane Smith",
            contact_type="support",
            email="jane@example.com",
            is_active=False,
        )

        active_contacts = self.vendor.get_contacts()
        self.assertEqual(active_contacts.count(), 1)
        self.assertEqual(active_contacts.first().full_name, "John Doe")

    def test_vendor_get_identifiers(self):
        """Test get_identifiers method."""
        VendorIdentifier.objects.create(
            vendor=self.vendor,
            identifier_type="duns",
            identifier_value="123456789",
        )
        VendorIdentifier.objects.create(
            vendor=self.vendor,
            identifier_type="tax_id",
            identifier_value="98-7654321",
        )

        identifiers = self.vendor.get_identifiers()
        self.assertEqual(identifiers.count(), 2)


class VendorContactModelTestCase(TestCase):
    """Tests for VendorContact model."""

    def setUp(self):
        """Set up test fixtures."""
        self.vendor = Vendor.objects.create(
            vendor_id="TEST-001",
            legal_name="Test Vendor Inc",
            display_name="Test Vendor",
        )

    def test_contact_creation(self):
        """Test vendor contact creation."""
        contact = VendorContact.objects.create(
            vendor=self.vendor,
            full_name="John Doe",
            contact_type="primary",
            email="john@example.com",
            phone="555-1234",
            is_primary=True,
        )
        self.assertIsNotNone(contact.id)
        self.assertEqual(contact.full_name, "John Doe")
        self.assertTrue(contact.is_primary)

    def test_contact_str_representation(self):
        """Test contact __str__ method."""
        contact = VendorContact.objects.create(
            vendor=self.vendor,
            full_name="John Doe",
            contact_type="primary",
        )
        self.assertEqual(str(contact), "John Doe (primary)")


class OnboardingWorkflowTestCase(TestCase):
    """Tests for OnboardingWorkflow state machine."""

    def setUp(self):
        """Set up test fixtures."""
        self.vendor = Vendor.objects.create(
            vendor_id="TEST-001",
            legal_name="Test Vendor Inc",
            display_name="Test Vendor",
        )
        self.workflow = OnboardingWorkflow.objects.create(
            vendor=self.vendor,
            current_state="draft",
            initiated_by="test_user",
        )

    def test_workflow_creation(self):
        """Test workflow creation."""
        self.assertEqual(self.workflow.current_state, "draft")
        self.assertEqual(self.workflow.initiated_by, "test_user")

    def test_workflow_state_transitions(self):
        """Test workflow state transitions."""
        # Draft -> Pending Information
        self.workflow.request_information(reason="missing_documents")
        self.workflow.save()
        self.assertEqual(self.workflow.current_state, "pending_information")

        # Pending Information -> Under Review
        self.workflow.mark_information_received()
        self.workflow.save()
        self.assertEqual(self.workflow.current_state, "under_review")

        # Under Review -> Compliance Check
        self.workflow.assign_for_review(reviewer="test_reviewer")
        self.workflow.save()
        self.assertEqual(self.workflow.current_state, "compliance_check")

        # Compliance Check -> Approved
        self.workflow.approve_vendor(reviewer="test_reviewer")
        self.workflow.save()
        self.assertEqual(self.workflow.current_state, "approved")

        # Approved -> Active
        self.workflow.activate_vendor()
        self.workflow.save()
        self.assertEqual(self.workflow.current_state, "active")

    def test_workflow_rejection(self):
        """Test workflow rejection path."""
        self.workflow.request_information()
        self.workflow.save()
        self.assertEqual(self.workflow.current_state, "pending_information")

        self.workflow.mark_information_received()
        self.workflow.save()
        self.workflow.assign_for_review(reviewer="test_reviewer")
        self.workflow.save()
        self.workflow.reject_vendor(reviewer="test_reviewer", notes="Compliance failed")
        self.workflow.save()
        self.assertEqual(self.workflow.current_state, "rejected")


class VendorAPITestCase(APITestCase):
    """Tests for Vendor REST API endpoints."""

    def setUp(self):
        """Set up test fixtures."""
        # Create test user
        self.user = User.objects.create_user(
            username="testuser",
            password="testpass123"
        )
        
        # Create test client
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

        # Create test vendor
        self.vendor = Vendor.objects.create(
            vendor_id="TEST-001",
            legal_name="Test Vendor Inc",
            display_name="Test Vendor",
            lifecycle_state="active",
            risk_tier="medium",
        )

    def test_vendor_list_api(self):
        """Test vendor list endpoint."""
        url = reverse("vendor-api-list")
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("results", response.data)

    def test_vendor_retrieve_api(self):
        """Test vendor retrieve endpoint."""
        url = reverse("vendor-api-detail", kwargs={"pk": self.vendor.id})
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["vendor_id"], "TEST-001")

    def test_vendor_create_api(self):
        """Test vendor creation via API."""
        url = reverse("vendor-api-list")
        data = {
            "vendor_id": "TEST-NEW",
            "legal_name": "New Vendor LLC",
            "display_name": "New Vendor",
            "lifecycle_state": "active",
            "risk_tier": "low",
        }
        response = self.client.post(url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["vendor_id"], "TEST-NEW")

    def test_vendor_update_api(self):
        """Test vendor update via API."""
        url = reverse("vendor-api-detail", kwargs={"pk": self.vendor.id})
        data = {
            "vendor_id": "TEST-001",
            "legal_name": "Updated Vendor Name",
            "display_name": "Updated Display",
            "lifecycle_state": "inactive",
            "risk_tier": "high",
        }
        response = self.client.patch(url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.vendor.refresh_from_db()
        self.assertEqual(self.vendor.legal_name, "Updated Vendor Name")

    def test_vendor_delete_api(self):
        """Test vendor deletion via API."""
        url = reverse("vendor-api-detail", kwargs={"pk": self.vendor.id})
        response = self.client.delete(url)
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Vendor.objects.filter(id=self.vendor.id).exists())

    def test_vendor_summary_api(self):
        """Test vendor summary endpoint."""
        # Add some related objects
        VendorContact.objects.create(
            vendor=self.vendor,
            full_name="John Doe",
            contact_type="primary",
        )
        VendorNote.objects.create(
            vendor=self.vendor,
            note_type="general",
            note_text="Test note",
            created_by="test_user",
        )

        url = reverse("vendor-api-summary", kwargs={"pk": self.vendor.id})
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["contact_count"], 1)
        self.assertEqual(response.data["note_count"], 1)


class VendorContactAPITestCase(APITestCase):
    """Tests for VendorContact API endpoints."""

    def setUp(self):
        """Set up test fixtures."""
        self.user = User.objects.create_user(
            username="testuser",
            password="testpass123"
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

        self.vendor = Vendor.objects.create(
            vendor_id="TEST-001",
            legal_name="Test Vendor Inc",
            display_name="Test Vendor",
        )

    def test_contact_create(self):
        """Test contact creation via API."""
        url = reverse("vendor-contact-api-list")
        data = {
            "vendor": self.vendor.id,
            "full_name": "John Doe",
            "contact_type": "primary",
            "email": "john@example.com",
            "phone": "555-1234",
        }
        response = self.client.post(url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["full_name"], "John Doe")

    def test_contact_list_by_vendor(self):
        """Test filtering contacts by vendor."""
        VendorContact.objects.create(
            vendor=self.vendor,
            full_name="John Doe",
            contact_type="primary",
        )
        
        url = reverse("vendor-contact-api-list")
        response = self.client.get(url, {"vendor_id": self.vendor.vendor_id})
        self.assertEqual(response.status_code, status.HTTP_200_OK)


class OnboardingWorkflowAPITestCase(APITestCase):
    """Tests for OnboardingWorkflow API endpoints."""

    def setUp(self):
        """Set up test fixtures."""
        self.user = User.objects.create_user(
            username="testuser",
            password="testpass123"
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

        self.vendor = Vendor.objects.create(
            vendor_id="TEST-001",
            legal_name="Test Vendor Inc",
            display_name="Test Vendor",
        )
        self.workflow = OnboardingWorkflow.objects.create(
            vendor=self.vendor,
            current_state="draft",
            initiated_by="test_user",
        )

    def test_workflow_retrieve(self):
        """Test workflow retrieval."""
        url = reverse("onboarding-workflow-api-detail", kwargs={"pk": self.workflow.id})
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["current_state"], "draft")

    def test_workflow_state_change(self):
        """Test workflow state change via API."""
        url = reverse("onboarding-workflow-api-change-state", kwargs={"pk": self.workflow.id})
        data = {
            "action": "request_information",
            "reason": "missing_documents",
            "notes": "Please provide additional docs",
        }
        response = self.client.post(url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["current_state"], "pending_information")


class VendorWarningAutoCreationTestCase(TestCase):
    """Tests for automatic ticket creation when critical warnings are created."""

    def setUp(self):
        """Set up test fixtures."""
        self.vendor = Vendor.objects.create(
            vendor_id="TEST-001",
            legal_name="Test Vendor Inc",
            display_name="Test Vendor",
        )

    def test_critical_warning_creates_ticket(self):
        """Test that critical warnings auto-create tickets."""
        initial_ticket_count = VendorTicket.objects.filter(vendor=self.vendor).count()
        
        VendorWarning.objects.create(
            vendor=self.vendor,
            warning_category="compliance",
            severity="critical",
            status="active",
            title="Critical Compliance Issue",
            detected_at=timezone.now(),
            created_by="system",
        )

        final_ticket_count = VendorTicket.objects.filter(vendor=self.vendor).count()
        self.assertEqual(final_ticket_count, initial_ticket_count + 1)


class DemoScoreCalculationTestCase(TestCase):
    """Tests for automatic demo score calculation."""

    def setUp(self):
        """Set up test fixtures."""
        self.vendor = Vendor.objects.create(
            vendor_id="TEST-001",
            legal_name="Test Vendor Inc",
            display_name="Test Vendor",
        )
        self.demo = VendorDemo.objects.create(
            vendor=self.vendor,
            demo_id="DEMO-001",
            demo_date=timezone.now(),
            created_by="test_user",
        )

    def test_demo_overall_score_calculation(self):
        """Test automatic overall score calculation."""
        DemoScore.objects.create(
            demo=self.demo,
            score_category="functionality",
            score_value=85,
            weight=1.0,
        )
        DemoScore.objects.create(
            demo=self.demo,
            score_category="usability",
            score_value=90,
            weight=1.0,
        )

        self.demo.refresh_from_db()
        expected_score = (85 + 90) / 2
        self.assertEqual(self.demo.overall_score, expected_score)


@pytest.mark.django_db
class VendorFilteringTests:
    """Tests for vendor filtering and search."""

    def test_vendor_filter_by_lifecycle_state(self):
        """Test filtering vendors by lifecycle state."""
        Vendor.objects.create(
            vendor_id="ACTIVE-001",
            legal_name="Active Vendor",
            display_name="Active",
            lifecycle_state="active",
        )
        Vendor.objects.create(
            vendor_id="INACTIVE-001",
            legal_name="Inactive Vendor",
            display_name="Inactive",
            lifecycle_state="inactive",
        )

        active_vendors = Vendor.objects.filter(lifecycle_state="active")
        assert active_vendors.count() == 1
        assert active_vendors.first().vendor_id == "ACTIVE-001"

    def test_vendor_filter_by_risk_tier(self):
        """Test filtering vendors by risk tier."""
        Vendor.objects.create(
            vendor_id="HIGH-RISK",
            legal_name="High Risk Vendor",
            display_name="High Risk",
            risk_tier="high",
        )
        Vendor.objects.create(
            vendor_id="LOW-RISK",
            legal_name="Low Risk Vendor",
            display_name="Low Risk",
            risk_tier="low",
        )

        high_risk = Vendor.objects.filter(risk_tier="high")
        assert high_risk.count() == 1
        assert high_risk.first().vendor_id == "HIGH-RISK"

    def test_vendor_search_by_vendor_id(self):
        """Test searching vendors by vendor ID."""
        Vendor.objects.create(
            vendor_id="ABC-123",
            legal_name="ABC Corp",
            display_name="ABC",
        )
        Vendor.objects.create(
            vendor_id="XYZ-456",
            legal_name="XYZ Corp",
            display_name="XYZ",
        )

        result = Vendor.objects.filter(vendor_id__icontains="ABC")
        assert result.count() == 1
        assert result.first().vendor_id == "ABC-123"
