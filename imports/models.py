"""
Import models for Shop Window application.

This module implements import tracking and data quality management for the
progressive data enrichment system. Handles CSV imports, Excel file processing,
PDF extraction, and manual data entry with comprehensive audit trails.

Key Features:
- Import batch tracking with status management
- Data quality flag system for non-blocking validation
- File processing metadata and error logging
- Import statistics and success metrics
- Progressive data enrichment audit trail
"""

from django.db import models
from django.contrib.auth.models import User
from django.contrib.postgres.fields import JSONField
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils import timezone
from django.core.files.storage import default_storage
import hashlib
import os
import logging

logger = logging.getLogger(__name__)


# =============================================================================
# IMPORT BATCH MODEL
# =============================================================================

class ImportBatch(models.Model):
    """
    Track import operations for comprehensive audit trail.
    
    Supports multiple import pathways:
    - CSV file imports (denormalized property data)
    - Excel file imports (sample data loading)
    - PDF extraction (tenant tables and property details)
    - Manual data entry (progressive enrichment)
    
    Business Rules:
    - Each import operation creates a batch record
    - Batch status tracks processing lifecycle
    - Comprehensive metrics for success/failure analysis
    - File metadata stored for reproducibility
    - Error logging for debugging and improvement
    """
    
    # =============================================================================
    # IMPORT TYPE CHOICES
    # =============================================================================
    
    IMPORT_TYPES = [
        ('CSV', 'CSV File Import'),
        ('EXCEL', 'Excel File Import'),
        ('PDF', 'PDF Text Extraction'),
        ('MANUAL', 'Manual Data Entry'),
        ('API', 'API Data Import'),
        ('BULK', 'Bulk Data Operation'),
    ]
    
    IMPORT_STATUS = [
        ('PENDING', 'Pending Processing'),
        ('PROCESSING', 'Currently Processing'),
        ('REVIEW', 'Ready for Review'),
        ('APPROVED', 'Approved for Import'),
        ('COMPLETED', 'Successfully Completed'),
        ('FAILED', 'Failed with Errors'),
        ('CANCELLED', 'Cancelled by User'),
        ('PARTIAL', 'Partially Completed'),
    ]
    
    # =============================================================================
    # CORE FIELDS
    # =============================================================================
    
    id = models.AutoField(primary_key=True)
    import_type = models.CharField(
        max_length=10,
        choices=IMPORT_TYPES,
        help_text="Type of import operation"
    )
    status = models.CharField(
        max_length=20,
        choices=IMPORT_STATUS,
        default='PENDING',
        help_text="Current processing status"
    )
    
    # =============================================================================
    # FILE TRACKING
    # =============================================================================
    
    file_name = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        help_text="Original filename of uploaded file"
    )
    file_path = models.CharField(
        max_length=500,
        blank=True,
        null=True,
        help_text="Storage path for uploaded file"
    )
    file_size = models.BigIntegerField(
        blank=True,
        null=True,
        help_text="File size in bytes"
    )
    file_hash = models.CharField(
        max_length=64,
        blank=True,
        null=True,
        help_text="SHA256 hash for file integrity verification"
    )
    mime_type = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        help_text="MIME type of uploaded file"
    )
    
    # =============================================================================
    # PROCESSING METRICS
    # =============================================================================
    
    total_records = models.IntegerField(
        default=0,
        help_text="Total number of records to process"
    )
    successful_records = models.IntegerField(
        default=0,
        help_text="Successfully processed records"
    )
    failed_records = models.IntegerField(
        default=0,
        help_text="Records that failed processing"
    )
    skipped_records = models.IntegerField(
        default=0,
        help_text="Records skipped due to business rules"
    )
    
    # Data enrichment metrics
    fields_extracted = models.IntegerField(
        default=0,
        help_text="Number of EXTRACT fields populated"
    )
    fields_determined = models.IntegerField(
        default=0,
        help_text="Number of DETERMINE fields calculated"
    )
    fields_pending_manual = models.IntegerField(
        default=0,
        help_text="Number of DEFINE fields awaiting manual entry"
    )
    
    # Business object metrics
    shopping_centers_created = models.IntegerField(
        default=0,
        help_text="New shopping centers created"
    )
    shopping_centers_updated = models.IntegerField(
        default=0,
        help_text="Existing shopping centers updated"
    )
    tenants_created = models.IntegerField(
        default=0,
        help_text="New tenant records created"
    )
    tenants_updated = models.IntegerField(
        default=0,
        help_text="Existing tenant records updated"
    )
    
    # =============================================================================
    # TIMESTAMPS
    # =============================================================================
    
    created_at = models.DateTimeField(auto_now_add=True)
    started_at = models.DateTimeField(
        blank=True,
        null=True,
        help_text="When processing actually began"
    )
    completed_at = models.DateTimeField(
        blank=True,
        null=True,
        help_text="When processing finished (success or failure)"
    )
    
    # =============================================================================
    # USER TRACKING
    # =============================================================================
    
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_import_batches',
        help_text="User who initiated the import"
    )
    reviewed_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='reviewed_import_batches',
        help_text="User who reviewed the import results"
    )
    
    # =============================================================================
    # CONFIGURATION AND ERROR TRACKING
    # =============================================================================
    
    import_config = JSONField(
        default=dict,
        blank=True,
        help_text="Import configuration and parameters"
    )
    error_log = JSONField(
        default=dict,
        blank=True,
        help_text="Detailed error messages and stack traces"
    )
    processing_notes = models.TextField(
        blank=True,
        help_text="Human-readable processing notes and observations"
    )
    
    # =============================================================================
    # MODEL METHODS
    # =============================================================================
    
    def calculate_file_hash(self, file_content):
        """Calculate SHA256 hash of file content."""
        if isinstance(file_content, str):
            file_content = file_content.encode('utf-8')
        return hashlib.sha256(file_content).hexdigest()
    
    def get_success_rate(self):
        """Calculate processing success rate as percentage."""
        if self.total_records == 0:
            return 0.0
        return round((self.successful_records / self.total_records) * 100, 2)
    
    def get_processing_duration(self):
        """Get processing duration in seconds."""
        if self.started_at and self.completed_at:
            duration = self.completed_at - self.started_at
            return duration.total_seconds()
        return None
    
    def get_file_size_mb(self):
        """Get file size in megabytes."""
        if self.file_size:
            return round(self.file_size / (1024 * 1024), 2)
        return None
    
    def mark_started(self):
        """Mark import as started and update status."""
        self.started_at = timezone.now()
        self.status = 'PROCESSING'
        self.save()
    
    def mark_completed(self, success=True):
        """Mark import as completed with success/failure status."""
        self.completed_at = timezone.now()
        
        if success:
            if self.failed_records == 0:
                self.status = 'COMPLETED'
            else:
                self.status = 'PARTIAL'
        else:
            self.status = 'FAILED'
        
        self.save()
    
    def add_error(self, error_type, message, details=None):
        """Add error to error log."""
        if 'errors' not in self.error_log:
            self.error_log['errors'] = []
        
        error_entry = {
            'timestamp': timezone.now().isoformat(),
            'type': error_type,
            'message': message,
            'details': details or {}
        }
        
        self.error_log['errors'].append(error_entry)
        self.save()
    
    def get_summary_stats(self):
        """Get summary statistics for dashboard display."""
        return {
            'total_records': self.total_records,
            'success_rate': self.get_success_rate(),
            'processing_duration': self.get_processing_duration(),
            'file_size_mb': self.get_file_size_mb(),
            'shopping_centers_affected': self.shopping_centers_created + self.shopping_centers_updated,
            'tenants_affected': self.tenants_created + self.tenants_updated,
            'data_quality_improvement': {
                'extracted': self.fields_extracted,
                'determined': self.fields_determined,
                'pending_manual': self.fields_pending_manual
            }
        }
    
    # =============================================================================
    # MODEL CONFIGURATION
    # =============================================================================
    
    class Meta:
        db_table = 'import_batches'
        ordering = ['-created_at']
        verbose_name = 'Import Batch'
        verbose_name_plural = 'Import Batches'
        
        indexes = [
            models.Index(fields=['status', 'created_at']),
            models.Index(fields=['import_type', 'created_at']),
            models.Index(fields=['created_by']),
            models.Index(fields=['file_hash']),
        ]
    
    def __str__(self):
        return f"{self.get_import_type_display()} - {self.file_name or 'Manual'} ({self.get_status_display()})"
    
    def __repr__(self):
        return f"<ImportBatch: {self.import_type} - {self.status}>"


