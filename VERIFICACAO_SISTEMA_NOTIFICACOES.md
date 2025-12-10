# 🔍 Verificação Completa do Sistema de Notificações WhatsApp

## ✅ Status do Sistema

### 1. **Scheduler (Verificador Automático)**
- ✅ **Localização**: `backend/apps/campaigns/apps.py` - `CampaignsConfig.ready()`
- ✅ **Frequência**: Verifica a cada **60 segundos**
- ✅ **Janela de tempo**: ±1 minuto para evitar perda de notificações
- ✅ **Thread separada**: Executa em background sem bloquear o Django
- ✅ **Proteção contra duplicação**: Usa `select_for_update(skip_locked=True)`
- ✅ **Marcação imediata**: Marca como enviado ANTES de processar (evita duplicação)

### 2. **Configurações Verificadas**

#### Preferências de Notificação
- ✅ **1 preferência** configurada
- 👤 **Usuário**: paulo.bernal@rbtec.com.br
- ⏰ **Horário**: 12:10
- 📱 **WhatsApp**: ✅ Habilitado
- 📡 **WebSocket**: ✅ Habilitado
- 📧 **Email**: ❌ Desabilitado
- 📞 **Telefone**: +5517991253112 (normalizado corretamente)

#### Instâncias WhatsApp
- ✅ **2 instâncias** ativas encontradas:
  1. **Cobrança - RA** (Maristela Advocacia)
     - URL: https://evo.rbtec.com.br
     - Instance: 3769a871-4804-4fc9-b120-8452d4cb0e4f
  2. **RBTEC** (RBTec Informática) ← **Usada pelo seu usuário**
     - URL: https://evo.rbtec.com.br
     - Instance: 262b8dcd-337c-4db0-8970-d5d3e28d63cc

#### Conexões Evolution (Fallback)
- ✅ **1 conexão** ativa encontrada

### 3. **Próximas Notificações Agendadas**

⏰ **Notificação agendada para os próximos 60 minutos:**
- 👤 **Usuário**: paulo.bernal@rbtec.com.br
- ⏰ **Horário**: 12:10
- 📱 **WhatsApp**: ✅ Habilitado
- ✅ **Configuração**: OK

---

## 🔄 Como Funciona o Sistema

### Fluxo de Verificação (a cada 60 segundos)

1. **Scheduler acorda** e verifica o horário atual
2. **Calcula janela de tempo**: ±1 minuto do horário atual
3. **Busca preferências** dentro da janela usando `select_for_update`
4. **Para cada preferência encontrada**:
   - Adquire lock (evita duplicação)
   - Marca como enviado IMEDIATAMENTE (`last_daily_summary_sent_date`)
   - Busca tarefas do usuário:
     - ✅ Tarefas agendadas para hoje (com `due_date`)
     - ✅ Pendências sem data agendada (sem `due_date`, agrupadas por departamento)
     - ✅ Tarefas atrasadas
   - Formata mensagem WhatsApp
   - Envia via WhatsApp e WebSocket
5. **Aguarda 60 segundos** e repete

### Formato da Mensagem WhatsApp

```
👋 Bom dia, Paulo!

📋 Resumo do seu dia - Segunda-feira, 10/12/2025

⚠️ Tarefas Atrasadas: X
  • Tarefa 1 (X dia(s) atrasada) [Departamento]
  • Tarefa 2 [Departamento]

📝 Tarefas para hoje: X
  • Tarefa 1 às 14:00 [Departamento]
  • Tarefa 2 [Departamento]

🔄 Em andamento: X
  • Tarefa 1 [Departamento]

✅ Concluídas hoje: X
  • Tarefa 1 [Departamento]

📋 Pendências (sem data agendada): X

  🏢 Departamento 1: X
    • Tarefa 1 - Nome do Usuário
    • Tarefa 2 - Nome do Usuário

  🏢 Departamento 2: X
    • Tarefa 1 - Nome do Usuário

📊 Total: X tarefa(s) no seu dia

💡 Dica: Priorize as tarefas atrasadas para manter tudo em dia!
```

