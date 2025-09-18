"""
Properties Views - Shop Window Backend API
Django REST Framework views for shopping centers and tenants.

Implements OpenAPI 3.0 specification from shopwindow-api-spec.txt
"""

from django.db import transaction
from django.db.models import Q, Count, Avg, Sum
from django.db.models.functions import Distance
from django.shortcuts import get_object_or_404
from django.contrib.gis.measure import D
from django.contrib.gis.geos import Point
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from django.utils import timezone

from rest_framework import status, generics, filters
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.pagination import PageNumberPagination
from rest_framework.viewsets import ModelViewSet
from rest_framework.decorators import action

from django_filters.rest_framework import DjangoFilterBackend

from .models import ShoppingCenter, Tenant
from .serializers import (
    ShoppingCenterSerializer,
    ShoppingCenterDetailSerializer,
    ShoppingCenterCreateSerializer,
    TenantSerializer,
    TenantCreateSerializer
)
from .filters import ShoppingCenterFilter, TenantFilter
from services.business_logic import calculate_center_type, calculate_data_quality_score
from services.geocoding import geocode_address


# =============================================================================
# PAGINATION CONFIGURATION
# =============================================================================

class StandardResultsSetPagination(PageNumberPagination):
    """Standard pagination for API responses"""
    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 100


# =============================================================================
# SHOPPING CENTER VIEWS
# =============================================================================

