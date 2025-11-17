-- ============================================================
-- SCRIPT PARA LIMPAR TODOS OS CONTATOS DE UM TENANT
-- ============================================================
-- 
-- ⚠️ ATENÇÃO: Este script DELETA TODOS os contatos do tenant!
-- Use com cuidado e sempre faça backup antes.
--
-- Como usar:
-- 1. Substitua 'RBTec' pelo nome do seu tenant (ou use o tenant_id diretamente)
-- 2. Execute no banco de dados
-- 3. Verifique o resultado antes de confirmar
--
-- ============================================================

-- PASSO 1: Identificar o tenant_id (descomente e execute para ver)
-- SELECT id, name FROM tenancy_tenant WHERE name ILIKE '%rbtec%';

-- PASSO 2: Substitua o tenant_id abaixo pelo ID encontrado acima
-- OU use o nome do tenant diretamente na query

-- ============================================================
-- DELETAR CONTATOS DO TENANT (ORDEM CORRETA)
-- ============================================================

BEGIN;

-- 1. Deletar relacionamentos ManyToMany (tags e lists)
-- Tabela intermediária: contacts_contact_tags
DELETE FROM contacts_contact_tags 
WHERE contact_id IN (
    SELECT id FROM contacts_contact 
    WHERE tenant_id = (SELECT id FROM tenancy_tenant WHERE name ILIKE '%rbtec%')
);

-- Tabela intermediária: contacts_contact_lists  
DELETE FROM contacts_contact_lists 
WHERE contact_id IN (
    SELECT id FROM contacts_contact 
    WHERE tenant_id = (SELECT id FROM tenancy_tenant WHERE name ILIKE '%rbtec%')
);

-- 2. Deletar CampaignContact (CASCADE automático, mas vamos fazer explícito)
-- Isso deleta automaticamente CampaignNotification também
DELETE FROM campaigns_campaigncontact 
WHERE contact_id IN (
    SELECT id FROM contacts_contact 
    WHERE tenant_id = (SELECT id FROM tenancy_tenant WHERE name ILIKE '%rbtec%')
);

-- 3. Deletar ContactImport (histórico de importações)
DELETE FROM contacts_contactimport 
WHERE tenant_id = (SELECT id FROM tenancy_tenant WHERE name ILIKE '%rbtec%');

-- 4. FINALMENTE: Deletar os contatos
-- Isso vai deletar automaticamente (CASCADE):
-- - CampaignContact relacionados
-- - CampaignNotification relacionados
DELETE FROM contacts_contact 
WHERE tenant_id = (SELECT id FROM tenancy_tenant WHERE name ILIKE '%rbtec%');

-- Verificar quantos foram deletados
SELECT COUNT(*) as contatos_deletados 
FROM contacts_contact 
WHERE tenant_id = (SELECT id FROM tenancy_tenant WHERE name ILIKE '%rbtec%');

-- Se o resultado for 0, pode fazer COMMIT
-- Se houver algum problema, faça ROLLBACK
-- COMMIT;
-- ROLLBACK;

-- ============================================================
-- VERSÃO ALTERNATIVA: Usando tenant_id diretamente
-- ============================================================
-- Se você souber o tenant_id (UUID), use esta versão mais rápida:
--
-- BEGIN;
--
-- DELETE FROM contacts_contact_tags 
-- WHERE contact_id IN (SELECT id FROM contacts_contact WHERE tenant_id = 'SEU-TENANT-ID-AQUI');
--
-- DELETE FROM contacts_contact_lists 
-- WHERE contact_id IN (SELECT id FROM contacts_contact WHERE tenant_id = 'SEU-TENANT-ID-AQUI');
--
-- DELETE FROM campaigns_campaigncontact 
-- WHERE contact_id IN (SELECT id FROM contacts_contact WHERE tenant_id = 'SEU-TENANT-ID-AQUI');
--
-- DELETE FROM contacts_contactimport 
-- WHERE tenant_id = 'SEU-TENANT-ID-AQUI';
--
-- DELETE FROM contacts_contact 
-- WHERE tenant_id = 'SEU-TENANT-ID-AQUI';
--
-- COMMIT;

