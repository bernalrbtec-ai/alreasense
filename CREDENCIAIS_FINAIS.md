# 🔐 CREDENCIAIS DO SISTEMA

## Super Admin (Acesso Total ao Sistema)
- **Email:** superadmin@alreasense.com
- **Senha:** admin123
- **Role:** superadmin
- **Acesso:** Total (gerencia clientes, produtos, planos)

## Admin do Cliente "Admin Tenant"
- **Email:** admin@alreasense.com
- **Senha:** senha123
- **Role:** admin
- **Acesso:** Administrador do cliente

## Admin do Cliente "RBTec Informática"
- **Email:** paulo@rbtec.com
- **Senha:** senha123
- **Role:** admin
- **Acesso:** Administrador do cliente

---

## Scripts para Recriar Usuários

Após recriar o Docker, execute:

```bash
docker-compose exec backend python fix_superadmin.py
docker-compose exec backend python fix_usernames.py
```

---

## Estrutura de Roles

- **superadmin** → Super Admin do Sistema
- **admin** → Admin do Cliente
- **user** → Usuário do Cliente (futuro)


