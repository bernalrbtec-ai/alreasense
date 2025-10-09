# 🧪 GUIA DE TESTE COMPLETO - AMBIENTE LOCAL

## ✅ PREPARAÇÃO CONCLUÍDA

- [x] Docker Compose configurado
- [x] PostgreSQL local rodando
- [x] Redis local rodando
- [x] Backend Django rodando (porta 8000)
- [x] Frontend React rodando (porta 5173)
- [x] Celery Worker ativo
- [x] Celery Beat ativo
- [x] Migration api_key nullable aplicada
- [x] Fix QR Code prefixo duplicado
- [x] Fix null.id no modal QR

---

## 🎯 TESTE PASSO A PASSO

### **ETAPA 1: Verificar Servidor Evolution API** ✅

1. Acesse: http://localhost:8000/admin
2. Login: `admin@alreasense.com` / `admin123`
3. Navegue: **Connections → Evolution connections**
4. Verifique se existe um registro ativo
5. Se não existir, clique **Add** e preencha:
   - Name: `Evolution RBTec`
   - Base URL: `https://evo.rbtec.com.br`
   - API Key: `[SUA_CHAVE_MASTER]`
   - Is Active: ✅
   - Tenant: `Default Tenant`
6. Salve

---

### **ETAPA 2: Criar Instância WhatsApp** 📱

1. Acesse: http://localhost:5173
2. Faça login (ou use as mesmas credenciais do admin)
3. Vá em: **Conexões** → **WhatsApp**
4. Clique: **Nova Instância**
5. Preencha:
   - **Nome Amigável**: `Teste Local 001`
   - **Nome da Instância**: `teste_local_001` (sem espaços)
   - **Padrão**: Marque se for a primeira
6. Clique: **Salvar**

**✅ ESPERADO:**
- Instância criada com sucesso
- Aparece na lista
- Status: "Inativo" (normal, ainda não conectou)

**❌ SE DER ERRO:**
- Copie a mensagem de erro e me mostre

---

### **ETAPA 3: Gerar QR Code** 📷

1. Na instância criada, clique no ícone **QR Code** (botão azul)
2. Aguarde (pode levar 5-10 segundos)

**✅ ESPERADO:**
- Modal abre com QR Code visível
- QR Code bem formatado (sem duplicação de prefixo)
- Mensagem: "QR code gerado com sucesso"
- Contador de expiração

**❌ SE DER ERRO:**
- Abra o console do navegador (F12)
- Copie o erro e me mostre
- Veja os logs do backend:
  ```bash
  docker-compose -f docker-compose.local.yml logs -f backend
  ```

---

### **ETAPA 4: Verificar Criação na Evolution API** 🔍

**Abra outro terminal e monitore os logs:**
```bash
docker-compose -f docker-compose.local.yml logs -f backend
```

**Procure por:**
```
📋 Resposta criar instância: {...}
✅ API key específica capturada: ...
```

**✅ ESPERADO:**
- Log mostra criação na Evolution API
- API key específica é capturada e salva
- Status 200/201 da Evolution API

---

### **ETAPA 5: Conectar WhatsApp** 📱

1. **Abra WhatsApp no celular**
2. **Vá em:**
   - Android: Menu → Aparelhos conectados → Conectar
   - iPhone: Ajustes → WhatsApp Web → Conectar
3. **Escaneie o QR Code** mostrado no navegador
4. **Aguarde a conexão**

**✅ ESPERADO:**
- WhatsApp conecta
- Status da instância muda para "Conectado"
- Botão "Enviar Teste" fica disponível

---

### **ETAPA 6: Enviar Mensagem de Teste** 💬

1. Clique em **"Enviar Teste"** (ícone de mensagem)
2. Confirme o envio
3. Verifique seu WhatsApp

**✅ ESPERADO:**
- Você recebe uma mensagem do próprio número
- Toast de sucesso no frontend
- Logs mostram envio com status 200

---

### **ETAPA 7: Deletar Instância** 🗑️

1. Clique no ícone **Lixeira** (vermelho)
2. Confirme a exclusão

**✅ ESPERADO:**
- Instância removida da lista
- Logs mostram:
  ```
  🗑️ Deletando instância teste_local_001 da Evolution API...
  ✅ Instância deletada da Evolution API
  ```
- Status 200/204 da Evolution API

**❌ SE DER ERRO 404:**
- Significa que a instância não estava na Evolution API
- Verifique se o QR Code foi gerado corretamente antes

---

## 📊 CHECKLIST DE VALIDAÇÃO

- [ ] Servidor Evolution configurado no admin
- [ ] Teste de conexão Evolution retorna 200 OK
- [ ] Instância criada no sistema (banco local)
- [ ] QR Code gerado com sucesso
- [ ] QR Code aparece visualmente no modal
- [ ] Logs mostram criação na Evolution API
- [ ] API key específica capturada
- [ ] WhatsApp conectado após escanear
- [ ] Mensagem de teste enviada
- [ ] Instância deletada do sistema
- [ ] Instância deletada da Evolution API (log mostra status 200/204)

---

## 🐛 LOGS ÚTEIS PARA DEBUG

### Ver logs em tempo real
```bash
# Backend
docker-compose -f docker-compose.local.yml logs -f backend

# Frontend
docker-compose -f docker-compose.local.yml logs -f frontend

# Todos
docker-compose -f docker-compose.local.yml logs -f
```

### Ver logs específicos
```bash
# Últimas 50 linhas do backend
docker-compose -f docker-compose.local.yml logs backend --tail=50

# Buscar por palavra-chave
docker-compose -f docker-compose.local.yml logs backend | grep -i "evolution"
docker-compose -f docker-compose.local.yml logs backend | grep -i "qr"
docker-compose -f docker-compose.local.yml logs backend | grep -i "delete"
```

---

## 🔍 MONITORAMENTO EM TEMPO REAL

**Terminal 1 (Logs Backend):**
```bash
docker-compose -f docker-compose.local.yml logs -f backend
```

**Terminal 2 (Comandos):**
```bash
# Status dos containers
docker-compose -f docker-compose.local.yml ps

# Entrar no backend
docker-compose -f docker-compose.local.yml exec backend bash
```

**Navegador:**
- Frontend: http://localhost:5173
- Console (F12): Ver erros JavaScript

---

## ⚡ ATALHOS RÁPIDOS

### Reiniciar só o backend (após mudanças Python)
```bash
docker-compose -f docker-compose.local.yml restart backend
```

### Rebuild rápido do backend
```bash
docker-compose -f docker-compose.local.yml up -d --build backend
```

### Executar comando Django
```bash
docker-compose -f docker-compose.local.yml exec backend python manage.py COMANDO
```

### Ver banco de dados
```bash
docker-compose -f docker-compose.local.yml exec db psql -U postgres -d alrea_sense_local
```

---

## 🚀 QUANDO TUDO ESTIVER 100% OK

### Fazer deploy para Railway:

```bash
# 1. Commit final
git add .
git commit -m "✅ Fluxo WhatsApp 100% testado localmente"

# 2. Push
git push origin main

# 3. Aguardar Railway processar (ou fazer deploy manual)
```

---

## 📝 NOTAS IMPORTANTES

1. **Dados são locais**: Nada afeta Railway enquanto você testa
2. **Evolution API é externa**: Instâncias criadas vão para o servidor real
3. **Lembre de deletar instâncias de teste** da Evolution API depois
4. **Banco local separado**: `alrea_sense_local` vs `railway` (produção)

---

**🎯 COMECE AGORA!**

Acesse http://localhost:5173 e siga as etapas acima.

Qualquer erro, me mostre e vou ajudar! 💙

