"""
Script de teste para importação de campanhas via CSV

Uso:
    python manage.py shell < test_campaign_import.py
    ou
    python test_campaign_import.py
"""

import os
import sys
import django

# Configurar Django
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'alrea_sense.settings')
django.setup()

from django.contrib.auth import get_user_model
from apps.tenancy.models import Tenant
from apps.campaigns.services import CampaignImportService, MessageVariableService
from apps.contacts.models import Contact
from apps.campaigns.models import Campaign
import io

User = get_user_model()


def test_message_variables():
    """Testa MessageVariableService com campos customizados"""
    print("\n" + "="*60)
    print("TESTE 1: MessageVariableService com custom_fields")
    print("="*60)
    
    # Criar tenant e usuário de teste
    tenant, _ = Tenant.objects.get_or_create(name="Test Tenant")
    user, _ = User.objects.get_or_create(
        username="test_user",
        defaults={'tenant': tenant}
    )
    if not user.tenant:
        user.tenant = tenant
        user.save()
    
    # Criar contato de teste com custom_fields
    contact, _ = Contact.objects.get_or_create(
        tenant=tenant,
        phone="+5511999999999",
        defaults={
            'name': 'Maria Silva',
            'email': 'maria@test.com',
            'custom_fields': {
                'clinica': 'Hospital Veterinário Santa Inês',
                'valor': 'R$ 1.500,00',
                'data_compra': '25/03/2024'
            },
            'last_purchase_value': 1500.00
        }
    )
    
    # Atualizar custom_fields se já existir
    contact.custom_fields = {
        'clinica': 'Hospital Veterinário Santa Inês',
        'valor': 'R$ 1.500,00',
        'data_compra': '25/03/2024'
    }
    contact.save()
    
    # Template de mensagem
    template = """{{saudacao}}, {{primeiro_nome}}!

Lembramos que você tem uma pendência de {{valor_compra}} referente à sua compra em {{data_compra}} na {{clinica}}.

Entre em contato conosco para regularizar."""
    
    # Renderizar
    rendered = MessageVariableService.render_message(template, contact)
    
    print(f"\n📝 Template:")
    print(template)
    print(f"\n✅ Mensagem renderizada:")
    print(rendered)
    print(f"\n📊 Variáveis disponíveis:")
    variables = MessageVariableService.get_available_variables(contact)
    for var in variables:
        print(f"  - {var['variable']}: {var['display_name']} ({var['category']})")
    
    # Validar template
    is_valid, errors = MessageVariableService.validate_template(template)
    print(f"\n✅ Template válido: {is_valid}")
    if errors:
        print(f"❌ Erros: {errors}")


def test_csv_import():
    """Testa importação de CSV e criação de campanha"""
    print("\n" + "="*60)
    print("TESTE 2: Importação CSV + Criação de Campanha")
    print("="*60)
    
    # Criar tenant e usuário de teste
    tenant, _ = Tenant.objects.get_or_create(name="Test Tenant")
    user, _ = User.objects.get_or_create(
        username="test_user",
        defaults={'tenant': tenant}
    )
    if not user.tenant:
        user.tenant = tenant
        user.save()
    
    # CSV de teste (simulando o formato fornecido)
    csv_content = """Nome;DDD;Telefone;email;Clinica;data_compra;Valor
Maria Silva;11;999999999;maria@test.com;Hospital Veterinário Santa Inês;25/03/2024;R$ 1.500,00
João Santos;11;988888888;joao@test.com;Amparo Hospital Veterinário 24h;15/02/2024;R$ 800,00"""
    
    # Criar arquivo em memória
    csv_file = io.BytesIO(csv_content.encode('utf-8'))
    csv_file.name = 'test_campaign.csv'
    
    # Criar service
    service = CampaignImportService(tenant=tenant, user=user)
    
    # Importar
    print("\n📤 Importando CSV e criando campanha...")
    result = service.import_csv_and_create_campaign(
        file=csv_file,
        campaign_name="Teste Campanha Cobrança RA",
        campaign_description="Campanha de teste para cobrança",
        messages=[
            {
                'content': '{{saudacao}}, {{primeiro_nome}}! Você tem uma pendência de {{valor_compra}} na {{clinica}}.',
                'order': 1
            }
        ],
        update_existing=False
    )
    
    print(f"\n✅ Resultado da importação:")
    print(f"  - Status: {result.get('status')}")
    print(f"  - Campanha ID: {result.get('campaign_id')}")
    print(f"  - Contatos criados: {result.get('contacts_created')}")
    print(f"  - Contatos atualizados: {result.get('contacts_updated')}")
    print(f"  - Total na campanha: {result.get('total_contacts')}")
    
    # Verificar campanha criada
    if result.get('campaign_id'):
        campaign = Campaign.objects.get(id=result['campaign_id'])
        print(f"\n📋 Campanha criada:")
        print(f"  - Nome: {campaign.name}")
        print(f"  - Status: {campaign.status}")
        print(f"  - Total de contatos: {campaign.total_contacts}")
        print(f"  - Mensagens: {campaign.messages.count()}")
        
        # Verificar contatos
        contacts = campaign.contacts.all()[:3]
        print(f"\n👥 Primeiros contatos:")
        for contact in contacts:
            print(f"  - {contact.name} ({contact.phone})")
            print(f"    Custom fields: {contact.custom_fields}")


if __name__ == '__main__':
    print("\n🧪 TESTES DE IMPORTAÇÃO DE CAMPANHAS VIA CSV")
    print("="*60)
    
    try:
        # Teste 1: Variáveis
        test_message_variables()
        
        # Teste 2: Importação CSV
        test_csv_import()
        
        print("\n" + "="*60)
        print("✅ TODOS OS TESTES CONCLUÍDOS!")
        print("="*60)
        
    except Exception as e:
        print(f"\n❌ ERRO: {str(e)}")
        import traceback
        traceback.print_exc()

