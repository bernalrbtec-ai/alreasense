# 🧪 GUIA COMPLETO - Testar Importação + Campanha Simples

**Data:** 2025-10-11  
**Status:** ✅ Pronto para testar

---

## 📦 **O QUE FOI IMPLEMENTADO**

### ✅ **BACKEND COMPLETO**
1. **Importação de Contatos**
   - Auto-detecção de delimitador (`,` ou `;`)
   - Suporta formato `Nome;DDD;Telefone;email`
   - Combina DDD + Telefone automaticamente
   - Preview antes de importar
   - Celery task assíncrona
   - Validações robustas

2. **Integração Campanhas + Contatos**
   - Seleção por: All, Tags, Listas, Manual
   - `get_target_contacts()` com filtro opted_out
   - `MessageVariableService` para {name}, {greeting}
   - Migration criada

### ✅ **FRONTEND COMPLETO**
1. **ImportContactsModal** (5 steps)
   - Upload com drag & drop
   - Configurações (merge strategy)
   - Preview com mapeamento
   - Progress bar em tempo real
   - Resultado com cards

2. **ContactSelector** 
   - Seleção por tags/listas
   - Contador de contatos
   - Visual integrado

---

## 🚀 **PASSO A PASSO PARA TESTAR**

### **FASE 1: PREPARAR AMBIENTE**

#### 1.1. Aplicar Migrations

```bash
cd backend
python manage.py migrate campaigns
python manage.py migrate contacts
```

#### 1.2. Verificar Celery

```bash
# Terminal 1: Worker
celery -A alrea_sense worker --loglevel=info --pool=solo

# Terminal 2: Beat (scheduler)
celery -A alrea_sense beat --loglevel=info
```

#### 1.3. Rodar Backend + Frontend

```bash
# Terminal 3: Backend
cd backend
python manage.py runserver

# Terminal 4: Frontend
cd frontend
npm run dev
```

---

### **FASE 2: TESTAR IMPORTAÇÃO**

#### 2.1. Preparar CSV de Teste

Usar seu arquivo real: `INDICAÇÕESCSV (1).csv`

**Formato:**
```csv
Nome;DDD;Telefone;email;Quem Indicou
Frederico;33;999730911;;
Andre;19;998427160;;
```

Ou criar um teste menor:
```csv
Nome;DDD;Telefone;email;Quem Indicou
Maria Silva;11;999999999;maria@email.com;João
João Santos;11;988888888;;Pedro
Ana Costa;21;977777777;ana@email.com;
```

Salve como: `teste_importacao.csv`

#### 2.2. Importar via Interface

1. **Login** → Acesse `http://localhost:5173`

2. **Ir para Contatos** → Menu lateral

3. **Clicar "Importar CSV"** → Abre modal

4. **STEP 1: Upload**
   - Arrastar arquivo ou clicar
   - Verificar se detecta o arquivo
   - Clicar "Próximo"

5. **STEP 2: Configurações**
   - Escolher: ○ Pular duplicatas (padrão)
   - Checkbox: ☐ Consentimento LGPD (opcional)
   - Clicar "Preview"

6. **STEP 3: Preview**
   - Verificar mapeamento:
     ```
     Nome → name ✅
     DDD → (combinado) ✅
     Telefone → phone ✅
     email → email ✅
     Quem Indicou → notes ✅
     ```
   - Ver primeiras linhas na tabela
   - Verificar warnings (se houver)
   - Clicar "Iniciar Importação"

7. **STEP 4: Processando**
   - Ver progress bar (0-100%)
   - Ver contadores em tempo real:
     - Criados: 0 → 474
     - Erros: X
   - Aguardar conclusão

8. **STEP 5: Resultado**
   - Ver cards com totais
   - Se teve erros, ver lista
   - Clicar "Concluir"

9. **Verificar Lista de Contatos**
   - Deve mostrar os 474 contatos importados
   - Telefones normalizados: `+5533999730911`
   - Campo "Quem Indicou" deve estar em Notes

#### 2.3. Testar via API (Alternativo)

```bash
# Preview
curl -X POST http://localhost:8000/api/contacts/contacts/preview_csv/ \
  -H "Authorization: Bearer {seu_token}" \
  -F "file=@teste_importacao.csv"

# Resposta esperada:
{
  "status": "success",
  "headers": ["Nome", "DDD", "Telefone", "email", "Quem Indicou"],
  "column_mapping": {
    "Nome": "name",
    "DDD": "ddd",
    "Telefone": "phone",
    "email": "email",
    "Quem Indicou": null
  },
  "delimiter": ";",
  "has_ddd_separated": true,
  "sample_rows": [...]
}

# Importar
curl -X POST http://localhost:8000/api/contacts/contacts/import_csv/ \
  -H "Authorization: Bearer {seu_token}" \
  -F "file=@teste_importacao.csv" \
  -F "update_existing=false" \
  -F "async_processing=true"

# Resposta:
{
  "status": "processing",
  "import_id": "uuid-xxxx",
  "message": "Importação iniciada..."
}

# Verificar progresso
curl http://localhost:8000/api/contacts/imports/{import_id}/ \
  -H "Authorization: Bearer {seu_token}"
```

---

### **FASE 3: CRIAR TAGS E LISTAS**

#### 3.1. Criar Tags de Teste

```bash
# Via API
POST /api/contacts/tags/
{
  "name": "VIP",
  "color": "#10B981",
  "description": "Clientes VIP"
}

POST /api/contacts/tags/
{
  "name": "Lead Quente",
  "color": "#F59E0B"
}
```

#### 3.2. Associar Contatos às Tags

```bash
# Pegar IDs de alguns contatos
GET /api/contacts/contacts/?limit=10

# Editar contato e adicionar tag
PATCH /api/contacts/contacts/{contact_id}/
{
  "tag_ids": ["uuid-da-tag-vip"]
}
```

#### 3.3. Criar Lista de Teste

```bash
POST /api/contacts/lists/
{
  "name": "Black Friday 2024",
  "description": "Lista para campanha da Black Friday"
}

# Adicionar contatos à lista
PATCH /api/contacts/contacts/{contact_id}/
{
  "list_ids": ["uuid-da-lista"]
}
```

---

### **FASE 4: CRIAR CAMPANHA COM CONTATOS**

#### 4.1. Verificar Instância WhatsApp

```bash
GET /api/notifications/instances/

# Garantir que tem pelo menos 1 instância conectada
# Se não tiver, criar uma
```

#### 4.2. Criar Campanha por Tags

```bash
POST /api/campaigns/campaigns/
{
  "name": "Teste Campanha VIP",
  "description": "Campanha de teste para contatos VIP",
  "instance_id": "uuid-da-instancia",
  
  # NOVO: Seleção de contatos
  "contact_selection_type": "tags",
  "tag_ids": ["uuid-da-tag-vip"],
  
  # Mensagens (com variáveis!)
  "message_texts": [
    "Olá {name}, {greeting}! Você é cliente VIP e temos uma oferta especial!"
  ],
  
  # Agendamento
  "schedule_type": "immediate"
}
```

**Resposta esperada:**
```json
{
  "id": "uuid",
  "name": "Teste Campanha VIP",
  "contact_selection_type": "tags",
  "target_contacts_count": 15,  // ← Novo campo!
  "status": "draft"
}
```

#### 4.3. Criar Campanha por Lista

```bash
POST /api/campaigns/campaigns/
{
  "name": "Black Friday 2024",
  "instance_id": "uuid-da-instancia",
  
  "contact_selection_type": "lists",
  "list_ids": ["uuid-da-lista-black-friday"],
  
  "message_texts": [
    "{greeting} {name}! 🎉 Black Friday começou! 50% OFF em tudo!"
  ]
}
```

#### 4.4. Criar Campanha para Todos

```bash
POST /api/campaigns/campaigns/
{
  "name": "Newsletter Mensal",
  "instance_id": "uuid-da-instancia",
  
  "contact_selection_type": "all",  // ← Todos os contatos
  
  "message_texts": [
    "Olá {first_name}! Confira as novidades deste mês."
  ]
}
```

---

### **FASE 5: INICIAR E MONITORAR CAMPANHA**

#### 5.1. Iniciar Campanha

```bash
POST /api/campaigns/campaigns/{campaign_id}/start/
```

**O que acontece:**
1. ✅ Sistema chama `campaign.get_target_contacts()`
2. ✅ Filtra automaticamente `opted_out=False`
3. ✅ Cria `CampaignContact` para cada contato
4. ✅ Celery scheduler pega a campanha
5. ✅ Para cada contato:
   - Renderiza mensagem com `MessageVariableService`
   - Substitui `{name}`, `{greeting}`, etc
   - Envia via WhatsApp Gateway
   - Aplica delay aleatório (20-50s)

#### 5.2. Verificar Logs

```bash
# Ver contatos da campanha
GET /api/campaigns/campaigns/{campaign_id}/contacts/

# Ver logs de envio
GET /api/campaigns/campaigns/{campaign_id}/logs/
```

#### 5.3. Testar Variáveis

