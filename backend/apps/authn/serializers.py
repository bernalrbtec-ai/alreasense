from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from .models import User, Department
from apps.tenancy.serializers import TenantSerializer


class DepartmentSerializer(serializers.ModelSerializer):
    """
    Serializer para o modelo Department.
    Retorna informações básicas do departamento.
    """
    tenant_id = serializers.UUIDField(source='tenant.id', read_only=True)
    
    class Meta:
        model = Department
        fields = [
            'id', 'tenant_id', 'name', 'color', 'ai_enabled',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'tenant_id', 'created_at', 'updated_at']
    
    def validate(self, attrs):
        """Valida que não pode criar departamento duplicado no mesmo tenant."""
        name = attrs.get('name')
        
        # Pega o tenant da instância (update) ou do contexto (create)
        if self.instance:
            tenant = self.instance.tenant
        else:
            # Tenant será adicionado pelo perform_create do ViewSet
            # Não validamos duplicidade aqui pois não temos o tenant ainda
            return attrs
        
        # Verifica duplicidade apenas em updates
        if name:
            exists = Department.objects.filter(tenant=tenant, name=name).exclude(pk=self.instance.pk)
            if exists.exists():
                raise serializers.ValidationError({
                    'name': f'Já existe um departamento "{name}" neste tenant.'
                })
        
        return attrs


class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    """Custom JWT serializer with tenant and role info."""
    
    # Override to accept 'email' instead of 'username'
    username_field = User.USERNAME_FIELD
    
    # Add email field explicitly
    email = serializers.EmailField(required=True)
    
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
    
    tenant_id = serializers.UUIDField(source='tenant.id', read_only=True)
    tenant_name = serializers.CharField(source='tenant.name', read_only=True)
    department_ids = serializers.SerializerMethodField()
    department_names = serializers.SerializerMethodField()
    is_admin = serializers.ReadOnlyField()
    is_operator = serializers.ReadOnlyField()
    avatar = serializers.SerializerMethodField()
    
    class Meta:
        model = User
        fields = [
            'id', 'username', 'email', 'first_name', 'last_name',
            'tenant_id', 'tenant_name', 'role', 
            'department_ids', 'department_names',
            'is_active', 'date_joined',
            'is_admin', 'is_operator', 'is_superuser', 'is_staff',
            'avatar', 'display_name', 'phone', 'birth_date',
            'notify_email', 'notify_whatsapp'
        ]
        read_only_fields = ['id', 'date_joined', 'is_superuser', 'is_staff']
    
    def get_department_ids(self, obj):
        """Retorna lista de IDs dos departamentos."""
        return [str(dept.id) for dept in obj.departments.all()]
    
    def get_department_names(self, obj):
        """Retorna lista de nomes dos departamentos."""
        return [dept.name for dept in obj.departments.all()]
    
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
    department_ids = serializers.ListField(
        child=serializers.UUIDField(),
        write_only=True,
        required=False,
        allow_empty=True
    )
    
    class Meta:
        model = User
        fields = [
            'username', 'email', 'first_name', 'last_name',
            'password', 'password_confirm', 'role', 'department_ids',
            'phone', 'is_active'
        ]
    
    def validate(self, attrs):
        if attrs['password'] != attrs['password_confirm']:
            raise serializers.ValidationError({"password": "As senhas não coincidem"})
        
        # Set username to email if not provided
        if not attrs.get('username'):
            attrs['username'] = attrs['email']
        
        return attrs
    
    def create(self, validated_data):
        validated_data.pop('password_confirm')
        password = validated_data.pop('password')
        department_ids = validated_data.pop('department_ids', [])
        
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
        
        # Associar departamentos
        if department_ids:
            departments = Department.objects.filter(
                id__in=department_ids,
                tenant=tenant
            )
            user.departments.set(departments)
        
        return user


class UserUpdateSerializer(serializers.ModelSerializer):
    """Serializer para atualizar usuários."""
    
    department_ids = serializers.ListField(
        child=serializers.UUIDField(),
        write_only=True,
        required=False,
        allow_empty=True
    )
    password = serializers.CharField(write_only=True, required=False)
    password_confirm = serializers.CharField(write_only=True, required=False)
    
    class Meta:
        model = User
        fields = [
            'username', 'email', 'first_name', 'last_name',
            'role', 'department_ids', 'phone', 'is_active',
            'password', 'password_confirm'
        ]
    
    def validate(self, attrs):
        password = attrs.get('password')
        password_confirm = attrs.get('password_confirm')
        
        if password and password != password_confirm:
            raise serializers.ValidationError({"password": "As senhas não coincidem"})
        
        return attrs
    
    def update(self, instance, validated_data):
        password = validated_data.pop('password', None)
        validated_data.pop('password_confirm', None)
        department_ids = validated_data.pop('department_ids', None)
        
        # Atualizar campos básicos
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        
        # Atualizar senha se fornecida
        if password:
            instance.set_password(password)
        
        instance.save()
        
        # Atualizar departamentos se fornecidos
        if department_ids is not None:
            departments = Department.objects.filter(
                id__in=department_ids,
                tenant=instance.tenant
            )
            instance.departments.set(departments)
        
        return instance
