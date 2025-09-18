"""
URL configuration for properties app.

This module defines the URL routing for shopping centers and tenants API endpoints.
Uses Django REST Framework's router system for automatic ViewSet URL generation
with custom action support.

URL Structure:
- /api/v1/shopping-centers/                    - Shopping center list/create
- /api/v1/shopping-centers/{id}/               - Shopping center detail/update/delete
- /api/v1/shopping-centers/{id}/tenants/       - Tenant management for specific center
- /api/v1/shopping-centers/map_bounds/         - Map integration endpoint
- /api/v1/shopping-centers/statistics/         - Dashboard analytics
- /api/v1/shopping-centers/{id}/geocode/       - Manual geocoding
- /api/v1/shopping-centers/{id}/nearby/        - Spatial queries
- /api/v1/tenants/                            - Tenant list/create (all centers)
- /api/v1/tenants/{id}/                       - Tenant detail/update/delete
- /api/v1/tenants/chains/                     - Multi-location tenant analysis
- /api/v1/tenants/categories/                 - Retail category statistics
"""

from django.urls import path, include
from rest_framework.routers import DefaultRouter
from rest_framework.urlpatterns import format_suffix_patterns

from .views import ShoppingCenterViewSet, TenantViewSet


# =============================================================================
# ROUTER CONFIGURATION
# =============================================================================

# Create main router for API endpoints
router = DefaultRouter()

# Register ViewSets with the router
router.register(r'', ShoppingCenterViewSet, basename='shopping-center')
router.register(r'tenants', TenantViewSet, basename='tenant')

# The router automatically generates these URL patterns:
#
# Shopping Center URLs (registered at root ''):
# ^$ [name='shopping-center-list']                     - GET (list), POST (create)
# ^(?P<pk>[^/.]+)/$ [name='shopping-center-detail']    - GET, PUT, PATCH, DELETE
#
# Custom Shopping Center Actions:
# ^map_bounds/$ [name='shopping-center-map-bounds']     - GET
# ^statistics/$ [name='shopping-center-statistics']    - GET  
# ^(?P<pk>[^/.]+)/geocode/$ [name='shopping-center-geocode'] - POST
# ^(?P<pk>[^/.]+)/nearby/$ [name='shopping-center-nearby']   - GET
# ^(?P<pk>[^/.]+)/tenants/$ [name='shopping-center-tenants'] - GET, POST
#
# Tenant URLs:
# ^tenants/$ [name='tenant-list']                       - GET (list), POST (create)
# ^tenants/(?P<pk>[^/.]+)/$ [name='tenant-detail']      - GET, PUT, PATCH, DELETE
#
# Custom Tenant Actions:
# ^tenants/chains/$ [name='tenant-chains']              - GET
# ^tenants/categories/$ [name='tenant-categories']      - GET


# =============================================================================
# CUSTOM URL PATTERNS
# =============================================================================

# Additional custom patterns that don't fit the standard ViewSet routing
custom_patterns = [
    # No additional custom patterns needed - all endpoints handled by ViewSets
]


# =============================================================================
# MAIN URL PATTERNS
# =============================================================================

urlpatterns = [
    # Include router URLs
    path('', include(router.urls)),
    
    # Include custom URL patterns
    *custom_patterns,
]

# Apply format suffix patterns for content negotiation
# Allows URLs like /api/v1/shopping-centers/1.json or /api/v1/shopping-centers/1.xml
urlpatterns = format_suffix_patterns(urlpatterns)


# =============================================================================
# URL PATTERN DOCUMENTATION
# =============================================================================

