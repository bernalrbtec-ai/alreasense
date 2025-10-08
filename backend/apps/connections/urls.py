from django.urls import path
from . import views

urlpatterns = [
    path('', views.EvolutionConnectionListCreateView.as_view(), name='connection-list'),
    path('<int:pk>/', views.EvolutionConnectionDetailView.as_view(), name='connection-detail'),
    path('<int:pk>/test/', views.test_connection, name='connection-test'),
    path('<int:pk>/toggle/', views.toggle_connection, name='connection-toggle'),
]
