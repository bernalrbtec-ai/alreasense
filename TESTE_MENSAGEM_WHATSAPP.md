# 📱 COMO RECEBER A MENSAGEM DE TESTE

## ⚡ Quick Start - 3 Passos

### 1️⃣ Configurar Servidor Evolution (1 minuto)

1. Acesse: **http://localhost:5173**
2. Login: `admin@alreasense.com` / `admin123`
3. Vá em: **Admin** (canto superior direito) → **Servidor de Instância**
4. Preencha:
   - URL Base: `https://evo.rbtec.com.br` (ou sua URL do Evolution)
   - API Key: Sua API Key master do Evolution
5. Clique **Salvar**

---

### 2️⃣ Criar e Conectar Instância WhatsApp (2 minutos)

1. Ainda no Admin, vá em: **Notificações**
2. Aba: **Instâncias WhatsApp**
3. Clique: **Nova Instância WhatsApp**
4. Preencha:
   - Nome: `Teste Campaigns`
   - Marcar como padrão: ✅
5. Clique **Salvar**
6. Clique no botão **Gerar QR Code**
7. Escaneie com seu WhatsApp
8. Aguarde conectar (status: Conectado ✅)

---

### 3️⃣ Rodar Teste e Receber Mensagem! (10 segundos)

Abra um terminal e rode:

```bash
docker-compose -f docker-compose.local.yml exec backend python manage.py test_campaign_send
```

**Saída esperada:**
```
🚀 Criando campanha de teste...
✓ Usando instância: Teste Campaigns
✓ Contato: Paulo (Teste ALREA)
✓ Campanha criada: 🎉 TESTE ALREA Campaigns - Sistema Funcionando!
✓ Mensagem criada
✓ Contato adicionado à campanha
✅ Campanha INICIADA!

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🎉 CAMPANHA DE TESTE CRIADA E INICIADA!
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

📱 Destinatário: Paulo (+5517991253112)
⚡ Status: ACTIVE
🚀 Envio: Será processado nos próximos 10 segundos

O Celery Beat scheduler irá processar automaticamente.
Você receberá a mensagem em breve!

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

**Em 10 segundos você receberá no WhatsApp:**

```
Bom dia, Paulo (Teste ALREA)! 🎉

✅ ALREA Campaigns está FUNCIONANDO!

O sistema de campanhas foi implementado com sucesso e está operacional!

*Funcionalidades Implementadas:*
📤 Sistema completo de campanhas
👥 Gestão de contatos
⏰ Agendamento inteligente (horários/feriados)
🔄 Rotação automática de mensagens
📊 Métricas e logs detalhados
🤖 Celery Beat para processamento automático

Esta é uma mensagem de teste enviada automaticamente pelo sistema.

Desenvolvido com ❤️ pela equipe ALREA
```

---

## 🔍 Monitorar Envio em Tempo Real

### Ver logs do Celery Beat (Scheduler):
```bash
docker-compose -f docker-compose.local.yml logs celery-beat --follow
```

Você verá:
```
[19:58:53] Scheduler: Sending due task campaign-scheduler
[19:58:53] 📊 1 campanha pronta para processar
[19:58:53] 📤 Enfileirado: Teste Campaigns → Paulo (Teste ALREA)
```

### Ver logs do Celery Worker (Dispatcher):
```bash
docker-compose -f docker-compose.local.yml logs celery --follow
```

Você verá:
```
[19:58:54] 📱 Enviando para Paulo (Teste ALREA) (+5517991253112)
[19:58:55] ✅ Enviado com sucesso para Paulo (Teste ALREA)
```

---

## ❓ Troubleshooting

### Se não receber a mensagem:

1. **Verifique se a instância está conectada:**
   ```bash
   docker-compose -f docker-compose.local.yml exec backend python check_instances.py
   ```
   Deve mostrar: `✓ Teste Campaigns (Conectado)`

2. **Verifique os logs da campanha:**
   - Acesse a API: `GET http://localhost:8000/api/campaigns/campaigns/`
   - Pegue o ID da campanha
   - Veja os logs: `GET http://localhost:8000/api/campaigns/campaigns/{id}/logs/`

3. **Verifique o status do contato:**
   - `GET http://localhost:8000/api/campaigns/campaigns/{id}/contacts/`
   - Status esperado: `sent` ou `delivered`

---

## ✅ Sistema Está Pronto!

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
STATUS DO SISTEMA:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

✅ Backend Django:     RODANDO (localhost:8000)
✅ Frontend React:     RODANDO (localhost:5173)
✅ PostgreSQL:         HEALTHY
✅ Redis:              HEALTHY
✅ Celery Beat:        ATIVO (scheduler a cada 10s)
✅ Celery Worker:      ATIVO (processando filas)
✅ Migrations:         100% Aplicadas
✅ Seeds:              100% Executados
✅ Admin:              Acessível

⏳ Aguardando:         Configuração de instância WhatsApp

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

**Basta configurar a instância WhatsApp e rodar o teste!** 🚀


