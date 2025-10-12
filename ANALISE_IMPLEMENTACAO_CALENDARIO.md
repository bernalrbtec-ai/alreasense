# 📅 ANÁLISE: Implementação de Calendário no Projeto

## 🎯 **OBJETIVO**

Implementar um calendário visual para mostrar:
1. **Agendamentos de envios** (mensagens programadas)
2. **Campanhas ocorridas** (histórico)
3. **Evolução futura** (eventos, feriados, etc)

---

## 📊 **ANÁLISE DE COMPLEXIDADE**

### **🟢 BAIXA COMPLEXIDADE - Calendário Básico (MVP)**
**Tempo estimado:** 4-6 horas  
**Dificuldade:** ⭐⭐☆☆☆

**O que já existe:**
- ✅ Campanhas têm `created_at` e `updated_at`
- ✅ Spec de ScheduledMessages já existe (não implementado)
- ✅ Celery Beat configurado
- ✅ Backend preparado para datas

**O que precisa fazer:**
1. Frontend: Componente de calendário (lib externa ou custom)
2. Backend: Endpoint para buscar eventos por mês
3. Integração: Mapear campanhas + agendamentos para eventos

### **🟡 MÉDIA COMPLEXIDADE - Calendário Interativo**
**Tempo estimado:** 8-12 horas  
**Dificuldade:** ⭐⭐⭐☆☆

**Adiciona:**
- Criar agendamentos clicando no calendário
- Arrastar para reagendar
- Modal de detalhes ao clicar em evento
- Filtros (campanhas, agendamentos, etc)

### **🔴 ALTA COMPLEXIDADE - Calendário Completo**
**Tempo estimado:** 16-24 horas  
**Dificuldade:** ⭐⭐⭐⭐☆

**Adiciona:**
- Recorrência (semanal, mensal)
- Conflitos de horário
- Integração com calendário Google/Outlook
- Notificações de lembrete
- Time zones

---

## 🗄️ **DADOS QUE JÁ EXISTEM NO PROJETO**

### **1. Campanhas** ✅
```python
# backend/apps/campaigns/models.py

Campaign:
  - created_at: DateTimeField           # ✅ Quando foi criada
  - scheduled_start_date: DateField?    # ⚠️ Precisa verificar se existe
  - status: draft/active/completed      # ✅ Para filtrar
  - name: CharField                     # ✅ Título no calendário
```

**O que pode mostrar:**
- 📅 Data de criação
- 📅 Data de conclusão
- 📊 Status (ativa, pausada, concluída)

### **2. ScheduledMessages** ⚠️
```python
# ALREA_SCHEDULED_MESSAGES_SPEC.md existe

ScheduledMessage:
  - scheduled_for: DateTimeField        # 📅 Data/hora exata
  - status: pending/sent/failed         # ✅ Status
  - recipient: Contact                  # ✅ Para quem
  - message: TextField                  # ✅ Conteúdo
```

**Status:** 📄 Especificado mas **NÃO implementado**

### **3. Feriados** ✅ (Potencial)
```python
# Já temos lógica de feriados para campanhas
# Pode ser usado no calendário também
```

---

## 🧩 **COMPONENTES NECESSÁRIOS**

### **Frontend:**

#### **Opção 1: Biblioteca Pronta** 🟢 (Recomendado)
**React Big Calendar**
- ✅ Completo e maduro
- ✅ Múltiplas views (mês, semana, dia)
- ✅ Eventos drag-and-drop
- ✅ Customizável
- ⚠️ ~100kb bundle size

**FullCalendar**
- ✅ Muito completo
- ✅ Responsivo
- ⚠️ Versão completa é paga

**React Calendar** (simples)
- ✅ Leve (~20kb)
- ✅ Só visualização
- ⚠️ Sem eventos built-in

#### **Opção 2: Custom (do zero)** 🔴
**Complexidade:** Alta  
**Vantagens:**
- ✅ Controle total
- ✅ Bundle size menor
- ✅ Exatamente o que precisa

