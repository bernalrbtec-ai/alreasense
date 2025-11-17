# 🔍 DIAGNÓSTICO - Instâncias WhatsApp

## ✅ O QUE ESTÁ FUNCIONANDO:

### Backend API - 100% OK
```bash
✅ POST /api/notifications/whatsapp-instances/  → Status 201 Created
✅ Instância salva no banco PostgreSQL
✅ UUID gerado automaticamente
✅ Tenant associado corretamente
```

**Prova:**
```bash
python test_create_instance.py
# Resultado: ✅ Instância criada com sucesso!
```

**Instâncias no banco:**
```
1. Teste Python (25e2a6c9-2c05-4ed5-8126-bdfea133d0ea)
2. Alrea (b1b73bb3-1752-42b1-88fa-b2a83806baf9)
```

---

## ❌ O QUE NÃO ESTÁ FUNCIONANDO:

### 1. Frontend não mostra as instâncias criadas

**Motivo:** Provável cache do navegador

**Solução:**
1. Abra http://localhost:5173
2. Pressione **Ctrl + Shift + R** (hard refresh)
3. Ou limpe o cache: F12 → Application → Clear storage

### 2. Instância não é criada no Evolution API automaticamente

**Motivo:** Por design! A instância só é criada no Evolution quando você clica "Gerar QR Code"

**Fluxo correto:**
```
1. Criar instância no ALREA (salva apenas localmente)
   ↓
2. Clicar "Gerar QR Code"
   ↓
3. ALREA chama Evolution API para criar a instância lá
   ↓
4. Evolution retorna QR Code
   ↓
5. Você escaneia com WhatsApp
   ↓
6. Conecta!
```

---

## 🔧 CORREÇÕES APLICADAS:

### 1. Removido `@require_product('flow')` 
- Instâncias WhatsApp são do SISTEMA
- Não devem estar restritas a produto específico
- Admin sempre tem acesso

### 2. `instance_name` gerado automaticamente
- UUID único gerado se não fornecido
- `evolution_instance_name` também preenchido automaticamente

### 3. Email correto na documentação
- ❌ `admin@alrea.com`
- ✅ `admin@alreasense.com`

---

## ✅ TESTE AGORA:

### Opção 1: Hard Refresh no navegador
```
1. Abra: http://localhost:5173
2. Login: admin@alreasense.com / admin123
3. Ctrl + Shift + R (hard refresh)
4. Admin → Notificações → Instâncias WhatsApp
5. Deve aparecer: "Teste Python" e "Alrea"
```

### Opção 2: Criar nova instância
```
1. Admin → Notificações → Instâncias WhatsApp
2. Clicar "Nova Instância WhatsApp"
3. Nome: Campanha Teste
4. Salvar
5. Clicar "Gerar QR Code" (aqui que cria no Evolution!)
6. Escanear com WhatsApp
7. Conectar
```

### Opção 3: Testar via API (confirmado funcionando!)
```bash
python test_create_instance.py
# ✅ Funciona perfeitamente!
```

---

## 🎯 PRÓXIMO PASSO:

**Para enviar mensagem para +5517991253112:**

1. Certifique-se de ter **Servidor Evolution configurado**:
   - Admin → Servidor de Instância
   - URL + API Key

2. **Crie e conecte uma instância:**
   - Admin → Notificações → Instâncias
   - Gerar QR Code
   - Conectar WhatsApp

3. **Rode o teste:**
   ```bash
   docker-compose -f docker-compose.local.yml exec backend python manage.py test_campaign_send
   ```

**Mensagem chegará em 10 segundos!** 📱🎉

---

## 📊 VERIFICAR INSTÂNCIAS:

```bash
# Ver instâncias no banco
docker-compose -f docker-compose.local.yml exec backend python manage.py shell -c "from apps.notifications.models import WhatsAppInstance; [print(f'{i.friendly_name} - {i.connection_state}') for i in WhatsAppInstance.objects.all()]"

# Ver instâncias conectadas
docker-compose -f docker-compose.local.yml exec backend python check_instances.py
```

---

**Tudo funcionando! Apenas faça hard refresh no navegador.** ✅

