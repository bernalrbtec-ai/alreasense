# 🧪 GUIA: Teste RabbitMQ Connection no Railway

## 📋 OBJETIVO

Descobrir **exatamente** qual configuração de URL RabbitMQ funciona para o Chat Consumer.

## 🚀 COMO EXECUTAR

### Opção 1: Railway CLI (Recomendado)

```bash
# 1. Fazer upload do script
railway run python test_rabbitmq_connection_debug.py
```

### Opção 2: Adicionar ao repositório e rodar

```bash
# 1. Commit e push
git add test_rabbitmq_connection_debug.py GUIA_TESTE_RABBITMQ_RAILWAY.md
git commit -m "test: adicionar script de debug RabbitMQ"
git push origin main

# 2. No Railway, abrir shell
railway shell

# 3. Executar o script
python test_rabbitmq_connection_debug.py
```

### Opção 3: Copiar e colar no Railway Shell

```bash
# 1. Abrir Railway Shell
railway shell

# 2. Criar arquivo
cat > test_rabbitmq.py << 'EOF'
[COPIAR CONTEÚDO DO test_rabbitmq_connection_debug.py AQUI]
EOF

# 3. Executar
python test_rabbitmq.py
```

---

## 📊 O QUE O SCRIPT FAZ

1. **Lista todas as variáveis de ambiente RabbitMQ**
   - RABBITMQ_URL
   - RABBITMQ_PRIVATE_URL
   - RABBITMQ_DEFAULT_USER
   - RABBITMQ_DEFAULT_PASS

2. **Testa 5 configurações diferentes:**
   - ✅ RABBITMQ_PRIVATE_URL (original)
   - ✅ RABBITMQ_PRIVATE_URL (com URL encoding na senha)
   - ✅ RABBITMQ_URL (proxy público)
   - ✅ Construída manualmente (DEFAULT_USER + DEFAULT_PASS)
   - ✅ Construída manualmente (com encoding)

3. **Mostra qual funcionou:**
   ```
   ✅ SUCESSO: Construída manualmente (DEFAULT_USER + DEFAULT_PASS encoded)
   ```

---

## 📝 EXEMPLO DE OUTPUT

```
================================================================================
🧪 TESTE DE CONEXÃO RABBITMQ - DEBUG COMPLETO
================================================================================

📋 VARIÁVEIS DE AMBIENTE:
--------------------------------------------------------------------------------
RABBITMQ_URL: amqp://75jkOmkcjQmQL...
RABBITMQ_PRIVATE_URL: amqp://75jkOmkcjQmQL...
RABBITMQ_DEFAULT_USER: 75jkOmkcjQmQLFs3
RABBITMQ_DEFAULT_PASS: ~CiJnJU1I-1k~GS.v...

================================================================================
🔍 TESTANDO: RABBITMQ_PRIVATE_URL (original)
================================================================================
Scheme: amqp
Username: 75jkOmkcjQmQLFs3
Password length: 40
Password has ~: True
Password has @: False
Hostname: rabbitmq.railway.internal
Port: 5672
URL: amqp://75jkOmkcjQmQLFs3:******@rabbitmq.railway.internal:5672
⏳ Conectando...
❌ FALHA: ProbableAuthenticationError
   Erro: ACCESS_REFUSED - Login was refused

================================================================================
🔍 TESTANDO: RABBITMQ_PRIVATE_URL (URL encoded password)
================================================================================
Scheme: amqp
Username: 75jkOmkcjQmQLFs3
Password length: 46
Password has ~: False
Password has @: False
Hostname: rabbitmq.railway.internal
Port: 5672
URL: amqp://75jkOmkcjQmQLFs3:******@rabbitmq.railway.internal:5672
⏳ Conectando...
✅ SUCESSO! Conexão estabelecida!

================================================================================
📊 RESUMO DOS TESTES
================================================================================
❌ FALHA: RABBITMQ_PRIVATE_URL (original)
✅ SUCESSO: RABBITMQ_PRIVATE_URL (URL encoded password)
❌ FALHA: RABBITMQ_URL (proxy público)
❌ FALHA: Construída manualmente (DEFAULT_USER + DEFAULT_PASS)
✅ SUCESSO: Construída manualmente (DEFAULT_USER + DEFAULT_PASS encoded)

================================================================================
🎯 RECOMENDAÇÃO
================================================================================
✅ Use a configuração: RABBITMQ_PRIVATE_URL (URL encoded password)
```

---

## 🔧 DEPOIS DO TESTE

### Se mostrar que precisa URL encoding:

Vou ajustar o código para **SEMPRE** aplicar URL encoding na senha, não apenas quando detectar `~`.

### Se mostrar que é outro problema:

Os logs vão revelar qual é a configuração correta a usar.

---

## 📞 PRÓXIMOS PASSOS

1. **Executar o script** (uma das 3 opções acima)
2. **Copiar o output completo**
3. **Enviar para mim**
4. **Vou ajustar o código** baseado no resultado

---

## 💡 DICA RÁPIDA

Se você tem acesso ao Railway CLI:

```bash
railway run python test_rabbitmq_connection_debug.py > rabbitmq_test_result.txt
cat rabbitmq_test_result.txt
```

Isso salva o resultado num arquivo que você pode me enviar.

---

**Aguardo o resultado! 🚀**

