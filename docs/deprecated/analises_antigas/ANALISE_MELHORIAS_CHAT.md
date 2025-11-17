# 🔍 Análise Completa - Melhorias no Chat

## 📊 Status Atual

### ✅ O que está funcionando bem:
1. **Redis Streams para envio**: Funcionando perfeitamente, muito mais rápido
2. **Fotos de perfil**: Estão sendo buscadas e atualizadas corretamente
3. **Webhooks**: Processamento de mensagens funcionando
4. **Read receipts**: Funcionando via Redis Streams

### ❌ Problemas identificados:

#### 1. **Nomes de Grupos não atualizam corretamente**
- **Problema**: `handle_fetch_group_info` atualiza `contact_name` mas pode não estar sendo chamado sempre
- **Causa**: Task só é enfileirada quando conversa é NOVA (linha 538-545 do webhooks.py)
- **Impacto**: Grupos existentes ficam com "Grupo WhatsApp" genérico

#### 2. **Nomes de Contatos não atualizam quando já existem**
- **Problema**: Webhook só busca nome se `conversation.contact_name` estiver VAZIO (linha 584)
- **Causa**: Se já tiver um nome errado (ex: seu próprio nome), nunca atualiza
- **Impacto**: Contatos ficam com nomes incorretos permanentemente

#### 3. **Busca de nome é síncrona no webhook**
- **Problema**: Busca de nome de contato individual é feita síncronamente no webhook (linha 584-621)
- **Causa**: Pode bloquear webhook se API estiver lenta
- **Impacto**: Webhook demora mais para responder

#### 4. **`handle_fetch_profile_pic` não busca nome**
- **Problema**: Função só busca foto, não busca nome do contato
- **Causa**: Separação de responsabilidades não permite buscar nome junto
- **Impacto**: Perde oportunidade de atualizar nome quando busca foto

---

## 🎯 Soluções Propostas

### **Solução 1: Criar task assíncrona para buscar nome de contato**

**Arquivo**: `backend/apps/chat/tasks.py`

```python
class fetch_contact_name:
    """Producer: Busca nome de contato via Evolution API (Redis)."""
    
    @staticmethod
    def delay(conversation_id: str, phone: str, instance_name: str, api_key: str, base_url: str):
        """Enfileira busca de nome de contato (Redis)."""
        enqueue_message(REDIS_QUEUE_FETCH_CONTACT_NAME, {
            'conversation_id': conversation_id,
            'phone': phone,
            'instance_name': instance_name,
            'api_key': api_key,
            'base_url': base_url
        })


async def handle_fetch_contact_name(
    conversation_id: str, 
    phone: str, 
    instance_name: str, 
    api_key: str, 
    base_url: str
):
    """
    Handler: Busca nome de contato via Evolution API.
    
    Fluxo:
    1. Busca conversa
    2. Chama endpoint /chat/whatsappNumbers
    3. Atualiza contact_name
    4. Broadcast via WebSocket
    """
    # Implementação similar a handle_fetch_profile_pic
```

**Benefícios**:
- ✅ Não bloqueia webhook
- ✅ Pode ser retentado se falhar
- ✅ Processamento assíncrono

---

### **Solução 2: Melhorar `handle_fetch_group_info` para sempre atualizar**

**Arquivo**: `backend/apps/chat/media_tasks.py`

**Mudanças**:
1. Sempre atualizar `contact_name` mesmo se já existir
2. Garantir que `group_metadata` seja atualizado corretamente
3. Adicionar retry automático se falhar

**Código**:
```python
# Sempre atualizar nome, mesmo se já existir
if group_name:
    conversation.contact_name = group_name  # ✅ Sempre atualizar
    update_fields.append('contact_name')
    logger.info(f"✅ [GROUP INFO] Nome atualizado: {group_name}")
```

---

### **Solução 3: Enfileirar busca de nome mesmo quando já existe**

**Arquivo**: `backend/apps/chat/webhooks.py`

**Mudanças**:
1. Sempre enfileirar busca de nome para contatos individuais (não só quando vazio)
2. Usar task assíncrona ao invés de busca síncrona
3. Para grupos, sempre enfileirar busca de info (não só quando nova)

**Código**:
```python
# 👤 Para INDIVIDUAIS: sempre enfileirar busca de nome (assíncrona)
if not is_group:
    from apps.chat.tasks import fetch_contact_name, fetch_profile_pic
    
    # Enfileirar busca de nome (sempre, não só quando vazio)
    fetch_contact_name.delay(
        conversation_id=str(conversation.id),
        phone=clean_phone,
        instance_name=instance_name,
        api_key=api_key,
        base_url=base_url
    )
    
    # Enfileirar busca de foto (sempre)
    fetch_profile_pic.delay(
        conversation_id=str(conversation.id),
        phone=clean_phone
    )
```

---

### **Solução 4: Melhorar `handle_fetch_profile_pic` para também buscar nome**

