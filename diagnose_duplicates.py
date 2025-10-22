"""
Script para diagnosticar conversas duplicadas.
Identifica contatos com múltiplas conversas e analisa as diferenças.
"""
import os
import sys
import django
from pathlib import Path
from collections import defaultdict

# Setup Django
current_dir = Path(__file__).parent
backend_dir = current_dir / 'backend'
sys.path.insert(0, str(backend_dir))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django.db.models import Count
from apps.chat.models import Conversation
from apps.tenancy.models import Tenant


def analyze_duplicates():
    """Analisa conversas duplicadas."""
    
    print("\n" + "="*80)
    print("🔍 DIAGNÓSTICO DE CONVERSAS DUPLICADAS")
    print("="*80)
    
    # Listar tenants
    tenants = Tenant.objects.all()
    
    for tenant in tenants:
        print(f"\n{'='*80}")
        print(f"📋 TENANT: {tenant.name} (ID: {tenant.id})")
        print(f"{'='*80}")
        
        # Buscar conversas
        conversations = Conversation.objects.filter(tenant=tenant).order_by(
            'contact_phone', '-last_message_at'
        )
        
        total_convs = conversations.count()
        print(f"\n📊 Total de conversas: {total_convs}")
        
        if total_convs == 0:
            print("   ✅ Nenhuma conversa encontrada")
            continue
        
        # Agrupar por telefone
        phone_groups = defaultdict(list)
        for conv in conversations:
            phone_groups[conv.contact_phone].append(conv)
        
        # Identificar duplicatas
        duplicates = {phone: convs for phone, convs in phone_groups.items() if len(convs) > 1}
        unique = {phone: convs for phone, convs in phone_groups.items() if len(convs) == 1}
        
        print(f"✅ Contatos únicos: {len(unique)}")
        print(f"⚠️  Contatos duplicados: {len(duplicates)}")
        
        if duplicates:
            print(f"\n{'='*80}")
            print("🔴 CONTATOS COM MÚLTIPLAS CONVERSAS:")
            print(f"{'='*80}")
            
            for phone, convs in sorted(duplicates.items(), key=lambda x: len(x[1]), reverse=True):
                print(f"\n📞 {phone}")
                print(f"   Nome: {convs[0].contact_name}")
                print(f"   Tipo: {convs[0].conversation_type}")
                print(f"   🔢 {len(convs)} conversas encontradas:\n")
                
                for idx, conv in enumerate(convs, 1):
                    msg_count = conv.messages.count()
                    status_emoji = {
                        'pending': '⏸️',
                        'open': '✅',
                        'closed': '🔒'
                    }.get(conv.status, '❓')
                    
                    print(f"      {idx}. ID: {conv.id}")
                    print(f"         Status: {status_emoji} {conv.status}")
                    print(f"         Mensagens: {msg_count}")
                    print(f"         Última msg: {conv.last_message_at or 'N/A'}")
                    print(f"         Departamento: {conv.department.name if conv.department else 'Inbox'}")
                    print(f"         Instância: {conv.instance_name or 'N/A'}")
                    print(f"         Criado em: {conv.created_at}")
                    
                    # Mostrar diferenças nos dados
                    diffs = []
                    if idx > 1:
                        prev = convs[idx-2]
                        if conv.contact_name != prev.contact_name:
                            diffs.append(f"Nome diferente: '{prev.contact_name}' → '{conv.contact_name}'")
                        if conv.profile_pic_url != prev.profile_pic_url:
                            diffs.append("Foto de perfil diferente")
                        if conv.instance_name != prev.instance_name:
                            diffs.append(f"Instância diferente: '{prev.instance_name}' → '{conv.instance_name}'")
                    
                    if diffs:
                        print(f"         ⚠️  Diferenças: {'; '.join(diffs)}")
                    print()
        
        # Estatísticas gerais
        print(f"\n{'='*80}")
        print("📊 ESTATÍSTICAS POR TIPO:")
        print(f"{'='*80}")
        
        types_count = conversations.values('conversation_type').annotate(
            count=Count('id')
        ).order_by('-count')
        
        for item in types_count:
            conv_type = item['conversation_type']
            count = item['count']
            print(f"   {conv_type}: {count}")
        
        # Estatísticas de status
        print(f"\n📊 ESTATÍSTICAS POR STATUS:")
        print(f"{'='*80}")
        
        status_count = conversations.values('status').annotate(
            count=Count('id')
        ).order_by('-count')
        
        for item in status_count:
            conv_status = item['status']
            count = item['count']
            emoji = {
                'pending': '⏸️',
                'open': '✅',
                'closed': '🔒'
            }.get(conv_status, '❓')
            print(f"   {emoji} {conv_status}: {count}")
        
        # Conversas sem última mensagem
        no_last_msg = conversations.filter(last_message_at__isnull=True).count()
        if no_last_msg > 0:
            print(f"\n⚠️  Conversas sem última mensagem: {no_last_msg}")
        
        # Conversas órfãs (sem instância)
        no_instance = conversations.filter(instance_name='').count()
        if no_instance > 0:
            print(f"⚠️  Conversas sem instância: {no_instance}")
    
    print(f"\n{'='*80}")
    print("✅ DIAGNÓSTICO CONCLUÍDO")
    print(f"{'='*80}\n")


def main():
    try:
        analyze_duplicates()
    except Exception as e:
        print(f"\n❌ ERRO: {e}")
        import traceback
        traceback.print_exc()


if __name__ == '__main__':
    main()