# =============================================================================
# DATA QUALITY FLAG MODEL
# =============================================================================

class DataQualityFlag(models.Model):
    """
    Track data quality issues without blocking imports.
    
    Implements non-blocking validation philosophy:
    - Quality issues are flagged but don't prevent import
    - Provides actionable feedback for data improvement
    - Supports progressive data enrichment workflow
    - Enables quality scoring and reporting
    
    Flag Types:
    - MISSING: Required field missing
    - INVALID: Field format/value invalid
    - SUSPICIOUS: Value seems incorrect but might be valid
    - DUPLICATE: Potential duplicate record
    - INCOMPLETE: Partial record missing related data
    - INCONSISTENT: Data conflicts with existing records
    """
    
    # =============================================================================
    # FLAG TYPE CHOICES
    # =============================================================================
    
    FLAG_TYPES = [
        ('MISSING', 'Missing Required Field'),
        ('INVALID', 'Invalid Format or Value'),
        ('SUSPICIOUS', 'Suspicious Value'),
        ('DUPLICATE', 'Potential Duplicate'),
        ('INCOMPLETE', 'Incomplete Record'),
        ('INCONSISTENT', 'Data Inconsistency'),
        ('GEOCODING', 'Geocoding Issue'),
        ('BUSINESS_RULE', 'Business Rule Violation'),
    ]
    
    SEVERITY_LEVELS = [
        (1, 'Low - Cosmetic Issue'),
        (2, 'Medium - Data Quality Impact'),
        (3, 'High - Significant Issue'),
        (4, 'Critical - Major Problem'),
        (5, 'Blocker - Must Fix'),
    ]
    
    # =============================================================================
    # CORE FIELDS
    # =============================================================================
    
    id = models.AutoField(primary_key=True)
    import_batch = models.ForeignKey(
        ImportBatch,
        on_delete=models.CASCADE,
        related_name='quality_flags',
        help_text="Import batch that generated this flag"
    )
    
    flag_type = models.CharField(
        max_length=20,
        choices=FLAG_TYPES,
        help_text="Type of quality issue"
    )
    severity = models.IntegerField(
        choices=SEVERITY_LEVELS,
        default=2,
        validators=[MinValueValidator(1), MaxValueValidator(5)],
        help_text="Issue severity level"
    )
    
    # =============================================================================
    # OBJECT REFERENCE (Polymorphic)
    # =============================================================================
    
    content_type = models.CharField(
        max_length=50,
        choices=[
            ('shopping_center', 'Shopping Center'),
            ('tenant', 'Tenant'),
            ('import_record', 'Import Record'),
        ],
        help_text="Type of object this flag applies to"
    )
    object_id = models.IntegerField(
        help_text="ID of the flagged object"
    )
    field_name = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        help_text="Specific field with the issue"
    )
    
    # =============================================================================
    # ISSUE DETAILS
    # =============================================================================
    
    message = models.TextField(
        help_text="Human-readable description of the issue"
    )
    current_value = models.CharField(
        max_length=500,
        blank=True,
        null=True,
        help_text="Current field value causing the issue"
    )
    suggested_value = models.CharField(
        max_length=500,
        blank=True,
        null=True,
        help_text="Suggested correction or improvement"
    )
    
    # Additional context
    context_data = JSONField(
        default=dict,
        blank=True,
        help_text="Additional context and debugging information"
    )
    
    # =============================================================================
    # RESOLUTION TRACKING
    # =============================================================================
    
    is_resolved = models.BooleanField(
        default=False,
        help_text="Whether this issue has been addressed"
    )
    resolved_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        help_text="User who resolved this issue"
    )
    resolved_at = models.DateTimeField(
        blank=True,
        null=True,
        help_text="When this issue was resolved"
    )
    resolution_notes = models.TextField(
        blank=True,
        help_text="Notes about how the issue was resolved"
    )
    
    # =============================================================================
    # TIMESTAMPS
    # =============================================================================
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    # =============================================================================
    # MODEL METHODS
    # =============================================================================
    
    def resolve(self, user, notes=""):
        """Mark flag as resolved."""
        self.is_resolved = True
        self.resolved_by = user
        self.resolved_at = timezone.now()
        self.resolution_notes = notes
        self.save()
    
    def get_object(self):
        """Get the flagged object instance."""
        if self.content_type == 'shopping_center':
            from properties.models import ShoppingCenter
            try:
                return ShoppingCenter.objects.get(id=self.object_id)
            except ShoppingCenter.DoesNotExist:
                return None
        elif self.content_type == 'tenant':
            from properties.models import Tenant
            try:
                return Tenant.objects.get(id=self.object_id)
            except Tenant.DoesNotExist:
                return None
        return None
    
    def get_severity_color(self):
        """Get color code for UI display based on severity."""
        colors = {
            1: '#28a745',  # Green - Low
            2: '#ffc107',  # Yellow - Medium
            3: '#fd7e14',  # Orange - High
            4: '#dc3545',  # Red - Critical
            5: '#6f42c1',  # Purple - Blocker
        }
        return colors.get(self.severity, '#6c757d')
    
    def get_age_days(self):
        """Get age of flag in days."""
        return (timezone.now() - self.created_at).days
    
    # =============================================================================
    # MODEL CONFIGURATION
    # =============================================================================
    
    class Meta:
        db_table = 'data_quality_flags'
        ordering = ['-severity', '-created_at']
        verbose_name = 'Data Quality Flag'
        verbose_name_plural = 'Data Quality Flags'
        
        indexes = [
            models.Index(fields=['content_type', 'object_id']),
            models.Index(fields=['is_resolved', 'severity']),
            models.Index(fields=['import_batch', 'flag_type']),
            models.Index(fields=['created_at']),
        ]
    
    def __str__(self):
        return f"{self.get_flag_type_display()} - {self.content_type} #{self.object_id}"
    
    def __repr__(self):
        return f"<DataQualityFlag: {self.flag_type} - Severity {self.severity}>"


