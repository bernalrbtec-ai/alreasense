"""
Views para gerenciamento de tenants
"""

import logging
import os
import uuid
from django.conf import settings
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from rest_framework import viewsets, status
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.contrib.auth import get_user_model
from .models import Tenant, TenantCompanyProfile
from .serializers import TenantSerializer, TenantCompanyProfileSerializer
from apps.common.decorators import require_product
from apps.common.permissions import IsTenantMember, IsAdminUser

logger = logging.getLogger(__name__)
User = get_user_model()

# Logo: 500 KB, PNG/JPEG/WebP
LOGO_MAX_BYTES = 500 * 1024
LOGO_ALLOWED_EXTENSIONS = {'.png', '.jpg', '.jpeg', '.webp'}
LOGO_ALLOWED_CONTENT_TYPES = {'image/png', 'image/jpeg', 'image/jpg', 'image/webp'}


class TenantViewSet(viewsets.ModelViewSet):
    """ViewSet para gerenciamento de tenants"""
    
    queryset = Tenant.objects.all()
    serializer_class = TenantSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        """Filtrar tenants baseado no usuário"""
        user = self.request.user
        
        # Otimização: select_related + prefetch_related para evitar N+1 queries
        base_queryset = Tenant.objects.select_related('current_plan').prefetch_related(
            'tenant_products__product',
            'users'
        )
        
        if user.is_superuser:
            return base_queryset
        else:
            # Usuário comum só vê seu próprio tenant
            return base_queryset.filter(users=user)
    
    def create(self, request, *args, **kwargs):
        """Criar tenant com usuário principal"""
        from apps.billing.models import Plan
        
        print(f"\n🔍 DEBUG - Dados recebidos:")
        print(f"   Request data: {request.data}")
        print(f"   Admin email: {request.data.get('admin_email')}")
        
        # Dados do tenant
        tenant_data = {
            'name': request.data.get('name'),
            'status': request.data.get('status', 'active'),
        }
        
        # Criar tenant
        serializer = self.get_serializer(data=tenant_data)
        serializer.is_valid(raise_exception=True)
        tenant = serializer.save()
        
        print(f"✅ Tenant criado: {tenant.name} (ID: {tenant.id})")
        
        # Atribuir plano se fornecido
        plan_slug = request.data.get('plan')
        if plan_slug:
            try:
                plan = Plan.objects.get(slug=plan_slug)
                tenant.current_plan = plan
                tenant.save()
                print(f"✅ Plano atribuído: {plan.name}")
                
                # Ativar produtos do plano
                for plan_product in plan.plan_products.all():
                    from apps.billing.models import TenantProduct
                    TenantProduct.objects.get_or_create(
                        tenant=tenant,
                        product=plan_product.product,
                        defaults={
                            'is_addon': False,
                            'is_active': True,
                        }
                    )
                    print(f"✅ Produto ativado: {plan_product.product.name}")
            except Plan.DoesNotExist:
                print(f"❌ Plano não encontrado: {plan_slug}")
                pass
        
        # Criar usuário admin se os dados forem fornecidos
        admin_email = request.data.get('admin_email')
        if admin_email:
            print(f"📧 Criando usuário admin: {admin_email}")
            admin_data = {
                'email': admin_email,
                'username': admin_email,  # Usar email como username
                'first_name': request.data.get('admin_first_name', ''),
                'last_name': request.data.get('admin_last_name', ''),
                'phone': request.data.get('admin_phone', ''),
                'tenant': tenant,
                'role': 'admin',
                'is_staff': False,
                'is_superuser': False,
                'is_active': True,
                'notify_email': request.data.get('notify_email', True),
                'notify_whatsapp': request.data.get('notify_whatsapp', False),
            }
            
            # Criar usuário
            admin_user = User.objects.create(**admin_data)
            admin_password = request.data.get('admin_password', 'changeme')
            admin_user.set_password(admin_password)
            admin_user.save()
            print(f"✅ Usuário admin criado: {admin_user.email} (ID: {admin_user.id})")
        else:
            print(f"⚠️ Nenhum email de admin fornecido, usuário não criado")
        
        headers = self.get_success_headers(serializer.data)
        return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)
    
    def update(self, request, *args, **kwargs):
        """Atualizar tenant (incluindo plano)"""
        from apps.billing.models import Plan, TenantProduct
        
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        
        print(f"\n🔍 DEBUG UPDATE - Dados recebidos:")
        print(f"   Tenant: {instance.name} (ID: {instance.id})")
        print(f"   Request data: {request.data}")
        
        # Extrair plan_slug antes de passar pro serializer
        plan_slug = request.data.get('plan')
        
        # Criar cópia dos dados sem o campo 'plan' para o serializer
        data_for_serializer = {k: v for k, v in request.data.items() if k != 'plan'}
        
        # Atualizar dados básicos do tenant
        serializer = self.get_serializer(instance, data=data_for_serializer, partial=partial)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)
        
        # Atualizar plano se fornecido
        if plan_slug:
            try:
                plan = Plan.objects.get(slug=plan_slug)
                
                # Atualizar current_plan
                instance.current_plan = plan
                instance.save()
                print(f"✅ Plano atualizado: {plan.name}")
                
                # Desativar todos os produtos atuais
                TenantProduct.objects.filter(tenant=instance).update(is_active=False)
                
                # Ativar produtos do novo plano
                for plan_product in plan.plan_products.all():
                    tenant_product, created = TenantProduct.objects.get_or_create(
                        tenant=instance,
                        product=plan_product.product,
                        defaults={
                            'is_addon': False,
                            'is_active': True,
                        }
                    )
                    if not created:
                        tenant_product.is_active = True
                        tenant_product.save()
                    print(f"✅ Produto ativado: {plan_product.product.name}")
                
            except Plan.DoesNotExist:
                print(f"❌ Plano não encontrado: {plan_slug}")
                return Response(
                    {'error': f'Plano "{plan_slug}" não encontrado'},
                    status=status.HTTP_400_BAD_REQUEST
                )
        
        # Atualizar dados do usuário admin se fornecidos
        admin_user_data = request.data.get('admin_user')
        if admin_user_data:
            from apps.authn.models import User
            
            # Buscar o usuário admin do tenant
            admin_user = User.objects.filter(tenant=instance, role='admin').first()
            if admin_user:
                print(f"🔧 Atualizando usuário admin: {admin_user.email}")
                
                # Atualizar campos fornecidos
                if 'first_name' in admin_user_data:
                    admin_user.first_name = admin_user_data['first_name']
                if 'last_name' in admin_user_data:
                    admin_user.last_name = admin_user_data['last_name']
                if 'email' in admin_user_data:
                    # Verificar se o email já existe
                    existing_user = User.objects.filter(email=admin_user_data['email']).exclude(id=admin_user.id).first()
                    if existing_user:
                        return Response(
                            {'error': f'Email "{admin_user_data["email"]}" já está em uso'},
                            status=status.HTTP_400_BAD_REQUEST
                        )
                    admin_user.email = admin_user_data['email']
                    admin_user.username = admin_user_data['email']  # Manter username = email
                if 'phone' in admin_user_data:
                    admin_user.phone = admin_user_data['phone']
                if 'password' in admin_user_data:
                    admin_user.set_password(admin_user_data['password'])
                
                admin_user.save()
                print(f"✅ Usuário admin atualizado: {admin_user.email}")
            else:
                print(f"⚠️ Usuário admin não encontrado para o tenant: {instance.name}")
                print(f"🔧 Criando novo usuário admin...")
                
                # Criar novo usuário admin
                email = admin_user_data.get('email')
                if not email:
                    return Response(
                        {'error': 'Email é obrigatório para criar usuário admin'},
                        status=status.HTTP_400_BAD_REQUEST
                    )
                
                # Verificar se o email já existe
                existing_user = User.objects.filter(email=email).first()
                if existing_user:
                    return Response(
                        {'error': f'Email "{email}" já está em uso'},
                        status=status.HTTP_400_BAD_REQUEST
                    )
                
                # Criar usuário
                admin_user = User.objects.create(
                    email=email,
                    username=email,
                    first_name=admin_user_data.get('first_name', ''),
                    last_name=admin_user_data.get('last_name', ''),
                    phone=admin_user_data.get('phone', ''),
                    tenant=instance,
                    role='admin',
                    is_staff=False,
                    is_superuser=False,
                    is_active=True,
                )
                
                # Definir senha
                password = admin_user_data.get('password', 'changeme')
                admin_user.set_password(password)
                admin_user.save()
                
                print(f"✅ Novo usuário admin criado: {admin_user.email}")
        
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def current(self, request):
        """Retorna informações do tenant atual"""
        tenant = request.tenant
        
        if not tenant:
            return Response(
                {'error': 'Tenant não encontrado'}, 
                status=status.HTTP_404_NOT_FOUND
            )
        
        serializer = self.get_serializer(tenant)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def limits(self, request):
        """Retorna informações de limites do tenant atual"""
        # Obter tenant do usuário autenticado
        tenant = getattr(request.user, 'tenant', None) if request.user.is_authenticated else None
        
        if not tenant:
            return Response(
                {'error': 'Tenant não encontrado'}, 
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Informações de limites
        limits_info = {
            'plan': {
                'name': tenant.current_plan.name if tenant.current_plan else 'Sem Plano',
                'slug': tenant.current_plan.slug if tenant.current_plan else None,
                'price': float(tenant.current_plan.price) if tenant.current_plan else 0,
            },
            'products': {},
            'monthly_total': tenant.monthly_total,
            'ui_access': tenant.ui_access,
        }
        
        # Limites por produto
        for product_slug in ['flow', 'sense', 'api_public']:
            if tenant.has_product(product_slug):
                if product_slug == 'flow':
                    limits_info['products'][product_slug] = tenant.get_instance_limit_info()
                elif product_slug == 'sense':
                    # Limites do Sense (análises)
                    limit = tenant.get_product_limit(product_slug, 'analyses')
                    current = tenant.get_current_usage(product_slug, 'analyses')
                    limits_info['products'][product_slug] = {
                        'has_access': True,
                        'current': current,
                        'limit': limit,
                        'unlimited': limit is None,
                        'message': None if limit is None else f'{current}/{limit} análises'
                    }
                elif product_slug == 'api_public':
                    # API Pública (requests)
                    limit = tenant.get_product_limit(product_slug, 'requests')
                    limits_info['products'][product_slug] = {
                        'has_access': True,
                        'api_key': tenant.get_product_api_key(product_slug),
                        'limit': limit,
                        'unlimited': limit is None,
                        'message': None if limit is None else f'Até {limit} requests/dia'
                    }
        
        return Response(limits_info)
    
    @action(detail=False, methods=['post'])
    def check_instance_limit(self, request):
        """Verifica se pode criar nova instância"""
        # Obter tenant do usuário autenticado
        tenant = getattr(request.user, 'tenant', None) if request.user.is_authenticated else None
        
        if not tenant:
            return Response(
                {'error': 'Tenant não encontrado'}, 
                status=status.HTTP_404_NOT_FOUND
            )
        
        can_create, message = tenant.can_create_instance()
        
        return Response({
            'can_create': can_create,
            'message': message,
            'limit_info': tenant.get_instance_limit_info()
        })
    
    @action(detail=True, methods=['get'])
    def metrics(self, request, pk=None):
        """Retorna métricas do tenant (OTIMIZADO)"""
        from datetime import timedelta
        from django.utils import timezone
        from django.db.models import Count, Avg, Q, Case, When, IntegerField
        from apps.chat_messages.models import Message
        from apps.campaigns.models import CampaignContact
        from apps.notifications.models import WhatsAppInstance
        
        tenant = self.get_object()
        
        # Datas de referência
        thirty_days_ago = timezone.now() - timedelta(days=30)
        today_start = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)
        
        # OTIMIZAÇÃO: Consolidar todas as queries de Message em UMA ÚNICA query
        message_metrics = Message.objects.filter(tenant=tenant).aggregate(
            total=Count('id'),
            today=Count('id', filter=Q(created_at__gte=today_start)),
            last_30=Count('id', filter=Q(created_at__gte=thirty_days_ago)),
            avg_sentiment=Avg('sentiment'),
            positive=Count('id', filter=Q(sentiment__gt=0.3)),
            sentiment_count=Count('id', filter=Q(sentiment__isnull=False)),
            avg_satisfaction=Avg('satisfaction')
        )
        
        # OTIMIZAÇÃO: Consolidar queries de CampaignContact em UMA query
        campaign_metrics = CampaignContact.objects.filter(
            campaign__tenant=tenant,
            status='sent'
        ).aggregate(
            total=Count('id'),
            today=Count('id', filter=Q(sent_at__gte=today_start)),
            last_30=Count('id', filter=Q(sent_at__gte=thirty_days_ago))
        )
        
        # Calcular totais combinados
        total_messages = (message_metrics['total'] or 0) + (campaign_metrics['total'] or 0)
        messages_today = (message_metrics['today'] or 0) + (campaign_metrics['today'] or 0)
        messages_last_30_days = (message_metrics['last_30'] or 0) + (campaign_metrics['last_30'] or 0)
        
        # Calcular percentual de mensagens positivas
        sentiment_count = message_metrics['sentiment_count'] or 0
        positive_count = message_metrics['positive'] or 0
        positive_messages_pct = (positive_count / sentiment_count * 100) if sentiment_count > 0 else 0.0
        
        # Conexões ativas (já é uma query simples)
        active_connections = WhatsAppInstance.objects.filter(
            tenant=tenant,
            connection_state='connected'
        ).count()
        
        # Latência média (mock por enquanto)
        avg_latency_ms = 120.0
        
        metrics = {
            'total_messages': total_messages,
            'messages_today': messages_today,
            'messages_last_30_days': messages_last_30_days,
            'avg_sentiment': float(message_metrics['avg_sentiment'] or 0.0),
            'positive_messages_pct': float(positive_messages_pct),
            'avg_satisfaction': float(message_metrics['avg_satisfaction'] or 0.0),
            'active_connections': active_connections,
            'avg_latency_ms': avg_latency_ms,
        }
        
        return Response(metrics)
    
    @action(detail=False, methods=['get'])
    def current(self, request):
        """Retorna informações do tenant atual do usuário logado"""
        user = request.user
        
        if not user.tenant:
            return Response(
                {'error': 'Usuário não possui tenant associado'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        serializer = self.get_serializer(user.tenant)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'], permission_classes=[IsAuthenticated])
    def aggregated_metrics(self, request):
        """
        Retorna métricas agregadas para superadmin
        NÃO retorna dados individuais de clientes
        """
        user = request.user
        
        # Apenas superadmin pode acessar
        if not (user.is_superuser or user.is_staff):
            return Response(
                {'error': 'Acesso negado. Apenas superadmin.'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        from apps.notifications.models import WhatsAppInstance
        from apps.contacts.models import Contact
        from django.db.models import Count, Sum
        
        # Métricas AGREGADAS (sem dados individuais)
        metrics = {
            'total_tenants': Tenant.objects.filter(status='active').count(),
            'total_instances': WhatsAppInstance.objects.count(),
            'instances_by_status': {
                'active': WhatsAppInstance.objects.filter(status='active').count(),
                'inactive': WhatsAppInstance.objects.filter(status='inactive').count(),
            },
            'total_contacts': Contact.objects.count(),
            'total_contacts_active': Contact.objects.filter(is_active=True).count(),
            'tenants_by_plan': list(
                Tenant.objects.values('current_plan__name')
                .annotate(count=Count('id'))
                .order_by('-count')
            ),
        }
        
        return Response(metrics)


# ---------------------------------------------------------------------------
# Company Profile (Dados da Empresa) - Fase 1
# ---------------------------------------------------------------------------

@api_view(['GET', 'PUT'])
@permission_classes([IsAuthenticated, IsTenantMember, IsAdminUser])
def company_profile(request):
    """GET/PUT perfil da empresa do tenant atual."""
    tenant = request.user.tenant
    if not tenant:
        return Response({'error': 'Tenant não encontrado'}, status=status.HTTP_404_NOT_FOUND)

    if request.method == 'GET':
        try:
            profile = TenantCompanyProfile.objects.get(tenant=tenant)
        except TenantCompanyProfile.DoesNotExist:
            return Response({
                'id': None, 'razao_social': None, 'cnpj': None, 'endereco': None,
                'endereco_latitude': None, 'endereco_longitude': None,
                'telefone': None, 'email_principal': None, 'ramo_atuacao': None,
                'data_fundacao': None, 'missao': None, 'sobre_empresa': None,
                'produtos_servicos': None, 'logo_url': None, 'created_at': None, 'updated_at': None,
            })
        serializer = TenantCompanyProfileSerializer(profile)
        return Response(serializer.data)

    # PUT
    try:
        profile = TenantCompanyProfile.objects.get(tenant=tenant)
    except TenantCompanyProfile.DoesNotExist:
        profile = TenantCompanyProfile(tenant=tenant)

    serializer = TenantCompanyProfileSerializer(profile, data=request.data, partial=True)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    serializer.save()
    # Sync chunk para pgvector (n8n) em background – Fase 2
    from apps.tenancy.rag_sync import sync_company_chunk_async
    sync_company_chunk_async(tenant.id)
    return Response(serializer.data)


@api_view(['POST'])
@permission_classes([IsAuthenticated, IsTenantMember, IsAdminUser])
def company_profile_upload_logo(request):
    """Upload de logo da empresa. Máx 500KB, PNG/JPEG/WebP."""
    tenant = request.user.tenant
    if not tenant:
        return Response({'error': 'Tenant não encontrado'}, status=status.HTTP_404_NOT_FOUND)

    if 'logo' not in request.FILES:
        return Response(
            {'error': 'Nenhum arquivo enviado. Use o campo "logo".'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    logo_file = request.FILES['logo']

    if logo_file.size > LOGO_MAX_BYTES:
        return Response(
            {'error': f'Arquivo muito grande. Máximo {LOGO_MAX_BYTES // 1024} KB.'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    ext = os.path.splitext(logo_file.name)[-1].lower()
    if ext not in LOGO_ALLOWED_EXTENSIONS:
        return Response(
            {'error': 'Formato inválido. Use PNG, JPEG ou WebP.'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    ct = (logo_file.content_type or '').lower()
    if ct not in LOGO_ALLOWED_CONTENT_TYPES:
        return Response(
            {'error': 'Tipo de arquivo inválido.'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        safe_ext = '.webp' if ext == '.webp' else ('.png' if 'png' in ct else '.jpg')
        filename = f"company_logos/{tenant.id}/logo_{uuid.uuid4().hex[:8]}{safe_ext}"
        file_path = default_storage.save(filename, ContentFile(logo_file.read()))

        # URL pública (MEDIA_URL + path)
        logo_url = request.build_absolute_uri(settings.MEDIA_URL + file_path)

        profile, _ = TenantCompanyProfile.objects.get_or_create(
            tenant=tenant,
            defaults={},
        )
        profile.logo_url = logo_url
        profile.save(update_fields=['logo_url', 'updated_at'])

        # Sync chunk para pgvector (logo incluído) – Fase 2
        from apps.tenancy.rag_sync import sync_company_chunk_async
        sync_company_chunk_async(tenant.id)

        return Response({'logo_url': logo_url})
    except Exception as e:
        logger.exception("company_profile_upload_logo failed: %s", e)
        return Response(
            {'error': f'Erro ao salvar logo: {str(e)}'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )