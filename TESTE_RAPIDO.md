# ⚡ TESTE RÁPIDO - ALREA CAMPAIGNS

**Bom dia, Paulo!** ☀️

## 🎯 Sistema 100% Rodando

```
✅ Backend:      http://localhost:8000
✅ Frontend:     http://localhost:5173
✅ Celery Beat:  Scheduler ativo (a cada 10s)
✅ PostgreSQL:   Healthy
✅ Redis:        Healthy
```

**Login:** `admin@alrea.com` / `admin123`

---

## 📱 ENVIAR MENSAGEM DE TESTE PARA +5517991253112

### Opção 1: Teste Rápido (Se já tem instância conectada)

```bash
docker-compose -f docker-compose.local.yml exec backend python manage.py test_campaign_send
```

**Se você já tiver uma instância WhatsApp conectada, receberá a mensagem em 10 segundos!**

---

### Opção 2: Configurar Tudo do Zero (2 minutos)

#### Passo 1: Verificar instâncias
```bash
docker-compose -f docker-compose.local.yml exec backend python check_instances.py
```

#### Passo 2: Se não tiver nenhuma conectada:

1. **Acesse:** http://localhost:5173
2. **Login:** admin@alrea.com / admin123
3. **Admin** → **Servidor de Instância**
   - URL: `https://evo.rbtec.com.br`
   - API Key: Sua chave master
4. **Admin** → **Notificações** → **Instâncias WhatsApp**
   - Clique "Nova Instância WhatsApp"
   - Nome: `Teste`
   - Marcar como padrão: ✅
   - Salvar
5. **Gerar QR Code** e conectar WhatsApp
6. **Rodar teste:**
   ```bash
   docker-compose -f docker-compose.local.yml exec backend python manage.py test_campaign_send
   ```

---

## 🔍 Monitorar em Tempo Real

### Ver scheduler processando:
```bash
docker-compose -f docker-compose.local.yml logs celery-beat --follow
```

### Ver envio da mensagem:
```bash
docker-compose -f docker-compose.local.yml logs celery --follow
```

### Ver logs do backend:
```bash
docker-compose -f docker-compose.local.yml logs backend --follow
```

---

## ✅ O Que Está Funcionando:

- ✅ **Campanhas**: Criar, iniciar, pausar, retomar, cancelar
- ✅ **Contatos**: CRUD completo + grupos
- ✅ **Mensagens**: Até 5 por campanha com rotação automática
- ✅ **Agendamento**: Horários, feriados, fins de semana
- ✅ **Variáveis**: `{{nome}}`, `{{saudacao}}`, `{{quem_indicou}}`, `{{dia_semana}}`
- ✅ **Celery**: Scheduler + Worker rodando
- ✅ **Anti-spam**: Lock Redis por telefone
- ✅ **Logs**: Auditoria completa

---

## 📊 Testar via API (Sem UI)

```bash
# 1. Login
curl -X POST http://localhost:8000/api/auth/login/ \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@alrea.com","password":"admin123"}'

# Copie o token da resposta

# 2. Listar campanhas
curl http://localhost:8000/api/campaigns/campaigns/ \
  -H "Authorization: Bearer SEU_TOKEN_AQUI"

# 3. Listar contatos
curl http://localhost:8000/api/contacts/contacts/ \
  -H "Authorization: Bearer SEU_TOKEN_AQUI"

# 4. Ver feriados
curl http://localhost:8000/api/campaigns/holidays/ \
  -H "Authorization: Bearer SEU_TOKEN_AQUI"
```

---

## 🎯 Exemplo de Campanha Manual (via API)

```bash
# Criar contato
curl -X POST http://localhost:8000/api/contacts/contacts/ \
  -H "Authorization: Bearer SEU_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Paulo Teste",
    "phone": "+5517991253112",
    "quem_indicou": "Sistema ALREA"
  }'

# Criar campanha (precisa de instance_id conectada)
curl -X POST http://localhost:8000/api/campaigns/campaigns/ \
  -H "Authorization: Bearer SEU_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Minha Primeira Campanha",
    "instance_id": "UUID_DA_INSTANCIA_CONECTADA",
    "contact_ids": ["UUID_DO_CONTATO"],
    "message_texts": [
      "{{saudacao}}, {{nome}}! Bem-vindo à ALREA! 🎉"
    ],
    "schedule_type": "immediate"
  }'

# Iniciar campanha
curl -X POST http://localhost:8000/api/campaigns/campaigns/UUID_CAMPANHA/start/ \
  -H "Authorization: Bearer SEU_TOKEN"

# Em 10 segundos a mensagem é enviada! 📱
```

---

## ❓ FAQ

**Q: Já posso enviar a mensagem para mim?**  
A: SIM! Basta ter uma instância WhatsApp conectada e rodar:
```bash
docker-compose -f docker-compose.local.yml exec backend python manage.py test_campaign_send
```

**Q: Como verifico se tenho instância conectada?**  
A: 
```bash
docker-compose -f docker-compose.local.yml exec backend python check_instances.py
```

**Q: O scheduler está rodando?**  
A: Sim! Veja os logs:
```bash
docker-compose -f docker-compose.local.yml logs celery-beat --tail=20
```
Deve aparecer a cada 10s: `Scheduler: Sending due task campaign-scheduler`

**Q: Posso testar sem conectar WhatsApp?**  
A: Não, precisa de uma instância conectada para enviar mensagens reais.

---

## 🚀 PRONTO PARA TESTAR!

**Escolha uma opção acima e teste o sistema!** 🎉