# =============================================================================
# IMPORT MAPPING CONFIGURATION MODEL
# =============================================================================

class ImportMappingConfig(models.Model):
    """
    Store reusable import mapping configurations.
    
    Allows users to save column mapping configurations for different
    data sources and file formats, enabling consistent imports.
    """
    
    id = models.AutoField(primary_key=True)
    name = models.CharField(
        max_length=100,
        help_text="Descriptive name for this mapping configuration"
    )
    description = models.TextField(
        blank=True,
        help_text="Description of when to use this mapping"
    )
    
    import_type = models.CharField(
        max_length=10,
        choices=ImportBatch.IMPORT_TYPES,
        help_text="Type of import this mapping applies to"
    )
    
    # Mapping configuration
    column_mapping = JSONField(
        default=dict,
        help_text="Column name to model field mapping"
    )
    default_values = JSONField(
        default=dict,
        blank=True,
        help_text="Default values for unmapped fields"
    )
    validation_rules = JSONField(
        default=dict,
        blank=True,
        help_text="Custom validation rules for this import type"
    )
    
    # Usage tracking
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    last_used_at = models.DateTimeField(
        blank=True,
        null=True,
        help_text="When this mapping was last used"
    )
    usage_count = models.IntegerField(
        default=0,
        help_text="Number of times this mapping has been used"
    )
    
    class Meta:
        db_table = 'import_mapping_configs'
        ordering = ['-last_used_at', 'name']
        unique_together = [['name', 'import_type']]
    
    def __str__(self):
        return f"{self.name} ({self.get_import_type_display()})"


