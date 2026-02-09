from rest_framework import generics, status, viewsets
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, AllowAny, IsAdminUser
from rest_framework.response import Response
from rest_framework_simplejwt.views import TokenObtainPairView
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth import authenticate
from django.core.files.storage import default_storage
from django.core.files.base import ContentFile
import uuid

from .models import User, Department
from apps.tenancy.models import Tenant
from .serializers import (
    CustomTokenObtainPairSerializer, 
    UserSerializer, 
    UserCreateSerializer,
    UserUpdateSerializer,
    DepartmentSerializer
)
from apps.tenancy.serializers import TenantSerializer


class CustomTokenObtainPairView(TokenObtainPairView):
    """Custom JWT login view."""
    
    serializer_class = CustomTokenObtainPairSerializer


@api_view(['POST'])
def login_with_email(request):
    """Login with email instead of username."""
    email = request.data.get('email')
    password = request.data.get('password')
    
    if not email or not password:
        return Response(
            {'detail': 'Email e senha são obrigatórios'}, 
            status=status.HTTP_400_BAD_REQUEST
        )
    
    # Try to find user by email
    try:
        user = User.objects.get(email=email)
        # Authenticate using the username (which might be different from email)
        authenticated_user = authenticate(username=user.username, password=password)
        
        if authenticated_user:
            refresh = RefreshToken.for_user(authenticated_user)
            return Response({
                'refresh': str(refresh),
                'access': str(refresh.access_token),
            })
        else:
            return Response(
                {'detail': 'Credenciais inválidas'}, 
                status=status.HTTP_401_UNAUTHORIZED
            )
    except User.DoesNotExist:
        return Response(
            {'detail': 'Usuário não encontrado'}, 
            status=status.HTTP_401_UNAUTHORIZED
        )


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def me(request):
    """Get current user info."""
    serializer = UserSerializer(request.user, context={'request': request})
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
    allowed_fields = ['first_name', 'last_name', 'email', 'display_name', 'phone', 'birth_date', 'notify_email', 'notify_whatsapp']
    for field in allowed_fields:
        if field in request.data:
            print(f"📝 Updating field {field}: {request.data[field]}")
            setattr(user, field, request.data[field])
    
    try:
        user.save()
        print(f"✅ Profile updated successfully for user: {user.username}")
        serializer = UserSerializer(user, context={'request': request})
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


# ============================================
# ViewSets REST para Tenants, Departments, Users
# ============================================

class TenantViewSet(viewsets.ModelViewSet):
    """
    ViewSet para gerenciar Tenants.
    Acesso restrito a superadmins.
    COM OTIMIZAÇÕES de performance.
    """
    queryset = Tenant.objects.all()
    serializer_class = TenantSerializer
    permission_classes = [IsAuthenticated, IsAdminUser]
    
    def get_queryset(self):
        """Superadmins veem todos, outros só o próprio tenant (COM OTIMIZAÇÕES)."""
        user = self.request.user
        
        # ✅ OTIMIZAÇÃO: select_related para current_plan (ForeignKey)
        # ✅ OTIMIZAÇÃO: prefetch_related para tenant_products (usado em active_products)
        # ✅ OTIMIZAÇÃO: prefetch_related para users (usado em get_admin_user)
        base_queryset = Tenant.objects.select_related('current_plan').prefetch_related(
            'tenant_products__product',  # Para active_products
            'users'  # Para get_admin_user
        )
        
        if user.is_superuser:
            return base_queryset.all()
        return base_queryset.filter(id=user.tenant.id)