**Desvantagens:**
- ❌ Tempo de desenvolvimento
- ❌ Bugs e edge cases
- ❌ Manutenção

### **Backend:**

```python
# Endpoint necessário
GET /api/calendar/events/?month=2024-11&type=campaigns,scheduled

Response:
{
  "events": [
    {
      "id": "uuid",
      "title": "Campanha Black Friday",
      "start": "2024-11-20T09:00:00Z",
      "end": "2024-11-25T18:00:00Z",
      "type": "campaign",
      "status": "completed",
      "metadata": {...}
    },
    {
      "id": "uuid",
      "title": "Lembrete Consulta - João",
      "start": "2024-11-10T14:00:00Z",
      "type": "scheduled",
      "status": "sent",
      "recipient": "João Silva"
    }
  ]
}
```

---

## 📋 **ROADMAP DE IMPLEMENTAÇÃO**

### **FASE 1: MVP - Calendário Visual (1-2 dias)** 🟢

**Objetivo:** Ver campanhas e agendamentos no calendário

**Backend:**
- [ ] Endpoint `/calendar/events/`
- [ ] Serializer para eventos
- [ ] Filtro por mês/ano

**Frontend:**
- [ ] Instalar `react-big-calendar` ou `react-calendar`
- [ ] Componente `CalendarPage.tsx`
- [ ] Mapear campanhas → eventos
- [ ] 3 views: mês, semana, dia

**Features:**
- ✅ Ver campanhas passadas
- ✅ Ver campanhas ativas
- ✅ Cores por status
- ✅ Click abre detalhes
- ✅ Navegação entre meses

---

### **FASE 2: Agendamentos (2-3 dias)** 🟡

**Objetivo:** Agendar envios pelo calendário

**Backend:**
- [ ] Implementar model `ScheduledMessage` (spec já existe)
- [ ] API CRUD para agendamentos
- [ ] Celery task para processar agendamentos
- [ ] Integrar com instâncias WhatsApp

**Frontend:**
- [ ] Modal de criar agendamento
- [ ] Click em data vazia → criar agendamento
- [ ] Seletor de contatos
- [ ] Preview de mensagem

**Features:**
- ✅ Criar agendamento clicando no dia
- ✅ Ver agendamentos no calendário
- ✅ Editar/cancelar agendamento
- ✅ Notificação antes do envio

---

### **FASE 3: Interatividade (2-3 dias)** 🟡

**Objetivo:** Calendário rico e interativo

**Frontend:**
- [ ] Drag-and-drop para reagendar
- [ ] Filtros (tipo, status, instância)
- [ ] Mini-calendário lateral
- [ ] Timeline view

**Backend:**
- [ ] Endpoint para reagendar
- [ ] Validação de conflitos
- [ ] Logging de mudanças

**Features:**
- ✅ Arrastar evento para outro dia
- ✅ Filtrar por tipo de evento
- ✅ Ver timeline do dia
- ✅ Exportar para .ics (Google Calendar)

---

### **FASE 4: Avançado (3-5 dias)** 🔴

**Objetivo:** Features premium

**Features:**
- ✅ Recorrência (semanal, mensal)
- ✅ Integração Google Calendar
- ✅ Time zones
- ✅ Lembretes por email/WhatsApp
- ✅ Analytics por período

---

## 💰 **CUSTO vs BENEFÍCIO**

| Fase | Tempo | Valor para Cliente | Recomendação |
|------|-------|-------------------|--------------|
| **MVP** | 1-2 dias | ⭐⭐⭐⭐⭐ Alto | ✅ **FAZER** |
| **Agendamentos** | 2-3 dias | ⭐⭐⭐⭐☆ Alto | ✅ **FAZER** |
| **Interatividade** | 2-3 dias | ⭐⭐⭐☆☆ Médio | 🤔 Avaliar |
| **Avançado** | 3-5 dias | ⭐⭐☆☆☆ Baixo | ⏳ Depois |

---

## 🎨 **MOCKUP VISUAL**

### **Calendário MVP:**

```
┌────────────────────────────────────────────────────────┐
│  📅 Calendário                    [Hoje] [Mês] [Semana]│
├────────────────────────────────────────────────────────┤
│                                                         │
│     NOVEMBRO 2024                                      │
│  D   S   T   Q   Q   S   S                            │
│                  1   2   3   4                         │
│  5   6   7   8   9  10  11                            │
│                     ┌────────┐                         │
│ 12  13  14  15  16 │ 17     │ 18                      │
│                    │ ● Camp1│                         │
│                    └────────┘                         │
│ 19  20  21  22  23  24  25                            │
│     ┌────────┐  ┌────────┐                           │
│     │ ● Camp2│  │ ● Agend│                           │
│     └────────┘  └────────┘                           │
│ 26  27  28  29  30                                     │
│                                                         │
│  Legenda:                                              │
│  ● Verde: Ativa  ● Azul: Agendada  ● Cinza: Concluída│
└────────────────────────────────────────────────────────┘
```

---

## 📦 **BIBLIOTECAS RECOMENDADAS**

### **1. React Big Calendar** ⭐ RECOMENDADO
```bash
npm install react-big-calendar moment
npm install @types/react-big-calendar -D
```

**Prós:**
- ✅ Completo (mês, semana, dia, agenda)
- ✅ Drag-and-drop built-in
- ✅ Customizável
- ✅ Eventos multi-dia
- ✅ Open source e gratuito

**Contras:**
- ⚠️ Bundle ~100kb
- ⚠️ Requer moment.js ou date-fns

**Código exemplo:**
```tsx
import { Calendar, momentLocalizer } from 'react-big-calendar'
import moment from 'moment'
import 'react-big-calendar/lib/css/react-big-calendar.css'

const localizer = momentLocalizer(moment)

<Calendar
  localizer={localizer}
  events={events}
  startAccessor="start"
  endAccessor="end"
  style={{ height: 600 }}
  onSelectEvent={(event) => handleEventClick(event)}
  onSelectSlot={(slotInfo) => handleCreateEvent(slotInfo)}
  selectable
/>
```

### **2. FullCalendar** (Alternativa)
- ✅ Muito rico
- ⚠️ Versão completa é paga ($199+)
- ⚠️ Bundle grande

### **3. React Calendar** (Minimalista)
- ✅ Leve (20kb)
- ⚠️ Só seleção de datas, sem eventos
- ⚠️ Precisa customizar muito

---

## 🎯 **RECOMENDAÇÃO: COMEÇAR COM MVP**

### **Semana 1: Calendário Visual (MVP)**
**Tempo:** 4-6 horas  
**Complexidade:** 🟢 Baixa

1. Instalar `react-big-calendar`
2. Criar `CalendarPage.tsx`
3. Criar endpoint `/calendar/events/`
4. Mapear campanhas existentes
5. 3 views: mês, semana, agenda

**Resultado:**
- ✅ Ver todas campanhas em calendário
- ✅ Click abre detalhes da campanha
- ✅ Cores por status (ativa, pausada, concluída)
- ✅ Navegação entre meses

### **Semana 2: Agendamentos**
**Tempo:** 8-12 horas  
**Complexidade:** 🟡 Média

1. Implementar model `ScheduledMessage`
2. API CRUD
3. Celery task
4. Modal de criar no calendário

**Resultado:**
- ✅ Clicar em dia vazio → criar agendamento
- ✅ Ver agendamentos no calendário
- ✅ Celery dispara na hora certa

---

## 💡 **DADOS QUE PODEM SER MOSTRADOS**

### **Eventos de Campanhas:**
```
┌─────────────────────────────────────────┐
│ 20/11 - Campanha Black Friday          │
│ ─────────────────────────────────       │
│ Status: ● Concluída                     │
│ Enviados: 8.542 / 10.000               │
│ Taxa entrega: 94%                       │
│ Duração: 20/11 até 25/11               │
└─────────────────────────────────────────┘
```

### **Eventos de Agendamentos:**
```
┌─────────────────────────────────────────┐
│ 10/11 14:00 - Lembrete Consulta        │
│ ─────────────────────────────────       │
│ Para: João Silva                        │
│ Mensagem: "Olá João, sua consulta..."  │
│ Status: ● Aguardando envio             │
└─────────────────────────────────────────┘
```

### **Eventos de Feriados:**
```
┌─────────────────────────────────────────┐
│ 20/11 - Dia da Consciência Negra       │
│ ─────────────────────────────────       │
│ ⚠️ Feriado Nacional                    │
│ Campanhas não enviarão hoje            │
└─────────────────────────────────────────┘
```

---

## 🎨 **CORES E LEGENDAS SUGERIDAS**

```
Campanhas:
  🟢 Verde  → Ativa (enviando agora)
  🟡 Amarelo → Pausada (pode retomar)
  🔵 Azul   → Agendada (vai começar)
  ⚪ Cinza  → Concluída (já terminou)
  🔴 Vermelho → Erro/Cancelada

Agendamentos:
  🔵 Azul claro → Pendente (aguardando)
  🟢 Verde → Enviado
  🔴 Vermelho → Falhou

Outros:
  🟣 Roxo → Feriado
  🟠 Laranja → Evento especial
```

---

## 📊 **ARQUITETURA PROPOSTA**

```
┌─────────────────────────────────────────────────────┐
│  FRONTEND - CalendarPage.tsx                        │
├─────────────────────────────────────────────────────┤
│  • React Big Calendar                               │
│  • Busca eventos do backend                         │
│  • Mapeia para formato do calendário                │
│  • Renderiza eventos com cores                      │
│  • Modal de detalhes ao clicar                      │
└─────────────────────────────────────────────────────┘
                        ↓ API
┌─────────────────────────────────────────────────────┐
│  BACKEND - CalendarViewSet                          │
├─────────────────────────────────────────────────────┤
│  GET /api/calendar/events/                          │
│    ?start_date=2024-11-01                          │
│    &end_date=2024-11-30                            │
│    &types=campaigns,scheduled                       │
│                                                     │
│  Retorna JSON com eventos formatados                │
└─────────────────────────────────────────────────────┘
                        ↓ Queries
┌─────────────────────────────────────────────────────┐
│  MODELS                                             │
├─────────────────────────────────────────────────────┤
│  • Campaign (já existe)                             │
│  • ScheduledMessage (a implementar)                 │
│  • Holiday (opcional)                               │
└─────────────────────────────────────────────────────┘
```

---

## 🚀 **ROADMAP SUGERIDO**

### **Sprint 1 (MVP) - 1 dia**
```
✅ Instalar react-big-calendar
✅ Criar CalendarPage básico
✅ Endpoint /calendar/events/
✅ Mapear apenas Campanhas
✅ View de mês
```

**Entrega:**
- Calendário mostrando campanhas existentes
- Click abre detalhes da campanha
- Navegação entre meses

### **Sprint 2 (Agendamentos) - 2-3 dias**
```
✅ Implementar ScheduledMessage model
✅ API CRUD de agendamentos
✅ Celery task para disparar
✅ Modal de criar agendamento
✅ Integrar com calendário
```

**Entrega:**
- Criar agendamento clicando no calendário
- Ver agendamentos junto com campanhas
- Sistema dispara na hora certa

### **Sprint 3 (Melhorias) - 2 dias**
```
✅ Drag-and-drop para reagendar
✅ Filtros por tipo
✅ Mini-calendário
✅ View de semana e dia
✅ Export para .ics
```

**Entrega:**
- Calendário completo e interativo
- Múltiplas views
- Export para Google Calendar