# =============================================================================
# CUSTOM MANAGERS
# =============================================================================

class ImportBatchManager(models.Manager):
    """Custom manager for ImportBatch with common queries."""
    
    def pending(self):
        """Get batches pending processing."""
        return self.filter(status='PENDING')
    
    def processing(self):
        """Get batches currently processing."""
        return self.filter(status='PROCESSING')
    
    def completed(self):
        """Get successfully completed batches."""
        return self.filter(status__in=['COMPLETED', 'PARTIAL'])
    
    def failed(self):
        """Get failed batches."""
        return self.filter(status='FAILED')
    
    def recent(self, days=30):
        """Get batches from recent days."""
        from datetime import date, timedelta
        cutoff_date = date.today() - timedelta(days=days)
        return self.filter(created_at__date__gte=cutoff_date)
    
    def by_user(self, user):
        """Get batches created by specific user."""
        return self.filter(created_by=user)


class DataQualityFlagManager(models.Manager):
    """Custom manager for DataQualityFlag with common queries."""
    
    def unresolved(self):
        """Get unresolved flags."""
        return self.filter(is_resolved=False)
    
    def high_severity(self):
        """Get high severity flags (4-5)."""
        return self.filter(severity__gte=4)
    
    def by_type(self, flag_type):
        """Get flags by type."""
        return self.filter(flag_type=flag_type)
    
    def for_shopping_center(self, shopping_center_id):
        """Get flags for specific shopping center."""
        return self.filter(
            content_type='shopping_center',
            object_id=shopping_center_id
        )
    
    def for_tenant(self, tenant_id):
        """Get flags for specific tenant."""
        return self.filter(
            content_type='tenant',
            object_id=tenant_id
        )


