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
    """Create default subscription plans only if they don't exist."""
    
    # Check if any plans already exist
    if Plan.objects.exists():
        print('📋 Plans already exist, skipping seed...')
        print(f'   Total: {Plan.objects.count()} plans in database')
        return
    
    plans_data = [
        {
            'slug': 'starter',
            'name': 'Starter',
            'description': 'Ideal para pequenas empresas',
            'price': 49.00,
            'color': '#10B981',
            'sort_order': 1,
            'is_active': True,
        },
        {
            'slug': 'pro',
            'name': 'Pro',
            'description': 'Para empresas em crescimento',
            'price': 149.00,
            'color': '#3B82F6',
            'sort_order': 2,
            'is_active': True,
        },
        {
            'slug': 'api-only',
            'name': 'API Only',
            'description': 'Apenas acesso via API',
            'price': 99.00,
            'color': '#8B5CF6',
            'sort_order': 3,
            'is_active': True,
        },
        {
            'slug': 'enterprise',
            'name': 'Enterprise',
            'description': 'Solução completa para grandes empresas',
            'price': 499.00,
            'color': '#F59E0B',
            'sort_order': 4,
            'is_active': True,
        },
    ]
    
    created_count = 0
    updated_count = 0
    
    for plan_data in plans_data:
        plan, created = Plan.objects.update_or_create(
            slug=plan_data['slug'],
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
        import traceback
        traceback.print_exc()
        sys.exit(1)
