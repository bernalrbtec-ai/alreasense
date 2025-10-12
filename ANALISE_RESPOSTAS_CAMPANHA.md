# 💬 ANÁLISE: Respostas de Contatos em Campanhas

## 🎯 **REQUISITO DO USUÁRIO:**

> "Quero salvar a resposta e avisar o usuário que o contato tal respondeu... seja em uma tela específica ou tipo um chat (apenas visualização), aí ele pode ver o que foi enviado e recebido."

---

## 📊 **SITUAÇÃO ATUAL:**

### **Modelos Existentes:**

1. **`CampaignContact`** (campaigns)
   - Rastreia envio da campanha
   - Status: pending → sent → delivered → read
   - **NÃO guarda respostas**

2. **`Message`** (chat_messages) - **Para o Sense**
   - Guarda conversas completas
   - Análise IA (sentimento, emoção, satisfação)
   - **É usado pelo Sense, não pelo Flow**

3. **`CampaignLog`** (campaigns)
   - Logs de eventos
   - **Não guarda conteúdo de mensagens**

---

## 💡 **OPÇÕES DE IMPLEMENTAÇÃO:**

### **OPÇÃO 1: Novo Modelo - CampaignReply** ⭐ **RECOMENDADO**

**Conceito:** Modelo específico para respostas de campanhas

```python
class CampaignReply(models.Model):
    """Respostas dos contatos às campanhas"""
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    
    # Relacionamentos
    campaign_contact = models.ForeignKey(
        CampaignContact,
        on_delete=models.CASCADE,
        related_name='replies'
    )
    campaign = models.ForeignKey(Campaign, on_delete=models.CASCADE)
    contact = models.ForeignKey('contacts.Contact', on_delete=models.CASCADE)
    tenant = models.ForeignKey('tenancy.Tenant', on_delete=models.CASCADE)
    
    # Conteúdo da resposta
    message_text = models.TextField(verbose_name='Texto da Resposta')
    whatsapp_message_id = models.CharField(max_length=255)  # ID no WhatsApp
    
    # Tipo de resposta
    reply_type = models.CharField(
        max_length=20,
        choices=[
            ('text', 'Texto'),
            ('image', 'Imagem'),
            ('video', 'Vídeo'),
            ('document', 'Documento'),
            ('audio', 'Áudio'),
            ('sticker', 'Sticker'),
            ('location', 'Localização'),
        ],
        default='text'
    )
    
    # Mídia (se houver)
    media_url = models.URLField(blank=True, null=True)
    media_caption = models.TextField(blank=True, null=True)
    
    # Metadados
    replied_at = models.DateTimeField(auto_now_add=True)
    is_opt_out = models.BooleanField(default=False)  # Se foi "SAIR"
    is_read = models.BooleanField(default=False)  # Se usuário já viu
    
    # Contexto da campanha (snapshot)
    message_sent = models.TextField(verbose_name='Mensagem Enviada')  # O que foi enviado
    sent_at = models.DateTimeField(verbose_name='Enviado Em')
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'campaigns_reply'
        ordering = ['-replied_at']
        indexes = [
            models.Index(fields=['campaign', '-replied_at']),
            models.Index(fields=['contact', '-replied_at']),
            models.Index(fields=['is_read', '-replied_at']),
            models.Index(fields=['is_opt_out']),
        ]
```

**✅ VANTAGENS:**
- **Foco específico:** Só para respostas de campanhas
- **Simples:** Não mistura com Sense (Message)
- **Rápido:** Queries otimizadas para Flow
- **Contexto:** Guarda o que foi enviado junto com a resposta
- **Notificações:** Fácil filtrar `is_read=False`

**❌ DESVANTAGENS:**
- Duplicação (se depois quiser usar no Sense, precisa sincronizar)

---

### **OPÇÃO 2: Reutilizar `Message` (Sense)** 🤔

**Conceito:** Usar o modelo existente, adicionar FK para Campaign

```python
# Adicionar em Message:
campaign_contact = models.ForeignKey(
    'campaigns.CampaignContact',
    on_delete=models.SET_NULL,
    null=True,
    blank=True,
    related_name='received_messages'
)
```

