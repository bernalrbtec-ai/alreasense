from rest_framework import generics, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from rest_framework_simplejwt.views import TokenObtainPairView
from django.contrib.auth import authenticate
from django.core.files.storage import default_storage
from django.core.files.base import ContentFile
import uuid

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


@api_view(['PATCH'])
@permission_classes([IsAuthenticated])
def update_profile(request):
    """Update user profile information."""
    user = request.user
    
    # Update allowed fields
    allowed_fields = ['first_name', 'last_name', 'email']
    for field in allowed_fields:
        if field in request.data:
            setattr(user, field, request.data[field])
    
    try:
        user.save()
        serializer = UserSerializer(user)
        return Response(serializer.data)
    except Exception as e:
        return Response(
            {'detail': f'Erro ao atualizar perfil: {str(e)}'}, 
            status=status.HTTP_400_BAD_REQUEST
        )


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def change_password(request):
    """Change user password."""
    user = request.user
    current_password = request.data.get('current_password')
    new_password = request.data.get('new_password')
    
    if not current_password or not new_password:
        return Response(
            {'detail': 'Senha atual e nova senha são obrigatórias'}, 
            status=status.HTTP_400_BAD_REQUEST
        )
    
    # Verify current password
    if not user.check_password(current_password):
        return Response(
            {'detail': 'Senha atual incorreta'}, 
            status=status.HTTP_400_BAD_REQUEST
        )
    
    # Set new password
    user.set_password(new_password)
    user.save()
    
    return Response({'detail': 'Senha alterada com sucesso'})


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def upload_avatar(request):
    """Upload user avatar."""
    user = request.user
    
    if 'avatar' not in request.FILES:
        return Response(
            {'detail': 'Nenhum arquivo enviado'}, 
            status=status.HTTP_400_BAD_REQUEST
        )
    
    avatar_file = request.FILES['avatar']
    
    # Validate file size (max 2MB)
    if avatar_file.size > 2 * 1024 * 1024:
        return Response(
            {'detail': 'Arquivo muito grande. Máximo 2MB.'}, 
            status=status.HTTP_400_BAD_REQUEST
        )
    
    # Validate file type
    if not avatar_file.content_type.startswith('image/'):
        return Response(
            {'detail': 'Por favor, envie uma imagem válida.'}, 
            status=status.HTTP_400_BAD_REQUEST
        )
    
    try:
        # Generate unique filename
        file_extension = avatar_file.name.split('.')[-1]
        filename = f"avatars/{user.id}_{uuid.uuid4().hex[:8]}.{file_extension}"
        
        # Save file
        file_path = default_storage.save(filename, ContentFile(avatar_file.read()))
        
        # Update user avatar
        user.avatar = file_path
        user.save()
        
        return Response({
            'avatar': user.avatar.url if user.avatar else None,
            'detail': 'Avatar atualizado com sucesso'
        })
        
    except Exception as e:
        return Response(
            {'detail': f'Erro ao fazer upload: {str(e)}'}, 
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )
