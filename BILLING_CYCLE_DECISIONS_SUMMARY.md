# 📋 **RESUMO DAS DECISÕES - CICLO DE MENSAGENS**

> **Decisões Finais Aprovadas**  
> **Data:** Janeiro 2025

---

## ✅ **DECISÕES TÉCNICAS**

| # | Questão | Decisão | Detalhes |
|---|--------|---------|----------|
| 1 | **Template** | Genérico OU Específico | Opção na gestão de templates |
| 2 | **Variações** | ✅ Rotacionar | Cada mensagem usa variação diferente |
| 3 | **Dias Úteis** | ✅ Respeitar | Usar BusinessHoursService |
| 4 | **Fim de Semana** | ✅ **ANTECIPAR** | Enviar na última sexta-feira antes |
| 5 | **Retry** | ✅ Implementar | Usar max_retry_attempts |
| 6 | **Status Completed** | ✅ Quando todas enviadas | Sent ou failed |
| 7 | **Relatório** | ✅ Página igual campanhas | `/billing-api/cycles` |
| 8 | **Cadastro Destinatário** | ✅ Automático | Criar Contact com TAG "COBRANÇA" |

---

## 🏗️ **ARQUITETURA ESCOLHIDA**

### **Opção 3: Híbrida** ⭐

**Modelos:**
- `BillingCycle` - Ciclo completo da cobrança
- `BillingContact` modificado - Mensagens agendadas

**Vantagens:**
- ✅ Balanceia simplicidade e funcionalidade
- ✅ Fácil cancelar ciclo inteiro
- ✅ Histórico completo
- ✅ Reutiliza modelos existentes

---

## 🔄 **FLUXO COMPLETO**

```
1. Cliente envia BATCH de cobranças
   ↓
2. Sistema cria BillingCycle para cada cobrança
   ↓
3. Sistema cadastra destinatário automaticamente (Contact + TAG "COBRANÇA")
   ↓
4. Sistema cria BillingContact agendados:
   - Se notify_before_due: 3 mensagens (5d, 3d, 1d antes)
   - Se notify_after_due: 3 mensagens (1d, 3d, 5d depois)
   - Todas com scheduled_date recalculado (dias úteis + antecipação)
   ↓
5. Scheduler diário verifica mensagens com scheduled_date = hoje
   ↓
6. Para cada mensagem:
   - Verifica horário comercial
   - Seleciona template (genérico ou específico)
   - Rotaciona variação
   - Cria campanha e envia
   ↓
7. Cliente envia baixa → Cancela ciclo completo
```

---

## 📅 **CÁLCULO DE DATAS**

### **Regra de Antecipação:**
```
Se scheduled_date cair em:
- Fim de semana → Último dia útil ANTES
- Fora do horário → Último horário válido ANTES

Exemplo:
- Vencimento: 15/01 (Quarta)
- 5 dias antes: 10/01 (Sexta) ✅
- 3 dias antes: 12/01 (Domingo) → ANTECIPAR para 10/01 (Sexta) ✅
- 1 dia antes: 14/01 (Terça) ✅
```

---

## 🗄️ **ESTRUTURA DE DADOS**

### **BillingCycle:**
- `external_billing_id` (único por tenant)
- `contact_id` (FK para Contact cadastrado)
- `due_date`
- `status` (active, cancelled, paid, completed)
- `notify_before_due` / `notify_after_due`

### **BillingContact (modificado):**
- `billing_cycle_id` (FK)
- `cycle_message_type` (upcoming_5d, overdue_1d, etc)
- `cycle_index` (1, 2, 3, 4, 5, 6)
- `scheduled_date` (já recalculado)
- `billing_status` (active, cancelled, paid)

---

## 📊 **RELATÓRIO E VISUALIZAÇÃO**

### **Página: `/billing-api/cycles`**

**Funcionalidades:**
- ✅ Listagem de ciclos (ativo, completo, cancelado)
- ✅ Filtros (status, data, tipo)
- ✅ Detalhes do ciclo (todas as 6 mensagens)
- ✅ Gráficos de envios diários
- ✅ Estatísticas (taxa de cancelamento, etc)

**Similar a:** `/billing-api/campaigns`

---

## 👤 **CADASTRO DE DESTINATÁRIO**

### **Processo Automático:**
1. Recebe cobrança com `nome` e `telefone`
2. Normaliza telefone com `normalize_phone`
3. Busca `Contact` existente (por telefone)
4. Se não existir:
   - Cria `Contact` com nome e telefone
   - Associa ao tenant
   - Cria TAG "COBRANÇA"
5. Se existir:
   - Atualiza nome se mudou
   - Garante que tem TAG "COBRANÇA"

---

## 🎯 **PRÓXIMOS PASSOS**

1. ✅ **Documentação** - COMPLETA
2. ⏳ **Modelos** - Criar BillingCycle
3. ⏳ **Services** - BillingCycleService
4. ⏳ **APIs** - Batch e Cancelamento
5. ⏳ **Scheduler** - Verificação diária
6. ⏳ **Frontend** - Página de ciclos

---

**Status:** ✅ **APROVADO - PRONTO PARA IMPLEMENTAÇÃO**

