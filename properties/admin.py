# properties/admin.py
# Backend Architect: Django 5.0 compatible GIS admin implementation
# Modern approach - no OSMGeoAdmin needed

from django.contrib import admin
from django.contrib.gis import admin as gis_admin
from .models import ShoppingCenter, Tenant


@admin.register(ShoppingCenter)
class ShoppingCenterAdmin(admin.ModelAdmin):
    """
    Modern Django 5.0 admin for ShoppingCenter with GIS support
    Geographic fields automatically get appropriate widgets
    """
    
    list_display = [
        'shopping_center_name', 
        'address_city', 
        'address_state',
        'center_type',
        'total_gla',
        'data_quality_score',
        'created_at'
    ]
    
    list_filter = [
        'center_type',
        'address_state',
        'address_city',
        'data_quality_score',
        'created_at'
    ]
    
    search_fields = [
        'shopping_center_name',
        'address_street',
        'address_city',
        'owner',
        'property_manager'
    ]
    
    readonly_fields = [
        'id',
        'calculated_gla',
        'data_quality_score',
        'created_at',
        'updated_at'
    ]
    
    fieldsets = (
        ('Basic Information', {
            'fields': (
                'shopping_center_name',
                'center_type',
                'data_quality_score'
            )
        }),
        ('Address & Location', {
            'fields': (
                'address_street',
                'address_city', 
                'address_state',
                'address_zip',
                'latitude',
                'longitude'
            ),
            'description': 'Geographic fields will show map widgets automatically'
        }),
        ('Property Details', {
            'fields': (
                'total_gla',
                'calculated_gla',
                'year_built'
            )
        }),
        ('Management & Ownership', {
            'fields': (
                'owner',
                'property_manager',
                'leasing_agent',
                'leasing_brokerage'
            )
        }),
        ('Administrative Details', {
            'fields': (
                'county',
                'municipality', 
                'zoning_authority'
            )
        }),
        ('Contact Information', {
            'fields': (
                'contact_name',
                'contact_phone',
                'contact_email'
            )
        }),
        ('Import Tracking', {
            'fields': (
                'import_batch',
                'last_import_batch',
                'created_at',
                'updated_at'
            ),
            'classes': ('collapse',)
        })
    )
    
    # Enable facet counts (Django 5.0 feature)
    show_facets = admin.ShowFacets.ALWAYS
    
    # Optimize database queries
    list_select_related = ['import_batch', 'last_import_batch']


@admin.register(Tenant)
class TenantAdmin(admin.ModelAdmin):
    """
    Modern Django 5.0 admin for Tenant management
    """
    
    list_display = [
        'tenant_name',
        'shopping_center',
        'tenant_suite_number', 
        'square_footage',
        'retail_category',
        'lease_status'
    ]
    
    list_filter = [
        'retail_category',
        'ownership_type',
        'lease_status',
        'credit_category',
        'shopping_center__center_type',
        'shopping_center__address_state'
    ]
    
    search_fields = [
        'tenant_name',
        'tenant_suite_number',
        'shopping_center__shopping_center_name',
        'shopping_center__address_city'
    ]
    
    readonly_fields = [
        'id', 
        'created_at', 
        'updated_at'
    ]
    
    fieldsets = (
        ('Tenant Information', {
            'fields': (
                'tenant_name',
                'shopping_center',
                'tenant_suite_number'
            )
        }),
        ('Space Details', {
            'fields': (
                'square_footage',
                'retail_category',
                'ownership_type'
            )
        }),
        ('Lease Information', {
            'fields': (
                'lease_status',
                'base_rent',
                'lease_term',
                'lease_commence',
                'lease_expiration',
                'credit_category'
            )
        }),
        ('Contact Information', {
            'fields': (
                'contact_name',
                'contact_phone',
                'contact_email'
            )
        }),
        ('Import Tracking', {
            'fields': (
                'import_batch',
                'last_import_batch',
                'created_at',
                'updated_at'
            ),
            'classes': ('collapse',)
        })
    )
    
    # Enable facet counts (Django 5.0 feature)
    show_facets = admin.ShowFacets.ALWAYS
    
    # Optimize database queries
    list_select_related = ['shopping_center', 'import_batch', 'last_import_batch']
    
    # Custom admin actions
    actions = ['mark_lease_active', 'mark_lease_expired']
    
    def mark_lease_active(self, request, queryset):
        queryset.update(lease_status='ACTIVE')
        self.message_user(request, f"Marked {queryset.count()} tenants as active")
    mark_lease_active.short_description = "Mark selected tenants as active"
    
    def mark_lease_expired(self, request, queryset):
        queryset.update(lease_status='EXPIRED') 
        self.message_user(request, f"Marked {queryset.count()} tenants as expired")
    mark_lease_expired.short_description = "Mark selected tenants as expired"


# Optional: Import batch admin if you want to manage import history
try:
    from imports.models import ImportBatch
    
    @admin.register(ImportBatch)
    class ImportBatchAdmin(admin.ModelAdmin):
        list_display = [
            'id',
            'import_type', 
            'status',
            'file_name',
            'total_records',
            'created_at'
        ]
        
        list_filter = [
            'import_type',
            'status', 
            'created_at'
        ]
        
        readonly_fields = [
            'id',
            'created_at',
            'updated_at'
        ]
        
        show_facets = admin.ShowFacets.ALWAYS

except ImportError:
    # ImportBatch model not available yet
    pass
