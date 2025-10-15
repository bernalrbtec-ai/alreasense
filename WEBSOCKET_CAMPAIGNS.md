# Sistema WebSocket para Campanhas - Documentação

## Visão Geral

Este documento descreve a implementação do sistema WebSocket para atualizações em tempo real de campanhas, substituindo o sistema de polling anterior por uma solução mais eficiente e responsiva.

## Arquitetura

### Backend (Django + Channels)

#### 1. RabbitMQ Consumer (`backend/apps/campaigns/rabbitmq_consumer.py`)

**Método `_send_websocket_update`:**
- Envia atualizações WebSocket apenas em eventos específicos
- Implementa sistema de throttling (mínimo 2 segundos entre updates)
- Executa em thread separada para evitar bloqueios
- Usa `async_to_sync` para compatibilidade com Django Channels

**Eventos que disparam WebSocket:**
- `campaign_started` - Campanha iniciada
- `campaign_paused` - Campanha pausada
- `message_sent` - Mensagem enviada com sucesso
- `message_failed` - Falha ao enviar mensagem
- `next_message_starting` - Próxima mensagem sendo processada

#### 2. WebSocket Consumer (`backend/apps/chat_messages/consumers.py`)

**Handler `campaign_update`:**
- Processa mensagens de atualização de campanhas
- Envia dados estruturados para o frontend
- Inclui timestamp para sincronização

### Frontend (React + TypeScript)

#### 1. Hook WebSocket (`frontend/src/hooks/useCampaignWebSocket.ts`)

**Funcionalidades:**
- Conexão automática com reconexão inteligente
- Heartbeat para manter conexão viva
- Backoff exponencial para reconexão
- Callbacks para atualizações e mudanças de status

**Estados da conexão:**
- `connecting` - Conectando
- `connected` - Conectado
- `disconnected` - Desconectado
- `error` - Erro (fallback para polling)

#### 2. Componente de Status (`frontend/src/components/campaigns/WebSocketStatus.tsx`)

**Indicadores visuais:**
- Verde: WebSocket conectado (Tempo Real)
- Amarelo: Conectando
- Vermelho: Erro (Polling)
- Cinza: Desconectado (Polling)

#### 3. Sistema de Notificações (`frontend/src/hooks/useCampaignNotifications.ts`)

**Notificações automáticas para:**
- Início de campanha
- Pausa de campanha
- Conclusão de campanha
- Falhas de mensagens
- Erros de campanha

#### 4. Integração na Página (`frontend/src/pages/CampaignsPage.tsx`)

**Comportamento híbrido:**
- WebSocket como método principal
- Polling como fallback (10s quando WebSocket falha)
- Atualizações otimizadas (apenas mudanças significativas)
- Indicador visual de status da conexão

## Fluxo de Dados

```
1. RabbitMQ Consumer processa mensagem
   ↓
2. Atualiza dados no banco (PostgreSQL)
   ↓
3. Envia update via WebSocket (com throttling)
   ↓
4. Channels distribui para tenant group
   ↓
5. Frontend recebe e atualiza interface
   ↓
6. Notificações toast para eventos importantes
```

## Configuração

### URLs WebSocket

**Desenvolvimento:**
```
ws://localhost:8000/ws/tenant/{tenant_id}/
```

**Produção:**
```
wss://alreasense-backend-production.up.railway.app/ws/tenant/{tenant_id}/
```

### Throttling

- **Backend:** Mínimo 2 segundos entre updates por campanha
- **Frontend:** Atualizações apenas em mudanças significativas

### Reconexão

- **Máximo de tentativas:** 10
- **Delay inicial:** 3 segundos
- **Backoff exponencial:** Até 30 segundos máximo
- **Heartbeat:** A cada 30 segundos

## Benefícios

### Performance
- ✅ Elimina polling desnecessário
- ✅ Reduz carga no servidor
- ✅ Atualizações instantâneas
- ✅ Menor latência

### Experiência do Usuário
- ✅ Indicador visual de conexão
- ✅ Notificações em tempo real
- ✅ Fallback automático para polling
- ✅ Reconexão transparente

### Robustez
- ✅ Tratamento de erros
- ✅ Throttling anti-spam
- ✅ Reconexão automática
- ✅ Fallback para polling

## Monitoramento

### Logs Backend
```
🔧 [WEBSOCKET] Enviando campaign_started para campanha Teste
📡 [WEBSOCKET] campaign_started enviado para campanha Teste
🚫 [WEBSOCKET] Throttling update para Teste (1.2s)
```

### Logs Frontend
```
🔌 [CAMPAIGN-WS] Conectando em: wss://...
✅ [CAMPAIGN-WS] Conectado com sucesso
📡 [CAMPAIGN-WS] Recebido update: Teste campaign_started
🔄 [CAMPAIGN-WS] Tentando reconectar em 3000ms (tentativa 1/10)
```

## Troubleshooting

### WebSocket não conecta
1. Verificar se Channels está configurado
2. Verificar URL do WebSocket
3. Verificar CORS/ALLOWED_HOSTS
4. Verificar logs do servidor

### Updates não aparecem
1. Verificar throttling (logs de "Throttling update")
2. Verificar se consumer está ativo
3. Verificar se campanha está enviando eventos
4. Verificar logs do frontend

### Reconexão infinita
1. Verificar configuração de rede
2. Verificar se servidor está respondendo
3. Verificar logs de erro
4. Considerar aumentar delay de reconexão

## Próximos Passos

1. **Métricas:** Adicionar métricas de WebSocket (conexões ativas, mensagens/s)
2. **Compressão:** Implementar compressão de mensagens WebSocket
3. **Clustering:** Suporte a múltiplos workers Django
4. **Persistência:** Salvar mensagens WebSocket em caso de desconexão
5. **Rate Limiting:** Rate limiting por tenant
