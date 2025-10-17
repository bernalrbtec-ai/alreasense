# 🔍 Investigação de Issues da Campanha

## ✅ Problemas Resolvidos

### 1. Layout do Card - RESOLVIDO ✅
- **Problema**: Cards ocupando largura total, não cabia 2 colunas
- **Solução**: Alterado grid para `grid-cols-1 lg:grid-cols-2`
- **Commit**: `50e24d5`

### 2. Tamanho do Gráfico - RESOLVIDO ✅  
- **Problema**: Gráfico muito grande
- **Solução**: 
  - Reduzido de `w-48 h-48` para `w-36 h-36`
  - Ajustado innerRadius de 60 para 45
  - Ajustado outerRadius de 80 para 60
  - Espaçamento reduzido de `space-y-6` para `space-y-4`
- **Commit**: `50e24d5`

---

## 🔴 Problemas Ativos para Investigação

### 3. Mensagens Sendo Enviadas 3x ❌

**Status**: Em investigação

**Descrição**: 
- Campanha está enviando a mesma mensagem 3 vezes para cada contato
- Possível problema de retry/duplicação

**Localização do Código**:
- `backend/apps/campaigns/rabbitmq_consumer.py` (linha 496-604)
- `backend/apps/campaigns/engine.py` (linha 352-402)
- `backend/apps/campaigns/engine_simple.py` (linha 98-132)

**Hipóteses**:

1. **Retry Loop Incorreto**:
   ```python
   # Linha 512-592 em rabbitmq_consumer.py
   for attempt in range(1, max_retries + 1):  # 1, 2, 3
   ```
   - Pode estar fazendo 3 tentativas mesmo quando a primeira tem sucesso

2. **Múltiplos Consumidores**:
   - Pode haver múltiplas instâncias do RabbitMQ consumer rodando
   - Verificar se há processos duplicados

3. **Fila não sendo confirmada (ACK)**:
   - Mensagem pode não estar sendo removida da fila após envio bem-sucedido
   - Verificar `basic_ack` no consumer

**Ações Recomendadas**:

1. **Verificar Logs**:
   ```bash
   # Ver logs do consumer RabbitMQ
   tail -f logs/rabbitmq_consumer.log
   
   # Ver logs da campanha
   tail -f logs/campaign_engine.log
   ```

2. **Verificar Processos Ativos**:
   ```bash
   # Verificar quantos consumers estão rodando
   ps aux | grep rabbitmq_consumer
   ps aux | grep start_campaign_engine
   ```

3. **Debug no Código**:
   - Adicionar logs antes e depois de cada envio
   - Verificar se `return True` na linha 577 está sendo executado corretamente
   - Confirmar se o retry só acontece em caso de erro

4. **Verificar RabbitMQ**:
   - Acessar painel do RabbitMQ
   - Verificar se há mensagens duplicadas na fila
   - Verificar `unacked messages`

5. **Código a Revisar**:
   ```python:backend/apps/campaigns/rabbitmq_consumer.py
   # Linha 559-577
   if response.status_code == 200:
       response_data = response.json()
       if response_data.get('sent'):
           # ✅ SUCESSO - Deve retornar aqui e NÃO fazer retry
           return True
       else:
           # ❌ ERRO - Deve fazer retry
           if attempt < max_retries:
               await asyncio.sleep(delay)
               continue  # ⚠️ VERIFICAR SE ISSO ESTÁ CAUSANDO REENVIO
   ```

---

### 4. Countdown Não Aparecendo no Card ❌

**Status**: Em investigação

**Descrição**:
- O contador regressivo para o próximo disparo não está aparecendo no card
- O campo `countdown_seconds` deve estar vindo do backend mas não está sendo exibido

**Localização do Código**:

1. **Backend - Cálculo do Countdown**:
   ```python:backend/apps/campaigns/serializers.py
   # Linha 127-137
   def _calculate_countdown_seconds(self, instance):
       if not instance.next_message_scheduled_at or instance.status != 'running':
           return None
       
       from django.utils import timezone
       now = timezone.now()
       target = instance.next_message_scheduled_at
       
       diff_seconds = int((target - now).total_seconds())
       return max(0, diff_seconds)
   ```

