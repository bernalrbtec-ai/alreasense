# 🔄 Como Reiniciar Workers no Railway

## ⚠️ PROBLEMA ATUAL

O deploy do backend foi concluído, MAS os workers que processam tasks RabbitMQ ainda estão rodando o código ANTIGO.

**Sintoma:**
- Frontend funciona ✅
- Upload S3 funciona ✅
- Confirm upload funciona ✅
- WebSocket funciona ✅  
- Evolution API retorna 400 ❌ (workers com código antigo)

## ✅ SOLUÇÃO 1: Restart Manual via Railway Dashboard

1. Acesse o Railway Dashboard
2. Vá no serviço **backend**
3. Clique em **"Settings"**
4. Clique em **"Restart"** ou **"Redeploy"**
5. Aguarde 2-3 minutos para o deploy completar

**OU** force um novo deploy:

## ✅ SOLUÇÃO 2: Force Deploy via Git (Recomendado)

```bash
# Fazer um commit vazio para forçar deploy
git commit --allow-empty -m "chore: force redeploy workers"
git push origin main
```

Isso força o Railway a:
1. Fazer novo build
2. Reiniciar TODOS os processos (web + workers)
3. Carregar o código NOVO

## ✅ SOLUÇÃO 3: Verificar se Worker está ativo

No Railway:
1. Vá em **"Deployments"**
2. Verifique se o último deploy está **"SUCCESS"**
3. Verifique se há **processos ativos**:
   - ✅ web (Gunicorn)
   - ✅ worker (Python consumer - ESTE é o problema!)

Se o worker não está listado, é porque não há um Procfile ou comando configurado para ele.

## 📋 VERIFICAR PROCFILE

O arquivo `Procfile` deve ter:

```
web: gunicorn alrea_sense.wsgi --bind 0.0.0.0:$PORT --workers 4 --timeout 120
worker: python backend/manage.py start_chat_consumers
release: python backend/manage.py migrate --noinput
```

Se não tem o `worker:`, o Railway NÃO está rodando o consumer RabbitMQ!

## 🔍 DIAGNÓSTICO

### Verificar se o código novo está no Railway:

```bash
# Ver último commit deployado
git log --oneline -1
```

Deve mostrar: `08203a1 docs: adicionar analise completa do sistema de anexos`

Se o Railway não mostra este commit, o deploy não completou.

### Verificar logs do worker:

No Railway Dashboard:
1. Vá em **"Deployments"**
2. Clique no último deploy
3. Veja os logs do **worker** (não web)
4. Procure por erros ou se ele está processando tasks

## ⚡ SOLUÇÃO RÁPIDA (Execute Agora)

```bash
# 1. Force novo deploy
git commit --allow-empty -m "chore: force redeploy para atualizar workers RabbitMQ"
git push origin main

# 2. Aguarde 2-3 minutos

# 3. Teste novamente o upload de anexo
```

## 🎯 CONFIRMAR QUE FUNCIONOU

Após o redeploy, teste:
1. ✅ Envie um anexo no Flow Chat
2. ✅ Verifique os logs do Railway
3. ✅ O payload deve mostrar: `'mediaType': 'document'` (camelCase)
4. ✅ Evolution API deve retornar **200 OK** (não 400)
5. ✅ Arquivo deve chegar no WhatsApp do destinatário

## 🐛 SE AINDA NÃO FUNCIONAR

1. Verifique se o Procfile existe e tem a linha `worker:`
2. Verifique se o Railway tem o processo worker configurado
3. Verifique se há erros nos logs do worker
4. Pode ser necessário configurar o worker como um serviço separado no Railway

## 📊 ESTRUTURA CORRETA NO RAILWAY

Deve ter:
- ✅ **Service: backend** (web + worker)
- ✅ **Service: frontend** (static files)
- ✅ **Service: postgres** (database)
- ✅ **Service: redis** (cache + channels)
- ✅ **Service: rabbitmq** (queue)
- ✅ **Service: minio** (S3 storage)

Se o worker não está rodando, as tasks RabbitMQ ficam na fila mas não são processadas!

