-- Script SQL para corrigir permissões do admin@alreasense.com
-- Execute via Railway Dashboard: Database > Query > Cole este SQL

-- Verificar usuário atual
SELECT 
    id,
    email,
    username,
    is_superuser,
    is_staff,
    is_active,
    role
FROM authn_user
WHERE email = 'admin@alreasense.com';

-- Corrigir permissões
UPDATE authn_user
SET 
    is_superuser = TRUE,
    is_staff = TRUE,
    is_active = TRUE,
    role = 'admin'
WHERE email = 'admin@alreasense.com';

-- Verificar resultado
SELECT 
    id,
    email,
    username,
    is_superuser,
    is_staff,
    is_active,
    role
FROM authn_user
WHERE email = 'admin@alreasense.com';

