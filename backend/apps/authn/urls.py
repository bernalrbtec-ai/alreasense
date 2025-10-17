from django.urls import path, include
from rest_framework import routers
from . import views
from . import views_debug

# Router para ViewSets REST
router = routers.DefaultRouter()
router.register(r'tenants', views.TenantViewSet, basename='tenant')
router.register(r'departments', views.DepartmentViewSet, basename='department')
router.register(r'users-api', views.UserViewSet, basename='user-api')

urlpatterns = [
    # Rotas ViewSets (REST padrão)
    path('', include(router.urls)),
    
    # Rotas customizadas (mantidas para compatibilidade)
    path('login/', views.CustomTokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('me/', views.me, name='me'),
    path('profile/', views.update_profile, name='update-profile'),
    path('change-password/', views.change_password, name='change-password'),
    path('avatar/', views.upload_avatar, name='upload-avatar'),
    path('users/', views.UserListCreateView.as_view(), name='user-list'),
    path('users/<int:pk>/', views.UserDetailView.as_view(), name='user-detail'),
    
    # Debug endpoints
    path('debug/user-tenant/', views_debug.debug_user_tenant, name='debug-user-tenant'),
    path('debug/fix-user-tenant/', views_debug.fix_user_tenant, name='fix-user-tenant'),
]
