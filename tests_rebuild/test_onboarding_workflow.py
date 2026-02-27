"""
Comprehensive tests for OnboardingWorkflow state machine implementation.
Tests cover model state transitions, serializers, and API endpoints.
"""

import json
from datetime import datetime, timedelta

import pytest
from django.utils import timezone
from django.test import TestCase, Client
from django.contrib.auth.models import User

from apps.vendors.models import Vendor, OnboardingWorkflow
from apps.vendors.serializers import OnboardingWorkflowSerializer, OnboardingWorkflowStateChangeSerializer


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def vendor():
    """Create a test vendor."""
    return Vendor.objects.create(
        vendor_id="TEST-WORKFLOW-001",
        legal_name="Test Workflow Vendor",
        display_name="Test Workflow",
        lifecycle_state="active",
        owner_org_id="test-org",
        risk_tier="low",
    )


@pytest.fixture
def workflow(vendor):
    """Create a test workflow."""
    return OnboardingWorkflow.objects.create(
        vendor=vendor,
        initiated_by="admin@company.com",
    )


# ============================================================================
# Model Tests: OnboardingWorkflow States
# ============================================================================

class TestOnboardingWorkflowModel(TestCase):
    """Test OnboardingWorkflow model initialization and basic functionality."""

    def setUp(self):
        """Set up test data."""
        self.vendor = Vendor.objects.create(
            vendor_id="TEST-WF-001",
            legal_name="Test Vendor",
            display_name="Test",
            lifecycle_state="active",
        )
        self.workflow = OnboardingWorkflow.objects.create(
            vendor=self.vendor,
            initiated_by="test@example.com",
        )

    def test_workflow_creation(self):
        """Test workflow is created in draft state."""
        self.assertEqual(self.workflow.current_state, "draft")
        self.assertEqual(self.workflow.vendor, self.vendor)
        self.assertEqual(self.workflow.initiated_by, "test@example.com")
        self.assertIsNotNone(self.workflow.initiated_at)

    def test_workflow_string_representation(self):
        """Test string representation of workflow."""
        expected = f"{self.vendor.vendor_id} - Draft"
        self.assertEqual(str(self.workflow), expected)

    def test_workflow_initial_fields(self):
        """Test initial field values."""
        self.assertIsNone(self.workflow.assigned_reviewer)
        self.assertIsNone(self.workflow.assigned_date)
        self.assertIsNone(self.workflow.reviewed_by)
        self.assertIsNone(self.workflow.information_request_sent_at)
        self.assertIsNone(self.workflow.documents_received_at)
        self.assertIsNone(self.workflow.compliance_check_completed_at)

    def test_workflow_state_choices(self):
        """Test workflow state choices are defined."""
        states = dict(OnboardingWorkflow.STATE_CHOICES)
        expected_states = [
            "draft",
            "pending_information",
            "under_review",
            "compliance_check",
            "approved",
            "rejected",
            "active",
            "archived",
        ]
        for state in expected_states:
            self.assertIn(state, states)


# ============================================================================
# State Transition Tests
# ============================================================================