class ShoppingCenterViewSet(ModelViewSet):
    """
    ViewSet for shopping center CRUD operations.
    
    Provides:
    - GET /api/v1/shopping-centers/ - List with filtering and search
    - POST /api/v1/shopping-centers/ - Create new shopping center
    - GET /api/v1/shopping-centers/{id}/ - Retrieve specific center
    - PATCH /api/v1/shopping-centers/{id}/ - Partial update
    - DELETE /api/v1/shopping-centers/{id}/ - Delete center
    
    Business Rules:
    - Shopping center names must be unique
    - Progressive data enrichment (all fields optional except name)
    - Auto-calculate center_type from total_gla
    - Auto-geocode from address fields
    """
    
    queryset = ShoppingCenter.objects.all().order_by('-updated_at')
    pagination_class = StandardResultsSetPagination
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_class = ShoppingCenterFilter
    search_fields = [
        'shopping_center_name',
        'address_city',
        'address_state',
        'owner',
        'property_manager'
    ]
    ordering_fields = [
        'shopping_center_name',
        'total_gla',
        'data_quality_score',
        'created_at',
        'updated_at'
    ]
    
    def get_serializer_class(self):
        """Return appropriate serializer based on action"""
        if self.action == 'list':
            return ShoppingCenterSerializer
        elif self.action == 'create':
            return ShoppingCenterCreateSerializer
        elif self.action == 'retrieve':
            return ShoppingCenterDetailSerializer
        else:
            return ShoppingCenterSerializer
    
    def get_queryset(self):
        """
        Optimize queryset with prefetch_related for tenants
        Add spatial filtering for map bounds if provided
        """
        queryset = ShoppingCenter.objects.prefetch_related('tenants').select_related('import_batch')
        
        # Map bounds filtering for frontend map interface
        bounds = self.request.query_params.get('bounds')
        if bounds:
            try:
                # Format: "sw_lat,sw_lng,ne_lat,ne_lng"
                sw_lat, sw_lng, ne_lat, ne_lng = map(float, bounds.split(','))
                queryset = queryset.filter(
                    latitude__gte=sw_lat,
                    latitude__lte=ne_lat,
                    longitude__gte=sw_lng,
                    longitude__lte=ne_lng
                )
            except (ValueError, TypeError):
                pass  # Invalid bounds format, return all
        
        return queryset.order_by('-updated_at')
    
    def perform_create(self, serializer):
        """
        Custom create logic with business rules:
        - Enforce shopping center name uniqueness
        - Auto-calculate center_type from GLA
        - Auto-geocode from address
        - Calculate initial quality score
        """
        with transaction.atomic():
            # Check for existing shopping center with same name
            name = serializer.validated_data.get('shopping_center_name')
            if ShoppingCenter.objects.filter(shopping_center_name=name).exists():
                return Response(
                    {'error': f'Shopping center "{name}" already exists'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Auto-calculate center_type from GLA
            gla = serializer.validated_data.get('total_gla')
            if gla:
                serializer.validated_data['center_type'] = calculate_center_type(gla)
            
            # Auto-geocode from address fields
            address_fields = [
                serializer.validated_data.get('address_street'),
                serializer.validated_data.get('address_city'),
                serializer.validated_data.get('address_state'),
                serializer.validated_data.get('address_zip')
            ]
            
            if any(address_fields):
                full_address = ', '.join(filter(None, address_fields))
                try:
                    lat, lng = geocode_address(full_address)
                    serializer.validated_data['latitude'] = lat
                    serializer.validated_data['longitude'] = lng
                except Exception as e:
                    # Geocoding failed, log but don't block creation
                    print(f"Geocoding failed for {full_address}: {str(e)}")
            
            # Save the instance
            instance = serializer.save()
            
            # Calculate initial data quality score
            instance.data_quality_score = calculate_data_quality_score(instance)
            instance.save(update_fields=['data_quality_score'])
    
    def perform_update(self, serializer):
        """
        Custom update logic with progressive enrichment:
        - Recalculate center_type if GLA changes
        - Re-geocode if address changes
        - Update quality score
        """
        with transaction.atomic():
            # Get the existing instance
            instance = self.get_object()
            
            # Check if GLA changed, recalculate center_type
            new_gla = serializer.validated_data.get('total_gla')
            if new_gla and new_gla != instance.total_gla:
                serializer.validated_data['center_type'] = calculate_center_type(new_gla)
            
            # Check if address changed, re-geocode
            address_fields = ['address_street', 'address_city', 'address_state', 'address_zip']
            address_changed = any(
                serializer.validated_data.get(field) != getattr(instance, field)
                for field in address_fields
                if field in serializer.validated_data
            )
            
            if address_changed:
                address_parts = [
                    serializer.validated_data.get('address_street', instance.address_street),
                    serializer.validated_data.get('address_city', instance.address_city),
                    serializer.validated_data.get('address_state', instance.address_state),
                    serializer.validated_data.get('address_zip', instance.address_zip)
                ]
                full_address = ', '.join(filter(None, address_parts))
                
                try:
                    lat, lng = geocode_address(full_address)
                    serializer.validated_data['latitude'] = lat
                    serializer.validated_data['longitude'] = lng
                except Exception as e:
                    print(f"Re-geocoding failed for {full_address}: {str(e)}")
            
            # Save the instance
            updated_instance = serializer.save()
            
            # Recalculate data quality score
            updated_instance.data_quality_score = calculate_data_quality_score(updated_instance)
            updated_instance.save(update_fields=['data_quality_score'])
    
    @action(detail=True, methods=['get'])
    def tenants(self, request, pk=None):
        """
        Get all tenants for a specific shopping center
        GET /api/v1/shopping-centers/{id}/tenants/
        """
        shopping_center = self.get_object()
        tenants = shopping_center.tenants.all()
        
        # Apply tenant filtering if provided
        tenant_filter = TenantFilter(request.GET, queryset=tenants)
        filtered_tenants = tenant_filter.qs
        
        # Paginate results
        paginator = StandardResultsSetPagination()
        page = paginator.paginate_queryset(filtered_tenants, request)
        
        serializer = TenantSerializer(page, many=True)
        return paginator.get_paginated_response(serializer.data)
    
    @action(detail=True, methods=['post'])
    def add_tenant(self, request, pk=None):
        """
        Add a tenant to a specific shopping center
        POST /api/v1/shopping-centers/{id}/tenants/
        """
        shopping_center = self.get_object()
        
        # Create tenant with shopping center relationship
        serializer = TenantCreateSerializer(data=request.data)
        if serializer.is_valid():
            with transaction.atomic():
                tenant = serializer.save(shopping_center=shopping_center)
                
                # Recalculate shopping center quality score
                shopping_center.data_quality_score = calculate_data_quality_score(shopping_center)
                shopping_center.save(update_fields=['data_quality_score'])
                
                return Response(
                    TenantSerializer(tenant).data,
                    status=status.HTTP_201_CREATED
                )
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=True, methods=['get'])
    def analytics(self, request, pk=None):
        """
        Get analytics summary for a shopping center
        GET /api/v1/shopping-centers/{id}/analytics/
        """
        shopping_center = self.get_object()
        tenants = shopping_center.tenants.all()
        
        analytics_data = {
            'total_tenants': tenants.count(),
            'occupied_tenants': tenants.filter(occupancy_status='OCCUPIED').count(),
            'vacant_suites': tenants.filter(occupancy_status='VACANT').count(),
            'total_leased_sf': tenants.aggregate(total_sf=Sum('square_footage'))['total_sf'] or 0,
            'occupancy_rate': 0,
            'anchor_tenants': tenants.filter(is_anchor=True).count(),
            'retail_categories': list(
                tenants.exclude(retail_category__isnull=True)
                .values_list('retail_category', flat=True)
            )
        }
        
        # Calculate occupancy rate
        if shopping_center.total_gla:
            analytics_data['occupancy_rate'] = round(
                (analytics_data['total_leased_sf'] / shopping_center.total_gla) * 100, 2
            )
        
        return Response(analytics_data)


# =============================================================================
# TENANT VIEWS
# =============================================================================

class TenantViewSet(ModelViewSet):
    """
    ViewSet for tenant CRUD operations.
    
    Provides:
    - GET /api/v1/tenants/ - List all tenants with filtering
    - POST /api/v1/tenants/ - Create new tenant
    - GET /api/v1/tenants/{id}/ - Retrieve specific tenant
    - PATCH /api/v1/tenants/{id}/ - Partial update
    - DELETE /api/v1/tenants/{id}/ - Delete tenant
    
    Business Rules:
    - Tenants can exist in multiple shopping centers
    - Suite numbers must be unique within a center
    """
    
    queryset = Tenant.objects.all().order_by('-updated_at')
    serializer_class = TenantSerializer
    pagination_class = StandardResultsSetPagination
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_class = TenantFilter
    search_fields = ['tenant_name', 'retail_category']
    ordering_fields = ['tenant_name', 'square_footage', 'base_rent', 'created_at']
    
    def get_queryset(self):
        """Optimize queryset with shopping center relationship"""
        return Tenant.objects.select_related('shopping_center').order_by('-updated_at')
    
    def get_serializer_class(self):
        """Return appropriate serializer based on action"""
        if self.action == 'create':
            return TenantCreateSerializer
        return TenantSerializer


# =============================================================================
# HEALTH CHECK AND UTILITY VIEWS
# =============================================================================

@api_view(['GET'])
def health_check(request):
    """
    Health check endpoint for monitoring and load balancers
    GET /api/v1/health/
    """
    try:
        # Test database connectivity
        shopping_center_count = ShoppingCenter.objects.count()
        tenant_count = Tenant.objects.count()
        
        health_data = {
            'status': 'healthy',
            'service': 'shopwindow-backend',
            'database': 'connected',
            'data': {
                'shopping_centers': shopping_center_count,
                'tenants': tenant_count
            },
            'timestamp': timezone.now().isoformat()
        }
        
        return Response(health_data, status=status.HTTP_200_OK)
    
    except Exception as e:
        error_data = {
            'status': 'unhealthy',
            'service': 'shopwindow-backend',
            'error': str(e),
            'timestamp': timezone.now().isoformat()
        }
        
        return Response(error_data, status=status.HTTP_503_SERVICE_UNAVAILABLE)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def api_info(request):
    """
    API information and statistics
    GET /api/v1/info/
    """
    from django.conf import settings
    
    info_data = {
        'api_version': 'v1',
        'service': 'Shop Window Backend',
        'django_version': settings.DJANGO_VERSION if hasattr(settings, 'DJANGO_VERSION') else 'Unknown',
        'database': {
            'shopping_centers': ShoppingCenter.objects.count(),
            'tenants': Tenant.objects.count(),
            'latest_import': 'Not implemented yet'  # TODO: Add import batch info
        },
        'features': {
            'spatial_queries': True,
            'geocoding': True,
            'progressive_enrichment': True,
            'data_quality_scoring': True
        }
    }
    
    return Response(info_data)


# =============================================================================
# SPATIAL QUERY VIEWS
# =============================================================================

@api_view(['GET'])
def nearby_properties(request):
    """
    Find shopping centers near a point
    GET /api/v1/nearby/?lat={lat}&lng={lng}&radius={miles}
    """
    try:
        lat = float(request.GET.get('lat'))
        lng = float(request.GET.get('lng'))
        radius_miles = float(request.GET.get('radius', 10))  # Default 10 miles
        
        # Create point and find nearby properties
        point = Point(lng, lat, srid=4326)  # Note: Point(lng, lat) order
        
        # Filter properties with coordinates and calculate distance
        nearby = ShoppingCenter.objects.filter(
            latitude__isnull=False,
            longitude__isnull=False
        ).extra(
            select={
                'distance': """
                    ST_Distance(
                        ST_MakePoint(longitude, latitude)::geography,
                        ST_MakePoint(%s, %s)::geography
                    ) / 1609.34
                """  # Convert meters to miles
            },
            select_params=[lng, lat]
        ).extra(
            where=['ST_Distance(ST_MakePoint(longitude, latitude)::geography, ST_MakePoint(%s, %s)::geography) / 1609.34 <= %s'],
            params=[lng, lat, radius_miles]
        ).order_by('distance')[:50]  # Limit to 50 results
        
        serializer = ShoppingCenterSerializer(nearby, many=True)
        return Response({
            'count': len(nearby),
            'radius_miles': radius_miles,
            'center_point': {'lat': lat, 'lng': lng},
            'results': serializer.data
        })
    
    except (ValueError, TypeError) as e:
        return Response(
            {'error': 'Invalid coordinates or radius provided'},
            status=status.HTTP_400_BAD_REQUEST
        )
    except Exception as e:
        return Response(
            {'error': f'Spatial query failed: {str(e)}'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


# =============================================================================
# IMPORT VIEWS (Sprint 2 preparation)
# =============================================================================

# TODO: Implement in Sprint 2
# @api_view(['POST'])
# @permission_classes([IsAuthenticated])
# def import_csv(request):
#     """CSV import endpoint - Sprint 2"""
#     pass

# @api_view(['POST']) 
# @permission_classes([IsAuthenticated])
# def import_pdf(request):
#     """PDF import endpoint - Sprint 2"""
#     pass
