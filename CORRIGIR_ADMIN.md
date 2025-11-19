# 🔧 Como Corrigir o Admin do Sistema

## Problema

O admin do sistema está configurado como `admin@alreasense.com` mas deveria ser `paulo.bernal@alrea.ai`.

## Solução

Foram criados scripts para corrigir automaticamente:

1. **Script standalone:** `backend/fix_admin_user.py`
2. **Comando Django:** `python manage.py fix_admin`
3. **Correção automática:** O script `create_superuser.py` já foi atualizado para corrigir automaticamente durante deploy

## Como Executar

### Opção 1: Comando Django (Recomendado)

```bash
cd backend
python manage.py fix_admin
```

### Opção 2: Script Standalone

```bash
cd backend
python fix_admin_user.py
```

### Opção 3: Via Railway (Produção)

O script `create_superuser.py` já foi atualizado e será executado automaticamente durante o próximo deploy. Mas você pode executar manualmente via Railway CLI:

```bash
railway run python backend/manage.py fix_admin
```

Ou via Railway Dashboard:
1. Vá em **Deployments**
2. Clique no último deploy
3. Abra **Shell**
4. Execute: `python backend/manage.py fix_admin`

## O que o Script Faz

1. ✅ Verifica se `paulo.bernal@alrea.ai` existe
2. ✅ Cria o usuário se não existir
3. ✅ Promove `paulo.bernal@alrea.ai` a superuser (is_superuser=True, is_staff=True, role='admin')
4. ✅ Desativa `admin@alreasense.com` (remove permissões de superuser)

## Resultado Esperado

Após executar o script:

- ✅ `paulo.bernal@alrea.ai` será o admin do sistema
- ✅ `admin@alreasense.com` será desativado
- ✅ Você poderá acessar com `paulo.bernal@alrea.ai` / `admin123`

## Prevenção Futura

O script `backend/create_superuser.py` foi atualizado para:

- ✅ Criar superuser com `paulo.bernal@alrea.ai` por padrão
- ✅ Corrigir automaticamente se detectar admin incorreto durante deploy
- ✅ Promover `paulo.bernal@alrea.ai` se já existir

## Verificação

Após executar, verifique:

```bash
python manage.py shell
```

```python
from django.contrib.auth import get_user_model
User = get_user_model()

# Verificar admin correto
admin = User.objects.filter(is_superuser=True).first()
print(f"Admin: {admin.email}")
print(f"Is Superuser: {admin.is_superuser}")
print(f"Is Staff: {admin.is_staff}")
print(f"Role: {admin.role}")
```

Deve mostrar:
```
Admin: paulo.bernal@alrea.ai
Is Superuser: True
Is Staff: True
Role: admin
```

---

**Última atualização:** 2025-01-20

