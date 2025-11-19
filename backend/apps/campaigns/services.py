"""
Services para o sistema de campanhas
Inclui lógica de rotação de instâncias
"""
from typing import Optional, List
from django.db import models
from django.db.models import F, Q
from apps.notifications.models import WhatsAppInstance
from .models import Campaign, CampaignLog
import random
import json


class RotationService:
    """
    Serviço para seleção de instâncias baseado em diferentes estratégias
    """
    
    def __init__(self, campaign: Campaign):
        self.campaign = campaign
    
    def select_next_instance(self) -> Optional[WhatsAppInstance]:
        """
        Seleciona a próxima instância baseada no modo de rotação da campanha
        """
        # Buscar instâncias disponíveis
        available_instances = self._get_available_instances()
        
        if not available_instances:
            # Log de erro apenas se não foi logado recentemente
            from django.utils import timezone
            from datetime import timedelta
            
            recent_error = CampaignLog.objects.filter(
                campaign=self.campaign,
                log_type='error',
                message__contains="Nenhuma instância disponível",
                created_at__gte=timezone.now() - timedelta(minutes=5)
            ).exists()
            
            if not recent_error:
                CampaignLog.log_error(
                    self.campaign,
                    "Nenhuma instância disponível para envio",
                    details={'rotation_mode': self.campaign.rotation_mode}
                )
            return None
        
        # Selecionar baseado no modo
        if self.campaign.rotation_mode == 'round_robin':
            instance = self._select_round_robin(available_instances)
            reason = "Round Robin (sequencial)"
        elif self.campaign.rotation_mode == 'balanced':
            instance = self._select_balanced(available_instances)
            reason = "Balanceado (menor uso)"
        else:  # intelligent
            instance = self._select_intelligent(available_instances)
            reason = "Inteligente (melhor health)"
        
        # Log da seleção (mantido para debug, mas com limite)
        # Removido log de "Instância Selecionada" - informação redundante
        # A instância já aparece no log de "Mensagem Enviada"
        
        return instance
    
    def _get_available_instances(self) -> List[WhatsAppInstance]:
        """
        Retorna lista de instâncias disponíveis para envio
        Filtra por:
        - Conectadas (connection_state = 'open')
        - Dentro do limite diário
        - Health score baixo apenas gera log (não bloqueia)
        """
        instances = self.campaign.instances.all()
        available = []
        
        for instance in instances:
            # Reset de contadores diários se necessário
            instance.reset_daily_counters_if_needed()
            
            # Verificar conexão (bloqueante)
            if instance.connection_state != 'open':
                continue
            
            # Verificar health (apenas log, sem pausar)
            if instance.health_score < self.campaign.pause_on_health_below:
                # Log de health issue (apenas informativo)
                CampaignLog.log_health_issue(
                    self.campaign, instance,
                    f"Health score baixo: {instance.health_score} (mínimo: {self.campaign.pause_on_health_below}) - Continuando envio"
                )
                # continue  # Comentado - não pula mais a instância
            
            # Verificar limite diário
            if instance.msgs_sent_today >= self.campaign.daily_limit_per_instance:
                CampaignLog.log_limit_reached(
                    self.campaign, instance, 'daily'
                )
                continue
            
            # Verificar health mínimo (apenas log, sem pausar)
            if instance.health_score < self.campaign.pause_on_health_below:
                CampaignLog.log_health_issue(
                    self.campaign, instance,
                    f"Health abaixo do mínimo: {instance.health_score} < {self.campaign.pause_on_health_below} - Continuando envio"
                )
                # continue  # Comentado - não pula mais a instância
            
            available.append(instance)
        
        return available
    
    def _select_round_robin(self, instances: List[WhatsAppInstance]) -> Optional[WhatsAppInstance]:
        """
        Seleção Round Robin (sequencial)
        Usa current_instance_index para manter o estado
        """
        if not instances:
            return None
        
        # Ordenar por ID para garantir ordem consistente
        instances = sorted(instances, key=lambda x: str(x.id))
        
        # Obter índice atual
        index = self.campaign.current_instance_index
        
        # Validar índice
        if index >= len(instances):
            index = 0
        
        # Selecionar instância
        instance = instances[index]
        
        # Incrementar índice para próxima vez
        self.campaign.current_instance_index = (index + 1) % len(instances)
        self.campaign.save(update_fields=['current_instance_index'])
        
        return instance
    
    def _select_balanced(self, instances: List[WhatsAppInstance]) -> Optional[WhatsAppInstance]:
        """
        Seleção Balanceada
        Escolhe a instância com MENOR número de mensagens enviadas hoje
        """
        if not instances:
            return None
        
        # Ordenar por msgs_sent_today (ascendente)
        instances = sorted(instances, key=lambda x: x.msgs_sent_today)
        
        # Retornar a primeira (menor uso)
        return instances[0]
    
    def _select_intelligent(self, instances: List[WhatsAppInstance]) -> Optional[WhatsAppInstance]:
        """
        Seleção Inteligente
        Calcula um "peso" baseado em:
        - Health score (70%)
        - Disponibilidade (30%)
        
        Escolhe a instância com maior peso
        """
        if not instances:
            return None
        
        weighted_instances = []
        
        for instance in instances:
            # Calcular disponibilidade (% de capacidade restante)
            capacity_remaining = (
                (self.campaign.daily_limit_per_instance - instance.msgs_sent_today) /
                self.campaign.daily_limit_per_instance * 100
            )
            
            # Calcular peso
            # 70% health + 30% disponibilidade
            weight = (instance.health_score * 0.7) + (capacity_remaining * 0.3)
            
            weighted_instances.append({
                'instance': instance,
                'weight': weight,
                'health': instance.health_score,
                'capacity': capacity_remaining
            })
        
        # Ordenar por peso (descendente)
        weighted_instances.sort(key=lambda x: x['weight'], reverse=True)
        
        # Retornar a melhor
        best = weighted_instances[0]
        
        # Log detalhado
        
        return best['instance']
    
    def can_send_message(self) -> tuple[bool, str]:
        """
        Verifica se a campanha pode enviar mensagens agora
        Retorna (pode_enviar, motivo)
        """
        # Verificar status da campanha
        if self.campaign.status != 'running':
            return False, f"Campanha não está rodando (status: {self.campaign.status})"
        
        # Verificar se há instâncias disponíveis
        available = self._get_available_instances()
        if not available:
            return False, "Nenhuma instância disponível"
        
        # Verificar se há contatos pendentes
        pending_count = self.campaign.campaign_contacts.filter(status='pending').count()
        if pending_count == 0:
            return False, "Nenhum contato pendente"
        
        return True, "OK"
    