"""
Complete API Endpoint Reference:
================================

SHOPPING CENTER ENDPOINTS:
--------------------------

1. List/Create Shopping Centers
   GET  /api/v1/shopping-centers/
   POST /api/v1/shopping-centers/
   
   Query Parameters for GET:
   - search: Search across name, city, owner, property manager
   - center_type: Filter by center type
   - address_city: Filter by city (exact or contains)
   - address_state: Filter by state
   - data_quality_score__gte: Minimum quality score
   - total_gla__gte / total_gla__lte: GLA range filtering
   - owner: Filter by owner (exact or contains)
   - property_manager: Filter by property manager
   - has_coordinates: true/false - filter geocoded centers
   - min_tenants: Minimum number of tenants
   - ordering: Sort by field (shopping_center_name, data_quality_score, total_gla)
   - page: Page number for pagination
   - page_size: Results per page (max 200)

2. Shopping Center Details
   GET    /api/v1/shopping-centers/{id}/
   PUT    /api/v1/shopping-centers/{id}/
   PATCH  /api/v1/shopping-centers/{id}/
   DELETE /api/v1/shopping-centers/{id}/

3. Map Integration
   GET /api/v1/shopping-centers/map_bounds/
   
   Required Query Parameters:
   - north: Northern latitude boundary
   - south: Southern latitude boundary  
   - east: Eastern longitude boundary
   - west: Western longitude boundary
   
   Optional Query Parameters:
   - zoom_level: Map zoom level for result optimization (default: 10)
   - All standard filtering parameters apply

4. Dashboard Statistics
   GET /api/v1/shopping-centers/statistics/
   
   Returns:
   - Total counts (centers, tenants)
   - GLA statistics (total, average)
   - Quality score metrics
   - Centers by type breakdown
   - Top owners list
   - Recent additions count
   - Geocoding completion percentage

5. Manual Geocoding
   POST /api/v1/shopping-centers/{id}/geocode/
   
   Triggers geocoding for a specific shopping center.

6. Nearby Centers (Spatial Query)
   GET /api/v1/shopping-centers/{id}/nearby/
   
   Query Parameters:
   - radius: Search radius in kilometers (default: 10, max: 100)
   - limit: Maximum results (default: 20, max: 50)

7. Tenant Management for Specific Center
   GET  /api/v1/shopping-centers/{id}/tenants/
   POST /api/v1/shopping-centers/{id}/tenants/
   
   Query Parameters for GET:
   - retail_category: Filter by category
   - occupancy_status: Filter by status (OCCUPIED, VACANT, PENDING, UNKNOWN)
   - expiring_soon: true - show leases expiring within 12 months
   - ordering: Sort by tenant_name, tenant_suite_number, square_footage, base_rent


TENANT ENDPOINTS:
-----------------

1. List/Create Tenants (All Centers)
   GET  /api/v1/tenants/
   POST /api/v1/tenants/
   
   Query Parameters for GET:
   - search: Search across tenant name, shopping center, retail category
   - shopping_center: Filter by shopping center ID
   - occupancy_status: Filter by status
   - is_anchor: Filter anchor tenants (true/false)
   - ownership_type: Filter by ownership type
   - retail_category__contains: Filter by retail category
   - square_footage__gte / square_footage__lte: Size range filtering
   - base_rent__gte / base_rent__lte: Rent range filtering
   - lease_expiring: Number of months ahead to check for lease expiration
   - ordering: Sort by various fields

2. Tenant Details
   GET    /api/v1/tenants/{id}/
   PUT    /api/v1/tenants/{id}/
   PATCH  /api/v1/tenants/{id}/
   DELETE /api/v1/tenants/{id}/

3. Tenant Chain Analysis
   GET /api/v1/tenants/chains/
   
   Returns tenants that appear in multiple shopping centers with:
   - Location count
   - Total square footage across all locations
   - Detailed location information

4. Retail Category Statistics
   GET /api/v1/tenants/categories/
   
   Returns breakdown of tenants by retail category with:
   - Tenant count per category
   - Total square footage per category
   - Shopping center count per category


RESPONSE FORMATS:
-----------------

All endpoints return JSON responses with consistent structure:

Success Response:
{
  "count": 123,
  "next": "http://example.com/api/v1/shopping-centers/?page=3",
  "previous": "http://example.com/api/v1/shopping-centers/?page=1", 
  "results": [...]
}

Error Response:
{
  "error": true,
  "message": "Description of error",
  "details": {...},
  "status_code": 400
}


AUTHENTICATION:
---------------

- GET requests: No authentication required (public read access)
- POST/PUT/PATCH/DELETE: JWT token required
- Token format: Authorization: Bearer <token>
- Get token: POST /api/v1/auth/token/ with username/password


CONTENT TYPE SUPPORT:
---------------------

All endpoints support content negotiation:
- Default: application/json
- Available: application/json, application/xml
- Request format: Accept: application/json
- URL suffix: .json, .xml (e.g., /api/v1/shopping-centers/1.json)


RATE LIMITING:
--------------

- Public endpoints: 1000 requests/hour per IP
- Authenticated endpoints: 5000 requests/hour per user
- Map endpoints: 500 requests/hour per IP (performance-intensive)
- Statistics endpoint: 100 requests/hour per IP (cached responses)


ERROR CODES:
------------

- 200: Success
- 201: Created
- 400: Bad Request (validation errors)
- 401: Unauthorized (authentication required)
- 403: Forbidden (insufficient permissions)
- 404: Not Found
- 429: Too Many Requests (rate limited)
- 500: Internal Server Error


PAGINATION:
-----------

Default pagination: 50 items per page
- Query parameter: ?page=2
- Custom page size: ?page_size=100 (max 200 for regular endpoints, 1000 for map)
- Response includes: count, next, previous, results


EXAMPLES:
---------

1. Get shopping centers in Philadelphia:
   GET /api/v1/shopping-centers/?address_city=Philadelphia&address_state=PA

2. Get high-quality centers with large GLA:
   GET /api/v1/shopping-centers/?data_quality_score__gte=80&total_gla__gte=100000

3. Find centers for map display:
   GET /api/v1/shopping-centers/map_bounds/?north=40.1&south=39.9&east=-75.0&west=-75.2

4. Get all Starbucks locations:
   GET /api/v1/tenants/?search=Starbucks

5. Find tenants with expiring leases:
   GET /api/v1/tenants/?lease_expiring=6

6. Get dashboard statistics:
   GET /api/v1/shopping-centers/statistics/
"""