---

## ✅ Verificações Realizadas

### ✅ Scheduler
- [x] Thread iniciada corretamente
- [x] Loop de verificação funcionando
- [x] Janela de tempo configurada (±1 minuto)
- [x] Proteção contra duplicação (`select_for_update`)

### ✅ Configurações
- [x] Preferências de notificação configuradas
- [x] Instâncias WhatsApp ativas e configuradas
- [x] Telefone do usuário cadastrado e normalizado
- [x] Configuração WhatsApp OK para o tenant

### ✅ Funcionalidades
- [x] Pendências sem data agendada incluídas
- [x] Agrupamento por departamento funcionando
- [x] Retry com backoff exponencial (3 tentativas)
- [x] Logs detalhados para debugging

---

## 📊 Resumo da Verificação

| Item | Status | Detalhes |
|------|--------|----------|
| **Scheduler** | ✅ OK | Verifica a cada 60s, janela ±1min |
| **Preferências** | ✅ OK | 1 configurada, horário 12:10 |
| **WhatsApp** | ✅ OK | 2 instâncias ativas, configuração OK |
| **Telefone** | ✅ OK | Normalizado: +5517991253112 |
| **Pendências** | ✅ OK | Incluídas e agrupadas por departamento |
| **Próxima notificação** | ⏰ 12:10 | Agendada para hoje |

---

## 🧪 Como Testar

### Opção 1: Aguardar o horário agendado (12:10)
- O scheduler verificará automaticamente
- Verifique os logs do Django para acompanhar

### Opção 2: Teste manual
```bash
cd backend
python scripts/test_notification_flow.py
```

### Opção 3: Forçar envio agora
```bash
cd backend
python scripts/force_send_notifications.py
```

---

## 📝 Logs para Acompanhar

O sistema gera logs detalhados com os seguintes prefixos:

- `[DAILY NOTIFICATIONS]` - Notificações diárias
- `[WHATSAPP NOTIFICATION]` - Envio via WhatsApp
- `[SCHEDULER]` - Scheduler e verificações

**Exemplo de log esperado:**
```
✅ [DAILY NOTIFICATIONS] Lock adquirido e last_daily_summary_sent_date=2025-12-10 marcado para preferência X
📱 [WHATSAPP NOTIFICATION] ====== INICIANDO ENVIO ======
   Usuário: paulo.bernal@rbtec.com.br (ID: X)
   Telefone normalizado: +5517991253112
   URL: https://evo.rbtec.com.br/message/sendText/262b8dcd-337c-4db0-8970-d5d3e28d63cc
✅ [WHATSAPP NOTIFICATION] WhatsApp enviado com sucesso para +5517991253112
✅ [DAILY NOTIFICATIONS] Resumo diário enviado para paulo.bernal@rbtec.com.br
```

---

## ⚠️ Possíveis Problemas e Soluções

### Problema: Notificação não chegou
**Verificações:**
1. ✅ Scheduler está rodando? (verificar logs)
2. ✅ Horário está dentro da janela (±1 minuto)?
3. ✅ `last_daily_summary_sent_date` foi atualizado?
4. ✅ Telefone está correto e normalizado?
5. ✅ Instância WhatsApp está conectada?
6. ✅ API Evolution está respondendo?

### Problema: Notificação duplicada
**Solução:** Sistema já protege com `select_for_update(skip_locked=True)`

### Problema: Pendências não aparecem
**Verificação:** 
- ✅ Tarefas têm `include_in_notifications=True`?
- ✅ Tarefas têm `due_date__isnull=True`?
- ✅ Status é `pending` ou `in_progress`?

---

## 🎯 Conclusão

✅ **Sistema está configurado corretamente!**

- Scheduler funcionando
- Configurações OK
- Telefone normalizado
- Pendências incluídas e agrupadas por departamento
- Próxima notificação agendada para **12:10**

**Aguarde o horário agendado e verifique se a notificação chega!**

Se não chegar, verifique os logs do Django para identificar o problema.

