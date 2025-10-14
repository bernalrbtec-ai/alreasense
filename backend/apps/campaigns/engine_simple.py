"""
Engine de Campanhas Simplificado - Versão de Teste
Implementa funcionalidades básicas sem dependências complexas
"""
import time
import logging
from typing import Dict, Any, Optional
from django.utils import timezone
from django.db import transaction

from .models import Campaign, CampaignContact, CampaignLog
from apps.notifications.models import WhatsAppInstance

logger = logging.getLogger(__name__)


class SimpleCampaignEngine:
    """Engine simplificado de campanhas"""
    
    def __init__(self, campaign_id: str):
        self.campaign_id = campaign_id
        self.campaign = None
        self.status = 'initializing'
        self._load_campaign()
    
    def _load_campaign(self):
        """Carrega dados da campanha"""
        try:
            self.campaign = Campaign.objects.get(id=self.campaign_id)
            logger.info(f"🎯 [ENGINE] Campanha carregada: {self.campaign.name}")
        except Campaign.DoesNotExist:
            logger.error(f"❌ [ENGINE] Campanha não encontrada: {self.campaign_id}")
            raise
    
    def start(self):
        """Inicia processamento da campanha"""
        try:
            logger.info(f"🚀 [ENGINE] Iniciando campanha: {self.campaign.name}")
            
            # Atualizar status
            self.status = 'running'
            self.campaign.status = 'running'
            self.campaign.save(update_fields=['status'])
            
            # Log de início
            CampaignLog.log_campaign_started(self.campaign)
            
            # Processar mensagens
            self._process_messages()
            
        except Exception as e:
            logger.error(f"❌ [ENGINE] Erro ao iniciar campanha: {e}")
            self.status = 'failed'
            raise
    
    def _process_messages(self):
        """Processa mensagens da campanha"""
        try:
            # Buscar contatos pendentes
            pending_contacts = CampaignContact.objects.filter(
                campaign=self.campaign,
                status__in=['pending', 'sending']
            ).select_related('contact')
            
            logger.info(f"📦 [ENGINE] Processando {pending_contacts.count()} contatos")
            
            for contact in pending_contacts:
                # Verificar se campanha ainda está rodando
                self.campaign.refresh_from_db()
                if self.campaign.status != 'running':
                    logger.info(f"⏸️ [ENGINE] Campanha pausada, parando processamento")
                    break
                
                # Processar contato
                self._process_contact(contact)
                
                # Pequena pausa entre mensagens
                time.sleep(1)
            
            # Verificar se completou
            remaining = CampaignContact.objects.filter(
                campaign=self.campaign,
                status__in=['pending', 'sending']
            ).count()
            
            if remaining == 0:
                logger.info(f"🎯 [ENGINE] Campanha completada")
                self.campaign.complete()
                self.status = 'completed'
            else:
                logger.info(f"📊 [ENGINE] {remaining} contatos restantes")
                
        except Exception as e:
            logger.error(f"❌ [ENGINE] Erro ao processar mensagens: {e}")
            self.status = 'failed'
            raise
    
    def _process_contact(self, contact):
        """Processa um contato individual"""
        try:
            # Selecionar instância
            instance = self._select_instance()
            if not instance:
                logger.warning(f"⚠️ [ENGINE] Nenhuma instância disponível para {contact.contact.name}")
                return
            
            # Simular envio (substituir por lógica real)
            logger.info(f"📤 [ENGINE] Enviando para {contact.contact.name} via {instance.friendly_name}")
            
            # Atualizar status do contato
            with transaction.atomic():
                contact.status = 'sent'
                contact.sent_at = timezone.now()
                contact.save()
                
                # Atualizar contadores da campanha
                self.campaign.messages_sent += 1
                self.campaign.save(update_fields=['messages_sent'])
            
            logger.info(f"✅ [ENGINE] Mensagem enviada com sucesso")
            
        except Exception as e:
            logger.error(f"❌ [ENGINE] Erro ao processar contato: {e}")
            
            # Marcar como falha
            with transaction.atomic():
                contact.status = 'failed'
                contact.save()
                
                self.campaign.messages_failed += 1
                self.campaign.save(update_fields=['messages_failed'])
    
    def _select_instance(self) -> Optional[WhatsAppInstance]:
        """Seleciona instância disponível"""
        try:
            available_instances = WhatsAppInstance.objects.filter(
                is_active=True,
                health_score__gte=self.campaign.pause_on_health_below
            )
            
            if not available_instances.exists():
                return None
            
            # Lógica simples de round robin
            return available_instances.first()
            
        except Exception as e:
            logger.error(f"❌ [ENGINE] Erro ao selecionar instância: {e}")
            return None
    
    def pause(self):
        """Pausa a campanha"""
        logger.info(f"⏸️ [ENGINE] Pausando campanha")
        self.status = 'paused'
        self.campaign.status = 'paused'
        self.campaign.save(update_fields=['status'])
        
        CampaignLog.log_campaign_paused(self.campaign)
    
    def resume(self):
        """Resume a campanha"""
        logger.info(f"▶️ [ENGINE] Resumindo campanha")
        self.status = 'running'
        self.campaign.status = 'running'
        self.campaign.save(update_fields=['status'])
        
        CampaignLog.log_campaign_resumed(self.campaign)
    
    def stop(self):
        """Para a campanha"""
        logger.info(f"🛑 [ENGINE] Parando campanha")
        self.status = 'completed'
        self.campaign.status = 'completed'
        self.campaign.save(update_fields=['status'])
        
        CampaignLog.log_campaign_completed(self.campaign)
    
    def get_status(self) -> Dict[str, Any]:
        """Retorna status atual da campanha"""
        return {
            'campaign_id': self.campaign_id,
            'status': self.status,
            'campaign_name': self.campaign.name,
            'messages_sent': self.campaign.messages_sent,
            'messages_delivered': self.campaign.messages_delivered,
            'messages_failed': self.campaign.messages_failed
        }


