"""
Forms for vendor contacts and identifiers management.
"""

from django import forms
from django.core.exceptions import ValidationError
from .models import VendorContact, VendorIdentifier


class VendorContactForm(forms.ModelForm):
    """Form for creating and editing vendor contacts."""

    CONTACT_TITLE_CHOICES = [
        ("", "-- Select Role --"),
        ("Account Manager", "Account Manager"),
        ("Sales Manager", "Sales Manager"),
        ("Support Lead", "Support Lead"),
        ("Technical Lead", "Technical Lead"),
        ("Finance Manager", "Finance Manager"),
        ("Director", "Director"),
        ("VP", "VP"),
        ("Other", "Other"),
    ]

    class Meta:
        model = VendorContact
        fields = ['full_name', 'contact_type', 'title', 'email', 'phone', 'is_primary', 'is_active', 'notes']
        widgets = {
            'full_name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter contact full name',
                'required': True,
            }),
            'contact_type': forms.Select(attrs={
                'class': 'form-select',
                'required': True,
            }),
            'title': forms.TextInput(attrs={
                'class': 'form-select',
            }),
            'email': forms.EmailInput(attrs={
                'class': 'form-control',
                'placeholder': 'contact@vendor.com',
                'type': 'email',
            }),
            'phone': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': '555-1234 or +1-555-1234',
            }),
            'is_primary': forms.CheckboxInput(attrs={
                'class': 'form-check-input',
            }),
            'is_active': forms.CheckboxInput(attrs={
                'class': 'form-check-input',
            }),
            'notes': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 4,
                'placeholder': 'Add any additional notes or context...',
            }),
        }

    def __init__(self, *args, **kwargs):
        self.vendor = kwargs.pop('vendor', None)
        super().__init__(*args, **kwargs)

        self.fields['title'].widget = forms.Select(
            choices=self.CONTACT_TITLE_CHOICES,
            attrs={'class': 'form-select'}
        )

        # Set default for is_active
        if not self.instance.pk:
            self.fields['is_active'].initial = True

    def clean_email(self):
        """Validate email format if provided."""
        email = self.cleaned_data.get('email')
        if email:
            if '@' not in email:
                raise ValidationError("Enter a valid email address.")
        return email

    def clean_full_name(self):
        """Validate full name is not empty."""
        full_name = self.cleaned_data.get('full_name')
        if not full_name or not full_name.strip():
            raise ValidationError("Full name is required.")
        return full_name.strip()

    def clean(self):
        """Validate the entire form."""
        cleaned_data = super().clean()

        # Ensure vendor is available for validation
        if not self.vendor:
            raise ValidationError("Vendor must be specified.")

        # Check for duplicate primary contact
        is_primary = cleaned_data.get('is_primary')
        if is_primary and self.vendor:
            # Exclude current instance if editing
            exclude_id = self.instance.pk if self.instance.pk else None
            existing_primary = VendorContact.objects.filter(
                vendor=self.vendor,
                is_primary=True
            ).exclude(id=exclude_id).exists()

            if existing_primary:
                raise ValidationError(
                    "This vendor already has a primary contact. "
                    "Uncheck 'is_primary' or edit the existing primary contact first."
                )

        return cleaned_data

    def save(self, commit=True):
        """Save the form instance."""
        if self.vendor:
            self.instance.vendor = self.vendor
        return super().save(commit=commit)


class VendorIdentifierForm(forms.ModelForm):
    """Form for creating and editing vendor identifiers."""

    class Meta:
        model = VendorIdentifier
        fields = [
            'identifier_type',
            'identifier_value',
            'country_code',
            'is_primary',
            'is_verified',
            'verified_by',
            'verified_at',
            'notes'
        ]
        widgets = {
            'identifier_type': forms.Select(attrs={
                'class': 'form-select',
                'required': True,
            }),
            'identifier_value': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter the identifier value',
                'required': True,
            }),
            'country_code': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'US, DE, JP, etc.',
                'maxlength': '2',
                'pattern': '[A-Z]{2}',
            }),
            'is_primary': forms.CheckboxInput(attrs={
                'class': 'form-check-input',
            }),
            'is_verified': forms.CheckboxInput(attrs={
                'class': 'form-check-input',
            }),
            'verified_by': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Email or name of verifier',
            }),
            'verified_at': forms.DateTimeInput(attrs={
                'class': 'form-control',
                'type': 'datetime-local',
                'placeholder': 'YYYY-MM-DD HH:MM',
            }),
            'notes': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 4,
                'placeholder': 'Verification method, source, usage notes...',
            }),
        }

    def __init__(self, *args, **kwargs):
        self.vendor = kwargs.pop('vendor', None)
        super().__init__(*args, **kwargs)

    def clean_identifier_value(self):
        """Validate identifier value is not empty."""
        value = self.cleaned_data.get('identifier_value')
        if not value or not value.strip():
            raise ValidationError("Identifier value is required.")
        return value.strip()

    def clean_country_code(self):
        """Validate country code format."""
        code = self.cleaned_data.get('country_code')
        if code:
            code = code.upper().strip()
            if len(code) != 2 or not code.isalpha():
                raise ValidationError(
                    "Country code must be a 2-letter ISO code (e.g., US, DE, JP)."
                )
        return code if code else None

    def clean_verified_at(self):
        """Validate verified_at date if is_verified is checked."""
        verified_at = self.cleaned_data.get('verified_at')
        is_verified = self.cleaned_data.get('is_verified')

        if is_verified and not verified_at:
            raise ValidationError(
                "Verification date is required when marking as verified."
            )

        return verified_at

    def clean(self):
        """Validate the entire form."""
        cleaned_data = super().clean()

        # Ensure vendor is available
        if not self.vendor:
            raise ValidationError("Vendor must be specified.")

        # Check for duplicate identifiers
        identifier_type = cleaned_data.get('identifier_type')
        identifier_value = cleaned_data.get('identifier_value')

        if identifier_type and identifier_value and self.vendor:
            # Exclude current instance if editing
            exclude_id = self.instance.pk if self.instance.pk else None
            existing = VendorIdentifier.objects.filter(
                vendor=self.vendor,
                identifier_type=identifier_type,
                identifier_value=identifier_value
            ).exclude(id=exclude_id).exists()

            if existing:
                raise ValidationError(
                    f"This {identifier_type.upper()} identifier already exists for this vendor. "
                    "Identifiers must be unique per type per vendor."
                )

        # Check for duplicate primary identifier
        is_primary = cleaned_data.get('is_primary')
        if is_primary and self.vendor:
            exclude_id = self.instance.pk if self.instance.pk else None
            existing_primary = VendorIdentifier.objects.filter(
                vendor=self.vendor,
                is_primary=True
            ).exclude(id=exclude_id).exists()

            if existing_primary:
                raise ValidationError(
                    "This vendor already has a primary identifier. "
                    "Uncheck 'is_primary' or edit the existing primary identifier first."
                )

        return cleaned_data

    def save(self, commit=True):
        """Save the form instance."""
        if self.vendor:
            self.instance.vendor = self.vendor
        return super().save(commit=commit)
