#!/usr/bin/env python
"""
Script para criar templates de notificação WhatsApp para eventos do sistema
"""
import os
import sys
import django
from django.utils import timezone

# Configurar Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'alrea_sense.settings')
django.setup()

from apps.notifications.models import NotificationTemplate
from apps.authn.models import User

def create_whatsapp_templates():
    """Cria templates de notificação WhatsApp"""
    print("📱 Criando templates de notificação WhatsApp...")
    
    # Buscar um usuário admin para ser o criador
    admin_user = User.objects.filter(is_superuser=True).first()
    if not admin_user:
        admin_user = User.objects.first()
    
    templates = [
        {
            'name': 'celery_worker_down',
            'type': 'whatsapp',
            'category': 'custom',
            'subject': '🚨 ALERTA: Workers do Celery',
            'content': '''🚨 *ALERTA: Workers do Celery*

❌ Os workers do Celery pararam de funcionar!

⏰ *Hora:* {{timestamp}}
🔧 *Status:* Offline
🌐 *Ambiente:* {{environment}}

⚠️ *Ação Necessária:*
• Verificar logs do Railway
• Reiniciar workers se necessário
• Verificar filas de tasks

📊 *Sistema:* Alrea Sense
🏢 *Tenant:* {{tenant_name}}''',
            'is_global': True,
            'is_active': True
        },
        {
            'name': 'celery_worker_up',
            'type': 'whatsapp',
            'category': 'custom',
            'subject': '✅ Workers do Celery Online',
            'content': '''✅ *Workers do Celery Online*

🎉 Os workers do Celery voltaram a funcionar!

⏰ *Hora:* {{timestamp}}
🔧 *Status:* Online
🌐 *Ambiente:* {{environment}}

📊 *Sistema:* Alrea Sense
🏢 *Tenant:* {{tenant_name}}

💚 *Tudo funcionando normalmente!*''',
            'is_global': True,
            'is_active': True
        },
        {
            'name': 'campaign_started',
            'type': 'whatsapp',
            'category': 'custom',
            'subject': '📧 Campanha Iniciada',
            'content': '''📧 *Campanha Iniciada*

🚀 *Nome:* {{campaign_name}}
👥 *Contatos:* {{total_contacts}}
📱 *Instâncias:* {{active_instances}}

⏰ *Iniciada em:* {{started_at}}
🔄 *Modo:* {{rotation_mode}}

📊 *Sistema:* Alrea Sense
🏢 *Tenant:* {{tenant_name}}

🎯 *Campanha em execução!*''',
            'is_global': True,
            'is_active': True
        },
        {
            'name': 'campaign_paused',
            'type': 'whatsapp',
            'category': 'custom',
            'subject': '⏸️ Campanha Pausada',
            'content': '''⏸️ *Campanha Pausada*

📧 *Nome:* {{campaign_name}}
📊 *Progresso:* {{progress_percentage}}%
📤 *Enviadas:* {{messages_sent}}
✅ *Entregues:* {{messages_delivered}}

⏰ *Pausada em:* {{paused_at}}
⏸️ *Status:* Pausada

📊 *Sistema:* Alrea Sense
🏢 *Tenant:* {{tenant_name}}

💤 *Campanha pausada pelo usuário*''',
            'is_global': True,
            'is_active': True
        },
        {
            'name': 'campaign_resumed',
            'type': 'whatsapp',
            'category': 'custom',
            'subject': '▶️ Campanha Retomada',
            'content': '''▶️ *Campanha Retomada*

📧 *Nome:* {{campaign_name}}
📊 *Progresso:* {{progress_percentage}}%
📤 *Enviadas:* {{messages_sent}}
✅ *Entregues:* {{messages_delivered}}

⏰ *Retomada em:* {{resumed_at}}
🔄 *Status:* Em execução

📊 *Sistema:* Alrea Sense
🏢 *Tenant:* {{tenant_name}}

🎯 *Campanha retomada com sucesso!*''',
            'is_global': True,
            'is_active': True
        },
        {
            'name': 'campaign_completed',
            'type': 'whatsapp',
            'category': 'custom',
            'subject': '✅ Campanha Finalizada',
            'content': '''✅ *Campanha Finalizada*

📧 *Nome:* {{campaign_name}}
📊 *Resultados:*
   • 📤 Enviadas: {{messages_sent}}
   • ✅ Entregues: {{messages_delivered}} ({{delivery_rate}}%)
   • 👁️ Lidas: {{messages_read}} ({{read_rate}}%)
   • ❌ Falhas: {{messages_failed}}

⏰ *Finalizada em:* {{completed_at}}
⏱️ *Duração:* {{duration}}

📊 *Sistema:* Alrea Sense
🏢 *Tenant:* {{tenant_name}}

🎉 *Campanha concluída com sucesso!*''',
            'is_global': True,
            'is_active': True
        },
        {
            'name': 'campaign_cancelled',
            'type': 'whatsapp',
            'category': 'custom',
            'subject': '❌ Campanha Cancelada',
            'content': '''❌ *Campanha Cancelada*

📧 *Nome:* {{campaign_name}}
📊 *Progresso:* {{progress_percentage}}%
📤 *Enviadas:* {{messages_sent}}
✅ *Entregues:* {{messages_delivered}}

⏰ *Cancelada em:* {{cancelled_at}}
❌ *Status:* Cancelada

📊 *Sistema:* Alrea Sense
🏢 *Tenant:* {{tenant_name}}

🛑 *Campanha cancelada pelo usuário*''',
            'is_global': True,
            'is_active': True
        },
        {
            'name': 'campaign_error',
            'type': 'whatsapp',
            'category': 'custom',
            'subject': '🚨 Erro na Campanha',
            'content': '''🚨 *Erro na Campanha*

📧 *Nome:* {{campaign_name}}
❌ *Erro:* {{error_message}}

⏰ *Ocorreu em:* {{error_at}}
📍 *Local:* {{error_location}}

📊 *Sistema:* Alrea Sense
🏢 *Tenant:* {{tenant_name}}

⚠️ *Ação necessária para resolver o problema*''',
            'is_global': True,
            'is_active': True
        },
        {
            'name': 'whatsapp_instance_down',
            'type': 'whatsapp',
            'category': 'custom',
            'subject': '📱 Instância WhatsApp Offline',
            'content': '''📱 *Instância WhatsApp Offline*

🔧 *Instância:* {{instance_name}}
📞 *Número:* {{phone_number}}
❌ *Status:* Desconectada

⏰ *Detectado em:* {{detected_at}}
🔍 *Última verificação:* {{last_check}}

📊 *Sistema:* Alrea Sense
🏢 *Tenant:* {{tenant_name}}

⚠️ *Instância precisa ser reconectada*''',
            'is_global': True,
            'is_active': True
        },
        {
            'name': 'whatsapp_instance_up',
            'type': 'whatsapp',
            'category': 'custom',
            'subject': '📱 Instância WhatsApp Online',
            'content': '''📱 *Instância WhatsApp Online*

🔧 *Instância:* {{instance_name}}
📞 *Número:* {{phone_number}}
✅ *Status:* Conectada

⏰ *Conectada em:* {{connected_at}}
💚 *Health Score:* {{health_score}}%

📊 *Sistema:* Alrea Sense
🏢 *Tenant:* {{tenant_name}}

🎉 *Instância funcionando normalmente!*''',
            'is_global': True,
            'is_active': True
        }
    ]
    
    created_count = 0
    updated_count = 0
    
    for template_data in templates:
        template, created = NotificationTemplate.objects.update_or_create(
            name=template_data['name'],
            type=template_data['type'],
            defaults={
                'category': template_data['category'],
                'subject': template_data['subject'],
                'content': template_data['content'],
                'is_global': template_data['is_global'],
                'is_active': template_data['is_active'],
                'created_by': admin_user,
                'updated_at': timezone.now()
            }
        )
        
        if created:
            print(f"✅ Criado: {template.name}")
            created_count += 1
        else:
            print(f"🔄 Atualizado: {template.name}")
            updated_count += 1
    
    print(f"\n📊 Resumo:")
    print(f"   ✅ Criados: {created_count}")
    print(f"   🔄 Atualizados: {updated_count}")
    print(f"   📱 Total de templates WhatsApp: {NotificationTemplate.objects.filter(type='whatsapp', is_global=True).count()}")
    
    return True

if __name__ == "__main__":
    try:
        create_whatsapp_templates()
        print("\n🎉 Templates de notificação WhatsApp criados com sucesso!")
    except Exception as e:
        print(f"\n❌ Erro ao criar templates: {e}")
        sys.exit(1)