class CampaignSender:
    """
    Serviço para envio de mensagens da campanha
    """
    
    def __init__(self, campaign: Campaign):
        self.campaign = campaign
        self.rotation_service = RotationService(campaign)
    
    def send_next_message(self) -> tuple[bool, str]:
        """
        Envia a próxima mensagem da campanha
        Retorna (sucesso, mensagem)
        """
        import time
        import random
        from django.utils import timezone
        
        # ✅ Selecionar próximo contato pendente (INCLUIR 'sending' como pendente)
        campaign_contact = self.campaign.campaign_contacts.filter(
            status__in=['pending', 'sending']  # ✅ Incluir 'sending' para retry
        ).select_related('contact').first()
        
        if not campaign_contact:
            return False, "Nenhum contato pendente"
        
        contact = campaign_contact.contact
        
        # ✅ Selecionar instância com HEALTH CHECK
        instance = self.rotation_service.select_next_instance()
        if not instance:
            return False, "Nenhuma instância disponível"
        
        # ✅ HEALTH CHECK VISUAL - apenas para referência, não bloqueia envio
        health_status = self._check_instance_health_visual(instance)
        print(f"🔍 [HEALTH] Status visual da instância {instance.friendly_name}: {health_status}")
        
        # Selecionar mensagem (rotacionar entre as disponíveis)
        # ✅ CORREÇÃO CRÍTICA: Usar query direta (não list()) e incrementar ANTES de enviar
        from django.db.models import F
        from .models import CampaignMessage
        
        # Buscar mensagem com menor uso usando query atômica
        message = CampaignMessage.objects.filter(
            campaign=self.campaign,
            is_active=True
        ).order_by('times_used', 'order').first()  # ✅ Usar .first() ao invés de list()[0]
        
        if not message:
            return False, "Nenhuma mensagem ativa configurada"
        
        # ✅ CORREÇÃO CRÍTICA: Incrementar times_used ANTES de enviar (atomicamente)
        # Isso garante que a próxima seleção já veja o valor atualizado
        CampaignMessage.objects.filter(id=message.id).update(times_used=F('times_used') + 1)
        
        # Recarregar mensagem para ter times_used atualizado
        message.refresh_from_db()
        
        # Log para debug
        import logging
        logger = logging.getLogger(__name__)
        total_messages = CampaignMessage.objects.filter(campaign=self.campaign, is_active=True).count()
        logger.info(f"🔄 [ROTAÇÃO] Mensagem selecionada: ordem={message.order}, times_used={message.times_used}, total_mensagens={total_messages}")
        
        # Atualizar status
        campaign_contact.status = 'sending'
        campaign_contact.instance_used = instance
        campaign_contact.message_used = message
        campaign_contact.save()
        
        try:
            # Marcar tempo inicial
            start_time = time.time()
            
            # ENVIO REAL VIA EVOLUTION API
            import requests
            
            # Preparar número (remover + e formatar)
            phone = contact.phone.replace('+', '').replace('-', '').replace(' ', '')
            if not phone.startswith('55'):
                phone = f'55{phone}'
            
            # Substituir variáveis na mensagem usando MessageVariableService
            logger.info(f"📝 [VARIÁVEIS] Template original: {message.content[:100]}...")
            message_text = MessageVariableService.render_message(
                template=message.content,
                contact=contact
            )
            logger.info(f"✅ [VARIÁVEIS] Mensagem renderizada: {message_text[:100]}...")
            
            # ✅ Enviar via Evolution API com RETRY e BACKOFF
            url = f"{instance.api_url}/message/sendText/{instance.instance_name}"
            headers = {
                'apikey': instance.api_key,
                'Content-Type': 'application/json'
            }
            payload = {
                'number': phone,
                'text': message_text
            }
            
            # ✅ RETRY com backoff exponencial
            max_retries = 3
            base_delay = 1  # 1 segundo base
            
            for attempt in range(max_retries + 1):
                try:
                    response = requests.post(url, json=payload, headers=headers, timeout=10)
                    response.raise_for_status()
                    break  # Sucesso, sair do loop
                    
                except requests.exceptions.RequestException as e:
                    if attempt == max_retries:
                        # Última tentativa falhou, re-raise
                        raise e
                    
                    # Calcular delay com backoff exponencial
                    delay = base_delay * (2 ** attempt)
                    print(f"⚠️ [RETRY] Tentativa {attempt + 1}/{max_retries + 1} falhou: {str(e)}")
                    print(f"⏳ [RETRY] Aguardando {delay}s antes da próxima tentativa...")
                    time.sleep(delay)
                    
                    # ✅ Tentar instância alternativa se disponível
                    if attempt == 1:  # Na segunda tentativa
                        alt_instance = self.rotation_service.select_next_instance()
                        if alt_instance and alt_instance.id != instance.id:
                            print(f"🔄 [RETRY] Tentando instância alternativa: {alt_instance.friendly_name}")
                            instance = alt_instance
                            url = f"{instance.api_url}/message/sendText/{instance.instance_name}"
                            headers['apikey'] = instance.api_key
            
            response_data = response.json()
            # Salvar ID da mensagem do WhatsApp se disponível
            if 'key' in response_data and 'id' in response_data['key']:
                campaign_contact.whatsapp_message_id = response_data['key']['id']
            
            # Calcular duração
            duration_ms = int((time.time() - start_time) * 1000)
            
            # Atualizar contadores
            instance.record_message_sent()
            # ✅ times_used já foi incrementado ANTES do envio (rotação balanceada)
            
            # Atualizar status do contato PRIMEIRO
            campaign_contact.status = 'sent'
            campaign_contact.sent_at = timezone.now()
            campaign_contact.save(update_fields=['status', 'sent_at', 'whatsapp_message_id'])
            
            # Atualizar campanha APÓS sucesso no envio
            self.campaign.messages_sent += 1
            self.campaign.last_message_sent_at = timezone.now()
            # Salvar informações do último contato enviado
            self.campaign.last_contact_name = contact.name
            self.campaign.last_contact_phone = contact.phone
            self.campaign.last_instance_name = instance.friendly_name
            
            # ✅ Verificar se há mais mensagens pendentes APÓS marcar como enviado (QUERY ATÔMICA)
            from .models import CampaignContact
            next_campaign_contact = CampaignContact.objects.filter(
                campaign=self.campaign,
                status__in=['pending', 'sending']  # ✅ Incluir 'sending' como pendente
            ).select_related('contact').first()
            
            if next_campaign_contact:
                # Calcular próximo disparo apenas se houver mais mensagens
                # ✅ PADRONIZAÇÃO: Usa random.uniform para tempos distintos e humanizados (não random.randint)
                import random
                next_interval = random.uniform(self.campaign.interval_min, self.campaign.interval_max)
                self.campaign.next_message_scheduled_at = timezone.now() + timezone.timedelta(seconds=next_interval)
                
                # Armazenar informações do próximo contato
                self.campaign.next_contact_name = next_campaign_contact.contact.name
                self.campaign.next_contact_phone = next_campaign_contact.contact.phone
            else:
                # Última mensagem - limpar próximo disparo
                self.campaign.next_message_scheduled_at = None
                self.campaign.next_contact_name = None
                self.campaign.next_contact_phone = None
            
            self.campaign.save(update_fields=['messages_sent', 'last_message_sent_at', 'last_contact_name', 'last_contact_phone', 'last_instance_name', 'next_message_scheduled_at', 'next_contact_name', 'next_contact_phone'])
            
            # Salvar mensagem no modelo Message para contadores do dashboard
            from apps.chat_messages.models import Message
            from django.utils import timezone
            
            Message.objects.create(
                tenant=self.campaign.tenant,
                connection=instance.connection if hasattr(instance, 'connection') else None,
                chat_id=f"campaign_{self.campaign.id}_{contact.id}",
                sender=f"campaign_{self.campaign.id}",
                text=message_text,
                created_at=timezone.now()
            )
            
            # ✅ Log de sucesso (SEMPRE registrado - sem limitação)
            from .models import CampaignLog
            CampaignLog.log_message_sent(
                self.campaign, instance, contact, campaign_contact,
                duration_ms=duration_ms,
                message_content=message_text,  # Passar mensagem com variáveis substituídas
                whatsapp_message_id=campaign_contact.whatsapp_message_id  # ID da mensagem WhatsApp
            )
            
            return True, f"Mensagem enviada para {contact.name}"
            
        except Exception as e:
            # ✅ MELHOR TRATAMENTO DE ERROS com logging detalhado
            error_msg = str(e)
            
            # ✅ Log detalhado do erro
            print(f"❌ [ERRO] Falha ao enviar mensagem:")
            print(f"   - Contato: {contact.name} ({contact.phone})")
            print(f"   - Instância: {instance.friendly_name}")
            print(f"   - Erro: {error_msg}")
            print(f"   - URL: {url}")
            print(f"   - Payload: {payload}")
            
            # ✅ Classificar tipo de erro
            error_type = "unknown"
            if "400" in error_msg:
                error_type = "bad_request"
            elif "401" in error_msg:
                error_type = "unauthorized"
            elif "403" in error_msg:
                error_type = "forbidden"
            elif "404" in error_msg:
                error_type = "not_found"
            elif "500" in error_msg:
                error_type = "server_error"
            elif "timeout" in error_msg.lower():
                error_type = "timeout"
            elif "connection" in error_msg.lower():
                error_type = "connection_error"
            
            # ✅ Log estruturado do erro
            from .models import CampaignLog
            CampaignLog.log_error(
                campaign=self.campaign,
                error_msg=f"Falha ao enviar mensagem para {contact.name}",
                details={
                    'contact_id': contact.id,
                    'contact_name': contact.name,
                    'contact_phone': contact.phone,
                    'instance_id': instance.id,
                    'instance_name': instance.friendly_name,
                    'error_type': error_type,
                    'error_message': error_msg,
                    'url': url,
                    'retry_count': campaign_contact.retry_count + 1
                }
            )
            
            # ✅ Atualizar contato com erro detalhado
            campaign_contact.status = 'failed'
            campaign_contact.error_message = f"[{error_type.upper()}] {error_msg}"
            campaign_contact.failed_at = timezone.now()
            campaign_contact.retry_count += 1
            campaign_contact.save()
            
            # ✅ Registrar falha na instância
            instance.record_message_failed(error_msg)
            
            # ✅ Incrementar contadores
            self.campaign.messages_sent += 1  # Contar como disparo realizado
            self.campaign.messages_failed += 1  # Contar como falha
            self.campaign.save(update_fields=['messages_sent', 'messages_failed'])
            
            # ✅ Log de falha estruturado
            CampaignLog.log_message_failed(
                self.campaign, instance, contact, campaign_contact,
                error_msg
            )
            
            return False, f"Erro ao enviar: {error_msg}"
    
    def _check_instance_health_visual(self, instance) -> str:
        """
        ✅ Verifica saúde da instância APENAS para referência visual - NÃO bloqueia envio
        """
        try:
            status_parts = []
            
            # Verificar health score da instância
            if hasattr(instance, 'health_score') and instance.health_score is not None:
                if instance.health_score < 30:
                    status_parts.append(f"health_baixo({instance.health_score})")
                else:
                    status_parts.append(f"health_ok({instance.health_score})")
            else:
                status_parts.append("health_nao_disponivel")
            
            # Verificar se instância está ativa
            if not instance.is_active:
                status_parts.append("inativa")
            else:
                status_parts.append("ativa")
            
            # Verificar connection state
            if hasattr(instance, 'connection_state'):
                status_parts.append(f"conn_{instance.connection_state}")
            else:
                status_parts.append("conn_nao_disponivel")
            
            # ✅ HEALTH CHECK via API (apenas para informação visual)
            try:
                import requests
                health_url = f"{instance.api_url}/instance/connectionState/{instance.instance_name}"
                headers = {'apikey': instance.api_key}
                
                response = requests.get(health_url, headers=headers, timeout=3)
                if response.status_code == 200:
                    data = response.json()
                    state = data.get('state')
                    status_parts.append(f"api_{state}")
                else:
                    status_parts.append(f"api_erro_{response.status_code}")
                    
            except Exception as e:
                status_parts.append(f"api_timeout")
            
            return " | ".join(status_parts)
            
        except Exception as e:
            return f"erro_verificacao: {str(e)}"
    
    def process_batch(self, batch_size: int = 10) -> dict:
        """
        Processa um lote de mensagens
        Retorna estatísticas do lote
        """
        results = {
            'sent': 0,
            'failed': 0,
            'skipped': 0,
            'paused': False,
            'messages': []
        }
        
        for i in range(batch_size):
            # ⚠️ CRÍTICO: Verificar status ANTES de cada mensagem
            self.campaign.refresh_from_db()
            
            if self.campaign.status != 'running':
                results['paused'] = True
                break
            
            # ✅ Log de contatos pendentes restantes (QUERY ATÔMICA)
            from .models import CampaignContact
            pending_count = CampaignContact.objects.filter(
                campaign=self.campaign,
                status__in=['pending', 'sending']  # ✅ Incluir 'sending' como pendente
            ).count()
            print(f"📋 [BATCH] Contatos pendentes restantes: {pending_count}")
            
            # ⚠️ TIMEOUT PROTECTION: Contador individual por disparo
            import time
            disparo_start_time = time.time()
            MAX_DISPARO_DURATION = 600  # 10 minutos por disparo individual
            
            # ✅ Log detalhado do início do disparo
            from .models import CampaignLogManager
            # Buscar contato e instância para o log
            contact, instance = self.get_next_contact_and_instance()
            if contact and instance:
                message_content = self.get_next_message_content()
                print(f"🎯 [DISPARO] Iniciando disparo para {contact.name} via {instance.friendly_name}")
                CampaignLogManager.log_disparo_started(
                    campaign=self.campaign,
                    contact=contact,
                    instance=instance,
                    message_content=message_content
                )
            
            success, message = self.send_next_message()
            
            # Log detalhado do resultado
            print(f"📊 [BATCH] Mensagem {i+1}: success={success}, message='{message}'")
            
            # Verificar timeout do disparo individual
            disparo_elapsed = time.time() - disparo_start_time
            if disparo_elapsed > MAX_DISPARO_DURATION:
                # Log de timeout do disparo
                if contact and instance:
                    CampaignLogManager.log_disparo_timeout(
                        campaign=self.campaign,
                        contact=contact,
                        instance=instance,
                        elapsed_time=disparo_elapsed
                    )
                
                # Log de pausa de segurança
                from .models import CampaignLog
                CampaignLog.log_campaign_paused(
                    campaign=self.campaign,
                    reason=f"Pausa de segurança - Disparo {i+1} com tempo excessivo ({disparo_elapsed:.1f}s)"
                )
                
                # ✅ AUTO-RESCHEDULE REMOVIDO para evitar loop infinito
                print(f"⚠️ [TIMEOUT] Disparo {i+1} com tempo excessivo ({disparo_elapsed:.1f}s) - NÃO reagendando")
                
                results['paused'] = True
                break
            
            # ✅ Verificar se falhou por falta de instâncias disponíveis (NÃO PARAR CAMPANHA)
            if not success and ("disponível" in message.lower() or "instância" in message.lower() or "health baixo" in message.lower()):
                print(f"⚠️ [BATCH] Instância indisponível, mas continuando com próximos contatos...")
                results['skipped'] += 1
                # ✅ NÃO fazer break - continuar tentando outros contatos
                continue
            
            if success:
                results['sent'] += 1
                
                # ✅ NOVO: Verificar se foi o último contato APÓS envio bem-sucedido (QUERY ATÔMICA)
                from .models import CampaignContact
                remaining_pending = CampaignContact.objects.filter(
                    campaign=self.campaign,
                    status__in=['pending', 'sending']  # ✅ Incluir 'sending' como pendente
                ).count()
                
                print(f"📊 [BATCH] Após envio bem-sucedido, contatos pendentes: {remaining_pending}")
                
                if remaining_pending == 0:
                    print(f"🎯 [BATCH] Campanha completada - último contato enviado!")
                    results['completed'] = True
                    break
                
                # ⚠️ TIMEOUT PROTECTION: Verificar se próxima mensagem deve aguardar
                if self.campaign.next_message_scheduled_at:
                    from django.utils import timezone
                    now = timezone.now()
                    if self.campaign.next_message_scheduled_at > now:
                        wait_seconds = (self.campaign.next_message_scheduled_at - now).total_seconds()
                        if wait_seconds > 30:  # Se precisa aguardar mais de 30s, pausar lote
                            results['skipped'] = 1
                            break
                    
            elif "pendente" in message.lower():
                # Se não há contatos pendentes, marcar como completado
                results['completed'] = True
                break
            elif "disponível" in message.lower() or "instância" in message.lower():
                results['skipped'] += 1
                break  # Parar se não há instâncias disponíveis
            else:
                results['failed'] += 1
            
            results['messages'].append(message)
            
            # Intervalo entre mensagens
            if i < batch_size - 1:  # Não esperar após a última
                import random
                import time
                interval = random.uniform(
                    self.campaign.interval_min,
                    self.campaign.interval_max
                )
                time.sleep(interval)
        
        return results
    
    def get_next_contact_and_instance(self):
        """Busca próximo contato e instância para logs"""
        try:
            # Buscar próximo contato pendente
            from .models import CampaignContact
            campaign_contact = CampaignContact.objects.filter(
                campaign=self.campaign,
                status='pending'
            ).first()
            
            if not campaign_contact:
                return None, None
            
            # Buscar instância disponível
            instance = self.rotation_service.select_next_instance()
            
            return campaign_contact.contact, instance
        except:
            return None, None
    
    def get_next_message_content(self):
        """Busca conteúdo da próxima mensagem para logs"""
        try:
            if self.campaign.messages.exists():
                return self.campaign.messages.first().content
            return "Mensagem não encontrada"
        except:
            return "Erro ao buscar mensagem"


class MessageVariableService:
    """
    Service para renderizar variáveis em mensagens de campanha
    Suporta campos padrão + custom_fields dinamicamente
    """
    
    # Variáveis padrão disponíveis
    STANDARD_VARIABLES = {
        'nome': lambda c: c.name or '',
        'primeiro_nome': lambda c: c.name.split()[0] if c.name else '',
        'email': lambda c: c.email or '',
        'cidade': lambda c: c.city or '',
        'estado': lambda c: c.state or '',
        'quem_indicou': lambda c: c.referred_by or '',
        'primeiro_nome_indicador': lambda c: c.referred_by.split()[0] if c.referred_by else '',
        'valor_compra': lambda c: f"R$ {c.last_purchase_value:.2f}".replace('.', ',') if c.last_purchase_value else '',
        'data_compra': lambda c: c.last_purchase_date.strftime('%d/%m/%Y') if c.last_purchase_date else '',
    }
    
    @staticmethod
    def get_greeting():
        """Retorna saudação baseada no horário"""
        from datetime import datetime
        hour = datetime.now().hour
        if hour < 12:
            return 'Bom dia'
        elif hour < 18:
            return 'Boa tarde'
        else:
            return 'Boa noite'
    
    @staticmethod
    def get_day_of_week():
        """Retorna dia da semana"""
        from datetime import datetime
        dias = ['Segunda-feira', 'Terça-feira', 'Quarta-feira', 'Quinta-feira', 
                'Sexta-feira', 'Sábado', 'Domingo']
        return dias[datetime.now().weekday()]
    
    @staticmethod
    def render_message(template: str, contact, extra_vars: dict = None) -> str:
        """
        Renderiza template de mensagem com dados do contato
        
        Variáveis suportadas:
        - Padrão: {{nome}}, {{primeiro_nome}}, {{email}}, etc.
        - Customizadas: {{clinica}}, {{valor}}, {{data_compra}}, etc.
        - Sistema: {{saudacao}}, {{dia_semana}}
        
        Args:
            template: Template da mensagem com variáveis {{variavel}}
            contact: Objeto Contact
            extra_vars: Variáveis extras (opcional)
        
        Returns:
            str: Mensagem renderizada
        """
        rendered = template
        
        # 1. Variáveis padrão
        for var_name, getter in MessageVariableService.STANDARD_VARIABLES.items():
            try:
                value = getter(contact)
                rendered = rendered.replace(f'{{{{{var_name}}}}}', str(value))
            except Exception:
                # Se der erro, substituir por string vazia
                rendered = rendered.replace(f'{{{{{var_name}}}}}', '')
        
        # 2. Variáveis de custom_fields (DINÂMICO!)
        if hasattr(contact, 'custom_fields') and contact.custom_fields:
            for key, value in contact.custom_fields.items():
                if value is not None:
                    # Suporta tanto {{clinica}} quanto {{custom.clinica}}
                    rendered = rendered.replace(f'{{{{{key}}}}}', str(value))
                    rendered = rendered.replace(f'{{{{custom.{key}}}}}', str(value))
        
        # 3. Variáveis do sistema
        rendered = rendered.replace('{{saudacao}}', MessageVariableService.get_greeting())
        rendered = rendered.replace('{{dia_semana}}', MessageVariableService.get_day_of_week())
        
        # 4. Variáveis extras (sobrescreve se houver)
        if extra_vars:
            for key, value in extra_vars.items():
                rendered = rendered.replace(f'{{{{{key}}}}}', str(value))
        
        return rendered
    
    @staticmethod
    def get_available_variables(contact=None) -> list:
        """
        Retorna lista de variáveis disponíveis
        
        Args:
            contact: Contato opcional (para incluir custom_fields)
        
        Returns:
            list: Lista de dicts com {variable, display_name, description, category}
        """
        variables = [
            {
                'variable': '{{nome}}',
                'display_name': 'Nome Completo',
                'description': 'Nome completo do contato',
                'category': 'padrão'
            },
            {
                'variable': '{{primeiro_nome}}',
                'display_name': 'Primeiro Nome',
                'description': 'Primeiro nome do contato',
                'category': 'padrão'
            },
            {
                'variable': '{{email}}',
                'display_name': 'Email',
                'description': 'Email do contato',
                'category': 'padrão'
            },
            {
                'variable': '{{cidade}}',
                'display_name': 'Cidade',
                'description': 'Cidade do contato',
                'category': 'padrão'
            },
            {
                'variable': '{{estado}}',
                'display_name': 'Estado (UF)',
                'description': 'Estado do contato',
                'category': 'padrão'
            },
            {
                'variable': '{{valor_compra}}',
                'display_name': 'Valor da Última Compra',
                'description': 'Valor formatado da última compra',
                'category': 'padrão'
            },
            {
                'variable': '{{data_compra}}',
                'display_name': 'Data da Última Compra',
                'description': 'Data da última compra (DD/MM/YYYY)',
                'category': 'padrão'
            },
            {
                'variable': '{{quem_indicou}}',
                'display_name': 'Quem Indicou',
                'description': 'Nome de quem indicou o contato',
                'category': 'padrão'
            },
            {
                'variable': '{{primeiro_nome_indicador}}',
                'display_name': 'Primeiro Nome Indicador',
                'description': 'Primeiro nome de quem indicou',
                'category': 'padrão'
            },
            {
                'variable': '{{saudacao}}',
                'display_name': 'Saudação',
                'description': 'Bom dia/Boa tarde/Boa noite (automático)',
                'category': 'sistema'
            },
            {
                'variable': '{{dia_semana}}',
                'display_name': 'Dia da Semana',
                'description': 'Dia da semana atual',
                'category': 'sistema'
            },
        ]
        
        # Adicionar custom_fields se contato fornecido
        if contact and hasattr(contact, 'custom_fields') and contact.custom_fields:
            import logging
            logger = logging.getLogger(__name__)
            logger.info(f"📋 [VARIABLES SERVICE] Adicionando custom_fields. Tipo: {type(contact)}, custom_fields: {contact.custom_fields}")
            
            for key, value in contact.custom_fields.items():
                variables.append({
                    'variable': f'{{{{{key}}}}}',
                    'display_name': key.replace('_', ' ').title(),
                    'description': f'Campo customizado: {key}',
                    'category': 'customizado',
                    'example_value': str(value) if value else ''
                })
                logger.debug(f"📋 [VARIABLES SERVICE] Adicionada variável customizada: {{{{key}}}}")
        else:
            import logging
            logger = logging.getLogger(__name__)
            logger.debug(f"📋 [VARIABLES SERVICE] Sem custom_fields. contact={contact}, hasattr={hasattr(contact, 'custom_fields') if contact else False}")
        
        return variables
    
    @staticmethod
    def validate_template(template: str) -> tuple[bool, list]:
        """
        Valida template de mensagem
        
        Returns:
            tuple: (is_valid, errors)
        """
        errors = []
        
        # Verificar balanceamento de chaves
        open_count = template.count('{{')
        close_count = template.count('}}')
        
        if open_count != close_count:
            errors.append('Chaves desbalanceadas: número de {{ não corresponde a }}')
        
        # Verificar variáveis malformadas
        import re
        malformed = re.findall(r'\{\{[^}]*[^}]$', template)
        if malformed:
            errors.append(f'Variáveis malformadas: {malformed}')
        
        return len(errors) == 0, errors


