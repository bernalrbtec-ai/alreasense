# 🔧 Corrigir Admin - Via SQL Direto

## Opção 1: SQL Direto (Mais Rápido) ⚡

### Via Railway Dashboard

1. Acesse **Railway Dashboard** → Seu Projeto
2. Vá em **Database** → **Query**
3. Cole e execute este SQL:

```sql
-- Corrigir permissões do admin@alreasense.com
UPDATE authn_user
SET 
    is_superuser = TRUE,
    is_staff = TRUE,
    is_active = TRUE,
    role = 'admin'
WHERE email = 'admin@alreasense.com';
```

4. Verificar resultado:

```sql
SELECT 
    id,
    email,
    is_superuser,
    is_staff,
    is_active,
    role
FROM authn_user
WHERE email = 'admin@alreasense.com';
```

Deve mostrar:
```
is_superuser: TRUE
is_staff: TRUE
is_active: TRUE
role: admin
```

## Opção 2: Script Python (Via Shell)

1. Railway Dashboard → **Deployments** → Último deploy → **Shell**
2. Execute:

```bash
cd backend
python fix_admin_permissions_direct.py
```

## Opção 3: Via Railway CLI

```bash
railway run python backend/fix_admin_permissions_direct.py
```

---

**Recomendação:** Use a **Opção 1 (SQL direto)** - é mais rápido e direto! ⚡