# Add custom managers to models
ImportBatch.add_to_class('objects', ImportBatchManager())
DataQualityFlag.add_to_class('objects', DataQualityFlagManager())


# =============================================================================
# UTILITY FUNCTIONS
# =============================================================================

def create_quality_flag(import_batch, content_type, object_id, flag_type, 
                       message, field_name=None, current_value=None, 
                       suggested_value=None, severity=2, context_data=None):
    """
    Convenience function to create quality flags during import processing.
    
    Args:
        import_batch: ImportBatch instance
        content_type: 'shopping_center' or 'tenant'
        object_id: ID of the flagged object
        flag_type: Type of flag (from FLAG_TYPES choices)
        message: Human-readable description
        field_name: Optional field name
        current_value: Optional current field value
        suggested_value: Optional suggested correction
        severity: Severity level (1-5)
        context_data: Optional additional context
    
    Returns:
        Created DataQualityFlag instance
    """
    return DataQualityFlag.objects.create(
        import_batch=import_batch,
        content_type=content_type,
        object_id=object_id,
        flag_type=flag_type,
        message=message,
        field_name=field_name,
        current_value=current_value,
        suggested_value=suggested_value,
        severity=severity,
        context_data=context_data or {}
    )


def get_import_statistics(days=30):
    """
    Get comprehensive import statistics for dashboard display.
    
    Args:
        days: Number of days to include in statistics
    
    Returns:
        Dictionary with import statistics
    """
    from datetime import date, timedelta
    cutoff_date = date.today() - timedelta(days=days)
    
    recent_batches = ImportBatch.objects.filter(created_at__date__gte=cutoff_date)
    
    stats = {
        'total_batches': recent_batches.count(),
        'completed_batches': recent_batches.filter(status__in=['COMPLETED', 'PARTIAL']).count(),
        'failed_batches': recent_batches.filter(status='FAILED').count(),
        'processing_batches': recent_batches.filter(status='PROCESSING').count(),
        'total_records_processed': recent_batches.aggregate(
            total=models.Sum('total_records')
        )['total'] or 0,
        'success_rate': 0,
        'unresolved_flags': DataQualityFlag.objects.filter(is_resolved=False).count(),
        'high_severity_flags': DataQualityFlag.objects.filter(
            is_resolved=False, severity__gte=4
        ).count(),
    }
    
    # Calculate overall success rate
    total_records = stats['total_records_processed']
    if total_records > 0:
        successful_records = recent_batches.aggregate(
            total=models.Sum('successful_records')
        )['total'] or 0
        stats['success_rate'] = round((successful_records / total_records) * 100, 2)
    
    return stats