**✅ VANTAGENS:**
- **Integração:** Sense pode analisar respostas de campanhas
- **Unificado:** Uma tabela para todas mensagens

**❌ DESVANTAGENS:**
- **Complexo:** Mistura Flow com Sense
- **Performance:** Tabela `messages_message` fica gigante
- **Confuso:** Message é pro Sense (conversas), não pro Flow (campanhas)
- **Dependência:** Flow depende do Sense (não é ideal)

---

### **OPÇÃO 3: Híbrida (CampaignReply + Message)** 🚀 **MELHOR A LONGO PRAZO**

**Conceito:** CampaignReply (rápido) + sincroniza com Message (análise)

```python
class CampaignReply(models.Model):
    # ... campos do Option 1 ...
    
    # Referência cruzada (opcional)
    message = models.OneToOneField(
        'chat_messages.Message',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='campaign_reply'
    )
```

**Fluxo:**
1. Webhook recebe resposta → cria `CampaignReply` (imediato)
2. Celery task (assíncrono) → cria `Message` e analisa IA
3. Liga os dois via FK

**✅ VANTAGENS:**
- **Melhor dos dois mundos:** Flow rápido + Sense completo
- **Flexível:** Pode analisar IA depois
- **Desacoplado:** Flow funciona independente do Sense
- **Escalável:** Pode ativar/desativar análise IA por plano

**❌ DESVANTAGENS:**
- Mais complexo de implementar
- Sincronização pode falhar (precisa retry)

---

## 🎨 **UX: COMO MOSTRAR AS RESPOSTAS?**

### **OPÇÃO A: Tela "Respostas da Campanha"** ⭐ **RECOMENDADO PARA MVP**

**Localização:** Dentro da página de detalhes da campanha

**Layout:**
```
┌─────────────────────────────────────────────────────┐
│  Campanha: Black Friday 2024                        │
│  ┌─────┬─────────┬─────────┬──────────┐            │
│  │Enviadas│Entregues│Lidas│Respostas│            │
│  │  1.250 │  1.180  │ 890 │   47 🔴 │            │ ← Badge vermelho (não lidas)
│  └─────┴─────────┴─────────┴──────────┘            │
│                                                     │
│  [Aba: Visão Geral] [Aba: Contatos] [Aba: Respostas] ← Nova aba!
│                                                     │
│  ┌───────────────────────────────────────────────┐ │
│  │ 💬 Respostas (47)    🔄 Atualizar  ✅ Marcar tudo como lido │
│  ├───────────────────────────────────────────────┤ │
│  │ 🔴 João Silva - há 2 minutos                   │ │
│  │    ├─ Você enviou: "Olá João! Confira..."    │ │
│  │    └─ Ele respondeu: "Gostei! Quero saber..." │ │
│  │    [Ver conversa] [Marcar como lido]          │ │
│  ├───────────────────────────────────────────────┤ │
│  │ 🔴 Maria Santos - há 15 minutos                │ │
│  │    ├─ Você enviou: "Oi Maria! Novidades..."   │ │
│  │    └─ Ela respondeu: "SAIR" ⚠️ Opt-out       │ │
│  │    [Ver conversa]                              │ │
│  ├───────────────────────────────────────────────┤ │
│  │ ⚪ Pedro Costa - há 1 hora                     │ │ ← Já lida
│  │    ├─ Você enviou: "Olá Pedro..."             │ │
│  │    └─ Ele respondeu: "Obrigado!"              │ │
│  │    [Ver conversa]                              │ │
│  └───────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────┘
```

**Features:**
- ✅ Lista de respostas em ordem cronológica
- ✅ Badge 🔴 para não lidas, ⚪ para lidas
- ✅ Preview do que foi enviado + resposta
- ✅ Detectar opt-out automaticamente
- ✅ Botão "Marcar como lido"
- ✅ Botão "Ver conversa" (modal)

**✅ VANTAGENS:**
- **Contexto:** Respostas dentro da campanha
- **Simples:** Fácil de implementar
- **Organizado:** Cada campanha tem suas respostas

