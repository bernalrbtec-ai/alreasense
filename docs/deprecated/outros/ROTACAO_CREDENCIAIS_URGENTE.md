# 🔐 ROTAÇÃO DE CREDENCIAIS - GUIA URGENTE

**Data:** 26 de Outubro de 2025  
**Prioridade:** 🔴 **MÁXIMA**  
**Tempo Estimado:** 30-45 minutos

---

## ⚠️ ATENÇÃO

As seguintes credenciais estão **COMPROMETIDAS** e devem ser rotacionadas **IMEDIATAMENTE**:

- ✅ Evolution API Key
- ✅ S3 Access Key / Secret Key
- ✅ Django SECRET_KEY
- ✅ RabbitMQ Credentials

---

## 🚨 ORDEM DE EXECUÇÃO

Execute na ordem exata para minimizar downtime:

1. Gerar novas credenciais
2. Atualizar Railway
3. Restart do backend
4. Validar funcionamento
5. Invalidar credenciais antigas

---

## 1️⃣ EVOLUTION API KEY

### Gerar Nova Chave

```bash
# 1. Acesse o servidor Evolution API
# URL: https://evo.rbtec.com.br/manager

# 2. Vá em: Settings → API Keys → Generate New Key
# Anote a nova chave gerada

# Exemplo de chave: ABC12345-6789-0DEF-GHIJ-KLMN01234567
```

### Atualizar no Railway

```bash
# 3. Atualize no Railway
railway login
railway link  # Selecione o projeto backend

# 4. Set nova chave
railway variables set EVOLUTION_API_KEY="NOVA_CHAVE_AQUI"

# 5. Verifique
railway variables
```

### Restart Backend

```bash
# 6. Force restart
railway up --detach

# OU pelo dashboard do Railway:
# Services → Backend → Settings → Restart
```

### Validar

```bash
# 7. Teste a conexão
curl -X GET https://alreasense-backend-production.up.railway.app/api/health/

# 8. Teste Evolution API
# Login como superuser no frontend
# Vá em: Configurações → Servidor de Instância → Testar Conexão
```

### Invalidar Chave Antiga

```bash
# 9. No painel do Evolution API
# Settings → API Keys → Revoke antiga chave (584B4A4A-0815...)
```

---

## 2️⃣ S3 / MINIO CREDENTIALS

### Gerar Novas Chaves

```bash
# 1. Acesse MinIO Console no Railway
# Services → MinIO → Open Console

# 2. Login com credenciais de admin

# 3. Vá em: Access Keys → Create New Access Key
# Anote:
# - Access Key: XXXXXXXXXXXXXXXX
# - Secret Key: YYYYYYYYYYYYYYYYYYYYYYYYYYYY
```

### Atualizar no Railway

```bash
# 4. Atualize no Railway
railway variables set S3_ACCESS_KEY="NOVA_ACCESS_KEY"
railway variables set S3_SECRET_KEY="NOVA_SECRET_KEY"

# 5. Mantenha o bucket name
railway variables set S3_BUCKET="flow-attachments"
railway variables set S3_ENDPOINT_URL="https://bucket-production-8fb1.up.railway.app"
```

### Restart Backend

```bash
railway up --detach
```

### Validar

```bash
# 6. Teste upload de mídia
# No frontend:
# - Entre no chat
# - Envie uma imagem
# - Verifique se carrega corretamente
```

### Invalidar Chaves Antigas

```bash
# 7. No MinIO Console
# Access Keys → Delete antiga chave (u2gh8ao...)
```

---

## 3️⃣ DJANGO SECRET_KEY

### Gerar Nova Secret Key

```bash
# 1. Gerar nova secret key forte
python -c 'from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())'

# Exemplo de output:
# django-insecure-abc123def456ghi789jkl012mno345pqr678stu901vwx234yz
```

### Atualizar no Railway

```bash
# 2. Atualize no Railway
railway variables set SECRET_KEY="NOVA_SECRET_KEY_AQUI"
```

### ⚠️ ATENÇÃO - TOKENS SERÃO INVALIDADOS

```
Ao rotacionar SECRET_KEY:
- ✅ Todos os JWT tokens serão invalidados
- ✅ Usuários terão que fazer login novamente
- ✅ Sessões ativas serão perdidas
- ✅ Cookies CSRF serão invalidados

Isso é ESPERADO e DESEJADO para segurança!
```

### Restart Backend

```bash
railway up --detach
```

### Validar

```bash
# 3. Teste login
# Frontend → Login com usuário de teste
# Deve funcionar normalmente

# 4. Verifique JWT
# Após login, vá em Application → Local Storage
# Verifique se token foi gerado
```

