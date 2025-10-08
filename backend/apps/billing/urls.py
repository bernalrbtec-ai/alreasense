from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

router = DefaultRouter()
router.register(r'plans', views.PlanViewSet, basename='plan')

urlpatterns = [
    path('', include(router.urls)),
    path('account/', views.PaymentAccountView.as_view(), name='payment-account'),
    path('info/', views.billing_info, name='billing-info'),
    path('checkout/', views.create_checkout_session, name='create-checkout'),
    path('portal/', views.create_portal_session, name='create-portal'),
    path('history/', views.billing_history, name='billing-history'),
]
