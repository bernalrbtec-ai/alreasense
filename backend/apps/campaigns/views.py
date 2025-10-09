from rest_framework import viewsets, status, serializers
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.shortcuts import get_object_or_404
from django.db import transaction, models
from django.utils import timezone
from apps.campaigns.models import (
    Campaign, CampaignMessage, CampaignContact, CampaignLog, Holiday
)
from apps.campaigns.serializers import (
    CampaignSerializer, CampaignMessageSerializer,
    CampaignContactSerializer, CampaignLogSerializer, HolidaySerializer
)
from apps.contacts.models import Contact
from apps.notifications.models import WhatsAppInstance
from apps.billing.decorators import require_product


@require_product('flow')
class CampaignViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    serializer_class = CampaignSerializer
    
    def get_queryset(self):
        return Campaign.objects.filter(
            tenant=self.request.tenant
        ).select_related('instance', 'created_by').prefetch_related('messages')
    
    def perform_create(self, serializer):
        # Criar campanha
        instance_id = serializer.validated_data.pop('instance_id')
        contact_ids = serializer.validated_data.pop('contact_ids', [])
        message_texts = serializer.validated_data.pop('message_texts', [])
        
        instance = WhatsAppInstance.objects.get(id=instance_id, tenant=self.request.tenant)
        
        with transaction.atomic():
            campaign = serializer.save(
                tenant=self.request.tenant,
                created_by=self.request.user,
                instance=instance
            )
            
            # Criar mensagens
            for idx, text in enumerate(message_texts, start=1):
                CampaignMessage.objects.create(
                    campaign=campaign,
                    message_text=text,
                    order=idx,
                    is_active=True
                )
            
            # Criar relacionamentos com contatos
            if contact_ids:
                contacts = Contact.objects.filter(
                    id__in=contact_ids,
                    tenant=self.request.tenant
                )
                campaign_contacts = [
                    CampaignContact(campaign=campaign, contact=contact)
                    for contact in contacts
                ]
                CampaignContact.objects.bulk_create(campaign_contacts)
                campaign.total_contacts = len(campaign_contacts)
                campaign.save(update_fields=['total_contacts'])
            
            # Log
            CampaignLog.objects.create(
                campaign=campaign,
                user=self.request.user,
                level=CampaignLog.Level.INFO,
                event_type='campaign_created',
                message=f'Campanha criada com {campaign.total_contacts} contatos',
                metadata={'contact_count': campaign.total_contacts}
            )
    
    @action(detail=True, methods=['post'])
    def start(self, request, pk=None):
        """Iniciar campanha"""
        campaign = self.get_object()
        
        try:
            campaign.start(user=request.user)
            return Response({
                'message': 'Campanha iniciada com sucesso',
                'campaign': CampaignSerializer(campaign).data
            })
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
    
    @action(detail=True, methods=['post'])
    def pause(self, request, pk=None):
        """Pausar campanha"""
        campaign = self.get_object()
        reason = request.data.get('reason', '')
        
        try:
            campaign.pause(user=request.user, reason=reason)
            return Response({
                'message': 'Campanha pausada',
                'campaign': CampaignSerializer(campaign).data
            })
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
    
    @action(detail=True, methods=['post'])
    def resume(self, request, pk=None):
        """Retomar campanha"""
        campaign = self.get_object()
        
        try:
            campaign.resume(user=request.user)
            return Response({
                'message': 'Campanha retomada',
                'campaign': CampaignSerializer(campaign).data
            })
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
    
    @action(detail=True, methods=['post'])
    def cancel(self, request, pk=None):
        """Cancelar campanha"""
        campaign = self.get_object()
        reason = request.data.get('reason', '')
        
        try:
            campaign.cancel(user=request.user, reason=reason)
            return Response({
                'message': 'Campanha cancelada',
                'campaign': CampaignSerializer(campaign).data
            })
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
    
    @action(detail=True, methods=['get'])
    def logs(self, request, pk=None):
        """Logs da campanha"""
        campaign = self.get_object()
        logs = campaign.logs.all()[:100]
        serializer = CampaignLogSerializer(logs, many=True)
        return Response(serializer.data)
    
    @action(detail=True, methods=['get'])
    def contacts(self, request, pk=None):
        """Contatos da campanha"""
        campaign = self.get_object()
        campaign_contacts = campaign.campaign_contacts.select_related('contact', 'message_sent')
        
        # Filtrar por status se fornecido
        status_filter = request.query_params.get('status')
        if status_filter:
            campaign_contacts = campaign_contacts.filter(status=status_filter)
        
        serializer = CampaignContactSerializer(campaign_contacts, many=True)
        return Response(serializer.data)


@require_product('flow')
class CampaignMessageViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    serializer_class = CampaignMessageSerializer
    
    def get_queryset(self):
        campaign_id = self.kwargs.get('campaign_pk')
        return CampaignMessage.objects.filter(
            campaign_id=campaign_id,
            campaign__tenant=self.request.tenant
        )
    
    def perform_create(self, serializer):
        campaign_id = self.kwargs.get('campaign_pk')
        campaign = get_object_or_404(
            Campaign,
            id=campaign_id,
            tenant=self.request.tenant
        )
        
        # Validar limite de 5 mensagens
        if campaign.messages.count() >= 5:
            raise serializers.ValidationError("Máximo 5 mensagens por campanha")
        
        serializer.save(campaign=campaign)
    
    @action(detail=True, methods=['get'])
    def preview(self, request, campaign_pk=None, pk=None):
        """Preview da mensagem com contatos reais"""
        message = self.get_object()
        campaign = message.campaign
        
        # Pegar 3 contatos aleatórios
        sample_contacts = Contact.objects.filter(
            campaigns_participated__campaign=campaign
        ).order_by('?')[:3]
        
        previews = []
        now = timezone.now()
        
        for contact in sample_contacts:
            rendered = message.render_variables(contact, now)
            previews.append({
                'contact_name': contact.name,
                'contact_phone': contact.phone,
                'rendered_message': rendered
            })
        
        return Response({
            'original_message': message.message_text,
            'previews': previews
        })


@require_product('flow')
class HolidayViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    serializer_class = HolidaySerializer
    
    def get_queryset(self):
        # Feriados nacionais + feriados do tenant
        return Holiday.objects.filter(
            models.Q(tenant=self.request.tenant) | 
            models.Q(is_national=True, tenant__isnull=True)
        ).order_by('date')
    
    def perform_create(self, serializer):
        serializer.save(tenant=self.request.tenant)

