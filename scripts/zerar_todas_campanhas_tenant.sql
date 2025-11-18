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
-- NOTA: Este script usa blocos DO com tratamento de erros
-- para que um erro em uma tabela não impeça a limpeza das outras
-- ============================================================

BEGIN;

-- ============================================================
-- 1. DELETAR NOTIFICAÇÕES DE CAMPANHAS
-- ============================================================
DO $$
BEGIN
    DELETE FROM campaigns_notification 
    WHERE tenant_id IN (
        SELECT id FROM tenancy_tenant WHERE name ILIKE '%RBTec Informática%'
    );
    RAISE NOTICE 'Notificações deletadas com sucesso';
EXCEPTION WHEN OTHERS THEN
    RAISE NOTICE 'Erro ao deletar notificações: %', SQLERRM;
END $$;

-- ============================================================
-- 2. DELETAR LOGS DE CAMPANHAS
-- ============================================================
DO $$
BEGIN
    DELETE FROM campaigns_log 
    WHERE campaign_id IN (
        SELECT id FROM campaigns_campaign 
        WHERE tenant_id IN (
            SELECT id FROM tenancy_tenant WHERE name ILIKE '%RBTec Informática%'
        )
    );
    RAISE NOTICE 'Logs deletados com sucesso';
EXCEPTION WHEN OTHERS THEN
    RAISE NOTICE 'Erro ao deletar logs: %', SQLERRM;
END $$;

-- ============================================================
-- 3. DELETAR CONTATOS DE CAMPANHAS (CampaignContact)
-- ============================================================
DO $$
BEGIN
    DELETE FROM campaigns_contact 
    WHERE campaign_id IN (
        SELECT id FROM campaigns_campaign 
        WHERE tenant_id IN (
            SELECT id FROM tenancy_tenant WHERE name ILIKE '%RBTec Informática%'
        )
    );
    RAISE NOTICE 'Contatos de campanha deletados com sucesso';
EXCEPTION WHEN OTHERS THEN
    RAISE NOTICE 'Erro ao deletar contatos de campanha: %', SQLERRM;
END $$;

-- ============================================================
-- 4. DELETAR MENSAGENS DE CAMPANHAS (CampaignMessage)
-- ============================================================
DO $$
BEGIN
    DELETE FROM campaigns_message 
    WHERE campaign_id IN (
        SELECT id FROM campaigns_campaign 
        WHERE tenant_id IN (
            SELECT id FROM tenancy_tenant WHERE name ILIKE '%RBTec Informática%'
        )
    );
    RAISE NOTICE 'Mensagens deletadas com sucesso';
EXCEPTION WHEN OTHERS THEN
    RAISE NOTICE 'Erro ao deletar mensagens: %', SQLERRM;
END $$;

-- ============================================================
-- 5. DELETAR RELACIONAMENTOS MANY-TO-MANY (Campaign <-> WhatsAppInstance)
-- ============================================================
DO $$
BEGIN
    DELETE FROM campaigns_campaign_instances 
    WHERE campaign_id IN (
        SELECT id FROM campaigns_campaign 
        WHERE tenant_id IN (
            SELECT id FROM tenancy_tenant WHERE name ILIKE '%RBTec Informática%'
        )
    );
    RAISE NOTICE 'Relacionamentos Many-to-Many deletados com sucesso';
EXCEPTION WHEN OTHERS THEN
    RAISE NOTICE 'Erro ao deletar relacionamentos Many-to-Many: %', SQLERRM;
END $$;

-- ============================================================
-- 6. FINALMENTE: DELETAR AS CAMPANHAS
-- ============================================================
DO $$
BEGIN
    DELETE FROM campaigns_campaign 
    WHERE tenant_id IN (
        SELECT id FROM tenancy_tenant WHERE name ILIKE '%RBTec Informática%'
    );
    RAISE NOTICE 'Campanhas deletadas com sucesso';
EXCEPTION WHEN OTHERS THEN
    RAISE NOTICE 'Erro ao deletar campanhas: %', SQLERRM;
END $$;

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
FROM campaigns_log 
WHERE campaign_id IN (
    SELECT id FROM campaigns_campaign 
    WHERE tenant_id IN (
        SELECT id FROM tenancy_tenant WHERE name ILIKE '%RBTec Informática%'
    )
);

-- Verificar se restou algum contato de campanha (deve retornar 0)
SELECT COUNT(*) as contatos_campanha_restantes 
FROM campaigns_contact 
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
FROM campaigns_message 
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
