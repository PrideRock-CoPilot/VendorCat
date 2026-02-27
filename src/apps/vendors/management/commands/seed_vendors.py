"""Management command to seed vendor catalog with sample data."""

from django.core.management.base import BaseCommand
from django.utils import timezone
from apps.vendors.models import (
    Vendor,
    VendorContact,
    VendorIdentifier,
    OnboardingWorkflow,
    VendorNote,
    VendorWarning,
    VendorBusinessOwner,
    VendorOrgAssignment,
)
import json


class Command(BaseCommand):
    """Seed the vendor catalog with sample data."""
    
    help = 'Populates the vendor catalog with sample data for testing and demonstration'

    def add_arguments(self, parser):
        """Add command arguments."""
        parser.add_argument(
            '--clear',
            action='store_true',
            help='Clear all vendor data before seeding'
        )
        parser.add_argument(
            '--count',
            type=int,
            default=10,
            help='Number of vendors to create (default: 10)'
        )

    def handle(self, *args, **options):
        """Handle command execution."""
        if options['clear']:
            self.stdout.write(self.style.WARNING('Clearing vendor data...'))
            Vendor.objects.all().delete()
            self.stdout.write(self.style.SUCCESS('Data cleared!'))

        count = options['count']
        self.stdout.write(f'Creating {count} sample vendors...')

        vendors_data = [
            {
                'vendor_id': f'VENDOR-{i:03d}',
                'legal_name': f'Vendor {i} Corporation',
                'display_name': f'Vendor {i}',
                'lifecycle_state': ['active', 'inactive', 'pending'][i % 3],
                'risk_tier': ['low', 'medium', 'high'][i % 3],
                'owner_org_id': f'ORG-{(i % 3) + 1:03d}',
                'contacts': [
                    {
                        'full_name': f'Contact {i}-1',
                        'contact_type': 'primary',
                        'email': f'contact{i}@vendor{i}.com',
                        'phone': f'555-{i:04d}',
                        'is_primary': True,
                    },
                    {
                        'full_name': f'Contact {i}-2',
                        'contact_type': 'support',
                        'email': f'support{i}@vendor{i}.com',
                        'phone': f'555-{i:04d}-1',
                    },
                ],
                'identifiers': [
                    {
                        'identifier_type': 'duns',
                        'identifier_value': f'1234567890{i:02d}',
                        'is_primary': True,
                        'is_verified': True,
                    },
                    {
                        'identifier_type': 'tax_id',
                        'identifier_value': f'98-765432{i:02d}',
                    },
                ],
                'business_owners': [
                    {
                        'owner_user_principal': f'user{i}@company.com',
                        'owner_name': f'Manager {i}',
                        'owner_department': 'Procurement',
                        'is_primary': True,
                    },
                ],
                'org_assignments': [
                    {
                        'org_id': f'ORG-{(i % 3) + 1:03d}',
                        'org_name': f'Department {(i % 3) + 1}',
                        'is_primary': True,
                    },
                ],
            }
            for i in range(1, count + 1)
        ]

        created_count = 0
        for vendor_data in vendors_data:
            try:
                # Extract related data
                contacts = vendor_data.pop('contacts', [])
                identifiers = vendor_data.pop('identifiers', [])
                business_owners = vendor_data.pop('business_owners', [])
                org_assignments = vendor_data.pop('org_assignments', [])

                # Create vendor
                vendor, created = Vendor.objects.get_or_create(
                    vendor_id=vendor_data['vendor_id'],
                    defaults=vendor_data
                )

                if created:
                    created_count += 1

                    # Create contacts
                    for contact_data in contacts:
                        VendorContact.objects.get_or_create(
                            vendor=vendor,
                            full_name=contact_data['full_name'],
                            defaults={
                                'contact_type': contact_data['contact_type'],
                                'email': contact_data.get('email'),
                                'phone': contact_data.get('phone'),
                                'is_primary': contact_data.get('is_primary', False),
                                'is_active': True,
                            }
                        )

                    # Create identifiers
                    for identifier_data in identifiers:
                        VendorIdentifier.objects.get_or_create(
                            vendor=vendor,
                            identifier_type=identifier_data['identifier_type'],
                            identifier_value=identifier_data['identifier_value'],
                            defaults={
                                'is_primary': identifier_data.get('is_primary', False),
                                'is_verified': identifier_data.get('is_verified', False),
                            }
                        )

                    # Create business owners
                    for owner_data in business_owners:
                        VendorBusinessOwner.objects.get_or_create(
                            vendor=vendor,
                            owner_user_principal=owner_data['owner_user_principal'],
                            defaults={
                                'owner_name': owner_data.get('owner_name'),
                                'owner_department': owner_data.get('owner_department'),
                                'is_primary': owner_data.get('is_primary', False),
                                'assigned_by': 'seed_command',
                            }
                        )

                    # Create org assignments
                    for org_data in org_assignments:
                        VendorOrgAssignment.objects.get_or_create(
                            vendor=vendor,
                            org_id=org_data['org_id'],
                            defaults={
                                'org_name': org_data.get('org_name'),
                                'is_primary': org_data.get('is_primary', False),
                                'assigned_by': 'seed_command',
                            }
                        )

                    # Create onboarding workflow if not exists
                    OnboardingWorkflow.objects.get_or_create(
                        vendor=vendor,
                        defaults={
                            'current_state': 'active',
                            'initiated_by': 'seed_command',
                        }
                    )

                    # Create a sample note
                    VendorNote.objects.create(
                        vendor=vendor,
                        note_type='general',
                        note_text=f'Sample vendor created during seed operation',
                        created_by='seed_command',
                    )

                    self.stdout.write(
                        self.style.SUCCESS(f'✓ Created vendor: {vendor.vendor_id}')
                    )
                else:
                    self.stdout.write(
                        self.style.WARNING(f'⊘ Vendor already exists: {vendor.vendor_id}')
                    )

            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(f'✗ Error creating vendor {vendor_data["vendor_id"]}: {str(e)}')
                )

        self.stdout.write(
            self.style.SUCCESS(f'\n✓ Seeding complete! Created {created_count} new vendors.')
        )
