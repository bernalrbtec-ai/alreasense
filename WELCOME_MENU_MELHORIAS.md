# 🎯 MELHORIAS DO MENU AUTOMÁTICO - DOCUMENTAÇÃO

## 📋 RESUMO DAS MELHORIAS

Sistema de menu de boas-vindas agora inclui:
1. **Mensagem de opção inválida** - Cliente recebe feedback quando digita opção errada
2. **Timeout de inatividade** - Sistema fecha conversas abandonadas automaticamente

---

## ✨ FUNCIONALIDADES IMPLEMENTADAS

### 1️⃣ **Mensagem de Opção Inválida**

**Antes:**
```
Cliente: "9"
Sistema: (nada acontece, apenas log de erro no backend)
```

**Depois:**
```
Cliente: "9"
Sistema: "❌ Opção 9 inválida.

Por favor, escolha uma das opções abaixo:

1 - Comercial
2 - Suporte  
3 - Financeiro
4 - Encerrar"
```

**Implementação:**
- `WelcomeMenuService._send_invalid_option_message()` - Envia mensagem de erro
- Reenvia opções do menu automaticamente
- Cancela timeout ativo (cliente respondeu)

---

### 2️⃣ **Timeout de Inatividade**

**Fluxo:**
```
1. Cliente envia mensagem → Sistema envia menu
2. Cliente não responde por 5 minutos → Sistema envia lembrete
3. Cliente não responde por mais 5 minutos (total 10min) → Sistema fecha conversa
```

**Configurações (por tenant):**
- `inactivity_timeout_enabled` - Habilitar/desabilitar timeout (padrão: True)
- `first_reminder_minutes` - Minutos até primeiro lembrete (padrão: 5)
- `auto_close_minutes` - Minutos até fechamento automático (padrão: 10)

**Implementação:**
- `WelcomeMenuTimeout` model - Rastreia timeouts ativos
- `WelcomeMenuService._send_inactivity_reminder()` - Envia lembrete
- Comando `check_welcome_menu_timeouts` - Task periódica

---

## 🗄️ ESTRUTURA DO BANCO DE DADOS

### Novos Campos em `WelcomeMenuConfig`:
```python
inactivity_timeout_enabled = BooleanField(default=True)
first_reminder_minutes = IntegerField(default=5)
auto_close_minutes = IntegerField(default=10)
```

### Nova Tabela `WelcomeMenuTimeout`:
```python
id = UUIDField(primary_key=True)
conversation = OneToOneField(Conversation)
menu_sent_at = DateTimeField()
reminder_sent = BooleanField(default=False)
reminder_sent_at = DateTimeField(null=True)
is_active = BooleanField(default=True)
```

**Índices:**
- `idx_timeout_active_sent` - Para buscar timeouts ativos por data
- `idx_timeout_reminder` - Para buscar timeouts que precisam de lembrete

---

## 🚀 IMPLANTAÇÃO

### 1. Aplicar Migration
```bash
python manage.py migrate chat 0012_welcome_menu_timeout_features
```

### 2. Iniciar Task Periódica
```bash
# Modo produção (loop contínuo)
python manage.py check_welcome_menu_timeouts

# Modo teste (executa uma vez)
python manage.py check_welcome_menu_timeouts --once

# Intervalo customizado (padrão: 60 segundos)
python manage.py check_welcome_menu_timeouts --interval 30
```

### 3. Configurar Supervisor (Produção)
```ini
[program:welcome_menu_timeouts]
command=python manage.py check_welcome_menu_timeouts
directory=/app
user=www-data
autostart=true
autorestart=true
redirect_stderr=true
stdout_logfile=/var/log/welcome_menu_timeouts.log
environment=DJANGO_SETTINGS_MODULE="alrea_sense.settings"
```

### 4. Ou Railway (Procfile)
```
release: python manage.py migrate
web: gunicorn alrea_sense.wsgi
worker: python manage.py start_chat_consumer
timeout_checker: python manage.py check_welcome_menu_timeouts
```

---

## 📊 FLUXO COMPLETO