class DepartmentViewSet(viewsets.ModelViewSet):
    """
    ViewSet para gerenciar Departamentos.
    Filtrado automaticamente por tenant do usuário autenticado.
    COM CACHE para otimizar performance.
    """
    serializer_class = DepartmentSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        """Retorna apenas departamentos do tenant do usuário (COM CACHE)."""
        from apps.common.cache_manager import CacheManager
        from django.db.models import Count, Q
        import logging
        
        logger = logging.getLogger(__name__)
        user = self.request.user
        
        # ✅ CORREÇÃO URGENTE: Se não tem tenant, retornar vazio
        if not user.tenant:
            logger.warning(f"⚠️ [DEPARTMENTS] Usuário {user.email} sem tenant, retornando queryset vazio")
            return Department.objects.none()
        
        # Cache key por tenant e tipo de usuário
        cache_key = CacheManager.make_key(
            CacheManager.PREFIX_DEPARTMENT,
            'all' if user.is_superuser else 'tenant',
            tenant_id=user.tenant.id if user.tenant else 'none'
        )
        
        def fetch_department_ids():
            """Função para buscar IDs de departamentos do banco (sem anotações)"""
            if user.is_superuser:
                queryset = Department.objects.select_related('tenant').all()
            else:
                queryset = Department.objects.filter(tenant=user.tenant).select_related('tenant')
            
            # Retornar apenas IDs para cache (anotações mudam frequentemente)
            ids = list(queryset.values_list('id', flat=True))
            logger.info(f"📋 [DEPARTMENTS] Buscados {len(ids)} departamentos do banco para tenant {user.tenant.id}")
            return ids
        
        # ✅ OTIMIZAÇÃO: Cachear apenas IDs (anotações mudam quando conversas são transferidas)
        # TTL de 5 minutos - dados podem mudar quando conversas são transferidas
        department_ids = CacheManager.get_or_set(
            cache_key,
            fetch_department_ids,
            ttl=CacheManager.TTL_MINUTE * 5
        )
        
        # ✅ CORREÇÃO URGENTE: Se cache retornou vazio ou None, buscar diretamente do banco
        # Isso evita que departamentos sumam se o cache estiver corrompido
        if not department_ids or len(department_ids) == 0:
            logger.warning(f"⚠️ [DEPARTMENTS] Cache retornou vazio para tenant {user.tenant.id}, buscando diretamente do banco")
            # Invalidar cache corrompido
            try:
                CacheManager.invalidate_pattern(f"{CacheManager.PREFIX_DEPARTMENT}:*")
            except Exception as e:
                logger.error(f"❌ [DEPARTMENTS] Erro ao invalidar cache: {e}")
            
            # Buscar diretamente do banco (bypass do cache)
            if user.is_superuser:
                queryset = Department.objects.select_related('tenant').all()
            else:
                queryset = Department.objects.filter(tenant=user.tenant).select_related('tenant')
        else:
            # ✅ OTIMIZAÇÃO: Construir queryset completo com anotações em uma única query
            if user.is_superuser:
                queryset = Department.objects.filter(id__in=department_ids).select_related('tenant')
            else:
                queryset = Department.objects.filter(
                    id__in=department_ids,
                    tenant=user.tenant
                ).select_related('tenant')
        
        # ✅ OTIMIZAÇÃO: Anotar contador de conversas pendentes (sempre necessário para serializer)
        # Esta anotação não é cacheada porque muda quando conversas são transferidas
        # ✅ CORREÇÃO: Excluir conversas atribuídas a usuários (não aparecem no inbox)
        queryset = queryset.annotate(
            pending_count_annotated=Count(
                'conversations',
                filter=Q(
                    conversations__status='pending',
                    conversations__tenant=user.tenant,
                    conversations__assigned_to__isnull=True  # ✅ NOVO: Excluir atribuídas
                ),
                distinct=True
            )
        )
        
        logger.info(f"✅ [DEPARTMENTS] Retornando {queryset.count()} departamentos para usuário {user.email}")
        return queryset
    
    def perform_create(self, serializer):
        """Ao criar, associa automaticamente ao tenant do usuário."""
        from apps.common.cache_manager import CacheManager
        
        tenant = self.request.user.tenant
        name = serializer.validated_data.get('name')
        
        # Validar duplicidade antes de salvar
        if Department.objects.filter(tenant=tenant, name=name).exists():
            from rest_framework.exceptions import ValidationError
            raise ValidationError({'name': f'Já existe um departamento "{name}" neste tenant.'})
        
        serializer.save(tenant=tenant)
        
        # ✅ INVALIDAR CACHE: por chave exata (funciona sem Redis)
        CacheManager.invalidate_department_cache_for_tenant(tenant.id)
    
    def perform_update(self, serializer):
        """Ao atualizar, invalidar cache."""
        from apps.common.cache_manager import CacheManager
        
        instance = serializer.save()
        
        # ✅ INVALIDAR CACHE: por chave exata (funciona sem Redis)
        if getattr(instance, 'tenant_id', None):
            CacheManager.invalidate_department_cache_for_tenant(instance.tenant_id)
    
    def perform_destroy(self, instance):
        """Ao deletar, invalidar cache."""
        from apps.common.cache_manager import CacheManager
        
        tenant_id = getattr(instance, 'tenant_id', None) or (instance.tenant.id if instance.tenant else None)
        instance.delete()
        
        # ✅ INVALIDAR CACHE: por chave exata (funciona sem Redis)
        if tenant_id:
            CacheManager.invalidate_department_cache_for_tenant(tenant_id)


