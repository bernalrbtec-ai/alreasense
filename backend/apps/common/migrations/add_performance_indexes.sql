-- ✅ PERFORMANCE: Índices de performance para otimização de queries
-- Script para rodar diretamente no banco de dados
-- Data: 2025-12-10

-- ==========================================
-- 1. WHATSAPP INSTANCE INDEXES
-- ==========================================
-- Índice composto para tenant + is_default (busca de instância padrão)
CREATE INDEX IF NOT EXISTS idx_whatsapp_instance_tenant_default 
ON notifications_whatsapp_instance(tenant_id, is_default) 
WHERE is_default = true;

-- Índice composto para tenant + connection_state (filtros de status)
CREATE INDEX IF NOT EXISTS idx_whatsapp_instance_tenant_state 
ON notifications_whatsapp_instance(tenant_id, connection_state);

-- Índice para created_at (ordenação)
CREATE INDEX IF NOT EXISTS idx_whatsapp_instance_created_at 
ON notifications_whatsapp_instance(created_at DESC);

-- ==========================================
-- 2. CONTACT INDEXES
-- ==========================================
-- Índice composto para tenant + is_active (filtros frequentes)
CREATE INDEX IF NOT EXISTS idx_contact_tenant_active 
ON contacts_contact(tenant_id, is_active) 
WHERE is_active = true;

-- Índice composto para tenant + opted_out (filtros LGPD)
CREATE INDEX IF NOT EXISTS idx_contact_tenant_opted_out 
ON contacts_contact(tenant_id, opted_out) 
WHERE opted_out = true;

-- Índice para phone (busca por telefone)
CREATE INDEX IF NOT EXISTS idx_contact_phone 
ON contacts_contact(phone);

-- Índice composto para tenant + phone (busca otimizada)
CREATE INDEX IF NOT EXISTS idx_contact_tenant_phone 
ON contacts_contact(tenant_id, phone);

-- ==========================================
-- 3. CONVERSATION INDEXES
-- ==========================================
-- Índice composto para tenant + status (filtros de status)
CREATE INDEX IF NOT EXISTS idx_conversation_tenant_status 
ON chat_conversation(tenant_id, status);

-- Índice composto para tenant + department + status (filtros combinados)
CREATE INDEX IF NOT EXISTS idx_conversation_tenant_dept_status 
ON chat_conversation(tenant_id, department_id, status) 
WHERE department_id IS NOT NULL;

-- Índice para tenant + status onde department é NULL (Inbox)
CREATE INDEX IF NOT EXISTS idx_conversation_tenant_pending 
ON chat_conversation(tenant_id, status) 
WHERE department_id IS NULL AND status = 'pending';

-- Índice para last_message_at (ordenação de conversas)
CREATE INDEX IF NOT EXISTS idx_conversation_last_message_at 
ON chat_conversation(last_message_at DESC NULLS LAST);

-- ==========================================
-- 4. TASK INDEXES
-- ==========================================
-- Índice composto para tenant + status (filtros de status)
CREATE INDEX IF NOT EXISTS idx_task_tenant_status 
ON contacts_task(tenant_id, status);

-- Índice composto para tenant + assigned_to + status (tarefas do usuário)
CREATE INDEX IF NOT EXISTS idx_task_tenant_assigned_status 
ON contacts_task(tenant_id, assigned_to_id, status) 
WHERE assigned_to_id IS NOT NULL;

-- Índice composto para tenant + department + status (tarefas do departamento)
CREATE INDEX IF NOT EXISTS idx_task_tenant_dept_status 
ON contacts_task(tenant_id, department_id, status);

-- Índice para due_date (ordenação de agenda)
CREATE INDEX IF NOT EXISTS idx_task_due_date 
ON contacts_task(due_date DESC NULLS LAST);

-- Índice composto para tarefas atrasadas (due_date < now AND status IN ('pending', 'in_progress'))
CREATE INDEX IF NOT EXISTS idx_task_overdue 
ON contacts_task(tenant_id, due_date, status) 
WHERE due_date IS NOT NULL AND status IN ('pending', 'in_progress');

-- ==========================================
-- 5. MESSAGE INDEXES (se necessário)
-- ==========================================
-- Índice composto para conversation + created_at (ordenação de mensagens)
-- NOTA: chat_message não tem tenant_id diretamente, apenas conversation_id
CREATE INDEX IF NOT EXISTS idx_message_conversation_created 
ON chat_message(conversation_id, created_at DESC);

-- ==========================================
-- VERIFICAR ÍNDICES CRIADOS
-- ==========================================
-- WhatsApp Instance
SELECT 
    indexname, 
    indexdef 
FROM pg_indexes 
WHERE tablename = 'notifications_whatsapp_instance' 
    AND indexname LIKE 'idx_whatsapp_instance%'
ORDER BY indexname;

-- Contact
SELECT 
    indexname, 
    indexdef 
FROM pg_indexes 
WHERE tablename = 'contacts_contact' 
    AND indexname LIKE 'idx_contact%'
ORDER BY indexname;

-- Conversation
SELECT 
    indexname, 
    indexdef 
FROM pg_indexes 
WHERE tablename = 'chat_conversation' 
    AND indexname LIKE 'idx_conversation%'
ORDER BY indexname;

-- Task
SELECT 
    indexname, 
    indexdef 
FROM pg_indexes 
WHERE tablename = 'contacts_task' 
    AND indexname LIKE 'idx_task%'
ORDER BY indexname;

-- Message
SELECT 
    indexname, 
    indexdef 
FROM pg_indexes 
WHERE tablename = 'chat_message' 
    AND indexname LIKE 'idx_message%'
ORDER BY indexname;

-- ==========================================
-- NOTAS IMPORTANTES
-- ==========================================
-- 1. A tabela chat_message NÃO tem coluna tenant_id diretamente
--    O tenant é obtido via conversation.tenant_id
-- 2. Alguns índices podem já existir (NOTICE é normal)
-- 3. Se algum índice falhar, verifique se a coluna existe na tabela