---

## 4️⃣ RABBITMQ CREDENTIALS

### Gerar Nova Senha

```bash
# 1. No Railway dashboard
# Services → RabbitMQ → Variables

# 2. Gere nova senha forte
python -c 'import secrets; print(secrets.token_urlsafe(32))'

# Exemplo: Xy4Zq-9Kp3Lm8Nv2Rt5Ws7Yu1Ab6Cd
```

### Atualizar no Railway

```bash
# 3. Atualize RABBITMQ_PRIVATE_URL completa
railway variables set RABBITMQ_PRIVATE_URL="amqp://USER:NOVA_SENHA@rabbitmq.railway.internal:5672"

# Mantenha o mesmo formato, apenas mude a senha
```

### Restart Backend

```bash
railway up --detach
```

### Validar

```bash
# 4. Verifique logs do backend
railway logs

# Procure por:
# "✅ RabbitMQ connected"
# "✅ Campaign consumer started"

# 5. Teste envio de campanha
# Frontend → Campanhas → Criar nova campanha de teste
# Verifique se mensagens são enviadas
```

---

## 5️⃣ ATUALIZAR .ENV LOCAL

```bash
# 1. Edite backend/.env
nano backend/.env

# 2. Atualize com as novas credenciais
EVOLUTION_API_KEY=NOVA_CHAVE_AQUI
S3_ACCESS_KEY=NOVA_CHAVE_AQUI
S3_SECRET_KEY=NOVA_CHAVE_AQUI
SECRET_KEY=NOVA_CHAVE_AQUI
RABBITMQ_PRIVATE_URL=amqp://USER:NOVA_SENHA@localhost:5672

# 3. Salve (Ctrl+O, Enter, Ctrl+X)

# 4. Restart local dev server
cd backend
python manage.py runserver
```

---

## 6️⃣ VALIDAÇÃO FINAL

### Checklist Completo

```bash
✅ Evolution API Key rotacionada
✅ S3 credentials rotacionadas
✅ SECRET_KEY rotacionada
✅ RabbitMQ password rotacionado
✅ Railway variables atualizadas
✅ Backend reiniciado
✅ .env local atualizado
✅ Credenciais antigas invalidadas
```

### Testes Funcionais

1. **Login/Autenticação**
   - [ ] Login funciona
   - [ ] JWT token é gerado
   - [ ] Refresh token funciona

2. **WhatsApp/Evolution**
   - [ ] Listar instâncias funciona
   - [ ] Gerar QR code funciona
   - [ ] Verificar status funciona
   - [ ] Enviar mensagem funciona

3. **Mídia/Storage**
   - [ ] Upload de imagem funciona
   - [ ] Visualização de imagem funciona
   - [ ] Download de anexo funciona
   - [ ] Foto de perfil carrega

4. **Campanhas**
   - [ ] Criar campanha funciona
   - [ ] Mensagens são enfileiradas
   - [ ] Mensagens são enviadas
   - [ ] Status é atualizado em tempo real

5. **Chat**
   - [ ] WebSocket conecta
   - [ ] Mensagens chegam em tempo real
   - [ ] Envio de mensagem funciona
   - [ ] Notificações funcionam

---

## 🚫 INVALIDAR CREDENCIAIS ANTIGAS

### Checklist de Invalidação

```bash
# 1. Evolution API
✅ Revogar chave antiga no painel Evolution
✅ Confirmar que antiga chave não funciona mais

# 2. S3/MinIO
✅ Deletar antiga Access Key no MinIO Console
✅ Confirmar que antiga chave não funciona mais

# 3. SECRET_KEY
✅ Antiga chave já está invalidada (trocou no settings)

# 4. RabbitMQ
✅ Antiga senha já está invalidada (trocou a URL)
```

### Teste de Invalidação

```bash
# Teste se credenciais antigas NÃO funcionam mais:

# Evolution API
curl -H "apikey: 584B4A4A-0815-AC86-DC39-C38FC27E8E17" \
  https://evo.rbtec.com.br/instance/fetchInstances
# Esperado: 401 Unauthorized

# S3
aws s3 ls s3://flow-attachments \
  --endpoint-url=https://bucket-production-8fb1.up.railway.app \
  --access-key=u2gh8aomMEdqPFW1JIlTn7VcCUhRCobL \
  --secret-key=zSMwLiOH1fURqSNX8zMtMYKBjrScDQYynCW2TbI2UuXM7Bti
# Esperado: Access Denied
```

---

## 📊 AUDITORIA PÓS-ROTAÇÃO

### Verificar Logs de Acesso

