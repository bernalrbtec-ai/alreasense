"""
URLs do app proxy.
"""
from django.urls import path

from . import views

urlpatterns = [
    path("overview/", views.proxy_overview),
    path("rotate/", views.proxy_rotate),
    path("rotation-history/", views.proxy_rotation_history),
    path("statistics/", views.proxy_statistics),
]