**Template:**
```
Olá {name}, {greeting}!

Vimos que você é de {city}, {state}.

Temos uma oferta especial!
```

**Contato:**
```json
{
  "name": "Maria Silva",
  "city": "São Paulo",
  "state": "SP"
}
```

**Mensagem renderizada (às 14h):**
```
Olá Maria Silva, Boa tarde!

Vimos que você é de São Paulo, SP.

Temos uma oferta especial!
```

---

### **FASE 6: TESTAR OPT-OUT**

#### 6.1. Marcar Contato como Opted-Out

```bash
POST /api/contacts/contacts/{contact_id}/opt_out/
```

#### 6.2. Criar Campanha

```bash
POST /api/campaigns/campaigns/
{
  "contact_selection_type": "all",
  "message_texts": ["Teste"]
}

# Verificar target_contacts_count
GET /api/campaigns/campaigns/{campaign_id}/
# → Contatos opted-out NÃO devem ser contados!
```

#### 6.3. Iniciar Campanha

```bash
POST /api/campaigns/campaigns/{campaign_id}/start/
```

**Verificar:**
- ✅ Contato opted-out NÃO recebe mensagem
- ✅ Logs mostram: "Contato opted-out - pulado"

---

## ✅ **CHECKLIST DE TESTE**

### Importação
- [ ] Upload arquivo CSV (arrasta ou clica)
- [ ] Preview mostra colunas corretas
- [ ] Mapeamento automático de Nome, DDD, Telefone
- [ ] Progress bar funciona
- [ ] Contadores atualizam em tempo real
- [ ] Resultado mostra totais corretos
- [ ] Contatos aparecem na lista

### Campanhas
- [ ] Seleção "Todos" mostra contagem
- [ ] Seleção "Por tags" filtra corretamente
- [ ] Seleção "Por listas" filtra corretamente
- [ ] Variáveis {name}, {greeting} são substituídas
- [ ] Opted-out são excluídos automaticamente
- [ ] Campanha envia com delays
- [ ] Logs registram tudo

---

## 🐛 **PROBLEMAS COMUNS**

### Erro: "Telefone inválido"

**Causa:** DDD inválido ou telefone muito curto

**Solução:**
```csv
❌ Nome;DDD;Telefone
   Maria;0;999999999     → DDD inválido (00)
   João;1;99999999       → DDD muito curto

✅ Nome;DDD;Telefone
   Maria;11;999999999    → OK
   João;21;988888888     → OK
```

### Erro: "Campos obrigatórios"

**Causa:** Nome ou Telefone vazio

**Solução:**
- Verificar se CSV tem linhas vazias no final
- Remover linhas em branco

### Progress bar não atualiza

**Causa:** Celery não está rodando

**Solução:**
```bash
# Verificar se Celery Worker está ativo
celery -A alrea_sense inspect active

# Se não estiver, iniciar
celery -A alrea_sense worker --loglevel=info --pool=solo
```

### Contatos não recebem mensagem

**Causa 1:** Opted-out = True
- Verificar: `GET /api/contacts/contacts/{id}/`
- Solução: `POST /api/contacts/contacts/{id}/opt_in/`

**Causa 2:** Instância desconectada
- Verificar: `GET /api/notifications/instances/{id}/`
- connection_state deve ser "open"

---

## 📊 **TESTES RECOMENDADOS**

### Teste 1: Importação Pequena (10 contatos)

**Objetivo:** Validar fluxo básico

```csv
Nome;DDD;Telefone;email
Maria;11;999999999;maria@email.com
João;11;988888888;
Ana;21;977777777;ana@email.com
```

**Verificar:**
- ✅ 3 contatos criados
- ✅ Telefones: +5511999999999, +5511988888888, +5521977777777
- ✅ João sem email (OK)

---

### Teste 2: Importação Grande (474 contatos)

**Objetivo:** Testar processamento assíncrono

**Arquivo:** `INDICAÇÕESCSV (1).csv` (seu arquivo real)

**Verificar:**
- ✅ Modal muda para "Processando" (step 4)
- ✅ Progress bar atualiza
- ✅ Contadores aumentam em tempo real
- ✅ Resultado mostra: 474 criados

---

### Teste 3: Campanha com Tags

**Objetivo:** Segmentação funciona

**Passos:**
1. Criar tag "Teste"
2. Adicionar 5 contatos à tag
3. Criar campanha com `contact_selection_type: "tags"`
4. Verificar `target_contacts_count: 5`
5. Iniciar campanha
6. Verificar que apenas 5 recebem

---

