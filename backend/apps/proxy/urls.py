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
    path("rotation-schedules/", views.proxy_rotation_schedule_list_create),
    path(
        "rotation-schedules/<int:pk>/",
        views.proxy_rotation_schedule_detail,
    ),
]
