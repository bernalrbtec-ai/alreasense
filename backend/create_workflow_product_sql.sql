-- Script SQL para criar produto Workflow e adicionar aos planos
-- Execute este script no banco de dados PostgreSQL

-- 1. Criar produto Workflow
INSERT INTO billing_product (id, slug, name, description, is_active, requires_ui_access, addon_price, icon, color, created_at, updated_at)
VALUES (
    gen_random_uuid(),
    'workflow',
    'ALREA Workflow',
    'Chat e Agenda/Tarefas integrados para gestão de atendimento e organização',
    true,
    true,
    29.90,
    '💬',
    '#10B981',
    NOW(),
    NOW()
)
ON CONFLICT (slug) DO UPDATE SET
    name = EXCLUDED.name,
    description = EXCLUDED.description,
    is_active = EXCLUDED.is_active,
    requires_ui_access = EXCLUDED.requires_ui_access,
    addon_price = EXCLUDED.addon_price,
    icon = EXCLUDED.icon,
    color = EXCLUDED.color,
    updated_at = NOW();

-- 2. Adicionar Workflow a todos os planos ativos
-- ✅ CORREÇÃO: id é BigAutoField (bigint), não UUID - deixar banco gerar automaticamente
INSERT INTO billing_plan_product (plan_id, product_id, is_included, is_addon_available, limit_value, limit_unit, created_at)
SELECT
    p.id,
    (SELECT id FROM billing_product WHERE slug = 'workflow'),
    true,
    true,
    NULL,  -- Ilimitado por padrão
    NULL,
    NOW()
FROM billing_plan p
WHERE p.is_active = true
ON CONFLICT (plan_id, product_id) DO UPDATE SET
    is_included = true,
    is_addon_available = true;

-- 3. Verificar resultado
SELECT 
    pp.id,
    p.name as plan_name,
    pr.name as product_name,
    pr.slug as product_slug,
    pp.is_included,
    pp.is_addon_available
FROM billing_plan_product pp
JOIN billing_plan p ON pp.plan_id = p.id
JOIN billing_product pr ON pp.product_id = pr.id
WHERE pr.slug = 'workflow'
ORDER BY p.name;

