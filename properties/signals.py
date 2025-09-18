# properties/signals.py
# Backend Architect: Django signals for ShoppingCenter and Tenant models
# Handles automated data quality scoring and relationship management

from django.db.models.signals import pre_save, post_save, post_delete
from django.dispatch import receiver
from .models import ShoppingCenter, Tenant


@receiver(pre_save, sender=ShoppingCenter)
def calculate_shopping_center_quality_score(sender, instance, **kwargs):
    """
    Calculate data quality score before saving ShoppingCenter
    Implements EXTRACT → DETERMINE → DEFINE quality methodology
    """
    score = 0
    
    # EXTRACT fields (40% of total score)
    extract_fields = {
        'shopping_center_name': 5,
        'address_street': 3,
        'address_city': 3, 
        'address_state': 3,
        'address_zip': 3,
        'contact_name': 2,
        'contact_phone': 2,
        'total_gla': 4,
    }
    
    for field_name, weight in extract_fields.items():
        if getattr(instance, field_name, None):
            score += weight
    
    # DETERMINE fields (20% of total score)  
    determine_fields = {
        'center_type': 8,
        'latitude': 6,
        'longitude': 6,
    }
    
    for field_name, weight in determine_fields.items():
        if getattr(instance, field_name, None):
            score += weight
            
    # DEFINE fields (40% of total score)
    define_fields = {
        'owner': 8,
        'property_manager': 8,
        'county': 4,
        'municipality': 4,
        'zoning_authority': 4,
        'year_built': 4,
        'leasing_agent': 4,
        'leasing_brokerage': 4,
    }
    
    for field_name, weight in define_fields.items():
        if getattr(instance, field_name, None):
            score += weight
    
    # Cap at 100 and set the score
    instance.data_quality_score = min(score, 100)


@receiver(post_save, sender=ShoppingCenter)
def update_calculated_gla(sender, instance, created, **kwargs):
    """
    Update calculated_gla based on tenant square_footage sum
    Only runs if total_gla is not manually set
    """
    if not instance.total_gla:
        # Calculate GLA from tenant data
        from django.db.models import Sum
        tenant_total = instance.tenants.aggregate(
            total_sf=Sum('square_footage')
        )['total_sf']
        
        if tenant_total:
            instance.calculated_gla = tenant_total
            # Avoid infinite loop by using update() instead of save()
            ShoppingCenter.objects.filter(id=instance.id).update(
                calculated_gla=tenant_total
            )


@receiver(post_save, sender=Tenant)
@receiver(post_delete, sender=Tenant) 
def recalculate_shopping_center_gla(sender, instance, **kwargs):
    """
    Recalculate shopping center GLA when tenants are added/removed/updated
    Maintains data integrity for calculated fields
    """
    if instance.shopping_center and not instance.shopping_center.total_gla:
        from django.db.models import Sum
        
        tenant_total = instance.shopping_center.tenants.aggregate(
            total_sf=Sum('square_footage')
        )['total_sf']
        
        # Update calculated_gla using update() to avoid signal loops
        ShoppingCenter.objects.filter(id=instance.shopping_center.id).update(
            calculated_gla=tenant_total or 0
        )


@receiver(post_save, sender=Tenant)
def update_shopping_center_quality_score_on_tenant_change(sender, instance, **kwargs):
    """
    Recalculate shopping center quality score when tenant data changes
    Tenant count and details affect the shopping center's data quality
    """
    if instance.shopping_center:
        # Trigger quality score recalculation
        shopping_center = instance.shopping_center
        shopping_center.save()  # This will trigger pre_save signal


# Optional: Logging signals for audit trail
@receiver(post_save, sender=ShoppingCenter)
def log_shopping_center_changes(sender, instance, created, **kwargs):
    """
    Log shopping center creation/updates for audit trail
    """
    if created:
        print(f"DEBUG: Created new shopping center: {instance.shopping_center_name}")
    else:
        print(f"DEBUG: Updated shopping center: {instance.shopping_center_name} (Quality Score: {instance.data_quality_score})")


@receiver(post_save, sender=Tenant)
def log_tenant_changes(sender, instance, created, **kwargs):
    """
    Log tenant creation/updates for audit trail  
    """
    if created:
        print(f"DEBUG: Added tenant {instance.tenant_name} to {instance.shopping_center.shopping_center_name}")
    else:
        print(f"DEBUG: Updated tenant {instance.tenant_name} in {instance.shopping_center.shopping_center_name}")


# Business rule enforcement signals
@receiver(pre_save, sender=Tenant)
def validate_tenant_business_rules(sender, instance, **kwargs):
    """
    Enforce business rules before saving tenants
    """
    # Ensure square_footage is positive
    if instance.square_footage and instance.square_footage <= 0:
        raise ValueError("Tenant square footage must be positive")
    
    # Normalize retail category
    if instance.retail_category:
        instance.retail_category = instance.retail_category.strip().title()


@receiver(pre_save, sender=ShoppingCenter) 
def validate_shopping_center_business_rules(sender, instance, **kwargs):
    """
    Enforce business rules before saving shopping centers
    """
    # Ensure shopping center name is unique (case-insensitive)
    if instance.shopping_center_name:
        instance.shopping_center_name = instance.shopping_center_name.strip()
        
        # Check for existing shopping center with same name (excluding current instance)
        existing = ShoppingCenter.objects.filter(
            shopping_center_name__iexact=instance.shopping_center_name
        ).exclude(id=instance.id).exists()
        
        if existing:
            raise ValueError(f"Shopping center '{instance.shopping_center_name}' already exists")
    
    # Normalize address fields
    if instance.address_city:
        instance.address_city = instance.address_city.strip().title()
    if instance.address_state:
        instance.address_state = instance.address_state.strip().upper()
