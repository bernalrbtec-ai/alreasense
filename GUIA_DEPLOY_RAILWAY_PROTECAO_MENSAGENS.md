# 🚀 Guia de Deploy Railway - Proteção de Mensagens e Zero Downtime

## 📋 Índice

1. [Visão Geral](#visão-geral)
2. [Arquitetura Atual](#arquitetura-atual)
3. [Problemas Identificados](#problemas-identificados)
4. [Estratégias de Proteção](#estratégias-de-proteção)
5. [Implementação](#implementação)
6. [Railway Preview Deployments](#railway-preview-deployments)
7. [Checklist de Deploy](#checklist-de-deploy)
8. [Troubleshooting](#troubleshooting)

---

## 🎯 Visão Geral

Este guia documenta a estratégia para proteger mensagens durante deploy e garantir zero downtime no Railway, usando preview deployments para testes antes de produção.

### Objetivos

- ✅ **Zero perda de mensagens** durante deploy
- ✅ **Reconexão automática** de WebSocket após deploy
- ✅ **Deploy sem downtime** visível para usuários
- ✅ **Testes em staging** antes de produção
- ✅ **Graceful shutdown** de todos os serviços

### Status Atual

| Componente | Status | Observações |
|------------|--------|-------------|
| Persistência de Mensagens | ✅ **Protegido** | Mensagens são salvas no PostgreSQL antes de processar |
| WebSocket Reconexão | ✅ **Funcional** | Frontend reconecta automaticamente |
| Graceful Shutdown | ⚠️ **Pendente** | Implementar signal handlers |
| Health Checks | ⚠️ **Pendente** | Criar endpoints `/health` e `/health/ready` |
| Railway Preview | ⚠️ **Pendente** | Configurar preview deployments |

---

## 🏗️ Arquitetura Atual

### Fluxo de Mensagens

```
Evolution API Webhook
    ↓
handle_message_upsert() [@transaction.atomic]
    ↓
PostgreSQL (Mensagem SALVA)
    ↓
RabbitMQ Queue (process_incoming_media)
    ↓
Worker Processa Mídia
    ↓
S3 Storage
    ↓
WebSocket Broadcast (notifica frontend)
```

### Componentes Críticos

1. **Backend Django + Channels**
   - Daphne (ASGI server) para HTTP + WebSocket
   - Workers RabbitMQ para processamento assíncrono
   - PostgreSQL para persistência

2. **Frontend React**
   - WebSocket Manager (singleton)
   - Reconexão automática implementada
   - Fila de mensagens pendentes (parcial)

3. **Railway**
   - Deploy automático via Git
   - Health checks (configurável)
   - Graceful shutdown (parcial)

---

## ⚠️ Problemas Identificados

### 1. Deploy Abrupto

**Problema:**
- Railway mata processos sem aviso durante deploy
- Conexões WebSocket são desconectadas abruptamente
- Workers RabbitMQ podem perder tasks em processamento

**Impacto:**
- Usuários perdem notificações em tempo real
- Reconexão pode demorar alguns segundos
- Tasks podem precisar ser reprocessadas

**Solução:**
- Implementar graceful shutdown
- Signal handlers (SIGTERM/SIGINT)
- Timeout de 30-60s para finalizar

### 2. Falta de Health Checks

**Problema:**
- Railway não sabe se serviço está pronto antes de trocar tráfego
- Pode trocar para instância quebrada

**Impacto:**
- Deploy pode quebrar produção
- Usuários podem ver erros temporários

**Solução:**
- Criar endpoints `/health` e `/health/ready`
- Configurar no Railway
- Verificar banco, Redis, RabbitMQ, workers

### 3. Sem Ambiente de Staging

**Problema:**
- Testes diretos em produção
- Risco de quebrar produção

**Impacto:**
- Bugs em produção
- Rollback necessário
- Experiência ruim para usuários

**Solução:**
- Railway Preview Deployments
- Testar PRs antes de merge
- Deploy apenas após aprovação

---

## 🛡️ Estratégias de Proteção

### 1. Graceful Shutdown

#### Objetivo
Permitir que serviços finalizem de forma controlada antes do deploy.

#### Como Funciona

```
Railway envia SIGTERM
    ↓
Backend recebe signal
    ↓
Para de aceitar novas conexões WebSocket
    ↓
Aguarda conexões existentes fecharem (30s timeout)
    ↓
Finaliza workers RabbitMQ com segurança
    ↓
Encerra processo
```

#### Implementação Necessária

**Backend (ASGI):**
- Signal handler para SIGTERM/SIGINT
- Fechar conexões WebSocket gradualmente
- Aguardar tasks RabbitMQ finalizarem

**Workers RabbitMQ:**
- Finalizar task atual antes de encerrar
- Não aceitar novas tasks durante shutdown
- Timeout de 30s para finalizar

**Frontend:**
- Detectar fechamento de WebSocket
- Reconectar imediatamente
- Carregar mensagens pendentes ao reconectar

### 2. Health Checks

#### Objetivo
Garantir que Railway só troque tráfego quando serviço estiver pronto.

#### Endpoints Necessários

**`/health`** - Básico
```json
{
  "status": "ok",
  "database": "connected",
  "timestamp": "2025-01-20T10:00:00Z"
}
```

**`/health/ready`** - Completo
```json
{
  "status": "ready",
  "database": "connected",
  "redis": "connected",
  "rabbitmq": "connected",
  "workers": "active",
  "timestamp": "2025-01-20T10:00:00Z"
}
```

#### Configuração Railway

```json
{
  "deploy": {
    "healthcheckPath": "/health/ready",
    "healthcheckTimeout": 5,
    "healthcheckInterval": 10
  }
}
```

### 3. Railway Preview Deployments

#### Objetivo
Testar mudanças em ambiente isolado antes de produção.

#### Como Funciona

```
Criar Pull Request
    ↓
Railway detecta PR automaticamente
    ↓
Cria preview deployment (URL única)
    ↓
Testa backend + frontend juntos
    ↓
Aprovação → Merge para main
    ↓
Deploy em produção
```

#### Configuração

1. **Railway Dashboard:**
   - Settings → Preview Deployments → Enable
   - Configurar variáveis de ambiente (opcional)

2. **Workflow Recomendado:**
   ```
   feature/novo-recurso
       ↓
   Criar PR → Railway cria preview
       ↓
   Testar preview → Aprovar
       ↓
   Merge → Deploy produção
   ```

### 4. Proteção de Mensagens

#### Situação Atual ✅

**Mensagens NÃO são perdidas:**
- Webhook salva no PostgreSQL antes de processar
- `@transaction.atomic` garante persistência
- Mesmo durante deploy, mensagem está salva

**O que pode acontecer:**
- WebSocket desconecta (usuário não vê notificação imediata)
- Frontend reconecta automaticamente
- Mensagens são carregadas ao reconectar

#### Melhorias Necessárias

1. **Graceful Shutdown:**
   - WebSocket fecha de forma controlada
   - Frontend detecta e reconecta imediatamente

2. **Fila de Mensagens Pendentes:**
   - Frontend mantém fila local
   - Reenvia ao reconectar (se necessário)

---

## 🔧 Implementação

### Fase 1: Health Checks (Prioridade Alta)

#### 1.1 Criar Endpoints

**Arquivo:** `backend/apps/common/health_views.py`

```python
"""
Health check endpoints para Railway
"""
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from django.db import connection
from django.core.cache import cache
import logging

logger = logging.getLogger(__name__)


@api_view(['GET'])
@permission_classes([AllowAny])
def health_basic(request):
    """
    Health check básico - apenas verifica banco de dados
    """
    try:
        # Verificar banco de dados
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
        
        return Response({
            'status': 'ok',
            'database': 'connected',
            'service': 'alreasense-backend'
        }, status=200)
    except Exception as e:
        logger.error(f"Health check failed: {e}", exc_info=True)
        return Response({
            'status': 'error',
            'database': 'disconnected',
            'error': str(e)
        }, status=503)


@api_view(['GET'])
@permission_classes([AllowAny])
def health_ready(request):
    """
    Health check completo - verifica todos os serviços
    Railway usa este endpoint para determinar se pode trocar tráfego
    """
    checks = {
        'status': 'ready',
        'database': 'unknown',
        'redis': 'unknown',
        'rabbitmq': 'unknown',
        'workers': 'unknown',
        'timestamp': None
    }
    
    all_ready = True
    
    # 1. Verificar banco de dados
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
        checks['database'] = 'connected'
    except Exception as e:
        logger.error(f"Database check failed: {e}")
        checks['database'] = 'disconnected'
        all_ready = False
    
    # 2. Verificar Redis
    try:
        cache.set('health_check', 'ok', 10)
        result = cache.get('health_check')
        if result == 'ok':
            checks['redis'] = 'connected'
        else:
            checks['redis'] = 'error'
            all_ready = False
    except Exception as e:
        logger.error(f"Redis check failed: {e}")
        checks['redis'] = 'disconnected'
        all_ready = False
    
    # 3. Verificar RabbitMQ (opcional - pode ser lento)
    # Se RabbitMQ estiver offline, workers não funcionam mas API pode continuar
    try:
        import pika
        from django.conf import settings
        
        rabbitmq_url = getattr(settings, 'RABBITMQ_URL', None)
        if rabbitmq_url:
            params = pika.URLParameters(rabbitmq_url)
            connection = pika.BlockingConnection(params)
            connection.close()
            checks['rabbitmq'] = 'connected'
        else:
            checks['rabbitmq'] = 'not_configured'
    except Exception as e:
        logger.warning(f"RabbitMQ check failed (non-critical): {e}")
        checks['rabbitmq'] = 'disconnected'
        # Não falhar health check se RabbitMQ estiver offline
        # Workers podem estar processando tasks ainda
    
    # 4. Verificar workers (verificar se processos estão rodando)
    # Railway gerencia workers via Procfile, então assumimos que estão ativos
    # se health check está respondendo
    checks['workers'] = 'assumed_active'
    
    from django.utils import timezone
    checks['timestamp'] = timezone.now().isoformat()
    
    status_code = 200 if all_ready else 503
    checks['status'] = 'ready' if all_ready else 'not_ready'
    
    return Response(checks, status=status_code)
```

#### 1.2 Adicionar URLs

**Arquivo:** `backend/alrea_sense/urls.py`

```python
from apps.common.health_views import health_basic, health_ready

urlpatterns = [
    # ... outras URLs ...
    
    # Health checks
    path('health', health_basic, name='health'),
    path('health/ready', health_ready, name='health_ready'),
]
```

#### 1.3 Configurar Railway

**Arquivo:** `railway.json`

```json
{
  "$schema": "https://railway.app/railway.schema.json",
  "build": {
    "builder": "DOCKERFILE",
    "context": ".",
    "dockerfilePath": "backend/Dockerfile"
  },
  "deploy": {
    "numReplicas": 1,
    "restartPolicyType": "ON_FAILURE",
    "restartPolicyMaxRetries": 10,
    "healthcheckPath": "/health/ready",
    "healthcheckTimeout": 5,
    "healthcheckInterval": 10
  }
}
```

### Fase 2: Graceful Shutdown (Prioridade Alta)

#### 2.1 Signal Handlers no ASGI

**Arquivo:** `backend/alrea_sense/asgi.py`

```python
import signal
import sys
import logging

logger = logging.getLogger(__name__)

# Flag global para graceful shutdown
shutdown_flag = False

def signal_handler(signum, frame):
    """Handler para SIGTERM/SIGINT"""
    global shutdown_flag
    logger.info(f"🛑 [SHUTDOWN] Recebido signal {signum}, iniciando graceful shutdown...")
    shutdown_flag = True
    
    # Daphne já tem graceful shutdown built-in
    # Mas podemos adicionar lógica customizada aqui
    sys.exit(0)

# Registrar handlers
signal.signal(signal.SIGTERM, signal_handler)
signal.signal(signal.SIGINT, signal_handler)
```

#### 2.2 Graceful Shutdown nos Consumers WebSocket

**Arquivo:** `backend/apps/chat/consumers_v2.py`

```python
import signal
import asyncio

class ChatConsumerV2(AsyncWebsocketConsumer):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.shutdown_flag = False
    
    async def connect(self):
        """Conectar e registrar signal handler"""
        # ... código existente ...
        
        # Registrar handler para graceful shutdown
        loop = asyncio.get_event_loop()
        loop.add_signal_handler(
            signal.SIGTERM,
            lambda: asyncio.create_task(self.graceful_shutdown())
        )
    
    async def graceful_shutdown(self):
        """Fechar conexão de forma controlada"""
        if self.shutdown_flag:
            return
        
        self.shutdown_flag = True
        logger.info(f"🛑 [WEBSOCKET] Iniciando graceful shutdown para {self.scope['user']}")
        
        # Fechar conexão
        await self.close()
```

#### 2.3 Graceful Shutdown nos Workers RabbitMQ

**Arquivo:** `backend/apps/chat/management/commands/start_chat_consumer.py`

```python
import signal
import sys

class Command(BaseCommand):
    def handle(self, *args, **options):
        shutdown_flag = False
        
        def signal_handler(signum, frame):
            nonlocal shutdown_flag
            logger.info(f"🛑 [WORKER] Recebido signal {signum}, finalizando tasks...")
            shutdown_flag = True
        
        signal.signal(signal.SIGTERM, signal_handler)
        signal.signal(signal.SIGINT, signal_handler)
        
        # Loop principal com verificação de shutdown
        while not shutdown_flag:
            try:
                # Processar tasks
                # ...
                pass
            except KeyboardInterrupt:
                shutdown_flag = True
                break
        
        logger.info("✅ [WORKER] Worker finalizado com segurança")
```

### Fase 3: Railway Preview Deployments (Prioridade Média)

#### 3.1 Habilitar Preview Deployments

1. **Railway Dashboard:**
   - Vá em Settings do projeto
   - Enable "Preview Deployments"
   - Configure variáveis de ambiente (opcional)

2. **Workflow Recomendado:**
   ```
   1. Criar branch: git checkout -b feature/nova-funcionalidade
   2. Fazer mudanças e commit
   3. Push: git push origin feature/nova-funcionalidade
   4. Criar PR no GitHub
   5. Railway cria preview automaticamente
   6. Testar preview → Aprovar PR
   7. Merge → Deploy produção
   ```

#### 3.2 Variáveis de Ambiente

**Produção:**
- `DATABASE_URL` (produção)
- `REDIS_URL` (produção)
- `RABBITMQ_URL` (produção)

**Preview (opcional):**
- Usar mesmo banco (testes rápidos)
- OU banco separado (testes isolados)

---

## 📋 Checklist de Deploy

### Antes do Deploy

- [ ] Código testado localmente
- [ ] Migrations criadas e testadas
- [ ] Health checks funcionando (`/health/ready`)
- [ ] Graceful shutdown implementado
- [ ] Preview deployment testado (se PR)

### Durante o Deploy

- [ ] Monitorar logs do Railway
- [ ] Verificar health check passando
- [ ] Verificar graceful shutdown funcionando
- [ ] Monitorar reconexões WebSocket no frontend

### Após o Deploy

- [ ] Verificar logs de erro
- [ ] Testar funcionalidades críticas
- [ ] Verificar métricas (tempo de resposta, erros)
- [ ] Confirmar que usuários reconectaram

---

## 🔍 Troubleshooting

### Problema: Health Check Falhando

**Sintomas:**
- Railway não troca tráfego
- Deploy fica travado

**Soluções:**
1. Verificar logs: `railway logs`
2. Testar endpoint manualmente: `curl https://seu-app.railway.app/health/ready`
3. Verificar conectividade (banco, Redis, RabbitMQ)
4. Ajustar timeout no `railway.json`

### Problema: WebSocket Não Reconecta

**Sintomas:**
- Usuários não recebem mensagens após deploy
- Conexão WebSocket permanece desconectada

**Soluções:**
1. Verificar logs do frontend (console do browser)
2. Verificar se `ChatWebSocketManager` está reconectando
3. Verificar se backend está aceitando conexões WebSocket
4. Testar conexão manualmente (WebSocket client)

### Problema: Mensagens Perdidas

**Sintomas:**
- Mensagens não aparecem após deploy
- Mensagens não são salvas no banco

**Soluções:**
1. Verificar logs do webhook (`handle_message_upsert`)
2. Verificar se `@transaction.atomic` está funcionando
3. Verificar se PostgreSQL está acessível durante deploy
4. Verificar se Evolution API está enviando webhooks

### Problema: Workers Não Finalizam

**Sintomas:**
- Deploy demora muito
- Tasks ficam presas

**Soluções:**
1. Verificar se signal handlers estão registrados
2. Verificar timeout de graceful shutdown
3. Verificar se tasks estão sendo finalizadas corretamente
4. Aumentar timeout no Railway (se necessário)

---

## 📚 Referências

- [Railway Health Checks](https://docs.railway.app/deploy/healthchecks)
- [Railway Preview Deployments](https://docs.railway.app/deploy/preview-deployments)
- [Django Channels Deployment](https://channels.readthedocs.io/en/stable/deploying.html)
- [Graceful Shutdown Best Practices](https://www.cloudbees.com/blog/graceful-shutdown)

---

## 📝 Notas de Implementação

### Prioridades

1. **Alta:** Health checks + Graceful shutdown
2. **Média:** Railway Preview Deployments
3. **Baixa:** Monitoramento e alertas

### Próximos Passos

1. Implementar health checks
2. Implementar graceful shutdown
3. Configurar Railway Preview
4. Testar deploy completo
5. Documentar processo para equipe

---

**Última atualização:** 2025-01-20  
**Versão:** 1.0  
**Autor:** Equipe AlreaSense