```
┌─────────────────────────────────────────────────────────┐
│  CLIENTE ENVIA PRIMEIRA MENSAGEM                         │
└─────────────────┬───────────────────────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────────────────────┐
│  Sistema envia menu de boas-vindas                       │
│  + Cria WelcomeMenuTimeout (menu_sent_at = now)         │
└─────────────────┬───────────────────────────────────────┘
                  │
                  ├─────────────────────────────────────────┐
                  │                                         │
                  ▼                                         ▼
┌────────────────────────────────┐    ┌──────────────────────────────┐
│  CLIENTE RESPONDE              │    │  CLIENTE NÃO RESPONDE        │
└────────┬───────────────────────┘    └────────┬─────────────────────┘
         │                                      │
         ├──────────────┬──────────────┐       │
         ▼              ▼              ▼       ▼
   ┌─────────┐   ┌──────────┐   ┌──────────┐  ┌──────────────────┐
   │ Válido  │   │ Inválido │   │  Fechar  │  │  Após 5 minutos  │
   └────┬────┘   └────┬─────┘   └────┬─────┘  └────────┬─────────┘
        │             │              │                   │
        ▼             ▼              ▼                   ▼
   Transfere    Reenvia Menu   Fecha Conv.    Envia Lembrete
   Departamento + Msg Erro    + Marca Lida   "Você está aí?"
   + Cancela    + Cancela     + Cancela       + reminder_sent=True
   Timeout      Timeout        Timeout              │
                                                     │
                                                     ▼
                                         ┌────────────────────────┐
                                         │ CLIENTE NÃO RESPONDE   │
                                         │ MAIS 5 MIN (total 10)  │
                                         └────────┬───────────────┘
                                                  │
                                                  ▼
                                         Fecha Conversa Auto.
                                         + Marca Todas Lidas
                                         + is_active=False
```

---

## 🔧 CONFIGURAÇÃO POR TENANT

Admins podem configurar via Django Admin:

```python
# Exemplo de configuração
config = WelcomeMenuConfig.objects.get(tenant=my_tenant)

# Habilitar timeout
config.inactivity_timeout_enabled = True
config.first_reminder_minutes = 3  # Lembrete após 3 min
config.auto_close_minutes = 8      # Fechar após 8 min
config.save()

# Desabilitar timeout
config.inactivity_timeout_enabled = False
config.save()
```

---

## 📝 LOGS E MONITORAMENTO

### Logs de Timeout:
```python
⏰ [WELCOME MENU] Timeout criado para conversa <id>
✅ [WELCOME MENU] Timeout cancelado - cliente respondeu
⏰ [TIMEOUT] Lembrete enviado para conversa <id> (5.2 min)
🔒 [TIMEOUT] Conversa <id> fechada por inatividade (10.1 min)
```

### Logs de Opção Inválida:
```python
⚠️ [WELCOME MENU] Número inválido escolhido: 9
✅ [WELCOME MENU] Mensagem de opção inválida enfileirada
```

### Comando check_welcome_menu_timeouts:
```
🔄 [ITERAÇÃO 1] 2025-12-16 10:00:00
📊 Total de timeouts ativos: 3
   ⏳ João Silva: 2.3 min decorridos (lembrete em 2.7 min, fechamento em 7.7 min)
   ⏰ Enviando lembrete: Maria Santos (5.1 min)
   🔒 Fechando conversa: Pedro Costa (10.2 min)

✅ Verificação concluída:
   📊 Processados: 3
   ⏰ Lembretes enviados: 1
   🔒 Conversas fechadas: 1
```

---

## ✅ TESTES

### Teste Manual:

1. **Opção Inválida:**
```bash
# 1. Enviar mensagem para instância
# 2. Receber menu: "1 - Comercial, 2 - Suporte, 3 - Encerrar"
# 3. Responder "9"
# 4. Verificar: deve receber mensagem de erro + menu novamente
```

2. **Timeout - Lembrete:**
```bash
# 1. Enviar mensagem para instância
# 2. Receber menu
# 3. Aguardar 5 minutos
# 4. Verificar: deve receber lembrete "Você está aí?"
```

3. **Timeout - Fechamento:**
```bash
# 1. Enviar mensagem para instância
# 2. Receber menu
# 3. Aguardar 10 minutos
# 4. Verificar: conversa deve ser fechada automaticamente
```

### Teste com Comando:
```bash
# Executar uma vez (não aguarda)
python manage.py check_welcome_menu_timeouts --once

# Ver logs detalhados
python manage.py check_welcome_menu_timeouts --once --verbosity 2
```

---

## 🎓 LIÇÕES APRENDIDAS

1. **Cancelamento de Timeout:** Sempre cancelar timeout quando cliente responde
2. **Timezone:** Usar `timezone.now()` (Django) para consistência
3. **Transações:** Usar `transaction.on_commit()` para enfileirar após commit
4. **Índices:** Adicionar índices em `is_active` e `menu_sent_at` para performance

---

## 📚 ARQUIVOS MODIFICADOS

1. **Migration:** `0012_welcome_menu_timeout_features.py`
2. **Models:** `models_welcome_menu.py` (campos + WelcomeMenuTimeout)
3. **Service:** `welcome_menu_service.py` (novos métodos)
4. **Command:** `check_welcome_menu_timeouts.py` (task periódica)

---

## 🚦 STATUS

✅ **Implementado:** Todas as funcionalidades
✅ **Testado:** Manualmente
⏳ **Produção:** Aguardando deploy

**Data:** 16/12/2025
**Versão:** v2.0 - Menu Automático com Timeout