---

### **OPÇÃO B: Chat Style (Visualização)** 🎨 **PARA DEPOIS**

**Localização:** Modal ou página separada

**Layout:**
```
┌─────────────────────────────────────────────────────┐
│  💬 Conversa com João Silva                         │
│  Campanha: Black Friday 2024                        │
│  ───────────────────────────────────────────────────│
│                                                     │
│  [Você - 14:30]                                     │
│  ┌─────────────────────────────────────┐           │
│  │ Olá João! Confira nossa promoção:   │           │
│  │ 50% OFF em todos os produtos! 🎉    │           │
│  └─────────────────────────────────────┘           │
│  ✓✓ Lida às 14:32                                  │
│                                                     │
│            ┌─────────────────────────────────┐     │
│            │ Gostei! Quero saber mais sobre  │     │
│            │ a entrega. Vocês fazem?         │     │
│            └─────────────────────────────────┘     │
│                            [João - 14:35] 🔴       │
│                                                     │
│  ───────────────────────────────────────────────────│
│  ⚠️ Esta é uma visualização. Respostas devem ser   │
│     feitas diretamente no WhatsApp do cliente.     │
│                                                     │
│  [❌ Fechar]  [✅ Marcar como lido]  [🔗 Abrir WhatsApp] │
└─────────────────────────────────────────────────────┘
```

**Features:**
- ✅ Interface estilo chat (WhatsApp-like)
- ✅ Mostra timestamps
- ✅ Status de leitura (✓✓)
- ✅ Apenas visualização (não envia resposta pelo sistema)
- ✅ Botão para abrir WhatsApp direto

**✅ VANTAGENS:**
- **Visual:** Bonito, familiar (tipo WhatsApp)
- **Contexto:** Vê a conversa completa
- **Profissional:** Boa UX

**❌ DESVANTAGENS:**
- Mais complexo de implementar
- Pode gerar expectativa de responder pelo sistema (e não é o caso)

---

### **OPÇÃO C: Notificação Push + Lista Global** 🔔 **COMPLEMENTAR**

**Localização:** 
- Sino de notificação no header
- Página "Todas as Respostas"

**Layout Header:**
```
┌────────────────────────────────────────┐
│  ALREA    [Dashboard] [Campanhas]      │
│           🔔 47 ← Badge vermelho       │
│              └─ Dropdown:              │
│                 João Silva respondeu   │
│                 Maria Santos respondeu │
│                 [Ver todas (47)]       │
└────────────────────────────────────────┘
```

**✅ VANTAGENS:**
- **Imediato:** Usuário vê na hora
- **Global:** Notificações de todas campanhas
- **Engajamento:** Aumenta interação

---

## 🎯 **RECOMENDAÇÃO (MVP → EVOLUÇÃO):**

### **FASE 1: MVP (Flow básico)** ✅ **FAZER AGORA**

**Backend:**
1. Criar modelo `CampaignReply` (Opção 1)
2. Webhook salva respostas quando recebe `messages.upsert` com `fromMe=false`
3. Atualizar contador `campaign.replies_count`
4. Detectar opt-out automaticamente

**Frontend:**
1. Aba "Respostas" na página da campanha (Opção A)
2. Lista de respostas com filtro (não lidas / todas)
3. Badge 🔴 para não lidas
4. Botão "Marcar como lido"
5. Notificação no header (Badge de respostas não lidas)

**Tempo estimado:** 4-6 horas

---

### **FASE 2: Melhorias (UX)** ⏳ **DEPOIS**

**Frontend:**
1. Modal com visualização estilo chat (Opção B)
2. Filtros avançados (por contato, data, tipo)
3. Exportar respostas (CSV)
4. Busca por texto

**Tempo estimado:** 6-8 horas

---

### **FASE 3: Integração com Sense** 🧠 **FUTURO**

**Backend:**
1. Sincronizar `CampaignReply` → `Message` (Opção 3)
2. Análise IA das respostas (sentimento, satisfação)
3. Insights: "47% respostas positivas", "2 opt-outs"
4. Dashboard: Taxa de resposta por campanha

