-- ============================================
-- MARCAR MIGRATIONS COMO APLICADAS NO DJANGO
-- Execute APENAS após confirmar que índices foram criados no banco
-- ============================================

-- Ver migrations atuais
SELECT app, name, applied 
FROM django_migrations 
WHERE app IN ('campaigns', 'chat', 'contacts')
  AND name LIKE '%composite%'
ORDER BY app, applied DESC;

-- Marcar as migrations como aplicadas
-- ATENÇÃO: Só execute se os índices foram criados com sucesso!

INSERT INTO django_migrations (app, name, applied)
VALUES 
    ('campaigns', '0011_add_composite_indexes', NOW()),
    ('chat', '0005_add_composite_indexes', NOW()),
    ('contacts', '0004_add_composite_indexes', NOW())
ON CONFLICT (app, name) DO NOTHING;

-- Verificar se foram inseridas
SELECT app, name, applied 
FROM django_migrations 
WHERE app IN ('campaigns', 'chat', 'contacts')
  AND name LIKE '%composite%'
ORDER BY app, applied DESC;

