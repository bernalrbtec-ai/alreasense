from django.urls import path
from . import views

urlpatterns = [
    path('account/', views.PaymentAccountView.as_view(), name='payment-account'),
    path('info/', views.billing_info, name='billing-info'),
    path('checkout/', views.create_checkout_session, name='create-checkout'),
    path('portal/', views.create_portal_session, name='create-portal'),
    path('history/', views.billing_history, name='billing-history'),
]
