"""
Management command para configurar webhooks do Flow Chat nas instâncias Evolution
"""
from django.core.management.base import BaseCommand
from django.conf import settings
from apps.connections.models import EvolutionConnection
import httpx
import asyncio


class Command(BaseCommand):
    help = 'Configura webhooks do Flow Chat em todas as instâncias Evolution ativas'

    def handle(self, *args, **options):
        self.stdout.write('🔧 Configurando webhooks do Flow Chat...\n')
        
        # URL do webhook (deve ser acessível externamente)
        webhook_url = getattr(settings, 'CHAT_WEBHOOK_URL', None)
        
        if not webhook_url:
            # Tentar descobrir automaticamente
            base_url = getattr(settings, 'BACKEND_URL', 'https://alreasense-backend-production.up.railway.app')
            webhook_url = f"{base_url}/api/chat/webhook/evolution/"
        
        self.stdout.write(f'📡 Webhook URL: {webhook_url}\n')
        
        # Buscar todas as instâncias ativas
        instances = EvolutionConnection.objects.filter(is_active=True, status='active')
        
        if not instances.exists():
            self.stdout.write(self.style.WARNING('⚠️  Nenhuma instância conectada encontrada'))
            return
        
        self.stdout.write(f'📱 Encontradas {instances.count()} instâncias conectadas\n')
        
        # Configurar webhook em cada instância
        asyncio.run(self.setup_webhooks(instances, webhook_url))
        
        self.stdout.write(self.style.SUCCESS('\n✅ Configuração concluída!'))
    
    async def setup_webhooks(self, instances, webhook_url):
        """Configura webhooks de forma assíncrona."""
        tasks = []
        for instance in instances:
            tasks.append(self.setup_instance_webhook(instance, webhook_url))
        
        await asyncio.gather(*tasks)
    
    async def setup_instance_webhook(self, instance, webhook_url):
        """Configura webhook para uma instância específica."""
        try:
            self.stdout.write(f'\n📲 Configurando: {instance.name} ({instance.instance_name})')
            
            # URL da API Evolution
            api_url = f"{instance.base_url}/webhook/set/{instance.instance_name}"
            
            headers = {
                'apikey': instance.api_key,
                'Content-Type': 'application/json'
            }
            
            payload = {
                'url': webhook_url,
                'webhook_by_events': False,
                'webhook_base64': False,
                'events': [
                    'MESSAGES_UPSERT',
                    'MESSAGES_UPDATE',
                    'SEND_MESSAGE'
                ]
            }
            
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(api_url, json=payload, headers=headers)
                
                if response.status_code in [200, 201]:
                    self.stdout.write(self.style.SUCCESS(f'   ✅ Webhook configurado com sucesso!'))
                else:
                    self.stdout.write(self.style.ERROR(
                        f'   ❌ Erro ao configurar webhook: {response.status_code} - {response.text}'
                    ))
        
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'   ❌ Erro: {str(e)}'))

