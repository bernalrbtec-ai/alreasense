from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from .models import User
from apps.tenancy.serializers import TenantSerializer


class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    """Custom JWT serializer with tenant and role info."""
    
    # Override to accept 'email' instead of 'username'
    username_field = 'email'
    
    def validate(self, attrs):
        # Debug: ver o que está chegando
        print(f"\n🔍 DEBUG LOGIN - Attrs recebidos: {attrs}")
        
        # Get email from attrs
        email = attrs.get('email')
        password = attrs.get('password')
        
        print(f"📧 Email: {email}")
        print(f"🔐 Password: {'***' if password else 'None'}")
        
        if not email or not password:
            print(f"❌ Email ou senha vazios!")
            raise serializers.ValidationError({'detail': 'Email e senha são obrigatórios'})
        
        # Authenticate using email as username (since USERNAME_FIELD = 'email')
        user = User.objects.filter(email=email).first()
        
        print(f"👤 User encontrado: {user.email if user else 'Nenhum'}")
        
        if not user:
            print(f"❌ Usuário não encontrado com email: {email}")
            raise serializers.ValidationError({'detail': 'Usuário e/ou senha incorreto(s)'})
        
        if not user.check_password(password):
            print(f"❌ Senha incorreta para: {email}")
            raise serializers.ValidationError({'detail': 'Usuário e/ou senha incorreto(s)'})
        
        if not user.is_active:
            raise serializers.ValidationError({'detail': 'Usuário inativo'})
        
        # Generate tokens
        refresh = self.get_token(user)
        
        return {
            'refresh': str(refresh),
            'access': str(refresh.access_token),
            'user': UserSerializer(user).data
        }
    
    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        
        # Add custom claims
        token['tenant_id'] = str(user.tenant.id) if user.tenant else None
        token['tenant_name'] = user.tenant.name if user.tenant else None
        token['role'] = user.role
        token['username'] = user.username
        token['email'] = user.email
        
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
            'avatar', 'display_name', 'phone', 'birth_date',
            'notify_email', 'notify_whatsapp'
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
        
        # Set username to email if not provided
        if not attrs.get('username'):
            attrs['username'] = attrs['email']
        
        return attrs
    
    def create(self, validated_data):
        validated_data.pop('password_confirm')
        password = validated_data.pop('password')
        
        # Get tenant from context
        tenant = self.context['request'].user.tenant
        
        # Ensure username is set to email
        if not validated_data.get('username'):
            validated_data['username'] = validated_data['email']
        
        user = User.objects.create(
            tenant=tenant,
            **validated_data
        )
        user.set_password(password)
        user.save()
        
        return user