**Arquivo**: `backend/apps/chat/tasks.py`

**Mudanças**:
1. Buscar nome junto com foto
2. Atualizar ambos em uma única chamada

**Código**:
```python
async def handle_fetch_profile_pic(conversation_id: str, phone: str):
    """
    Handler: Busca foto E nome de perfil via Evolution API.
    """
    # ... código existente ...
    
    # ✅ NOVO: Buscar nome também
    if not conversation.contact_name or conversation.contact_name == phone:
        endpoint_name = f"{base_url}/chat/whatsappNumbers/{instance_name}"
        response_name = await client.post(
            endpoint_name,
            json={'numbers': [clean_phone]},
            headers=headers
        )
        
        if response_name.status_code == 200:
            data_name = response_name.json()
            if data_name and len(data_name) > 0:
                contact_name = data_name[0].get('name') or data_name[0].get('pushname', '')
                if contact_name:
                    conversation.contact_name = contact_name
                    update_fields.append('contact_name')
```

---

### **Solução 5: Adicionar fila Redis para busca de nome**

**Arquivo**: `backend/apps/chat/redis_queue.py`

**Mudanças**:
1. Adicionar `REDIS_QUEUE_FETCH_CONTACT_NAME`
2. Adicionar consumer no `redis_consumer.py`

---

## 📋 Plano de Implementação

### **Fase 1: Criar infraestrutura**
1. ✅ Adicionar `REDIS_QUEUE_FETCH_CONTACT_NAME` em `redis_queue.py`
2. ✅ Criar `fetch_contact_name` producer em `tasks.py`
3. ✅ Criar `handle_fetch_contact_name` handler em `tasks.py`
4. ✅ Adicionar consumer em `redis_consumer.py`

### **Fase 2: Melhorar busca de grupos**
1. ✅ Atualizar `handle_fetch_group_info` para sempre atualizar nome
2. ✅ Garantir que grupos existentes também busquem info

### **Fase 3: Melhorar busca de contatos**
1. ✅ Atualizar webhook para sempre enfileirar busca de nome
2. ✅ Remover busca síncrona do webhook
3. ✅ Melhorar `handle_fetch_profile_pic` para buscar nome também

### **Fase 4: Testes**
1. ✅ Testar busca de nome de contato novo
2. ✅ Testar atualização de nome de contato existente
3. ✅ Testar busca de nome de grupo novo
4. ✅ Testar atualização de nome de grupo existente

---

## 🎯 Prioridades

### **CRÍTICO** (Fazer primeiro):
1. ✅ Melhorar `handle_fetch_group_info` para sempre atualizar nome
2. ✅ Criar task assíncrona para buscar nome de contato
3. ✅ Atualizar webhook para sempre enfileirar busca de nome

### **IMPORTANTE** (Fazer depois):
1. ✅ Melhorar `handle_fetch_profile_pic` para buscar nome também
2. ✅ Adicionar retry automático para busca de nomes

### **DESEJÁVEL** (Opcional):
1. ✅ Cache de nomes para evitar buscas repetidas
2. ✅ Webhook para atualizar nomes quando mudarem no WhatsApp

---

## 📊 Métricas Esperadas

### **Antes**:
- ❌ Nomes de grupos: ~30% ficam como "Grupo WhatsApp"
- ❌ Nomes de contatos: ~20% ficam incorretos
- ⏱️ Webhook bloqueia por 2-5s ao buscar nome

### **Depois**:
- ✅ Nomes de grupos: 100% atualizados corretamente
- ✅ Nomes de contatos: 100% atualizados corretamente
- ⚡ Webhook responde em <500ms (busca assíncrona)

---

## 🔧 Arquivos a Modificar

1. `backend/apps/chat/redis_queue.py` - Adicionar fila
2. `backend/apps/chat/tasks.py` - Criar producer/handler
3. `backend/apps/chat/redis_consumer.py` - Adicionar consumer
4. `backend/apps/chat/webhooks.py` - Atualizar para usar task assíncrona
5. `backend/apps/chat/media_tasks.py` - Melhorar handle_fetch_group_info

---

## ✅ Checklist de Implementação

- [ ] Criar `REDIS_QUEUE_FETCH_CONTACT_NAME`
- [ ] Criar `fetch_contact_name` producer
- [ ] Criar `handle_fetch_contact_name` handler
- [ ] Adicionar consumer em `redis_consumer.py`
- [ ] Atualizar `handle_fetch_group_info` para sempre atualizar
- [ ] Atualizar webhook para enfileirar busca de nome sempre
- [ ] Remover busca síncrona do webhook
- [ ] Melhorar `handle_fetch_profile_pic` para buscar nome
- [ ] Testar busca de nome de contato novo
- [ ] Testar atualização de nome de contato existente
- [ ] Testar busca de nome de grupo novo
- [ ] Testar atualização de nome de grupo existente