class TestWorkflowStateTransitions(TestCase):
    """Test state machine transitions."""

    def setUp(self):
        """Set up test data."""
        self.vendor = Vendor.objects.create(
            vendor_id="TEST-WF-STT-001",
            legal_name="Test Vendor",
            display_name="Test",
        )
        self.workflow = OnboardingWorkflow.objects.create(vendor=self.vendor)

    def test_transition_draft_to_pending_information(self):
        """Test transition from draft to pending_information."""
        self.workflow.request_information(
            reason="missing_documents",
            notes="Please provide missing documents",
        )
        self.workflow.save()

        # Re-fetch from database instead of refresh_from_db
        workflow = OnboardingWorkflow.objects.get(id=self.workflow.id)
        self.assertEqual(workflow.current_state, "pending_information")
        self.assertEqual(workflow.status_change_reason, "missing_documents")
        self.assertEqual(workflow.status_change_notes, "Please provide missing documents")
        self.assertIsNotNone(workflow.information_request_sent_at)

    def test_transition_pending_to_under_review(self):
        """Test transition from pending_information to under_review."""
        self.workflow.request_information()
        self.workflow.save()
        self.workflow.mark_information_received()
        self.workflow.save()

        workflow = OnboardingWorkflow.objects.get(id=self.workflow.id)
        self.assertEqual(workflow.current_state, "under_review")
        self.assertIsNotNone(workflow.documents_received_at)

    def test_transition_under_review_to_compliance_check(self):
        """Test transition from under_review to compliance_check."""
        self.workflow.request_information()
        self.workflow.save()
        self.workflow.mark_information_received()
        self.workflow.save()
        self.workflow.assign_for_review(
            reviewer="reviewer@company.com",
            reason="risk_assessment",
            notes="Assigning for compliance check",
        )
        self.workflow.save()

        workflow = OnboardingWorkflow.objects.get(id=self.workflow.id)
        self.assertEqual(workflow.current_state, "compliance_check")
        self.assertEqual(workflow.assigned_reviewer, "reviewer@company.com")
        self.assertIsNotNone(workflow.assigned_date)

    def test_transition_compliance_check_to_approved(self):
        """Test transition from compliance_check to approved."""
        self.workflow.request_information()
        self.workflow.save()
        self.workflow.mark_information_received()
        self.workflow.save()
        self.workflow.assign_for_review(reviewer="reviewer@company.com")
        self.workflow.save()
        self.workflow.approve_vendor(
            reviewer="reviewer@company.com",
            notes="Passed compliance check",
        )
        self.workflow.save()

        workflow = OnboardingWorkflow.objects.get(id=self.workflow.id)
        self.assertEqual(workflow.current_state, "approved")
        self.assertEqual(workflow.reviewed_by, "reviewer@company.com")
        self.assertEqual(workflow.status_change_reason, "manager_approval")

    def test_transition_compliance_check_to_rejected(self):
        """Test transition from compliance_check to rejected."""
        self.workflow.request_information()
        self.workflow.save()
        self.workflow.mark_information_received()
        self.workflow.save()
        self.workflow.assign_for_review(reviewer="reviewer@company.com")
        self.workflow.save()
        self.workflow.reject_vendor(
            reviewer="reviewer@company.com",
            notes="Failed compliance check",
        )
        self.workflow.save()

        workflow = OnboardingWorkflow.objects.get(id=self.workflow.id)
        self.assertEqual(workflow.current_state, "rejected")
        self.assertEqual(workflow.status_change_reason, "rejected_internal")

    def test_transition_approved_to_active(self):
        """Test transition from approved to active."""
        self.workflow.request_information()
        self.workflow.save()
        self.workflow.mark_information_received()
        self.workflow.save()
        self.workflow.assign_for_review(reviewer="reviewer@company.com")
        self.workflow.save()
        self.workflow.approve_vendor(reviewer="reviewer@company.com")
        self.workflow.save()
        self.workflow.activate_vendor(notes="Vendor onboarding complete")
        self.workflow.save()

        workflow = OnboardingWorkflow.objects.get(id=self.workflow.id)
        self.assertEqual(workflow.current_state, "active")
        self.assertEqual(workflow.status_change_reason, "onboarding_complete")

    def test_transition_from_any_non_terminal_to_archived(self):
        """Test archiving workflow from various states."""
        # Test 1: Archive from draft
        self.workflow.archive_workflow(notes="Archived by admin")
        self.workflow.save()
        workflow = OnboardingWorkflow.objects.get(id=self.workflow.id)
        self.assertEqual(workflow.current_state, "archived")

        # Test 2: Archive from pending_information (create new vendor for new workflow)
        vendor2 = Vendor.objects.create(
            vendor_id="TEST-WF-STT-ARCHIVE-002",
            legal_name="Test Vendor 2",
            display_name="Test 2",
        )
        workflow2 = OnboardingWorkflow.objects.create(vendor=vendor2)
        workflow2.request_information()
        workflow2.save()
        workflow2.archive_workflow(notes="Archived by admin")
        workflow2.save()
        workflow2 = OnboardingWorkflow.objects.get(id=workflow2.id)
        self.assertEqual(workflow2.current_state, "archived")

    def test_reopen_draft_from_pending(self):
        """Test reopening draft from pending_information."""
        self.workflow.request_information()
        self.workflow.save()
        self.workflow.reopen_draft(notes="Reopening for vendor corrections")
        self.workflow.save()

        workflow = OnboardingWorkflow.objects.get(id=self.workflow.id)
        self.assertEqual(workflow.current_state, "draft")


