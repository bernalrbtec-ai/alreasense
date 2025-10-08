from django.urls import path
from . import views

urlpatterns = [
    # Evolution API Configuration
    path('evolution/config/', views.evolution_config, name='evolution-config'),
    path('evolution/test/', views.test_evolution_connection, name='evolution-test'),
    
    # Legacy connection endpoints (if needed)
    path('', views.EvolutionConnectionListCreateView.as_view(), name='connection-list'),
    path('<int:pk>/', views.EvolutionConnectionDetailView.as_view(), name='connection-detail'),
    path('<int:pk>/test/', views.test_connection, name='connection-test'),
    path('<int:pk>/toggle/', views.toggle_connection, name='connection-toggle'),
]
