from django.urls import path
from . import views
from . import views_debug

urlpatterns = [
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
