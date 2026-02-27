"""Management command to generate vendor reports."""

from django.core.management.base import BaseCommand
from django.db.models import Count, Q
from apps.vendors.models import (
    Vendor,
    VendorWarning,
    VendorTicket,
    OnboardingWorkflow,
)
import json


class Command(BaseCommand):
    """Generate reports about vendor catalog status."""
    
    help = 'Generate various reports about vendor status and health'

    def add_arguments(self, parser):
        """Add command arguments."""
        parser.add_argument(
            '--report',
            type=str,
            default='summary',
            choices=['summary', 'warnings', 'tickets', 'onboarding', 'all'],
            help='Type of report to generate'
        )
        parser.add_argument(
            '--format',
            type=str,
            default='text',
            choices=['text', 'json'],
            help='Output format'
        )

    def handle(self, *args, **options):
        """Handle command execution."""
        report_type = options['report']
        output_format = options['format']

        reports = {}

        if report_type in ['summary', 'all']:
            reports['summary'] = self._get_summary_report()

        if report_type in ['warnings', 'all']:
            reports['warnings'] = self._get_warnings_report()

        if report_type in ['tickets', 'all']:
            reports['tickets'] = self._get_tickets_report()

        if report_type in ['onboarding', 'all']:
            reports['onboarding'] = self._get_onboarding_report()

        if output_format == 'json':
            self.stdout.write(json.dumps(reports, indent=2, default=str))
        else:
            self._print_reports(reports)

    def _get_summary_report(self):
        """Generate summary report."""
        total_vendors = Vendor.objects.count()
        active_vendors = Vendor.objects.filter(lifecycle_state='active').count()
        inactive_vendors = Vendor.objects.filter(lifecycle_state='inactive').count()
        pending_vendors = Vendor.objects.filter(lifecycle_state='pending').count()

        risk_distribution = dict(
            Vendor.objects.values('risk_tier').annotate(count=Count('id')).
            values_list('risk_tier', 'count')
        )

        return {
            'total_vendors': total_vendors,
            'by_lifecycle': {
                'active': active_vendors,
                'inactive': inactive_vendors,
                'pending': pending_vendors,
            },
            'by_risk_tier': risk_distribution,
        }

    def _get_warnings_report(self):
        """Generate warnings report."""
        active_warnings = VendorWarning.objects.filter(status='active').count()
        critical_warnings = VendorWarning.objects.filter(
            severity='critical',
            status='active'
        ).count()
        
        warnings_by_severity = dict(
            VendorWarning.objects.values('severity').annotate(count=Count('id')).
            values_list('severity', 'count')
        )

        return {
            'total_active': active_warnings,
            'critical': critical_warnings,
            'by_severity': warnings_by_severity,
        }

    def _get_tickets_report(self):
        """Generate tickets report."""
        open_tickets = VendorTicket.objects.filter(status='open').count()
        in_progress_tickets = VendorTicket.objects.filter(status='in_progress').count()
        closed_tickets = VendorTicket.objects.filter(status='closed').count()
        
        critical_open = VendorTicket.objects.filter(
            status='open',
            priority='critical'
        ).count()

        return {
            'open': open_tickets,
            'in_progress': in_progress_tickets,
            'closed': closed_tickets,
            'critical_open': critical_open,
        }

    def _get_onboarding_report(self):
        """Generate onboarding workflow report."""
        workflows = OnboardingWorkflow.objects.all()
        
        state_distribution = dict(
            workflows.values('current_state').annotate(count=Count('id')).
            values_list('current_state', 'count')
        )

        avg_days = None
        active_workflows = workflows.filter(current_state__in=['draft', 'pending_information', 'under_review', 'compliance_check'])
        if active_workflows.exists():
            total_days = sum(wf.get_total_onboarding_days() for wf in active_workflows)
            avg_days = total_days / active_workflows.count()

        return {
            'by_state': state_distribution,
            'average_days_in_process': avg_days,
            'total_workflows': workflows.count(),
        }

    def _print_reports(self, reports):
        """Print reports in text format."""
        for report_name, report_data in reports.items():
            self.stdout.write(self.style.SUCCESS(f'\n{report_name.upper()} REPORT'))
            self.stdout.write('=' * 50)
            self._print_data(report_data, indent=0)

    def _print_data(self, data, indent=0):
        """Recursively print data structure."""
        prefix = '  ' * indent
        if isinstance(data, dict):
            for key, value in data.items():
                if isinstance(value, (dict, list)):
                    self.stdout.write(f'{prefix}{key}:')
                    self._print_data(value, indent + 1)
                else:
                    self.stdout.write(f'{prefix}{key}: {value}')
        elif isinstance(data, list):
            for item in data:
                self._print_data(item, indent)