**Tempo estimado:** 8-12 horas

---

## 📊 **ESTRUTURA DE DADOS (FASE 1):**

### **Tabela: campaigns_reply**

```sql
CREATE TABLE campaigns_reply (
    id UUID PRIMARY KEY,
    campaign_id UUID NOT NULL REFERENCES campaigns_campaign(id),
    campaign_contact_id UUID NOT NULL REFERENCES campaigns_contact(id),
    contact_id UUID NOT NULL REFERENCES contacts_contact(id),
    tenant_id UUID NOT NULL REFERENCES tenancy_tenant(id),
    
    -- Resposta
    message_text TEXT NOT NULL,
    whatsapp_message_id VARCHAR(255) NOT NULL,
    reply_type VARCHAR(20) DEFAULT 'text',
    media_url TEXT,
    media_caption TEXT,
    
    -- Contexto (o que foi enviado)
    message_sent TEXT NOT NULL,  -- Snapshot
    sent_at TIMESTAMP NOT NULL,
    
    -- Estado
    replied_at TIMESTAMP NOT NULL,
    is_opt_out BOOLEAN DEFAULT FALSE,
    is_read BOOLEAN DEFAULT FALSE,  -- ← Usuário visualizou?
    
    created_at TIMESTAMP DEFAULT NOW(),
    
    INDEX idx_campaign_replied (campaign_id, replied_at DESC),
    INDEX idx_contact_replied (contact_id, replied_at DESC),
    INDEX idx_unread (is_read, replied_at DESC),
    INDEX idx_opt_out (is_opt_out)
);
```

---

## 🔄 **FLUXO COMPLETO (FASE 1):**

```
1. CAMPANHA ENVIA MENSAGEM
   ├─ CampaignContact.status = 'sent'
   ├─ CampaignContact.whatsapp_message_id = "ABC123"
   └─ CampaignContact.message_sent = "Olá! Confira..."

2. CONTATO RESPONDE (15 minutos depois)
   ├─ Webhook recebe: messages.upsert
   ├─ data.key.fromMe = false (é resposta!)
   └─ data.message.conversation = "Gostei! Quero saber mais"

3. WEBHOOK PROCESSA (handle_contact_reply)
   ├─ Busca CampaignContact pelo phone
   ├─ Cria CampaignReply:
   │   ├─ message_text = "Gostei! Quero saber mais"
   │   ├─ message_sent = "Olá! Confira..." (do CampaignContact)
   │   ├─ is_opt_out = False
   │   └─ is_read = False ← IMPORTANTE!
   │
   ├─ Atualiza Campaign:
   │   └─ replies_count += 1
   │
   ├─ Se opt-out ("SAIR"):
   │   ├─ CampaignReply.is_opt_out = True
   │   ├─ Contact.mark_opted_out()
   │   └─ CampaignContact.status = 'opted_out'
   │
   └─ CampaignLog.create(...)

4. FRONTEND CONSULTA
   ├─ GET /api/campaigns/{id}/replies/
   │   └─ Filtra: is_read=False (não lidas)
   │
   ├─ Badge no header: 47 respostas não lidas
   └─ Aba "Respostas" na campanha

5. USUÁRIO MARCA COMO LIDO
   ├─ POST /api/campaigns/replies/{id}/mark_read/
   └─ CampaignReply.is_read = True
```

---

## 🎯 **CONTADORES A ADICIONAR:**

### **No modelo Campaign:**

```python
class Campaign(models.Model):
    # ... campos existentes ...
    
    # ADICIONAR:
    replies_count = models.IntegerField(default=0)
    unread_replies_count = models.IntegerField(default=0)
    opt_out_count = models.IntegerField(default=0)  # Detectados via resposta
```

**Atualização:**
- `replies_count`: +1 a cada resposta
- `unread_replies_count`: +1 ao receber, -1 ao marcar como lido
- `opt_out_count`: +1 se resposta for "SAIR"

---

## 📡 **ENDPOINTS (FASE 1):**

