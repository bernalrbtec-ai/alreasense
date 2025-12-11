-- ============================================================================
-- Script SQL para alterar senha do usuário admin@alreasense.com
-- Nova senha: 123@qwe
-- ============================================================================

-- Atualizar senha do usuário admin@alreasense.com
UPDATE authn_user
SET password = 'pbkdf2_sha256$600000$ojrK5KpzIfLP4aMtPCLPSa$VCnYZ0PFEiZmMqjZSM5yCMLsKJFBs7XWUCjOgiDiyHQ='
WHERE email = 'admin@alreasense.com';

-- Verificar se foi atualizado corretamente
SELECT 
    id, 
    email, 
    username, 
    is_active, 
    is_superuser, 
    is_staff,
    CASE 
        WHEN password LIKE 'pbkdf2_sha256$%' THEN 'Hash válido (Django)'
        ELSE 'Hash inválido ou antigo'
    END as password_status
FROM authn_user
WHERE email = 'admin@alreasense.com';

-- ============================================================================
-- Instruções de uso:
-- 1. Conecte-se ao banco de dados PostgreSQL
-- 2. Execute este script SQL
-- 3. Verifique a saída da query SELECT para confirmar a atualização
-- 
-- Para usar via Railway CLI:
-- railway connect postgres
-- psql < update_admin_password.sql
-- 
-- Ou via psql direto:
-- psql -h <host> -U <user> -d <database> -f update_admin_password.sql
-- ============================================================================
















