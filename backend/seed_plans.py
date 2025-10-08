#!/usr/bin/env python
"""
Seed initial plans into the database.
Run this script after migrations to create default subscription plans.
"""
import os
import sys
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'alrea_sense.settings')
django.setup()

from apps.billing.models import Plan


def seed_plans():
    """Create default subscription plans."""
    
    plans_data = [
        {
            'name': 'Free',
            'description': 'Plano gratuito para testar a plataforma',
            'price': 0,
            'billing_cycle_days': 30,
            'is_free': True,
            'max_connections': 1,
            'max_messages_per_month': 1000,
            'features': [
                '1 conexão WhatsApp',
                '1.000 mensagens/mês',
                'Análise básica de sentimento',
                'Suporte por email',
            ],
            'is_active': True,
        },
        {
            'name': 'Starter',
            'description': 'Ideal para pequenas empresas',
            'price': 49.90,
            'billing_cycle_days': 30,
            'is_free': False,
            'max_connections': 3,
            'max_messages_per_month': 10000,
            'features': [
                '3 conexões WhatsApp',
                '10.000 mensagens/mês',
                'Análise completa de sentimento',
                'Dashboard personalizado',
                'Suporte prioritário',
            ],
            'is_active': True,
        },
        {
            'name': 'Pro',
            'description': 'Para empresas em crescimento',
            'price': 149.90,
            'billing_cycle_days': 30,
            'is_free': False,
            'max_connections': 10,
            'max_messages_per_month': 50000,
            'features': [
                '10 conexões WhatsApp',
                '50.000 mensagens/mês',
                'Análise avançada com IA',
                'Experimentos A/B',
                'Integração via API',
                'Suporte 24/7',
                'Webhooks personalizados',
            ],
            'is_active': True,
        },
        {
            'name': 'Enterprise',
            'description': 'Solução completa para grandes empresas',
            'price': 499.90,
            'billing_cycle_days': 30,
            'is_free': False,
            'max_connections': -1,  # Unlimited
            'max_messages_per_month': -1,  # Unlimited
            'features': [
                'Conexões ilimitadas',
                'Mensagens ilimitadas',
                'IA personalizada',
                'Suporte dedicado',
                'SLA garantido',
                'Treinamento da equipe',
                'Custom features sob demanda',
            ],
            'is_active': True,
        },
    ]
    
    created_count = 0
    updated_count = 0
    
    for plan_data in plans_data:
        plan, created = Plan.objects.update_or_create(
            name=plan_data['name'],
            defaults=plan_data
        )
        
        if created:
            created_count += 1
            print(f'✅ Created plan: {plan.name} - R$ {plan.price}')
        else:
            updated_count += 1
            print(f'🔄 Updated plan: {plan.name} - R$ {plan.price}')
    
    print(f'\n🎉 Seed completed!')
    print(f'   Created: {created_count} plans')
    print(f'   Updated: {updated_count} plans')
    print(f'   Total: {Plan.objects.count()} plans in database')


if __name__ == '__main__':
    print('🌱 Seeding plans...\n')
    try:
        seed_plans()
    except Exception as e:
        print(f'❌ Error seeding plans: {e}')
        sys.exit(1)

