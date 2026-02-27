"""Django signals for Vendor Catalog business logic."""

from django.db.models.signals import post_save, pre_save, post_delete
from django.dispatch import receiver
from django.utils import timezone
from .models import (
    Vendor,
    OnboardingWorkflow,
    VendorWarning,
    VendorTicket,
    VendorDemo,
    DemoScore,
)


@receiver(post_save, sender=Vendor)
def create_onboarding_workflow(sender, instance, created, **kwargs):
    """
    Create an onboarding workflow when a new vendor is created.
    
    Args:
        sender: The model class that sent the signal (Vendor)
        instance: The actual instance being saved
        created: Boolean; True if a new record was created, False if updated
        **kwargs: Additional keyword arguments
    """
    if created:
        workflow, _ = OnboardingWorkflow.objects.get_or_create(
            vendor=instance,
            defaults={
                'current_state': 'draft',
                'initiated_by': 'system',
                'initiated_at': timezone.now(),
            }
        )


@receiver(post_save, sender=VendorWarning)
def handle_critical_warning(sender, instance, created, **kwargs):
    """
    Auto-create a ticket when a critical warning is created.
    
    Args:
        sender: The model class that sent the signal (VendorWarning)
        instance: The actual instance being saved
        created: Boolean; True if a new record was created
        **kwargs: Additional keyword arguments
    """
    if created and instance.severity == 'critical' and instance.status == 'active':
        # Check if a ticket already exists for this warning
        existing_ticket = VendorTicket.objects.filter(
            vendor=instance.vendor,
            title=f"CRITICAL: {instance.title}",
            status__in=['open', 'in_progress']
        ).exists()
        
        if not existing_ticket:
            VendorTicket.objects.create(
                vendor=instance.vendor,
                title=f"CRITICAL: {instance.title}",
                description=f"Auto-created from critical warning: {instance.detail}",
                status='open',
                priority='critical',
                opened_date=timezone.now(),
                created_by='system',
            )


@receiver(post_save, sender=VendorWarning)
def handle_warning_resolution(sender, instance, created=False, **kwargs):
    """
    Auto-close related tickets when warning is resolved.
    
    Args:
        sender: The model class that sent the signal
        instance: The actual instance being saved
        created: Boolean; True if a new record was created
        **kwargs: Additional keyword arguments
    """
    if not created and instance.status == 'resolved':
        # Close related tickets
        related_tickets = VendorTicket.objects.filter(
            vendor=instance.vendor,
            title__contains=instance.title,
            status__in=['open', 'in_progress']
        )
        for ticket in related_tickets:
            ticket.status = 'closed'
            ticket.closed_date = timezone.now()
            ticket.save()


@receiver(post_save, sender=DemoScore)
def update_demo_overall_score(sender, instance, created, **kwargs):
    """
    Calculate and update the demo's overall score when a new score is added.
    
    Args:
        sender: The model class that sent the signal (DemoScore)
        instance: The actual instance being saved
        created: Boolean; True if a new record was created
        **kwargs: Additional keyword arguments
    """
    demo = instance.demo
    scores = demo.scores.all()
    
    if scores.exists():
        # Calculate weighted average if weights are provided
        weighted_sum = 0
        total_weight = 0
        
        for score in scores:
            weight = score.weight if score.weight else 1.0
            weighted_sum += score.score_value * weight
            total_weight += weight
        
        overall_score = weighted_sum / total_weight if total_weight > 0 else 0
        demo.overall_score = round(overall_score, 2)
        demo.save()


@receiver(post_save, sender=OnboardingWorkflow)
def log_workflow_state_change(sender, instance, created=False, **kwargs):
    """
    Log state transitions for audit trail.
    
    Args:
        sender: The model class that sent the signal
        instance: The actual instance being saved
        created: Boolean; True if a new record was created
        **kwargs: Additional keyword arguments
    """
    if not created:
        # You could extend this to create audit log entries
        # For now, we rely on the model's built-in timestamp fields
        pass


@receiver(post_save, sender=VendorDemo)
def auto_activate_vendor_on_selection(sender, instance, created=False, **kwargs):
    """
    Automatically activate vendor if demo result is 'selected'.
    
    Args:
        sender: The model class that sent the signal
        instance: The actual instance being saved
        created: Boolean; True if a new record was created
        **kwargs: Additional keyword arguments
    """
    if not created and instance.selection_outcome == 'selected':
        # Check the vendor's onboarding workflow
        try:
            workflow = instance.vendor.onboarding_workflow
            if workflow.current_state == 'approved':
                workflow.activate_vendor(notes=f"Auto-activated after demo selection")
                workflow.save()
        except OnboardingWorkflow.DoesNotExist:
            pass


@receiver(pre_save, sender=VendorTicket)
def notify_on_ticket_status_change(sender, instance, **kwargs):
    """
    Send notifications when ticket status changes.
    
    Args:
        sender: The model class that sent the signal
        instance: The actual instance being saved
        **kwargs: Additional keyword arguments
    """
    # Only if this is an update (not a new ticket)
    if instance.pk:
        try:
            old_instance = VendorTicket.objects.get(pk=instance.pk)
            if old_instance.status != instance.status:
                # Ticket status changed - you could trigger notifications here
                # For now, we just track the change
                if instance.status == 'closed' and not instance.closed_date:
                    instance.closed_date = timezone.now()
        except VendorTicket.DoesNotExist:
            pass


@receiver(post_delete, sender=VendorDemo)
def cleanup_demo_data(sender, instance, **kwargs):
    """
    Clean up related demo scores and notes when a demo is deleted.
    
    Args:
        sender: The model class that sent the signal
        instance: The actual instance being deleted
        **kwargs: Additional keyword arguments
    """
    # Django's CASCADE relationship should handle this, but we can add
    # additional cleanup logic if needed
    pass


def connect_signals():
    """
    Connect all signals. Call this in apps.py ready() method.
    
    Example:
        In apps.py:
        def ready(self):
            from apps.vendors.signals import connect_signals
            connect_signals()
    """
    # Signals are already connected via @receiver decorators
    # This function is here for documentation and potential future extensions
    pass