```bash
# 1. Evolution API
# Verificar no painel do Evolution:
# - Últimos acessos
# - IPs que acessaram
# - Ações executadas

# 2. Railway Logs
railway logs --tail 100 | grep -i "error\|unauthorized\|failed"

# 3. S3/MinIO
# No MinIO Console:
# Logs → Access Logs
# Verificar acessos suspeitos
```

### Procurar por Atividade Suspeita

```bash
# Sinais de comprometimento:
⚠️  Instâncias criadas/deletadas não reconhecidas
⚠️  Mensagens enviadas que você não reconhece
⚠️  Arquivos no S3 deletados/modificados
⚠️  Acessos de IPs não reconhecidos
⚠️  Horários de acesso fora do normal
⚠️  Mudanças de configuração não autorizadas
```

### Se Encontrar Atividade Suspeita

```bash
# 1. ISOLAR
# - Colocar backend em modo manutenção
# - Bloquear IPs suspeitos no Railway

# 2. PRESERVAR EVIDÊNCIAS
# - Exportar todos os logs
# - Fazer backup do banco de dados
# - Screenshot de atividades suspeitas

# 3. INVESTIGAR
# - Quando aconteceu?
# - De onde veio o acesso?
# - Quais dados foram acessados?
# - Quais ações foram executadas?

# 4. NOTIFICAR
# - Stakeholders internos
# - Clientes afetados (se necessário)
# - Autoridades (se lei exigir)

# 5. REMEDIAR
# - Rotacionar TODAS as credenciais novamente
# - Implementar 2FA
# - Adicionar IP whitelisting
# - Aumentar logging/monitoring
```

---

## 🔒 PRÓXIMOS PASSOS DE SEGURANÇA

Após rotacionar as credenciais:

### Curto Prazo (Esta Semana)

1. **Limpar Git History**
   ```bash
   # Remover credenciais antigas do Git
   # Veja: ANALISE_SEGURANCA_COMPLETA.md seção "LIMPAR GIT HISTORY"
   ```

2. **Implementar Pre-commit Hooks**
   ```bash
   pip install pre-commit
   pre-commit install
   pre-commit run --all-files
   ```

3. **Code Review**
   - Revisar TODOS os arquivos com credenciais
   - Remover credenciais hardcoded
   - Adicionar testes de segurança

4. **Aplicar Correções Automáticas**
   ```bash
   python CORRECAO_SEGURANCA_URGENTE.py --execute
   ```

### Médio Prazo (Este Mês)

1. **Secrets Management**
   - Avaliar HashiCorp Vault
   - Ou AWS Secrets Manager
   - Ou Railway Secrets (quando disponível)

2. **2FA para Superusers**
   - Implementar autenticação de 2 fatores
   - Obrigatório para contas com privilégios

3. **IP Whitelisting**
   - Limitar acesso a rotas admin por IP
   - Configurar VPN se necessário

4. **Monitoring & Alerting**
   - Configurar alertas de acesso suspeito
   - Monitorar uso de credenciais
   - Dashboard de segurança

### Longo Prazo (Este Trimestre)

1. **Security Audit Profissional**
   - Contratar pen test
   - Implementar correções encontradas

2. **Compliance**
   - ISO 27001
   - SOC 2
   - LGPD

3. **Incident Response Plan**
   - Documentar procedimentos
   - Treinar equipe
   - Testar regularmente

---

## 📞 SUPORTE

Se encontrar problemas durante a rotação:

1. **Erro de conexão Evolution API**
   - Verifique se a nova chave está correta
   - Teste no Postman/curl primeiro
   - Verifique logs do Evolution

2. **Erro de S3**
   - Verifique endpoint URL
   - Teste com AWS CLI
   - Verifique permissões do bucket

3. **Erro JWT/Autenticação**
   - Limpe localStorage do navegador
   - Faça logout e login novamente
   - Verifique SECRET_KEY no Railway

4. **Erro RabbitMQ**
   - Verifique formato da URL
   - Teste conexão com ferramenta RabbitMQ
   - Verifique logs do backend

---

## ✅ CONCLUSÃO

Após executar todos os passos:

✅ Todas as credenciais foram rotacionadas  
✅ Sistema foi validado e está funcionando  
✅ Credenciais antigas foram invalidadas  
✅ Logs foram auditados  
✅ Próximos passos de segurança estão documentados  

**O vazamento de credenciais foi MITIGADO.**

Agora execute as melhorias de longo prazo para prevenir futuros incidentes.

---

**Documento criado:** 26 de Outubro de 2025  
**Última atualização:** 26 de Outubro de 2025  
**Versão:** 1.0