2. **Frontend - Exibição do Countdown**:
   ```tsx:frontend/src/components/campaigns/CampaignCardOptimized.tsx
   # Linha 87-102
   useEffect(() => {
     if (countdown <= 0) return
     const timer = setInterval(() => {
       setCountdown(prev => {
         if (prev <= 1) return 0
         return prev - 1
       })
     }, 1000)
     return () => clearInterval(timer)
   }, [countdown])
   ```

**Possíveis Causas**:

1. **Campo `next_message_scheduled_at` não está sendo definido**:
   - Verificar se o campo está sendo atualizado no backend
   - Pode estar `null` ou não definido

2. **Status da campanha não é 'running'**:
   - Se status for diferente, `countdown_seconds` retorna `None`

3. **Countdown é 0 ou negativo**:
   - Se `next_message_scheduled_at` já passou, countdown será 0
   - Frontend não exibe se `countdown <= 0`

**Ações Recomendadas**:

1. **Verificar API Response**:
   - Abrir DevTools (F12)
   - Ir em Network → XHR
   - Verificar response da API `/campaigns/`
   - Conferir campos:
     ```json
     {
       "countdown_seconds": 45,
       "next_message_scheduled_at": "2025-01-17T10:30:00Z",
       "status": "running"
     }
     ```

2. **Adicionar Logs no Frontend**:
   ```tsx
   useEffect(() => {
     console.log('🔍 Countdown recebido:', campaign.countdown_seconds)
     console.log('🔍 Next scheduled:', campaign.next_message_scheduled_at)
     console.log('🔍 Status:', campaign.status)
     setCountdown(campaign.countdown_seconds || 0)
   }, [campaign.countdown_seconds])
   ```

3. **Verificar se `next_message_scheduled_at` está sendo definido**:
   - Procurar no código do engine onde esse campo é atualizado
   - Verificar se está sendo salvo no banco de dados

4. **Testar Condições de Exibição**:
   ```tsx
   // Linha 401-414 em CampaignCardOptimized.tsx
   {campaign.status === 'running' && (
     countdown > 0 ? (
       <div className="bg-blue-50 border border-blue-200 rounded-lg p-3">
         // ... Exibir countdown
       </div>
     ) : (
       <div>DEBUG: countdown={countdown}, status={campaign.status}</div>
     )
   )}
   ```

---

## 📋 Próximos Passos

1. ✅ Testar layout 2 colunas
2. ✅ Verificar tamanho do gráfico
3. 🔴 Investigar duplicação de mensagens (PRIORIDADE ALTA)
4. 🔴 Resolver countdown não aparecendo (PRIORIDADE MÉDIA)

---

## 🛠️ Como Testar

### Layout e Gráfico:
```bash
cd frontend
npm run dev
# Acessar http://localhost:5173/campaigns
# Verificar se aparecem 2 cards lado a lado em telas grandes
# Verificar se o gráfico está proporcional
```

### Mensagens Duplicadas:
```bash
# 1. Limpar logs existentes
> logs/rabbitmq_consumer.log

# 2. Iniciar campanha
# 3. Monitorar logs em tempo real
tail -f logs/rabbitmq_consumer.log | grep "Mensagem enviada"

# 4. Contar quantas vezes a mesma mensagem aparece
# Deve aparecer 1x por contato, não 3x
```

### Countdown:
```bash
# 1. Abrir DevTools (F12)
# 2. Console → ver logs do countdown
# 3. Network → ver response da API
# 4. Verificar se countdown_seconds > 0
```

---

## 📝 Notas

- **Engine Atual**: `rabbitmq_consumer.py` (produção) e `engine_simple.py` (teste)
- **Max Retries**: 3 tentativas configuradas
- **Delay entre retries**: 2s, 4s (exponencial)
- **Polling Frontend**: A cada 30 segundos (sem loading)

---

**Última Atualização**: 17/01/2025 - Bom dia! 🌅
**Status Geral**: Layout ✅ | Duplicação ❌ | Countdown ❌

