-- ============================================
-- 🗑️ LIMPAR TODOS OS ATTACHMENTS (SIMPLES)
-- ============================================
-- Script simples para deletar TODOS os attachments.
-- 
-- ⚠️ ATENÇÃO: Remove TUDO de TODOS os tenants!
-- ============================================

-- Verificar antes
SELECT COUNT(*) as total_attachments FROM chat_attachment;

-- DELETAR TUDO
DELETE FROM chat_attachment;

-- Verificar depois (deve retornar 0)
SELECT COUNT(*) as remaining_attachments FROM chat_attachment;

-- ============================================
-- Para deletar apenas de um tenant específico:
-- ============================================
-- DELETE FROM chat_attachment WHERE tenant_id = 'a72fbca7-92cd-4aa0-80cb-1c0a02761218';
-- ============================================
