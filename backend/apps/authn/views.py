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
    
    print(f"🔍 Updating profile for user: {user.username}")
    print(f"📝 Request data: {request.data}")
    
    # Update allowed fields
    allowed_fields = ['first_name', 'last_name', 'email', 'display_name', 'phone', 'birth_date']
    for field in allowed_fields:
        if field in request.data:
            print(f"📝 Updating field {field}: {request.data[field]}")
            setattr(user, field, request.data[field])
    
    try:
        user.save()
        print(f"✅ Profile updated successfully for user: {user.username}")
        serializer = UserSerializer(user)
        return Response(serializer.data)
    except Exception as e:
        print(f"❌ Error updating profile: {str(e)}")
        return Response(
            {'detail': f'Erro ao atualizar perfil: {str(e)}'}, 
            status=status.HTTP_400_BAD_REQUEST
        )


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def change_password(request):
    """Change user password."""
    user = request.user
    print(f"🔍 Changing password for user: {user.username}")
    print(f"🔍 Request data: {request.data}")
    
    current_password = request.data.get('current_password')
    new_password = request.data.get('new_password')
    
    print(f"🔍 Current password provided: {bool(current_password)}")
    print(f"🔍 New password provided: {bool(new_password)}")
    
    if not current_password or not new_password:
        print(f"❌ Missing required fields")
        return Response(
            {'detail': 'Senha atual e nova senha são obrigatórias'}, 
            status=status.HTTP_400_BAD_REQUEST
        )
    
    # Verify current password
    if not user.check_password(current_password):
        print(f"❌ Current password is incorrect")
        return Response(
            {'detail': 'Senha atual incorreta'}, 
            status=status.HTTP_400_BAD_REQUEST
        )
    
    # Set new password
    user.set_password(new_password)
    user.save()
    print(f"✅ Password changed successfully for user: {user.username}")
    
    return Response({'detail': 'Senha alterada com sucesso'})


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def upload_avatar(request):
    """Upload user avatar."""
    user = request.user
    print(f"🔍 Uploading avatar for user: {user.username}")
    print(f"🔍 Files in request: {list(request.FILES.keys())}")
    
    if 'avatar' not in request.FILES:
        print(f"❌ No avatar file in request")
        return Response(
            {'detail': 'Nenhum arquivo enviado'}, 
            status=status.HTTP_400_BAD_REQUEST
        )
    
    avatar_file = request.FILES['avatar']
    print(f"🔍 Avatar file: {avatar_file.name}, size: {avatar_file.size}, type: {avatar_file.content_type}")
    
    # Validate file size (max 2MB)
    if avatar_file.size > 2 * 1024 * 1024:
        print(f"❌ File too large: {avatar_file.size} bytes")
        return Response(
            {'detail': 'Arquivo muito grande. Máximo 2MB.'}, 
            status=status.HTTP_400_BAD_REQUEST
        )
    
    # Validate file type
    if not avatar_file.content_type.startswith('image/'):
        print(f"❌ Invalid file type: {avatar_file.content_type}")
        return Response(
            {'detail': 'Por favor, envie uma imagem válida.'}, 
            status=status.HTTP_400_BAD_REQUEST
        )
    
    try:
        # Generate unique filename
        file_extension = avatar_file.name.split('.')[-1]
        filename = f"avatars/{user.id}_{uuid.uuid4().hex[:8]}.{file_extension}"
        print(f"🔍 Generated filename: {filename}")
        
        # Save file
        file_path = default_storage.save(filename, ContentFile(avatar_file.read()))
        print(f"🔍 File saved to: {file_path}")
        
        # Update user avatar
        user.avatar = file_path
        user.save()
        print(f"✅ Avatar updated for user: {user.username}, path: {user.avatar}")
        
        avatar_url = user.avatar.url if user.avatar else None
        print(f"🔍 Avatar URL: {avatar_url}")
        
        return Response({
            'avatar': avatar_url,
            'detail': 'Avatar atualizado com sucesso'
        })
        
    except Exception as e:
        print(f"❌ Error uploading avatar: {str(e)}")
        return Response(
            {'detail': f'Erro ao fazer upload: {str(e)}'}, 
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )
