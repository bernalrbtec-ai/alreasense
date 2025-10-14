"""
Sistema de Monitoramento e Alertas para Campanhas
Implementa health checks, métricas e alertas em tempo real
"""
import time
import logging
from typing import Dict, Any, List, Optional
from dataclasses import dataclass
from datetime import datetime, timedelta
from django.utils import timezone
from django.db.models import Count, Q
from django.core.mail import send_mail
from django.conf import settings
import json

from .models import Campaign, CampaignContact, CampaignLog
from apps.notifications.models import WhatsAppInstance

logger = logging.getLogger(__name__)


@dataclass
class HealthMetrics:
    """Métricas de saúde da campanha"""
    campaign_id: str
    campaign_name: str
    status: str
    messages_sent: int
    messages_delivered: int
    messages_failed: int
    pending_contacts: int
    processing_rate: float  # mensagens por minuto
    success_rate: float     # taxa de sucesso
    last_activity: datetime
    health_score: int       # 0-100
    issues: List[str]
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'campaign_id': self.campaign_id,
            'campaign_name': self.campaign_name,
            'status': self.status,
            'messages_sent': self.messages_sent,
            'messages_delivered': self.messages_delivered,
            'messages_failed': self.messages_failed,
            'pending_contacts': self.pending_contacts,
            'processing_rate': self.processing_rate,
            'success_rate': self.success_rate,
            'last_activity': self.last_activity.isoformat() if self.last_activity else None,
            'health_score': self.health_score,
            'issues': self.issues
        }


@dataclass
class Alert:
    """Alerta do sistema"""
    alert_id: str
    campaign_id: str
    severity: str  # info, warning, error, critical
    title: str
    message: str
    timestamp: datetime
    resolved: bool = False
    resolved_at: Optional[datetime] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'alert_id': self.alert_id,
            'campaign_id': self.campaign_id,
            'severity': self.severity,
            'title': self.title,
            'message': self.message,
            'timestamp': self.timestamp.isoformat(),
            'resolved': self.resolved,
            'resolved_at': self.resolved_at.isoformat() if self.resolved_at else None
        }


class CampaignHealthMonitor:
    """Monitor de saúde das campanhas"""
    
    def __init__(self):
        self.metrics_history: Dict[str, List[HealthMetrics]] = {}
        self.active_alerts: Dict[str, List[Alert]] = {}
        self.alert_thresholds = {
            'processing_rate_min': 0.1,  # mensagens por minuto
            'success_rate_min': 0.7,     # 70% de sucesso
            'health_score_min': 60,      # score mínimo
            'stall_timeout': 300,        # 5 minutos sem atividade
            'error_rate_max': 0.3        # 30% de erro máximo
        }
    
    def collect_metrics(self, campaign_id: str) -> HealthMetrics:
        """Coleta métricas de uma campanha"""
        try:
            campaign = Campaign.objects.get(id=campaign_id)
            
            # Métricas básicas
            messages_sent = campaign.messages_sent
            messages_delivered = campaign.messages_delivered
            messages_failed = campaign.messages_failed
            
            # Contatos pendentes
            pending_contacts = CampaignContact.objects.filter(
                campaign=campaign,
                status__in=['pending', 'sending']
            ).count()
            
            # Taxa de sucesso
            total_processed = messages_delivered + messages_failed
            success_rate = (messages_delivered / total_processed) if total_processed > 0 else 0
            
            # Taxa de processamento (últimos 10 minutos)
            ten_minutes_ago = timezone.now() - timedelta(minutes=10)
            recent_sent = CampaignLog.objects.filter(
                campaign=campaign,
                log_type='message_sent',
                created_at__gte=ten_minutes_ago
            ).count()
            processing_rate = recent_sent / 10.0  # por minuto
            
            # Última atividade
            last_activity = CampaignLog.objects.filter(
                campaign=campaign
            ).order_by('-created_at').first()
            last_activity_time = last_activity.created_at if last_activity else None
            
            # Calcular health score
            health_score = self._calculate_health_score(
                success_rate, processing_rate, pending_contacts, last_activity_time
            )
            
            # Identificar issues
            issues = self._identify_issues(
                campaign, success_rate, processing_rate, pending_contacts, last_activity_time
            )
            
            metrics = HealthMetrics(
                campaign_id=campaign_id,
                campaign_name=campaign.name,
                status=campaign.status,
                messages_sent=messages_sent,
                messages_delivered=messages_delivered,
                messages_failed=messages_failed,
                pending_contacts=pending_contacts,
                processing_rate=processing_rate,
                success_rate=success_rate,
                last_activity=last_activity_time,
                health_score=health_score,
                issues=issues
            )
            
            # Armazenar histórico
            if campaign_id not in self.metrics_history:
                self.metrics_history[campaign_id] = []
            
            self.metrics_history[campaign_id].append(metrics)
            
            # Manter apenas últimos 100 registros
            if len(self.metrics_history[campaign_id]) > 100:
                self.metrics_history[campaign_id] = self.metrics_history[campaign_id][-100:]
            
            return metrics
            
        except Campaign.DoesNotExist:
            logger.error(f"❌ [MONITOR] Campanha não encontrada: {campaign_id}")
            raise
        except Exception as e:
            logger.error(f"❌ [MONITOR] Erro ao coletar métricas: {e}")
            raise
    
    def _calculate_health_score(self, success_rate: float, processing_rate: float, 
                              pending_contacts: int, last_activity: Optional[datetime]) -> int:
        """Calcula score de saúde (0-100)"""
        score = 100
        
        # Penalizar por taxa de sucesso baixa
        if success_rate < 0.9:
            score -= int((0.9 - success_rate) * 50)
        
        # Penalizar por taxa de processamento baixa
        if processing_rate < 0.5:
            score -= int((0.5 - processing_rate) * 30)
        
        # Penalizar por falta de atividade
        if last_activity:
            minutes_since_activity = (timezone.now() - last_activity).total_seconds() / 60
            if minutes_since_activity > 5:
                score -= min(int(minutes_since_activity * 2), 40)
        
        # Penalizar por muitos contatos pendentes sem progresso
        if pending_contacts > 100:
            score -= min(pending_contacts // 10, 20)
        
        return max(0, min(100, score))
    
    def _identify_issues(self, campaign: Campaign, success_rate: float, 
                        processing_rate: float, pending_contacts: int, 
                        last_activity: Optional[datetime]) -> List[str]:
        """Identifica problemas na campanha"""
        issues = []
        
        # Taxa de sucesso baixa
        if success_rate < self.alert_thresholds['success_rate_min']:
            issues.append(f"Taxa de sucesso baixa: {success_rate:.1%}")
        
        # Taxa de processamento baixa
        if processing_rate < self.alert_thresholds['processing_rate_min']:
            issues.append(f"Processamento lento: {processing_rate:.1f} msg/min")
        
        # Falta de atividade
        if last_activity:
            minutes_since_activity = (timezone.now() - last_activity).total_seconds() / 60
            if minutes_since_activity > self.alert_thresholds['stall_timeout'] / 60:
                issues.append(f"Sem atividade há {minutes_since_activity:.0f} minutos")
        
        # Muitos contatos pendentes
        if pending_contacts > 50:
            issues.append(f"Muitos contatos pendentes: {pending_contacts}")
        
        # Instâncias indisponíveis
        available_instances = WhatsAppInstance.objects.filter(
            is_active=True,
            health_score__gte=campaign.pause_on_health_below
        ).count()
        
        if available_instances == 0:
            issues.append("Nenhuma instância disponível")
        
        return issues
    
    def check_alerts(self, campaign_id: str, metrics: HealthMetrics) -> List[Alert]:
        """Verifica se há alertas para disparar"""
        alerts = []
        
        # Verificar se já existem alertas ativos
        active_alerts = self.active_alerts.get(campaign_id, [])
        
        # Alert de taxa de sucesso baixa
        if metrics.success_rate < self.alert_thresholds['success_rate_min']:
            alert_id = f"low_success_rate_{campaign_id}"
            if not any(a.alert_id == alert_id and not a.resolved for a in active_alerts):
                alert = Alert(
                    alert_id=alert_id,
                    campaign_id=campaign_id,
                    severity="warning",
                    title="Taxa de Sucesso Baixa",
                    message=f"Taxa de sucesso está em {metrics.success_rate:.1%}",
                    timestamp=timezone.now()
                )
                alerts.append(alert)
        
        # Alert de processamento lento
        if metrics.processing_rate < self.alert_thresholds['processing_rate_min']:
            alert_id = f"slow_processing_{campaign_id}"
            if not any(a.alert_id == alert_id and not a.resolved for a in active_alerts):
                alert = Alert(
                    alert_id=alert_id,
                    campaign_id=campaign_id,
                    severity="warning",
                    title="Processamento Lento",
                    message=f"Taxa de processamento: {metrics.processing_rate:.1f} msg/min",
                    timestamp=timezone.now()
                )
                alerts.append(alert)
        
        # Alert de campanha travada
        if metrics.last_activity:
            minutes_since_activity = (timezone.now() - metrics.last_activity).total_seconds() / 60
            if minutes_since_activity > self.alert_thresholds['stall_timeout'] / 60:
                alert_id = f"stalled_campaign_{campaign_id}"
                if not any(a.alert_id == alert_id and not a.resolved for a in active_alerts):
                    alert = Alert(
                        alert_id=alert_id,
                        campaign_id=campaign_id,
                        severity="error",
                        title="Campanha Travada",
                        message=f"Sem atividade há {minutes_since_activity:.0f} minutos",
                        timestamp=timezone.now()
                    )
                    alerts.append(alert)
        
        # Alert de instâncias indisponíveis
        if "Nenhuma instância disponível" in metrics.issues:
            alert_id = f"no_instances_{campaign_id}"
            if not any(a.alert_id == alert_id and not a.resolved for a in active_alerts):
                alert = Alert(
                    alert_id=alert_id,
                    campaign_id=campaign_id,
                    severity="critical",
                    title="Instâncias Indisponíveis",
                    message="Nenhuma instância WhatsApp disponível",
                    timestamp=timezone.now()
                )
                alerts.append(alert)
        
        # Armazenar alertas
        if alerts:
            if campaign_id not in self.active_alerts:
                self.active_alerts[campaign_id] = []
            
            self.active_alerts[campaign_id].extend(alerts)
            
            # Enviar notificações
            for alert in alerts:
                self._send_alert_notification(alert)
        
        return alerts
    
    def _send_alert_notification(self, alert: Alert):
        """Envia notificação de alerta"""
        try:
            # Log do alerta
            logger.warning(f"🚨 [ALERT] {alert.severity.upper()}: {alert.title} - {alert.message}")
            
            # Salvar no banco
            CampaignLog.log_error(
                campaign=Campaign.objects.get(id=alert.campaign_id),
                error_msg=f"ALERTA {alert.severity.upper()}: {alert.title}",
                details={
                    'alert_id': alert.alert_id,
                    'message': alert.message,
                    'timestamp': alert.timestamp.isoformat()
                }
            )
            
            # Enviar email (se configurado)
            if hasattr(settings, 'ALERT_EMAIL_RECIPIENTS'):
                self._send_email_alert(alert)
                
        except Exception as e:
            logger.error(f"❌ [ALERT] Erro ao enviar notificação: {e}")
    
    def _send_email_alert(self, alert: Alert):
        """Envia alerta por email"""
        try:
            subject = f"[{alert.severity.upper()}] {alert.title} - Campanha {alert.campaign_id}"
            message = f"""
            Alerta do Sistema de Campanhas
            
            Severidade: {alert.severity.upper()}
            Campanha: {alert.campaign_id}
            Título: {alert.title}
            Mensagem: {alert.message}
            Timestamp: {alert.timestamp}
            
            Acesse o painel para mais detalhes.
            """
            
            send_mail(
                subject=subject,
                message=message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=settings.ALERT_EMAIL_RECIPIENTS,
                fail_silently=True
            )
            
            logger.info(f"📧 [EMAIL] Alerta enviado: {alert.title}")
            
        except Exception as e:
            logger.error(f"❌ [EMAIL] Erro ao enviar email: {e}")
    
    def resolve_alert(self, campaign_id: str, alert_id: str):
        """Resolve um alerta"""
        if campaign_id in self.active_alerts:
            for alert in self.active_alerts[campaign_id]:
                if alert.alert_id == alert_id and not alert.resolved:
                    alert.resolved = True
                    alert.resolved_at = timezone.now()
                    logger.info(f"✅ [ALERT] Alerta resolvido: {alert_id}")
                    break
    
    def get_campaign_health(self, campaign_id: str) -> Optional[HealthMetrics]:
        """Retorna saúde atual da campanha"""
        try:
            return self.collect_metrics(campaign_id)
        except Exception as e:
            logger.error(f"❌ [MONITOR] Erro ao obter saúde: {e}")
            return None
    
    def get_campaign_alerts(self, campaign_id: str) -> List[Alert]:
        """Retorna alertas ativos da campanha"""
        return self.active_alerts.get(campaign_id, [])
    
    def get_all_active_alerts(self) -> Dict[str, List[Alert]]:
        """Retorna todos os alertas ativos"""
        return {k: [a for a in v if not a.resolved] for k, v in self.active_alerts.items()}


class SystemHealthMonitor:
    """Monitor de saúde do sistema"""
    
    def __init__(self):
        self.campaign_monitor = CampaignHealthMonitor()
    
    def monitor_all_campaigns(self):
        """Monitora todas as campanhas ativas"""
        try:
            active_campaigns = Campaign.objects.filter(status='running')
            
            for campaign in active_campaigns:
                try:
                    # Coletar métricas
                    metrics = self.campaign_monitor.collect_metrics(str(campaign.id))
                    
                    # Verificar alertas
                    alerts = self.campaign_monitor.check_alerts(str(campaign.id), metrics)
                    
                    # Log de status
                    logger.info(f"📊 [SYSTEM] Campanha {campaign.name}: "
                              f"Health={metrics.health_score}, "
                              f"Sent={metrics.messages_sent}, "
                              f"Pending={metrics.pending_contacts}")
                    
                except Exception as e:
                    logger.error(f"❌ [SYSTEM] Erro ao monitorar campanha {campaign.id}: {e}")
            
            logger.info(f"✅ [SYSTEM] Monitoramento concluído para {active_campaigns.count()} campanhas")
            
        except Exception as e:
            logger.error(f"❌ [SYSTEM] Erro no monitoramento: {e}")
    
    def get_system_health(self) -> Dict[str, Any]:
        """Retorna saúde geral do sistema"""
        try:
            # Estatísticas gerais
            total_campaigns = Campaign.objects.count()
            active_campaigns = Campaign.objects.filter(status='running').count()
            paused_campaigns = Campaign.objects.filter(status='paused').count()
            completed_campaigns = Campaign.objects.filter(status='completed').count()
            
            # Instâncias
            total_instances = WhatsAppInstance.objects.count()
            active_instances = WhatsAppInstance.objects.filter(is_active=True).count()
            
            # Alertas ativos
            all_alerts = self.campaign_monitor.get_all_active_alerts()
            total_alerts = sum(len(alerts) for alerts in all_alerts.values())
            critical_alerts = sum(
                len([a for a in alerts if a.severity == 'critical'])
                for alerts in all_alerts.values()
            )
            
            return {
                'timestamp': timezone.now().isoformat(),
                'campaigns': {
                    'total': total_campaigns,
                    'active': active_campaigns,
                    'paused': paused_campaigns,
                    'completed': completed_campaigns
                },
                'instances': {
                    'total': total_instances,
                    'active': active_instances
                },
                'alerts': {
                    'total': total_alerts,
                    'critical': critical_alerts
                },
                'system_health': 'healthy' if critical_alerts == 0 else 'degraded'
            }
            
        except Exception as e:
            logger.error(f"❌ [SYSTEM] Erro ao obter saúde do sistema: {e}")
            return {'error': str(e)}


# Instâncias globais
campaign_health_monitor = CampaignHealthMonitor()
system_health_monitor = SystemHealthMonitor()