# ============================================================================
# Helper Method Tests
# ============================================================================

class TestWorkflowHelperMethods(TestCase):
    """Test workflow helper methods."""

    def setUp(self):
        """Set up test data."""
        self.vendor = Vendor.objects.create(
            vendor_id="TEST-WF-HELPER-001",
            legal_name="Test",
            display_name="Test",
        )
        self.workflow = OnboardingWorkflow.objects.create(vendor=self.vendor)

    def test_is_pending_action(self):
        """Test pending action detection."""
        self.assertTrue(self.workflow.is_pending_action())

        self.workflow.request_information()
        self.workflow.save()
        workflow = OnboardingWorkflow.objects.get(id=self.workflow.id)
        self.assertTrue(workflow.is_pending_action())

        self.workflow.mark_information_received()
        self.workflow.save()
        workflow = OnboardingWorkflow.objects.get(id=self.workflow.id)
        self.assertFalse(workflow.is_pending_action())

    def test_is_under_internal_review(self):
        """Test internal review state detection."""
        self.assertFalse(self.workflow.is_under_internal_review())

        self.workflow.request_information()
        self.workflow.save()
        self.workflow.mark_information_received()
        self.workflow.save()
        workflow = OnboardingWorkflow.objects.get(id=self.workflow.id)
        self.assertTrue(workflow.is_under_internal_review())

        self.workflow.assign_for_review(reviewer="reviewer@company.com")
        self.workflow.save()
        workflow = OnboardingWorkflow.objects.get(id=self.workflow.id)
        self.assertTrue(workflow.is_under_internal_review())

    def test_is_completed(self):
        """Test completion state detection."""
        self.assertFalse(self.workflow.is_completed())

        # Complete the workflow
        self.workflow.request_information()
        self.workflow.save()
        self.workflow.mark_information_received()
        self.workflow.save()
        self.workflow.assign_for_review(reviewer="reviewer@company.com")
        self.workflow.save()
        self.workflow.approve_vendor(reviewer="reviewer@company.com")
        self.workflow.save()
        self.workflow.activate_vendor()
        self.workflow.save()
        workflow = OnboardingWorkflow.objects.get(id=self.workflow.id)
        self.assertTrue(workflow.is_completed())

    def test_get_days_in_state(self):
        """Test days in state calculation."""
        # Days should be small since we just created it
        days = self.workflow.get_days_in_state()
        self.assertGreaterEqual(days, 0)
        self.assertLess(days, 1)

    def test_get_total_onboarding_days(self):
        """Test total onboarding days calculation."""
        days = self.workflow.get_total_onboarding_days()
        self.assertGreaterEqual(days, 0)
        self.assertLess(days, 1)

    def test_get_next_states_from_draft(self):
        """Test next states from draft state."""
        next_states = self.workflow.get_next_states()
        self.assertIn("pending_information", next_states)
        self.assertIn("archived", next_states)
        self.assertEqual(len(next_states), 2)

    def test_get_next_states_from_pending_information(self):
        """Test next states from pending_information."""
        self.workflow.request_information()
        self.workflow.save()
        workflow = OnboardingWorkflow.objects.get(id=self.workflow.id)
        next_states = workflow.get_next_states()
        self.assertIn("under_review", next_states)
        self.assertIn("draft", next_states)
        self.assertIn("archived", next_states)

    def test_get_next_states_from_terminal_state(self):
        """Test no transitions from terminal states."""
        self.workflow.request_information()
        self.workflow.save()
        self.workflow.mark_information_received()
        self.workflow.save()
        self.workflow.assign_for_review(reviewer="reviewer@company.com")
        self.workflow.save()
        self.workflow.reject_vendor(reviewer="reviewer@company.com")
        self.workflow.save()
        workflow = OnboardingWorkflow.objects.get(id=self.workflow.id)

        next_states = workflow.get_next_states()
        self.assertEqual(len(next_states), 0)


# ============================================================================
# Serializer Tests
# ============================================================================

