-- ============================================================
-- SCRIPT PARA ZERAR TODAS AS CAMPANHAS DE UM TENANT
-- ============================================================
-- ⚠️ ATENÇÃO: Este script DELETA TODAS as campanhas e dados relacionados!
-- ⚠️ Nenhum log será preservado!
-- ⚠️ Execute com cuidado e faça backup antes se necessário.
-- ============================================================
-- 
-- INSTRUÇÕES:
-- 1. Substitua 'RBTec Informática' pelo nome do seu tenant
-- 2. Execute este script no banco de dados PostgreSQL
-- 3. Todas as campanhas, mensagens, contatos, logs e notificações serão deletadas
--
-- ============================================================

BEGIN;

-- ============================================================
-- 1. DELETAR NOTIFICAÇÕES DE CAMPANHAS
-- ============================================================
DELETE FROM campaigns_notification 
WHERE tenant_id IN (
    SELECT id FROM tenancy_tenant WHERE name ILIKE '%RBTec Informática%'
);

-- ============================================================
-- 2. DELETAR LOGS DE CAMPANHAS
-- ============================================================
DELETE FROM campaigns_campaignlog 
WHERE campaign_id IN (
    SELECT id FROM campaigns_campaign 
    WHERE tenant_id IN (
        SELECT id FROM tenancy_tenant WHERE name ILIKE '%RBTec Informática%'
    )
);

-- ============================================================
-- 3. DELETAR CONTATOS DE CAMPANHAS (CampaignContact)
-- ============================================================
DELETE FROM campaigns_campaigncontact 
WHERE campaign_id IN (
    SELECT id FROM campaigns_campaign 
    WHERE tenant_id IN (
        SELECT id FROM tenancy_tenant WHERE name ILIKE '%RBTec Informática%'
    )
);

-- ============================================================
-- 4. DELETAR MENSAGENS DE CAMPANHAS (CampaignMessage)
-- ============================================================
DELETE FROM campaigns_campaignmessage 
WHERE campaign_id IN (
    SELECT id FROM campaigns_campaign 
    WHERE tenant_id IN (
        SELECT id FROM tenancy_tenant WHERE name ILIKE '%RBTec Informática%'
    )
);

-- ============================================================
-- 5. DELETAR RELACIONAMENTOS MANY-TO-MANY (Campaign <-> WhatsAppInstance)
-- ============================================================
DELETE FROM campaigns_campaign_instances 
WHERE campaign_id IN (
    SELECT id FROM campaigns_campaign 
    WHERE tenant_id IN (
        SELECT id FROM tenancy_tenant WHERE name ILIKE '%RBTec Informática%'
    )
);

-- ============================================================
-- 6. FINALMENTE: DELETAR AS CAMPANHAS
-- ============================================================
DELETE FROM campaigns_campaign 
WHERE tenant_id IN (
    SELECT id FROM tenancy_tenant WHERE name ILIKE '%RBTec Informática%'
);

-- ============================================================
-- VERIFICAÇÃO FINAL
-- ============================================================
-- Verificar se restou alguma campanha (deve retornar 0)
SELECT COUNT(*) as campanhas_restantes 
FROM campaigns_campaign 
WHERE tenant_id IN (
    SELECT id FROM tenancy_tenant WHERE name ILIKE '%RBTec Informática%'
);

-- Verificar se restou algum log (deve retornar 0)
SELECT COUNT(*) as logs_restantes 
FROM campaigns_campaignlog 
WHERE campaign_id IN (
    SELECT id FROM campaigns_campaign 
    WHERE tenant_id IN (
        SELECT id FROM tenancy_tenant WHERE name ILIKE '%RBTec Informática%'
    )
);

-- Verificar se restou algum contato de campanha (deve retornar 0)
SELECT COUNT(*) as contatos_campanha_restantes 
FROM campaigns_campaigncontact 
WHERE campaign_id IN (
    SELECT id FROM campaigns_campaign 
    WHERE tenant_id IN (
        SELECT id FROM tenancy_tenant WHERE name ILIKE '%RBTec Informática%'
    )
);

-- Verificar se restou alguma notificação (deve retornar 0)
SELECT COUNT(*) as notificacoes_restantes 
FROM campaigns_notification 
WHERE tenant_id IN (
    SELECT id FROM tenancy_tenant WHERE name ILIKE '%RBTec Informática%'
);

-- Verificar se restou alguma mensagem de campanha (deve retornar 0)
SELECT COUNT(*) as mensagens_campanha_restantes 
FROM campaigns_campaignmessage 
WHERE campaign_id IN (
    SELECT id FROM campaigns_campaign 
    WHERE tenant_id IN (
        SELECT id FROM tenancy_tenant WHERE name ILIKE '%RBTec Informática%'
    )
);

-- ============================================================
-- SE TUDO ESTIVER OK, EXECUTE:
-- COMMIT;
-- ============================================================
-- 
-- SE HOUVER PROBLEMA, EXECUTE:
-- ROLLBACK;
-- ============================================================

-- ⚠️ IMPORTANTE: Descomente a linha abaixo para confirmar a exclusão:
-- COMMIT;

-- Ou execute ROLLBACK para cancelar:
-- ROLLBACK;

