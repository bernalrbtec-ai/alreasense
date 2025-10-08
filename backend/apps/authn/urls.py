from django.urls import path
from . import views

urlpatterns = [
    path('login/', views.CustomTokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('me/', views.me, name='me'),
    path('profile/', views.update_profile, name='update-profile'),
    path('change-password/', views.change_password, name='change-password'),
    path('avatar/', views.upload_avatar, name='upload-avatar'),
    path('users/', views.UserListCreateView.as_view(), name='user-list'),
    path('users/<int:pk>/', views.UserDetailView.as_view(), name='user-detail'),
]