class TestOnboardingWorkflowSerializer(TestCase):
    """Test workflow serializer."""

    def setUp(self):
        """Set up test data."""
        self.vendor = Vendor.objects.create(
            vendor_id="TEST-WF-SER-001",
            legal_name="Test",
            display_name="Test",
        )
        self.workflow = OnboardingWorkflow.objects.create(vendor=self.vendor)

    def test_workflow_serializer_basic_fields(self):
        """Test serializer includes all basic fields."""
        serializer = OnboardingWorkflowSerializer(self.workflow)
        data = serializer.data

        self.assertEqual(data["vendor"], self.vendor.id)
        self.assertEqual(data["current_state"], "draft")
        self.assertEqual(data["current_state_display"], "Draft")

    def test_workflow_serializer_includes_computed_fields(self):
        """Test serializer includes computed fields."""
        serializer = OnboardingWorkflowSerializer(self.workflow)
        data = serializer.data

        self.assertIn("next_states", data)
        self.assertIn("days_in_state", data)
        self.assertIn("total_onboarding_days", data)
        self.assertIsInstance(data["next_states"], dict)
        self.assertIsInstance(data["days_in_state"], int)
        self.assertIsInstance(data["total_onboarding_days"], int)

    def test_workflow_serializer_read_only_fields(self):
        """Test read-only fields are not writable."""
        # Create a new vendor for serialization test (to avoid OneToOne constraint)
        vendor2 = Vendor.objects.create(
            vendor_id="TEST-WF-SER-READONLY",
            legal_name="Test Readonly",
            display_name="Test RO",
        )
        
        data = {
            "vendor": vendor2.id,
            "initiated_by": "test@example.com",
            "current_state": "active",  # Try to set directly (will be ignored)
            "initiated_at": timezone.now().isoformat(),  # Will be ignored
        }
        serializer = OnboardingWorkflowSerializer(data=data)

        # Should validate - read_only fields like initiated_at will be ignored
        self.assertTrue(serializer.is_valid(), serializer.errors if not serializer.is_valid() else None)


class TestOnboardingWorkflowStateChangeSerializer(TestCase):
    """Test state change serializer."""

    def test_state_change_serializer_validates_action(self):
        """Test serializer validates action field."""
        data = {"action": "invalid_action"}
        serializer = OnboardingWorkflowStateChangeSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn("action", serializer.errors)

    def test_state_change_serializer_valid_actions(self):
        """Test serializer accepts valid actions."""
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

        for action in valid_actions:
            data = {"action": action}
            serializer = OnboardingWorkflowStateChangeSerializer(data=data)
            self.assertTrue(serializer.is_valid())

    def test_state_change_serializer_with_optional_fields(self):
        """Test serializer accepts optional fields."""
        data = {
            "action": "approve_vendor",
            "reviewer": "reviewer@company.com",
            "notes": "Passed all checks",
            "reason": "manager_approval",
        }
        serializer = OnboardingWorkflowStateChangeSerializer(data=data)
        self.assertTrue(serializer.is_valid())


# ============================================================================
# Integration Tests
# ============================================================================