class UserViewSet(viewsets.ModelViewSet):
    """
    ViewSet para gerenciar Usuários.
    Filtrado automaticamente por tenant do usuário autenticado.
    COM CACHE para otimizar performance.
    """
    permission_classes = [IsAuthenticated]
    
    def get_serializer_class(self):
        """Retorna o serializer apropriado para cada ação."""
        if self.action == 'create':
            from .serializers import UserCreateSerializer
            return UserCreateSerializer
        elif self.action in ['update', 'partial_update']:
            from .serializers import UserUpdateSerializer
            return UserUpdateSerializer
        return UserSerializer
    
    def get_queryset(self):
        """Retorna apenas usuários do tenant do usuário (COM CACHE MELHORADO)."""
        from apps.common.cache_manager import CacheManager
        import logging
        
        logger = logging.getLogger(__name__)
        user = self.request.user
        
        # ✅ CORREÇÃO: Se não tem tenant, retornar queryset vazio
        if not user.tenant:
            logger.warning(f"⚠️ [USERS] Usuário {user.email} sem tenant, retornando queryset vazio")
            return User.objects.none()
        
        # ✅ MELHORIA: Verificar se é uma requisição GET após POST/PATCH/DELETE
        # Se sim, sempre buscar do banco para garantir dados atualizados
        request_method = self.request.method
        force_refresh = self.request.GET.get('_refresh', 'false').lower() == 'true'
        
        # Cache key por tenant
        cache_key = CacheManager.make_key(
            CacheManager.PREFIX_USER,
            'all' if user.is_superuser else 'tenant',
            tenant_id=user.tenant.id
        )
        
        def fetch_user_ids():
            """Função para buscar IDs de usuários do banco"""
            if user.is_superuser:
                queryset = User.objects.select_related('tenant').prefetch_related('departments').all()
            else:
                queryset = User.objects.filter(tenant=user.tenant).select_related('tenant').prefetch_related('departments')
            
            # Retornar apenas IDs para cache
            ids = list(queryset.values_list('id', flat=True))
            logger.info(f"📋 [USERS] Buscados {len(ids)} usuários do banco para tenant {user.tenant.id}")
            return ids
        
        # ✅ MELHORIA: Se forçar refresh ou cache não existir, buscar do banco diretamente
        if force_refresh:
            logger.info(f"🔄 [USERS] Refresh forçado, buscando diretamente do banco")
            # Invalidar cache antes de buscar
            try:
                CacheManager.invalidate_pattern(f"{CacheManager.PREFIX_USER}:*")
            except Exception as e:
                logger.error(f"❌ [USERS] Erro ao invalidar cache: {e}")
            
            # Buscar diretamente do banco
            if user.is_superuser:
                queryset = User.objects.select_related('tenant').prefetch_related('departments').all()
            else:
                queryset = User.objects.filter(tenant=user.tenant).select_related('tenant').prefetch_related('departments')
        else:
            # ✅ OTIMIZAÇÃO: Cachear IDs (TTL reduzido para 2 minutos - dados mudam frequentemente)
            user_ids = CacheManager.get_or_set(
                cache_key,
                fetch_user_ids,
                ttl=CacheManager.TTL_MINUTE * 2  # Reduzido de 5 para 2 minutos
            )
            
            # ✅ CORREÇÃO: Se cache retornou vazio ou None, buscar diretamente do banco
            if not user_ids or len(user_ids) == 0:
                logger.warning(f"⚠️ [USERS] Cache retornou vazio para tenant {user.tenant.id}, buscando diretamente do banco")
                # Invalidar cache corrompido
                try:
                    CacheManager.invalidate_pattern(f"{CacheManager.PREFIX_USER}:*")
                except Exception as e:
                    logger.error(f"❌ [USERS] Erro ao invalidar cache: {e}")
                
                # Buscar diretamente do banco (bypass do cache)
                if user.is_superuser:
                    queryset = User.objects.select_related('tenant').prefetch_related('departments').all()
                else:
                    queryset = User.objects.filter(tenant=user.tenant).select_related('tenant').prefetch_related('departments')
            else:
                # ✅ OTIMIZAÇÃO: Reconstruir queryset com select_related/prefetch_related
                # Mas também verificar se há novos registros no banco
                if user.is_superuser:
                    db_count = User.objects.count()
                else:
                    db_count = User.objects.filter(tenant=user.tenant).count()
                
                # Se o número no banco é maior que no cache, buscar do banco
                if db_count > len(user_ids):
                    logger.warning(f"⚠️ [USERS] Banco tem {db_count} usuários mas cache tem {len(user_ids)}, buscando do banco")
                    try:
                        CacheManager.invalidate_pattern(f"{CacheManager.PREFIX_USER}:*")
                    except Exception as e:
                        logger.error(f"❌ [USERS] Erro ao invalidar cache: {e}")
                    
                    if user.is_superuser:
                        queryset = User.objects.select_related('tenant').prefetch_related('departments').all()
                    else:
                        queryset = User.objects.filter(tenant=user.tenant).select_related('tenant').prefetch_related('departments')
                else:
                    # Usar cache normalmente
                    if user.is_superuser:
                        queryset = User.objects.filter(id__in=user_ids).select_related('tenant').prefetch_related('departments')
                    else:
                        queryset = User.objects.filter(
                            id__in=user_ids,
                            tenant=user.tenant
                        ).select_related('tenant').prefetch_related('departments')
        
        count = queryset.count()
        logger.info(f"✅ [USERS] Retornando {count} usuários para usuário {user.email} (método: {request_method})")
        return queryset

    def list(self, request, *args, **kwargs):
        """
        Lista usuários. Se ?department=uuid for enviado, filtra por departamento.
        Agente só vê atendentes dos departamentos aos quais pertence; para outros
        departamentos retorna lista vazia (dropdown desabilitado no front).
        """
        queryset = self.get_queryset()
        department_id = request.query_params.get('department')
        if department_id:
            queryset = queryset.filter(departments__id=department_id).distinct()
            if not (request.user.is_admin or request.user.is_gerente):
                if not request.user.departments.filter(id=department_id).exists():
                    queryset = queryset.none()
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)
    
    def perform_create(self, serializer):
        """Ao criar, invalidar cache e forçar busca do banco."""
        from apps.common.cache_manager import CacheManager
        import logging
        
        logger = logging.getLogger(__name__)
        
        user = serializer.save()
        logger.info(f"✅ [USERS] Usuário criado: {user.email} (ID: {user.id})")
        
        # ✅ INVALIDAR CACHE: Limpar cache de usuários do tenant de forma mais agressiva
        try:
            CacheManager.invalidate_pattern(f"{CacheManager.PREFIX_USER}:*")
            logger.info(f"🔄 [USERS] Cache invalidado após criar usuário {user.email}")
        except Exception as e:
            logger.error(f"❌ [USERS] Erro ao invalidar cache: {e}")
        
        return user
    
    def perform_update(self, serializer):
        """Ao atualizar, invalidar cache."""
        from apps.common.cache_manager import CacheManager
        
        serializer.save()
        
        # ✅ INVALIDAR CACHE: Limpar cache de usuários do tenant
        CacheManager.invalidate_pattern(f"{CacheManager.PREFIX_USER}:*")
    
    def perform_destroy(self, instance):
        """Ao deletar, invalidar cache."""
        from apps.common.cache_manager import CacheManager
        
        instance.delete()
        
        # ✅ INVALIDAR CACHE: Limpar cache de usuários do tenant
        CacheManager.invalidate_pattern(f"{CacheManager.PREFIX_USER}:*")
