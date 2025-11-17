# 🔍 DIAGNÓSTICO - Foto de Perfil não aparece

## 📋 PROBLEMA

As fotos de perfil dos contatos não estão aparecendo no chat.

---

## 🔬 CAUSAS POSSÍVEIS

### 1️⃣ **Evolution API não envia `profilePicUrl` no webhook**

**Sintoma:**
- Campo `profile_pic_url` está vazio no banco
- Logs não mostram URL da foto

**Causa:**
- Evolution API **não inclui** foto de perfil automaticamente no evento `messages.upsert`
- Foto só vem se você **buscar manualmente** via endpoint específico

**Solução:**
- Buscar foto via API após criar conversa
- Endpoint: `GET /chat/fetchProfilePictureUrl/{instance}?number={phone}`

---

### 2️⃣ **URL expira rapidamente (WhatsApp)**

**Sintoma:**
- Foto apareceu 1x, depois quebrou
- Erro 403/404 no navegador

**Causa:**
- URLs do WhatsApp expiram em **1-2 horas**
- Não podemos salvar URL direta

**Solução:**
- **Baixar** a foto e salvar localmente
- Servir via proxy do backend
- Atualizar URL periodicamente

---

### 3️⃣ **CORS bloqueando imagem**

**Sintoma:**
- URL existe mas navegador bloqueia
- Console mostra erro CORS

**Causa:**
- WhatsApp não permite acesso direto de outros domínios

**Solução:**
- Proxy via backend (já implementado)
- Endpoint: `/api/chat/profile-pic/{phone}/`

---

## ✅ IMPLEMENTAÇÃO CORRETA

### **Backend:**

```python
# 1. Buscar foto via API quando criar conversa
async def fetch_and_save_profile_pic(conversation_id, phone):
    # GET /chat/fetchProfilePictureUrl/{instance}?number={phone}
    profile_url = await fetch_from_evolution(phone)
    
    if profile_url:
        # Baixar imagem
        image_data = await download_image(profile_url)
        
        # Salvar localmente
        file_path = f"profile_pics/{conversation_id}.jpg"
        save_file(file_path, image_data)
        
        # Atualizar conversa
        conversation.profile_pic_url = f"/api/chat/profile-pic/{conversation_id}/"
        conversation.save()
```

### **Webhook atualizado:**

```python
# backend/apps/chat/webhooks.py

# Após criar conversa
if created:
    # Enfileirar busca de foto de perfil
    fetch_profile_pic.delay(str(conversation.id), phone)
```

---

## 🛠️ SCRIPTS DE TESTE

### **1. Testar e diagnosticar:**
```bash
cd backend
python test_profile_pic.py
```

**O que faz:**
- Verifica se webhook recebeu foto
- Testa se URL está acessível
- Busca foto manualmente via API
- Mostra endpoints disponíveis

### **2. Atualizar todas as conversas:**
```bash
cd backend
python update_all_profile_pics.py
```

**O que faz:**
- Busca fotos de todas as conversas
- Atualiza no banco
- Mostra estatísticas

---

## 🎯 SOLUÇÃO RECOMENDADA

### **Opção 1: Buscar manualmente (Simples)**

**Prós:**
- Fácil de implementar
- Funciona com Evolution atual

**Contras:**
- Foto pode não estar na primeira mensagem
- Precisa atualizar periodicamente

**Como fazer:**
1. Adicionar task para buscar foto após criar conversa
2. Salvar URL no banco
3. Frontend usa URL direta

### **Opção 2: Baixar e servir localmente (Recomendado)**

**Prós:**
- Foto nunca expira
- Mais rápido (cache local)
- Funciona offline

**Contras:**
- Ocupa espaço em disco
- Mais complexo

**Como fazer:**
1. Baixar foto via Evolution API
2. Salvar em `/media/profile_pics/`
3. Servir via endpoint `/api/chat/profile-pic/{id}/`
4. Atualizar semanalmente

### **Opção 3: Proxy dinâmico (Ideal)**

**Prós:**
- Não ocupa disco
- Sempre atualizado
- Resolve CORS

**Contras:**
- Depende de Evolution online
- Latência adicional

**Como fazer:**
1. Frontend pede: `/api/chat/profile-pic/{phone}/`
2. Backend busca URL via Evolution
3. Backend faz proxy da imagem
4. Cache de 1 hora

---

## 📊 RESUMO EXECUTIVO

### ✅ **Backend está pronto:**
- Modelo tem campo `profile_pic_url` ✅
- Webhook salva se Evolution enviar ✅
- Serializer expõe para frontend ✅

### ⚠️ **Problema real:**
- **Evolution NÃO envia foto no webhook** ❌
- Precisa **buscar manualmente** via API

### 🎯 **Solução:**
1. Adicionar task para buscar foto após criar conversa
2. Usar endpoint: `GET /chat/fetchProfilePictureUrl/{instance}?number={phone}`
3. Baixar e salvar localmente (ou fazer proxy)
4. Atualizar periodicamente (1x por semana)

---

## 🚀 IMPLEMENTAÇÃO IMEDIATA

**Passo 1: Testar se Evolution suporta buscar foto**
```bash
python backend/test_profile_pic.py
```

**Passo 2: Se funcionar, implementar:**
- Task para buscar foto automaticamente
- Proxy de imagem via backend
- Atualização periódica

**Passo 3: Atualizar conversas existentes**
```bash
python backend/update_all_profile_pics.py
```

---

**Quer que eu implemente agora?** 🔧