class CampaignImportService:
    """
    Service para importar CSV e criar campanha automaticamente
    """
    
    def __init__(self, tenant, user):
        self.tenant = tenant
        self.user = user
        from apps.contacts.services import ContactImportService
        self.contact_service = ContactImportService(tenant, user)
    
    def import_csv_and_create_campaign(
        self,
        file,
        campaign_name,
        campaign_description=None,
        messages=None,
        instances=None,
        column_mapping=None,
        update_existing=False,
        auto_tag_id=None
    ):
        """
        Importa CSV e cria campanha em um único processo
        
        Args:
            file: Arquivo CSV
            campaign_name: Nome da campanha
            campaign_description: Descrição (opcional)
            messages: Lista de mensagens [{content: "...", order: 1}]
            instances: Lista de IDs de instâncias WhatsApp
            column_mapping: Mapeamento customizado (opcional)
            update_existing: Atualizar contatos existentes?
            auto_tag_id: Tag para adicionar automaticamente
        
        Returns:
            dict: {campaign_id, import_id, contacts_created, contacts_updated, total_contacts}
        """
        from django.utils import timezone
        from apps.contacts.models import Contact, ContactImport
        from .models import Campaign, CampaignMessage, CampaignContact
        
        # 1. Importar contatos
        import_result = self.contact_service.process_csv(
            file=file,
            update_existing=update_existing,
            auto_tag_id=auto_tag_id,
            column_mapping=column_mapping
        )
        
        if import_result['status'] != 'success':
            return import_result
        
        # 2. Buscar contatos importados (via import_record)
        import_record = ContactImport.objects.get(id=import_result['import_id'])
        
        # Buscar contatos criados/atualizados no período da importação
        # Usar timestamp da importação como referência
        import_timestamp = import_record.created_at
        
        # Buscar contatos criados após a importação ou atualizados
        recent_contacts = Contact.objects.filter(
            tenant=self.tenant
        ).filter(
            Q(created_at__gte=import_timestamp) |
            Q(updated_at__gte=import_timestamp)
        ).distinct()
        
        # Se não encontrou nenhum, buscar todos os contatos do tenant (fallback)
        if not recent_contacts.exists():
            recent_contacts = Contact.objects.filter(tenant=self.tenant)
        
        # 3. Criar campanha
        campaign = Campaign.objects.create(
            tenant=self.tenant,
            name=campaign_name,
            description=campaign_description or '',
            created_by=self.user,
            status='draft'
        )
        
        # 4. Adicionar instâncias
        if instances:
            from apps.notifications.models import WhatsAppInstance
            instance_objects = WhatsAppInstance.objects.filter(
                id__in=instances,
                tenant=self.tenant
            )
            campaign.instances.set(instance_objects)
        
        # 5. Criar mensagens
        if messages:
            for msg_data in messages:
                CampaignMessage.objects.create(
                    campaign=campaign,
                    content=msg_data.get('content', ''),
                    order=msg_data.get('order', 1)
                )
        
        # 6. Associar contatos à campanha (apenas ativos e não opted-out)
        campaign_contacts = []
        for contact in recent_contacts.filter(is_active=True, opted_out=False):
            campaign_contacts.append(
                CampaignContact(
                    campaign=campaign,
                    contact=contact,
                    status='pending'
                )
            )
        
        if campaign_contacts:
            CampaignContact.objects.bulk_create(campaign_contacts, ignore_conflicts=True)
        
        # 7. Atualizar contador
        campaign.total_contacts = len(campaign_contacts)
        campaign.save()
        
        return {
            'status': 'success',
            'campaign_id': str(campaign.id),
            'import_id': str(import_record.id),
            'contacts_created': import_result.get('created', 0),
            'contacts_updated': import_result.get('updated', 0),
            'total_contacts': len(campaign_contacts),
            'campaign_name': campaign.name
        }