class SimpleCampaignManager:
    """Gerenciador simplificado de campanhas"""
    
    def __init__(self):
        self.active_engines: Dict[str, SimpleCampaignEngine] = {}
    
    def start_campaign(self, campaign_id: str) -> SimpleCampaignEngine:
        """Inicia uma nova campanha"""
        if campaign_id in self.active_engines:
            logger.warning(f"⚠️ [MANAGER] Campanha já está ativa: {campaign_id}")
            return self.active_engines[campaign_id]
        
        engine = SimpleCampaignEngine(campaign_id)
        self.active_engines[campaign_id] = engine
        
        # Iniciar em thread separada
        import threading
        threading.Thread(target=engine.start, daemon=True).start()
        
        logger.info(f"🚀 [MANAGER] Campanha iniciada: {campaign_id}")
        return engine
    
    def pause_campaign(self, campaign_id: str):
        """Pausa uma campanha"""
        if campaign_id in self.active_engines:
            self.active_engines[campaign_id].pause()
        else:
            logger.warning(f"⚠️ [MANAGER] Campanha não encontrada: {campaign_id}")
    
    def resume_campaign(self, campaign_id: str):
        """Resume uma campanha"""
        if campaign_id in self.active_engines:
            self.active_engines[campaign_id].resume()
        else:
            # Tentar iniciar se não estiver ativa
            self.start_campaign(campaign_id)
    
    def stop_campaign(self, campaign_id: str):
        """Para uma campanha"""
        if campaign_id in self.active_engines:
            self.active_engines[campaign_id].stop()
            del self.active_engines[campaign_id]
        else:
            logger.warning(f"⚠️ [MANAGER] Campanha não encontrada: {campaign_id}")
    
    def get_campaign_status(self, campaign_id: str) -> Optional[Dict[str, Any]]:
        """Retorna status de uma campanha"""
        if campaign_id in self.active_engines:
            return self.active_engines[campaign_id].get_status()
        return None
    
    def list_active_campaigns(self) -> list:
        """Lista campanhas ativas"""
        return list(self.active_engines.keys())


# Instância global do gerenciador simplificado
simple_campaign_manager = SimpleCampaignManager()