### Teste 4: Variáveis de Mensagem

**Objetivo:** Renderização de variáveis

**Template:**
```
Olá {name}, {greeting}!

Você mora em {city}? Temos novidades!

Atenciosamente,
Equipe ALREA
```

**Contato:**
- name: "Maria Silva"
- city: "São Paulo"

**Resultado esperado (às 10h):**
```
Olá Maria Silva, Bom dia!

Você mora em São Paulo? Temos novidades!

Atenciosamente,
Equipe ALREA
```

---

### Teste 5: Opt-Out Compliance

**Objetivo:** Garantir que opted-out NÃO recebe

**Passos:**
1. Importar 10 contatos
2. Marcar 3 como opted-out: `POST /contacts/{id}/opt_out/`
3. Criar campanha com `contact_selection_type: "all"`
4. Verificar `target_contacts_count: 7` (não 10!)
5. Iniciar campanha
6. Verificar logs: apenas 7 enviados

---

## 🎯 **CASOS DE USO REAIS**

### Caso 1: Importar Base de Clientes

```
Cenário: Loja tem planilha Excel com 500 clientes

1. Salvar Excel como CSV (Arquivo → Salvar Como → CSV)
2. Abrir ALREA → Contatos → Importar
3. Upload do CSV
4. Preview → Conferir mapeamento
5. Configurar:
   ☑ Todos têm consentimento (compram na loja)
   Onde obteve: "Loja física"
6. Importar
7. Aguardar conclusão
8. ✅ 500 contatos prontos para campanhas
```

### Caso 2: Campanha de Aniversariantes

```
Cenário: Enviar parabéns para quem faz aniversário

1. Criar tag "Aniversariantes Mês"
2. Filtrar contatos: birth_month = 10 (outubro)
3. Adicionar tag "Aniversariantes Mês" neles
4. Criar campanha:
   - Seleção: Por tags → "Aniversariantes Mês"
   - Mensagem: "🎂 {name}, parabéns! Ganhe 15% OFF!"
5. Iniciar
```

### Caso 3: Recuperação de Churned

```
Cenário: Re-engajar clientes inativos

1. Criar lista "Churn 90 dias"
2. Importar CSV com:
   - last_purchase_date < 90 dias atrás
3. Adicionar à lista
4. Criar campanha:
   - Seleção: Por lista → "Churn 90 dias"
   - Mensagem: "{greeting} {name}! Sentimos sua falta..."
5. Iniciar
```

---

## 📈 **MÉTRICAS ESPERADAS**

### Performance
- Importação de 1.000 contatos: **~30-60 segundos**
- Preview de CSV: **< 2 segundos**
- Campanha para 1.000 contatos: **~6-12 horas** (com delays)

### Precisão
- Taxa de telefones normalizados: **100%**
- Taxa de opt-out respeitado: **100%**
- Taxa de variáveis renderizadas: **100%**

---

## 🔧 **CONFIGURAÇÃO DO CELERY BEAT**

Adicionar no `backend/alrea_sense/celery.py`:

```python
from celery.schedules import crontab

app.conf.beat_schedule = {
    'check-scheduled-campaigns': {
        'task': 'apps.campaigns.tasks.campaign_scheduler',
        'schedule': crontab(minute='*/1'),  # A cada 1 minuto
    },
    
    'cleanup-old-imports': {
        'task': 'apps.contacts.tasks.cleanup_old_import_files',
        'schedule': crontab(hour=3, minute=0),  # Todo dia às 3h
    },
}
```

---

## 🎉 **SUCESSO ESPERADO**

Ao final dos testes, você deve conseguir:

1. ✅ Importar CSV com formato `Nome;DDD;Telefone`
2. ✅ Ver preview antes de importar
3. ✅ Processar 474+ contatos em < 2 minutos
4. ✅ Criar tags e listas
5. ✅ Criar campanha selecionando por tags
6. ✅ Ver contagem de contatos selecionados
7. ✅ Iniciar campanha
8. ✅ Mensagens com {name}, {greeting} renderizados
9. ✅ Opted-out automaticamente excluídos
10. ✅ Monitorar progresso em tempo real

---

## 🚀 **PRÓXIMOS PASSOS**

Após validar que tudo funciona:

1. ✅ Deploy Railway (migrations + código)
2. ✅ Testar em produção com CSV real
3. ✅ Implementar Mensagens Agendadas
4. ✅ Implementar Billing Asaas
5. ✅ AI Message Generation (N8N)

---

**TUDO PRONTO PARA TESTAR! 🎯**

Qualquer erro que encontrar, me avisa que ajusto!





