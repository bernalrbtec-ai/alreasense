from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

router = DefaultRouter()
router.register(r'tenants', views.TenantViewSet, basename='tenant')

urlpatterns = [
    path('company-profile/', views.company_profile, name='company-profile'),
    path('company-profile/upload-logo/', views.company_profile_upload_logo, name='company-profile-upload-logo'),
    path('', include(router.urls)),
]
