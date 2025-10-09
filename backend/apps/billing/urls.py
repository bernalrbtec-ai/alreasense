"""
URLs para o sistema de billing
"""

from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .views import (
    ProductViewSet,
    PlanViewSet,
    TenantProductViewSet,
    BillingHistoryViewSet,
    TenantBillingViewSet
)

router = DefaultRouter()
router.register(r'products', ProductViewSet, basename='product')
router.register(r'plans', PlanViewSet, basename='plan')
router.register(r'tenant-products', TenantProductViewSet, basename='tenant-product')
router.register(r'history', BillingHistoryViewSet, basename='billing-history')
router.register(r'billing', TenantBillingViewSet, basename='tenant-billing')

urlpatterns = [
    path('', include(router.urls)),
]
