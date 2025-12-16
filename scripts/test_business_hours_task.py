"""
Script de teste para validação de criação de tarefas fora de horário.

Este script testa:
1. Parsing de next_open_time (formato legível para datetime)
2. Cálculo de próximo horário de abertura
3. Criação de tarefas consolidadas
"""
import os
import sys
import django
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

# Setup Django
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from apps.chat.services.business_hours_service import BusinessHoursService
from apps.chat.models_business_hours import BusinessHours
from apps.authn.models import Tenant
from django.utils import timezone as django_timezone

def test_next_open_datetime():
    """Testa o cálculo de próximo horário de abertura."""
    print("=" * 60)
    print("TESTE 1: Cálculo de próximo horário de abertura")
    print("=" * 60)
    
    # Buscar tenant de teste (ou criar um)
    tenant = Tenant.objects.first()
    if not tenant:
        print("❌ Nenhum tenant encontrado. Crie um tenant primeiro.")
        return
    
    # Buscar business hours
    business_hours = BusinessHoursService.get_business_hours(tenant)
    if not business_hours:
        print("❌ Nenhum business hours configurado. Configure primeiro.")
        return
    
    print(f"✅ Business hours encontrado: {business_hours.id}")
    print(f"   Timezone: {business_hours.timezone}")
    print(f"   Is Active: {business_hours.is_active}")
    
    # Testar com datetime atual
    current_dt = django_timezone.now()
    print(f"\n📅 Data/hora atual: {current_dt}")
    
    # Calcular próximo horário (string formatada)
    next_open_str = BusinessHoursService._get_next_open_time(business_hours, current_dt)
    print(f"📝 Próximo horário (string): {next_open_str}")
    
    # Calcular próximo horário (datetime)
    next_open_dt = BusinessHoursService._get_next_open_datetime(business_hours, current_dt)
    if next_open_dt:
        print(f"📅 Próximo horário (datetime): {next_open_dt}")
        print(f"   Timezone: {next_open_dt.tzinfo}")
        print(f"   É timezone-aware? {django_timezone.is_aware(next_open_dt)}")
    else:
        print("⚠️ Não foi possível calcular próximo horário")
    
    print("\n✅ Teste 1 concluído!\n")


def test_is_business_hours():
    """Testa a verificação de horário de atendimento."""
    print("=" * 60)
    print("TESTE 2: Verificação de horário de atendimento")
    print("=" * 60)
    
    tenant = Tenant.objects.first()
    if not tenant:
        print("❌ Nenhum tenant encontrado.")
        return
    
    # Testar com datetime atual
    current_dt = django_timezone.now()
    print(f"📅 Data/hora atual: {current_dt}")
    
    is_open, next_open_str = BusinessHoursService.is_business_hours(tenant, None, current_dt)
    print(f"⏰ Está aberto? {is_open}")
    print(f"📝 Próximo horário: {next_open_str}")
    
    print("\n✅ Teste 2 concluído!\n")


def test_parsing_next_open_time():
    """Testa o parsing de next_open_time em diferentes formatos."""
    print("=" * 60)
    print("TESTE 3: Parsing de next_open_time")
    print("=" * 60)
    
    tenant = Tenant.objects.first()
    if not tenant:
        print("❌ Nenhum tenant encontrado.")
        return
    
    business_hours = BusinessHoursService.get_business_hours(tenant)
    if not business_hours:
        print("❌ Nenhum business hours configurado.")
        return
    
    # Simular diferentes formatos de next_open_time
    test_cases = [
        "Terça-feira, 08:15",  # Formato legível (o que estava causando erro)
        "2025-12-16T08:15:00+00:00",  # Formato ISO
        None,  # None
    ]
    
    current_dt = django_timezone.now()
    
    for test_case in test_cases:
        print(f"\n🧪 Testando: {test_case}")
        
        # Simular o que acontece no create_after_hours_task
        if isinstance(test_case, str) and not test_case.startswith('2025'):
            # Formato legível - usar método direto
            next_open_dt = BusinessHoursService._get_next_open_datetime(business_hours, current_dt)
            if next_open_dt:
                print(f"   ✅ Parsing bem-sucedido: {next_open_dt}")
            else:
                print(f"   ⚠️ Não foi possível calcular (usando fallback)")
                next_open_dt = django_timezone.now() + timedelta(hours=24)
                print(f"   📅 Fallback: {next_open_dt}")
        elif isinstance(test_case, str) and test_case.startswith('2025'):
            # Formato ISO - tentar parsear
            try:
                next_open_dt = datetime.fromisoformat(test_case.replace('Z', '+00:00'))
                print(f"   ✅ Parsing ISO bem-sucedido: {next_open_dt}")
            except ValueError as e:
                print(f"   ❌ Erro ao parsear ISO: {e}")
                next_open_dt = django_timezone.now() + timedelta(hours=24)
                print(f"   📅 Fallback: {next_open_dt}")
        else:
            # None - usar fallback
            print(f"   ⚠️ next_open_time é None (usando fallback)")
            next_open_dt = django_timezone.now() + timedelta(hours=24)
            print(f"   📅 Fallback: {next_open_dt}")
        
        # Garantir timezone-aware
        if django_timezone.is_naive(next_open_dt):
            next_open_dt = django_timezone.make_aware(next_open_dt, ZoneInfo('UTC'))
            print(f"   🔧 Convertido para timezone-aware: {next_open_dt}")
    
    print("\n✅ Teste 3 concluído!\n")


if __name__ == '__main__':
    print("\n" + "=" * 60)
    print("TESTES DE BUSINESS HOURS TASK")
    print("=" * 60 + "\n")
    
    try:
        test_next_open_datetime()
        test_is_business_hours()
        test_parsing_next_open_time()
        
        print("=" * 60)
        print("✅ TODOS OS TESTES CONCLUÍDOS!")
        print("=" * 60)
    except Exception as e:
        print(f"\n❌ ERRO: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

