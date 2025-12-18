"""
Views Admin para Billing API
Endpoints para gerenciar API Keys, Templates e Campanhas (admin only)
"""
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from django.shortcuts import get_object_or_404
from django.db.models import Count, Q
from django.utils import timezone
from datetime import timedelta
import logging

from apps.billing.billing_api.serializers import (
    BillingAPIKeySerializer,
    BillingTemplateSerializer
)
from apps.billing.billing_api.billing_api_key import BillingAPIKey
from apps.billing.billing_api.billing_template import BillingTemplate
from apps.billing.billing_api.billing_campaign import BillingCampaign
from apps.billing.billing_api.billing_queue import BillingQueue
from apps.billing.billing_api.billing_contact import BillingContact
from apps.tenancy.models import Tenant

logger = logging.getLogger(__name__)


class BillingAPIKeysListView(APIView):
    """
    Lista todas as API Keys (admin)
    GET /api/billing/v1/billing/api-keys/
    """
    
    permission_classes = [IsAuthenticated, IsAdminUser]
    
    def get(self, request):
        """Lista todas as API Keys"""
        try:
            tenant_id = request.query_params.get('tenant_id')
            
            queryset = BillingAPIKey.objects.select_related('tenant').all()
            
            if tenant_id:
                queryset = queryset.filter(tenant_id=tenant_id)
            
            serializer = BillingAPIKeySerializer(queryset, many=True)
            
            return Response(
                {
                    'success': True,
                    'results': serializer.data,
                    'count': len(serializer.data)
                },
                status=status.HTTP_200_OK
            )
            
        except Exception as e:
            logger.error(f"❌ [BILLING_ADMIN] Erro ao listar API Keys: {e}", exc_info=True)
            return Response(
                {
                    'success': False,
                    'message': f'Erro ao listar API Keys: {str(e)}'
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class BillingAPIKeyCreateView(APIView):
    """
    Cria nova API Key (admin)
    POST /api/billing/v1/billing/api-keys/
    """
    
    permission_classes = [IsAuthenticated, IsAdminUser]
    
    def post(self, request):
        """Cria nova API Key"""
        try:
            tenant_id = request.data.get('tenant_id')
            if not tenant_id:
                return Response(
                    {
                        'success': False,
                        'message': 'tenant_id é obrigatório'
                    },
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            tenant = get_object_or_404(Tenant, id=tenant_id)
            
            api_key = BillingAPIKey.objects.create(
                tenant=tenant,
                name=request.data.get('name', 'Nova API Key'),
                expires_at=request.data.get('expires_at') or None,
                allowed_ips=request.data.get('allowed_ips', [])
            )
            
            serializer = BillingAPIKeySerializer(api_key)
            
            logger.info(f"✅ [BILLING_ADMIN] API Key criada: {api_key.id} para tenant {tenant.name}")
            
            return Response(
                {
                    'success': True,
                    'api_key': serializer.data
                },
                status=status.HTTP_201_CREATED
            )
            
        except Exception as e:
            logger.error(f"❌ [BILLING_ADMIN] Erro ao criar API Key: {e}", exc_info=True)
            return Response(
                {
                    'success': False,
                    'message': f'Erro ao criar API Key: {str(e)}'
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class BillingAPIKeyDeleteView(APIView):
    """
    Deleta API Key (admin)
    DELETE /api/billing/v1/billing/api-keys/{key_id}/
    """
    
    permission_classes = [IsAuthenticated, IsAdminUser]
    
    def delete(self, request, key_id):
        """Deleta API Key"""
        try:
            api_key = get_object_or_404(BillingAPIKey, id=key_id)
            api_key.delete()
            
            logger.info(f"✅ [BILLING_ADMIN] API Key deletada: {key_id}")
            
            return Response(
                {
                    'success': True,
                    'message': 'API Key deletada com sucesso'
                },
                status=status.HTTP_200_OK
            )
            
        except Exception as e:
            logger.error(f"❌ [BILLING_ADMIN] Erro ao deletar API Key: {e}", exc_info=True)
            return Response(
                {
                    'success': False,
                    'message': f'Erro ao deletar API Key: {str(e)}'
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class BillingTemplatesListView(APIView):
    """
    Lista todos os Templates (admin)
    GET /api/billing/v1/billing/templates/
    """
    
    permission_classes = [IsAuthenticated, IsAdminUser]
    
    def get(self, request):
        """Lista todos os Templates"""
        try:
            tenant_id = request.query_params.get('tenant_id')
            template_type = request.query_params.get('template_type')
            
            queryset = BillingTemplate.objects.select_related('tenant').prefetch_related('variations').all()
            
            if tenant_id:
                queryset = queryset.filter(tenant_id=tenant_id)
            
            if template_type:
                queryset = queryset.filter(template_type=template_type)
            
            serializer = BillingTemplateSerializer(queryset, many=True)
            
            return Response(
                {
                    'success': True,
                    'results': serializer.data,
                    'count': len(serializer.data)
                },
                status=status.HTTP_200_OK
            )
            
        except Exception as e:
            logger.error(f"❌ [BILLING_ADMIN] Erro ao listar Templates: {e}", exc_info=True)
            return Response(
                {
                    'success': False,
                    'message': f'Erro ao listar Templates: {str(e)}'
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class BillingTemplateCreateView(APIView):
    """
    Cria novo Template (admin)
    POST /api/billing/v1/billing/templates/
    """
    
    permission_classes = [IsAuthenticated, IsAdminUser]
    
    def post(self, request):
        """Cria novo Template"""
        try:
            tenant_id = request.data.get('tenant_id')
            if not tenant_id:
                return Response(
                    {
                        'success': False,
                        'message': 'tenant_id é obrigatório'
                    },
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            tenant = get_object_or_404(Tenant, id=tenant_id)
            
            template = BillingTemplate.objects.create(
                tenant=tenant,
                name=request.data.get('name'),
                template_type=request.data.get('template_type'),
                description=request.data.get('description', ''),
                priority=request.data.get('priority', 5),
                allow_retry=request.data.get('allow_retry', False),
                max_retries=request.data.get('max_retries', 3),
                rotation_strategy=request.data.get('rotation_strategy', 'weighted'),
                required_fields=request.data.get('required_fields', []),
                optional_fields=request.data.get('optional_fields', []),
                json_schema=request.data.get('json_schema'),
                media_type=request.data.get('media_type', 'none'),
                is_active=request.data.get('is_active', True)
            )
            
            serializer = BillingTemplateSerializer(template)
            
            logger.info(f"✅ [BILLING_ADMIN] Template criado: {template.id} para tenant {tenant.name}")
            
            return Response(
                {
                    'success': True,
                    'template': serializer.data
                },
                status=status.HTTP_201_CREATED
            )
            
        except Exception as e:
            logger.error(f"❌ [BILLING_ADMIN] Erro ao criar Template: {e}", exc_info=True)
            return Response(
                {
                    'success': False,
                    'message': f'Erro ao criar Template: {str(e)}'
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class BillingTemplateUpdateView(APIView):
    """
    Atualiza Template (admin)
    PATCH /api/billing/v1/billing/templates/{template_id}/
    """
    
    permission_classes = [IsAuthenticated, IsAdminUser]
    
    def patch(self, request, template_id):
        """Atualiza Template"""
        try:
            template = get_object_or_404(BillingTemplate, id=template_id)
            
            # Atualiza campos permitidos
            allowed_fields = [
                'name', 'description', 'priority', 'allow_retry', 'max_retries',
                'rotation_strategy', 'required_fields', 'optional_fields',
                'json_schema', 'media_type', 'is_active'
            ]
            
            for field in allowed_fields:
                if field in request.data:
                    setattr(template, field, request.data[field])
            
            template.save()
            
            serializer = BillingTemplateSerializer(template)
            
            logger.info(f"✅ [BILLING_ADMIN] Template atualizado: {template.id}")
            
            return Response(
                {
                    'success': True,
                    'template': serializer.data
                },
                status=status.HTTP_200_OK
            )
            
        except Exception as e:
            logger.error(f"❌ [BILLING_ADMIN] Erro ao atualizar Template: {e}", exc_info=True)
            return Response(
                {
                    'success': False,
                    'message': f'Erro ao atualizar Template: {str(e)}'
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class BillingTemplateDeleteView(APIView):
    """
    Deleta Template (admin)
    DELETE /api/billing/v1/billing/templates/{template_id}/
    """
    
    permission_classes = [IsAuthenticated, IsAdminUser]
    
    def delete(self, request, template_id):
        """Deleta Template"""
        try:
            template = get_object_or_404(BillingTemplate, id=template_id)
            template.delete()
            
            logger.info(f"✅ [BILLING_ADMIN] Template deletado: {template_id}")
            
            return Response(
                {
                    'success': True,
                    'message': 'Template deletado com sucesso'
                },
                status=status.HTTP_200_OK
            )
            
        except Exception as e:
            logger.error(f"❌ [BILLING_ADMIN] Erro ao deletar Template: {e}", exc_info=True)
            return Response(
                {
                    'success': False,
                    'message': f'Erro ao deletar Template: {str(e)}'
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class BillingCampaignsListView(APIView):
    """
    Lista todas as Campanhas (admin)
    GET /api/billing/v1/billing/campaigns/
    """
    
    permission_classes = [IsAuthenticated, IsAdminUser]
    
    def get(self, request):
        """Lista todas as Campanhas"""
        try:
            tenant_id = request.query_params.get('tenant_id')
            billing_type = request.query_params.get('billing_type')
            status_filter = request.query_params.get('status')
            
            queryset = BillingCampaign.objects.select_related(
                'tenant', 'campaign', 'template'
            ).prefetch_related('queue').all()
            
            if tenant_id:
                queryset = queryset.filter(tenant_id=tenant_id)
            
            if billing_type:
                queryset = queryset.filter(billing_type=billing_type)
            
            if status_filter:
                queryset = queryset.filter(queue__status=status_filter)
            
            # Anota estatísticas
            queryset = queryset.annotate(
                total_contacts_count=Count('billing_contacts'),
                sent_contacts_count=Count('billing_contacts', filter=Q(billing_contacts__status='sent')),
                failed_contacts_count=Count('billing_contacts', filter=Q(billing_contacts__status='failed'))
            )
            
            campaigns_data = []
            for campaign in queryset[:100]:  # Limita a 100
                queue = campaign.queue
                campaigns_data.append({
                    'id': str(campaign.id),
                    'external_id': campaign.external_id,
                    'billing_type': campaign.billing_type,
                    'total_contacts': queue.total_contacts if queue else 0,
                    'sent_contacts': queue.sent_contacts if queue else 0,
                    'failed_contacts': queue.failed_contacts if queue else 0,
                    'status': queue.status if queue else 'pending',
                    'created_at': campaign.created_at.isoformat() if campaign.created_at else None
                })
            
            return Response(
                {
                    'success': True,
                    'results': campaigns_data,
                    'count': len(campaigns_data)
                },
                status=status.HTTP_200_OK
            )
            
        except Exception as e:
            logger.error(f"❌ [BILLING_ADMIN] Erro ao listar Campanhas: {e}", exc_info=True)
            return Response(
                {
                    'success': False,
                    'message': f'Erro ao listar Campanhas: {str(e)}'
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class BillingStatsView(APIView):
    """
    Estatísticas gerais (admin)
    GET /api/billing/v1/billing/stats/
    """
    
    permission_classes = [IsAuthenticated, IsAdminUser]
    
    def get(self, request):
        """Retorna estatísticas gerais"""
        try:
            tenant_id = request.query_params.get('tenant_id')
            
            queryset = BillingCampaign.objects.all()
            if tenant_id:
                queryset = queryset.filter(tenant_id=tenant_id)
            
            # Total de campanhas
            total_campaigns = queryset.count()
            
            # Total enviadas/falhas (agregado de todas as queues)
            queues = BillingQueue.objects.filter(
                billing_campaign__in=queryset
            )
            
            total_sent = sum(q.sent_contacts for q in queues)
            total_failed = sum(q.failed_contacts for q in queues)
            
            # Filas ativas
            active_queues = queues.filter(
                status__in=['running', 'pending']
            ).count()
            
            return Response(
                {
                    'success': True,
                    'stats': {
                        'total_campaigns': total_campaigns,
                        'total_sent': total_sent,
                        'total_failed': total_failed,
                        'active_queues': active_queues
                    }
                },
                status=status.HTTP_200_OK
            )
            
        except Exception as e:
            logger.error(f"❌ [BILLING_ADMIN] Erro ao buscar stats: {e}", exc_info=True)
            return Response(
                {
                    'success': False,
                    'message': f'Erro ao buscar stats: {str(e)}'
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

