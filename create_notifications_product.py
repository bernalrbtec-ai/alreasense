#!/usr/bin/env python
"""
Criar produto de Notificações e configurar nos planos
"""
import psycopg2
from datetime import datetime

DATABASE_URL = "postgresql://postgres:wDxByyoBGIzFwodHccWSkeLmqCcuwpVt@caboose.proxy.rlwy.net:25280/railway"

def create_notifications_product():
    try:
        conn = psycopg2.connect(DATABASE_URL)
        cursor = conn.cursor()
        
        print("="*80)
        print("🔔 CRIANDO PRODUTO DE NOTIFICAÇÕES")
        print("="*80)
        
        # 1. Verificar se produto já existe
        cursor.execute("""
            SELECT id, name, slug FROM billing_product 
            WHERE slug = 'notifications' OR name ILIKE '%notificação%';
        """)
        
        existing_product = cursor.fetchone()
        
        if existing_product:
            print(f"⚠️ Produto já existe: {existing_product[1]} (ID: {existing_product[0]})")
            product_id = existing_product[0]
        else:
            # 2. Criar produto de Notificações
            cursor.execute("""
                INSERT INTO billing_product (
                    id, name, slug, description, 
                    requires_ui_access, addon_price, 
                    icon, color, is_active, created_at, updated_at
                ) VALUES (
                    gen_random_uuid(),
                    'Notificações de Campanha', 
                    'notifications', 
                    'Sistema de notificações em tempo real para respostas de campanhas de marketing',
                    true,
                    29.00,
                    'bell',
                    '#10B981',
                    true,
                    NOW(),
                    NOW()
                ) RETURNING id;
            """)
            
            product_id = cursor.fetchone()[0]
            print(f"✅ Produto criado: Notificações de Campanha (ID: {product_id})")
        
        # 3. Verificar planos existentes
        cursor.execute("""
            SELECT id, name, slug FROM billing_plan 
            WHERE is_active = true
            ORDER BY sort_order;
        """)
        
        plans = cursor.fetchall()
        print(f"\n📋 Planos encontrados: {len(plans)}")
        
        for plan_id, plan_name, plan_slug in plans:
            print(f"   - {plan_name} ({plan_slug})")
        
        # 4. Configurar produto nos planos
        print(f"\n🔧 CONFIGURANDO PRODUTO NOS PLANOS:")
        print("-" * 80)
        
        # Planos que devem incluir notificações
        plans_with_notifications = ['flow-pro', 'flow-enterprise']
        
        for plan_id, plan_name, plan_slug in plans:
            # Verificar se plano já tem o produto
            cursor.execute("""
                SELECT id FROM billing_plan_product 
                WHERE plan_id = %s AND product_id = %s;
            """, (plan_id, product_id))
            
            existing_association = cursor.fetchone()
            
            if plan_slug in plans_with_notifications:
                if existing_association:
                    print(f"✅ {plan_name}: Notificações já incluído")
                else:
                    # Adicionar produto ao plano
                    cursor.execute("""
                        INSERT INTO billing_plan_product (
                            plan_id, product_id, is_included, is_addon_available, created_at
                        ) VALUES (
                            %s, %s, true, false, NOW()
                        );
                    """, (plan_id, product_id))
                    
                    print(f"✅ {plan_name}: Notificações adicionado")
            else:
                if existing_association:
                    # Remover se existir (para planos que não devem ter)
                    cursor.execute("""
                        DELETE FROM billing_plan_product 
                        WHERE plan_id = %s AND product_id = %s;
                    """, (plan_id, product_id))
                    print(f"🔄 {plan_name}: Notificações removido")
                else:
                    print(f"⏭️ {plan_name}: Notificações não incluído")
        
        # 5. Verificar configuração final
        print(f"\n📊 CONFIGURAÇÃO FINAL:")
        print("-" * 80)
        
        cursor.execute("""
            SELECT 
                p.name as plan_name,
                p.slug as plan_slug,
                pr.name as product_name,
                pp.is_included
            FROM billing_plan p
            LEFT JOIN billing_plan_product pp ON p.id = pp.plan_id AND pp.product_id = %s
            LEFT JOIN billing_product pr ON pr.id = %s
            WHERE p.is_active = true
            ORDER BY p.sort_order;
        """, (product_id, product_id))
        
        final_config = cursor.fetchall()
        
        for plan_name, plan_slug, product_name, is_included in final_config:
            status = "✅ Incluído" if is_included else "❌ Não incluído"
            print(f"   {plan_name}: {status}")
        
        # 6. Commit das alterações
        conn.commit()
        
        print(f"\n🎉 PRODUTO DE NOTIFICAÇÕES CONFIGURADO COM SUCESSO!")
        print("="*80)
        
        cursor.close()
        conn.close()
        
    except Exception as e:
        print(f"\n❌ ERRO: {e}")
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    create_notifications_product()