```python
# Listar respostas da campanha
GET /api/campaigns/{campaign_id}/replies/
    ?is_read=false  # Filtrar não lidas
    ?is_opt_out=false  # Excluir opt-outs
    
Response:
{
  "count": 47,
  "unread_count": 23,
  "results": [
    {
      "id": "uuid",
      "contact": {
        "id": "uuid",
        "name": "João Silva",
        "phone": "+5511999999999"
      },
      "message_sent": "Olá João! Confira...",
      "message_text": "Gostei! Quero saber mais",
      "reply_type": "text",
      "is_opt_out": false,
      "is_read": false,
      "sent_at": "2024-11-10T14:30:00Z",
      "replied_at": "2024-11-10T14:35:00Z"
    }
  ]
}

# Marcar resposta como lida
POST /api/campaigns/replies/{reply_id}/mark_read/

# Marcar todas como lidas
POST /api/campaigns/{campaign_id}/replies/mark_all_read/

# Contadores globais (todas campanhas)
GET /api/campaigns/replies/unread_count/
Response: { "unread_count": 47 }
```

---

## 🎨 **COMPONENTES FRONTEND (FASE 1):**

```
frontend/src/
├── pages/
│   └── CampaignDetailPage.tsx (atualizar)
│       └── Adicionar aba "Respostas"
│
├── components/
│   └── campaigns/
│       ├── CampaignRepliesList.tsx ← NOVO! Lista de respostas
│       ├── CampaignReplyCard.tsx ← NOVO! Card individual
│       └── UnreadRepliesBadge.tsx ← NOVO! Badge no header
```

---

## ⚠️ **IMPORTANTE: O QUE NÃO FAZER:**

### **❌ NÃO implementar envio de resposta pelo sistema**

**Por quê:**
- WhatsApp Business API tem regras rígidas de janela de 24h
- Fora da janela, só pode enviar templates pré-aprovados
- Responder livremente exige integração oficial (cara)
- Cliente deve responder pelo WhatsApp direto

**✅ FAZER:**
- Visualização apenas
- Botão "Abrir no WhatsApp" (deep link)
- Mensagem clara: "Respostas devem ser feitas pelo WhatsApp"

---

## 📊 **RESUMO EXECUTIVO:**

```
┌─────────────────────────────────────────────────────┐
│  RESPOSTAS DE CAMPANHAS - ESTRATÉGIA MVP           │
├─────────────────────────────────────────────────────┤
│  BACKEND:                                           │
│  ✅ Novo modelo: CampaignReply                     │
│  ✅ Webhook salva respostas (messages.upsert)      │
│  ✅ Detecta opt-out automático                     │
│  ✅ Contadores: replies, unread, opt-outs          │
│                                                     │
│  FRONTEND:                                          │
│  ✅ Aba "Respostas" na campanha                    │
│  ✅ Lista: enviado + resposta                      │
│  ✅ Badge 🔴 não lidas, ⚪ lidas                   │
│  ✅ Notificação no header (contador global)        │
│  ✅ Marcar como lido                               │
│                                                     │
│  NÃO FAZER (MVP):                                   │
│  ❌ Chat completo (estilo WhatsApp)                │
│  ❌ Responder pelo sistema                         │
│  ❌ Análise IA (deixar pro Sense)                  │
│                                                     │
│  TEMPO: 4-6 horas                                   │
└─────────────────────────────────────────────────────┘
```

---

## 💡 **MINHA OPINIÃO:**

**RECOMENDO:** 

1. **Fase 1 (Agora):** Implementar CampaignReply + Aba de Respostas
   - Simples, rápido, útil
   - Foco em notificar e rastrear
   - Não confunde com Sense

2. **Fase 2 (Depois):** Melhorar UX com chat visual
   - Quando Flow estiver estável
   - Adicionar filtros, busca, exportação

3. **Fase 3 (Futuro):** Integrar com Sense
   - Análise IA das respostas
   - Insights de satisfação
   - Taxa de resposta por campanha

**É isso que você tinha em mente? Qual abordagem prefere?** 🤔