# =============================================================================
# URL NAME REFERENCE
# =============================================================================

"""
URL Names for Reverse Lookups:
===============================

Shopping Centers:
- shopping-center-list
- shopping-center-detail  
- shopping-center-map-bounds
- shopping-center-statistics
- shopping-center-geocode
- shopping-center-nearby
- shopping-center-tenants

Tenants:
- tenant-list
- tenant-detail
- tenant-chains
- tenant-categories

Usage in Django:
from django.urls import reverse
url = reverse('shopping-center-detail', kwargs={'pk': 1})

Usage in DRF:
from rest_framework.reverse import reverse
url = reverse('shopping-center-list', request=request)
"""

# =============================================================================
# TESTING URLS
# =============================================================================

"""
Quick Test Commands:
====================

# Test basic endpoints
curl http://localhost:8000/api/v1/shopping-centers/
curl http://localhost:8000/api/v1/shopping-centers/1/
curl http://localhost:8000/api/v1/shopping-centers/statistics/
curl http://localhost:8000/api/v1/tenants/
curl http://localhost:8000/api/v1/tenants/chains/

# Test filtering
curl "http://localhost:8000/api/v1/shopping-centers/?address_city=Chester"
curl "http://localhost:8000/api/v1/tenants/?search=Starbucks"

# Test map bounds
curl "http://localhost:8000/api/v1/shopping-centers/map_bounds/?north=40.1&south=39.9&east=-75.0&west=-75.2"

# Create shopping center (requires authentication)
curl -X POST http://localhost:8000/api/v1/shopping-centers/ \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"shopping_center_name": "Test Plaza", "address_city": "Philadelphia"}'
"""
