from rest_framework import generics, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from rest_framework_simplejwt.views import TokenObtainPairView
from django.contrib.auth import authenticate

from .models import User
from .serializers import (
    CustomTokenObtainPairSerializer, 
    UserSerializer, 
    UserCreateSerializer
)


class CustomTokenObtainPairView(TokenObtainPairView):
    """Custom JWT login view."""
    
    serializer_class = CustomTokenObtainPairSerializer


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def me(request):
    """Get current user info."""
    serializer = UserSerializer(request.user)
    return Response(serializer.data)


class UserListCreateView(generics.ListCreateAPIView):
    """List and create users for the tenant."""
    
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        return User.objects.filter(tenant=self.request.user.tenant)
    
    def get_serializer_class(self):
        if self.request.method == 'POST':
            return UserCreateSerializer
        return UserSerializer
    
    def perform_create(self, serializer):
        # Tenant is set in serializer.create()
        serializer.save()


class UserDetailView(generics.RetrieveUpdateDestroyAPIView):
    """Get, update or delete a user."""
    
    serializer_class = UserSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        return User.objects.filter(tenant=self.request.user.tenant)