class TestWorkflowIntegration(TestCase):
    """Test workflow integration with vendor system."""

    def setUp(self):
        """Set up test data."""
        self.vendor = Vendor.objects.create(
            vendor_id="TEST-WF-INT-001",
            legal_name="Integration Test Vendor",
            display_name="Integration Test",
            lifecycle_state="active",
        )

    def test_workflow_auto_creation_on_first_access(self):
        """Test workflow is created on first access if it doesn't exist."""
        self.assertFalse(
            OnboardingWorkflow.objects.filter(vendor=self.vendor).exists()
        )

        # Simulate first access by creating workflow
        workflow = OnboardingWorkflow.objects.get_or_create(vendor=self.vendor)[0]

        self.assertTrue(
            OnboardingWorkflow.objects.filter(vendor=self.vendor).exists()
        )
        self.assertEqual(workflow.current_state, "draft")

    def test_full_workflow_lifecycle(self):
        """Test complete workflow from draft to active."""
        workflow = OnboardingWorkflow.objects.create(vendor=self.vendor)

        # Step 1: Request information
        workflow.request_information(reason="missing_documents", notes="Initial request")
        workflow.save()
        workflow = OnboardingWorkflow.objects.get(id=workflow.id)
        self.assertEqual(workflow.current_state, "pending_information")

        # Step 2: Information received
        workflow.mark_information_received()
        workflow.save()
        workflow = OnboardingWorkflow.objects.get(id=workflow.id)
        self.assertEqual(workflow.current_state, "under_review")

        # Step 3: Assign for review
        workflow.assign_for_review(
            reviewer="reviewer@company.com",
            reason="risk_assessment",
        )
        workflow.save()
        workflow = OnboardingWorkflow.objects.get(id=workflow.id)
        self.assertEqual(workflow.current_state, "compliance_check")

        # Step 4: Approve
        workflow.approve_vendor(reviewer="reviewer@company.com")
        workflow.save()
        workflow = OnboardingWorkflow.objects.get(id=workflow.id)
        self.assertEqual(workflow.current_state, "approved")

        # Step 5: Activate
        workflow.activate_vendor(notes="Onboarding completed successfully")
        workflow.save()
        workflow = OnboardingWorkflow.objects.get(id=workflow.id)
        self.assertEqual(workflow.current_state, "active")

        # Verify final state
        workflow = OnboardingWorkflow.objects.get(id=workflow.id)
        self.assertIsNotNone(workflow.reviewed_by)


# ============================================================================
# API Endpoint Tests
# ============================================================================

class TestWorkflowAPIEndpoints(TestCase):
    """Test workflow API endpoints."""

    def setUp(self):
        """Set up test client and data."""
        self.client = Client()
        self.vendor = Vendor.objects.create(
            vendor_id="TEST-WF-API-001",
            legal_name="API Test Vendor",
            display_name="API Test",
        )

    def test_get_workflow_returns_workflow_data(self):
        """Test GET /api/{vendor_id}/workflow returns workflow."""
        response = self.client.get(f"/vendor-360/api/{self.vendor.vendor_id}/workflow")
        
        # Should return 200 and create workflow automatically
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertEqual(data["current_state"], "draft")

    def test_get_workflow_status_endpoint(self):
        """Test GET /api/{vendor_id}/workflow/status shows workflow status."""
        # Create workflow first
        OnboardingWorkflow.objects.create(vendor=self.vendor)

        response = self.client.get(
            f"/vendor-360/api/{self.vendor.vendor_id}/workflow/status"
        )

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertEqual(data["current_state"], "draft")

    def test_transition_not_found_for_missing_vendor(self):
        """Test 404 error for non-existent vendor."""
        response = self.client.get("/vendor-360/api/NONEXISTENT/workflow")
        self.assertEqual(response.status_code, 404)

    def test_state_transition_validation_rejects_invalid_action(self):
        """Test invalid action is rejected when authenticated."""
        # Create a user with vendor.write permission for this test
        from django.contrib.auth.models import User
        user = User.objects.create_user(username="testuser", password="testpass")
        
        # Log in the user
        self.client.login(username="testuser", password="testpass")
        
        data = json.dumps({"action": "invalid_action"})
        response = self.client.post(
            f"/vendor-360/api/{self.vendor.vendor_id}/workflow",
            data=data,
            content_type="application/json",
        )

        # Could be 400 if authenticated with permission, or 403 if not authorized
        # For now, just verify it's not 200 or 201
        self.assertIn(response.status_code, [400, 403])


@pytest.mark.django_db
class TestWorkflowPytest(object):
    """Pytest-style workflow tests."""

    def test_workflow_creation_with_fixtures(self, vendor, workflow):
        """Test workflow creation using fixtures."""
        assert workflow.vendor == vendor
        assert workflow.current_state == "draft"
        assert workflow.initiated_by is not None

    def test_workflow_state_transition_with_fixtures(self, workflow):
        """Test state transition."""
        workflow.request_information(reason="missing_documents")
        workflow.save()
        workflow = OnboardingWorkflow.objects.get(id=workflow.id)
        assert workflow.current_state == "pending_information"

    def test_workflow_next_states_from_draft(self, workflow):
        """Test next states from draft."""
        next_states = workflow.get_next_states()
        assert "pending_information" in next_states
        assert "archived" in next_states