---

## 📈 **EVOLUÇÃO FUTURA**

```
FASE 1 (Agora):
  → Ver campanhas no calendário
  → Agendar envios únicos
  
FASE 2 (Curto prazo):
  → Recorrência (toda segunda-feira)
  → Templates de agendamento
  → Notificações de lembrete
  
FASE 3 (Médio prazo):
  → Integração Google Calendar
  → Time zones por contato
  → Analytics por período
  
FASE 4 (Longo prazo):
  → IA sugere melhores horários
  → A/B testing de horários
  → Predição de engajamento
```

---

## ⚠️ **DESAFIOS TÉCNICOS**

### **1. Time Zones** 🌍
```
Problema: Cliente em SP, contato em NY
Solução fase 1: Usar timezone do tenant
Solução fase 2: Timezone por contato
```

### **2. Performance** ⚡
```
Problema: Calendário busca dados de 30 dias
Solução: 
  - Cache com Redis
  - Índices em date fields
  - Paginação por mês
```

### **3. Conflitos de Horário** ⚠️
```
Problema: 2 agendamentos no mesmo horário
Solução:
  - Validação no backend
  - Alert no frontend
  - Queue com prioridade
```

### **4. Recorrência** 🔄
```
Problema: "Todo dia 15 às 10h" → gerar eventos
Solução:
  - Library rrule (recurrence rules)
  - Gerar eventos on-the-fly
  - Não salvar todos no banco
```

---

## 🎯 **DIFICULDADE GERAL**

```
┌─────────────────────────────────────────────────┐
│  COMPLEXIDADE POR COMPONENTE                    │
├─────────────────────────────────────────────────┤
│  Calendário Visual (lib pronta)      ⭐⭐☆☆☆  │
│  Endpoint de eventos                 ⭐☆☆☆☆  │
│  Mapear campanhas → eventos          ⭐☆☆☆☆  │
│  Implementar ScheduledMessage        ⭐⭐⭐☆☆  │
│  Celery task para disparar           ⭐⭐☆☆☆  │
│  Drag-and-drop (reagendar)           ⭐⭐⭐☆☆  │
│  Recorrência                         ⭐⭐⭐⭐☆  │
│  Integração Google Calendar          ⭐⭐⭐⭐⭐  │
├─────────────────────────────────────────────────┤
│  MVP (Fase 1)                        ⭐⭐☆☆☆  │
│  Completo (Fases 1-3)                ⭐⭐⭐☆☆  │
│  Premium (Fases 1-4)                 ⭐⭐⭐⭐☆  │
└─────────────────────────────────────────────────┘
```

---

## ✅ **RESUMO E RECOMENDAÇÃO**

### **Dificuldade:** 🟢 **BAIXA a MÉDIA** (dependendo do escopo)

### **Recomendação:**
1. ✅ **Começar com MVP** (1-2 dias)
   - Usar `react-big-calendar`
   - Mostrar apenas campanhas existentes
   - View de mês

2. ✅ **Adicionar agendamentos** depois (2-3 dias)
   - Implementar ScheduledMessage
   - Click no calendário cria agendamento
   - Celery dispara na hora

3. ⏳ **Melhorias incrementais** conforme necessidade
   - Drag-and-drop
   - Filtros
   - Recorrência

### **Benefícios:**
- ✅ Visualização clara de todas atividades
- ✅ Planejamento facilitado
- ✅ Evita conflitos de horário
- ✅ Profissionaliza a plataforma
- ✅ Diferencial competitivo

### **ROI:**
- 🎯 **Alto valor** com **baixo esforço** (MVP)
- 📊 **Muito visual** e fácil de vender
- 🚀 **Evolutivo** (começa simples, cresce conforme precisa)

---

**💡 MINHA RECOMENDAÇÃO: IMPLEMENTAR MVP DO CALENDÁRIO! É baixa complexidade com alto valor percebido pelo cliente!**



