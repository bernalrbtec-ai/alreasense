-- ✅ PERFORMANCE: Tenant indexes
-- Script para rodar diretamente no banco de dados
-- Data: 2025-12-10

-- Índice para status (filtros frequentes)
CREATE INDEX IF NOT EXISTS idx_tenant_status 
ON tenancy_tenant(status);

-- Índice para created_at (ordenação e filtros por data)
CREATE INDEX IF NOT EXISTS idx_tenant_created_at 
ON tenancy_tenant(created_at DESC);

-- Índice composto para status + created_at (queries combinadas)
CREATE INDEX IF NOT EXISTS idx_tenant_status_created 
ON tenancy_tenant(status, created_at DESC);

-- Verificar índices criados
SELECT 
    indexname, 
    indexdef 
FROM pg_indexes 
WHERE tablename = 'tenancy_tenant' 
    AND indexname LIKE 'idx_tenant%'
ORDER BY indexname;


