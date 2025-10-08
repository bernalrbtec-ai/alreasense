from django.urls import path
from . import views

urlpatterns = [
    path('me/', views.TenantDetailView.as_view(), name='tenant-detail'),
    path('<uuid:tenant_id>/metrics/', views.tenant_metrics, name='tenant-metrics'),
]
