from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from .models import User
from apps.tenancy.serializers import TenantSerializer


class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    """Custom JWT serializer with tenant and role info."""
    
    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        
        # Add custom claims
        token['tenant_id'] = str(user.tenant.id)
        token['tenant_name'] = user.tenant.name
        token['role'] = user.role
        token['username'] = user.username
        
        return token


class UserSerializer(serializers.ModelSerializer):
    """Serializer for User model."""
    
    tenant = TenantSerializer(read_only=True)
    is_admin = serializers.ReadOnlyField()
    is_operator = serializers.ReadOnlyField()
    avatar = serializers.SerializerMethodField()
    
    class Meta:
        model = User
        fields = [
            'id', 'username', 'email', 'first_name', 'last_name',
            'tenant', 'role', 'is_active', 'date_joined',
            'is_admin', 'is_operator', 'is_superuser', 'is_staff',
            'avatar', 'display_name', 'phone', 'birth_date'
        ]
        read_only_fields = ['id', 'date_joined', 'is_superuser', 'is_staff']
    
    def get_avatar(self, obj):
        """Return the full URL for the avatar."""
        if obj.avatar:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.avatar.url)
            return obj.avatar.url
        return None


class UserCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating users."""
    
    password = serializers.CharField(write_only=True)
    password_confirm = serializers.CharField(write_only=True)
    
    class Meta:
        model = User
        fields = [
            'username', 'email', 'first_name', 'last_name',
            'password', 'password_confirm', 'role'
        ]
    
    def validate(self, attrs):
        if attrs['password'] != attrs['password_confirm']:
            raise serializers.ValidationError("Passwords don't match")
        return attrs
    
    def create(self, validated_data):
        validated_data.pop('password_confirm')
        password = validated_data.pop('password')
        
        # Get tenant from context
        tenant = self.context['request'].user.tenant
        
        user = User.objects.create(
            tenant=tenant,
            **validated_data
        )
        user.set_password(password)
        user.save()
        
        return user
