# 🎯 Solução Ultra-Refinada para Informações de Grupos

## 📊 Análise do Problema Atual

**Problema**: Grupos com foto e nome não chamam `refresh-info`, então `group_metadata.participants` não é atualizado.

**Causa Raiz**: Otimização no frontend pula `refresh-info` se grupo tem foto + nome, mas participantes podem estar faltando ou desatualizados.

## ✨ Solução Ultra-Refinada (3 Camadas)

### 🎯 Camada 1: Backend - Verificação Inteligente com Timestamp

**Localização**: `backend/apps/chat/api/views.py` - método `refresh_info`

**Melhorias**:
1. ✅ Adicionar timestamp de última atualização de participantes no `group_metadata`
2. ✅ Verificar timestamp antes de ignorar cache (participantes > 1 hora = desatualizados)
3. ✅ Verificação de qualidade (não apenas presença, mas validade dos dados)
4. ✅ Respeitar cooldown de 15min para evitar loops

```python
# ✅ NOVO: Verificação ultra-refinada para grupos
if conversation.conversation_type == 'group':
    group_metadata = conversation.group_metadata or {}
    participants = group_metadata.get('participants', [])
    participants_count = group_metadata.get('participants_count', 0)
    participants_updated_at = group_metadata.get('participants_updated_at')
    
    # ✅ Verificação 1: Timestamp de atualização (participantes > 1 hora = desatualizados)
    participants_stale = False
    if participants_updated_at:
        try:
            from dateutil.parser import parse as parse_dt
            updated_dt = parse_dt(participants_updated_at)
            if timezone.is_naive(updated_dt):
                updated_dt = timezone.make_aware(updated_dt, timezone.utc)
            elapsed_hours = (timezone.now() - updated_dt).total_seconds() / 3600
            if elapsed_hours > 1.0:  # Mais de 1 hora = desatualizado
                participants_stale = True
                logger.info(f"🔄 [REFRESH] Participantes desatualizados ({elapsed_hours:.1f}h atrás)")
        except Exception as e:
            logger.warning(f"⚠️ [REFRESH] Erro ao verificar timestamp: {e}")
    
    # ✅ Verificação 2: Inconsistência (participants_count > 0 mas participants vazio)
    has_inconsistency = participants_count > 0 and len(participants) == 0
    
    # ✅ Verificação 3: Qualidade dos dados (todos participantes inválidos)
    has_poor_quality = False
    if len(participants) > 0:
        valid_count = sum(1 for p in participants 
                         if p.get('phone') and not is_lid_number(p.get('phone', '')))
        # Se menos de 50% são válidos, considerar qualidade ruim
        if valid_count < len(participants) * 0.5:
            has_poor_quality = True
            logger.info(f"🔄 [REFRESH] Qualidade ruim: {valid_count}/{len(participants)} válidos")
    
    # ✅ Decisão: Ignorar cache apenas se realmente necessário
    needs_participants_refresh = (
        has_inconsistency or 
        has_poor_quality or 
        (participants_stale and len(participants) == 0)
    )
    
    # ✅ IMPORTANTE: Se precisa buscar participantes, ignorar cache Redis
    # Mas ainda respeitar cooldown de 15min (já verificado acima)
    if needs_participants_refresh:
        logger.info(f"🔄 [REFRESH] Ignorando cache Redis para atualizar participantes")
        # Continuar com busca da API (não retornar do cache)
    else:
        # Participantes OK, respeitar cache normalmente
        cached = cache.get(cache_key)
        if cached:
            logger.info(f"✅ [REFRESH] Cache hit (participantes OK)")
            return Response({...from_cache: True})
    
    # ... (continua com busca da API)
    
    # ✅ NOVO: Salvar timestamp quando participantes são atualizados
    if 'group_metadata' in update_fields:
        group_metadata['participants_updated_at'] = timezone.now().isoformat()
        conversation.group_metadata = group_metadata
        if 'group_metadata' not in update_fields:
            update_fields.append('group_metadata')
```

### 🎯 Camada 2: Frontend - Verificação Condicional com Debounce

**Localização**: `frontend/src/modules/chat/components/ChatWindow.tsx` - useEffect do refresh-info

**Melhorias**:
1. ✅ Verificação de qualidade dos participantes (não apenas presença)
2. ✅ Verificação de timestamp (se disponível)
3. ✅ Debounce para evitar múltiplas chamadas simultâneas
4. ✅ Fallback para `get_participants` se refresh-info não trouxer participantes

```typescript
// ✅ NOVO: Verificação ultra-refinada no frontend
useEffect(() => {
  if (!activeConversation) return;
  
  let isCancelled = false;
  const currentConversationId = activeConversation.id;
  
  // ✅ Debounce: evitar múltiplas chamadas simultâneas
  const refreshTimeoutRef = useRef<NodeJS.Timeout | null>(null);
  
  const refreshInfo = async () => {
    try {
      if (isCancelled) return;
      
      const { activeConversation: current } = useChatStore.getState();
      if (current?.id !== currentConversationId) return;
      
      const type = activeConversation.conversation_type === 'group' ? 'GRUPO' : 'CONTATO';
      
      // ✅ Verificação para grupos: qualidade dos participantes
      if (activeConversation.conversation_type === 'group') {
        const groupMetadata = activeConversation.group_metadata || {};
        const participants = groupMetadata.participants || [];
        const participantsCount = groupMetadata.participants_count || 0;
        const participantsUpdatedAt = groupMetadata.participants_updated_at;
        
        // ✅ Verificação 1: Inconsistência
        const hasInconsistency = participantsCount > 0 && participants.length === 0;
        
        // ✅ Verificação 2: Qualidade (pelo menos 50% válidos)
        const hasPoorQuality = participants.length > 0 && 
          participants.filter(p => p.phone && p.phone.length >= 10).length < participants.length * 0.5;
        
        // ✅ Verificação 3: Timestamp (se disponível, verificar se > 1 hora)
        let isStale = false;
        if (participantsUpdatedAt && participants.length === 0) {
          const updatedTime = new Date(participantsUpdatedAt).getTime();
          const now = Date.now();
          const oneHourAgo = now - (60 * 60 * 1000);
          isStale = updatedTime < oneHourAgo;
        }
        
        const needsParticipants = hasInconsistency || hasPoorQuality || isStale;
        
        // ✅ Verificação padrão: foto e nome
        const hasPhoto = activeConversation.profile_pic_url;
        const hasName = activeConversation.contact_name && 
                       activeConversation.contact_name !== 'Grupo WhatsApp' &&
                       !activeConversation.contact_name.match(/^\d+$/);
        
        // ✅ Decisão: só pular se tem foto + nome + participantes OK
        if (hasPhoto && hasName && !needsParticipants && participants.length > 0) {
          console.log(`✅ [${type}] Informações completas, pulando refresh-info`);
          return;
        }
        
        if (needsParticipants) {
          console.log(`🔄 [${type}] Forçando refresh-info para atualizar participantes`);
        }
      } else {
        // ✅ Contatos individuais: verificação padrão (foto + nome)
        const hasPhoto = activeConversation.profile_pic_url;
        const hasName = activeConversation.contact_name && 
                       activeConversation.contact_name !== 'Grupo WhatsApp' &&
                       !activeConversation.contact_name.match(/^\d+$/);
        
        if (hasPhoto && hasName) {
          console.log(`✅ [${type}] Informações já disponíveis, pulando refresh-info`);
          return;
        }
      }
      
      console.log(`🔄 [${type}] Atualizando informações...`);
      
      const response = await api.post(`/chat/conversations/${currentConversationId}/refresh-info/`);
      
      if (isCancelled) return;
      
      const { activeConversation: currentAfterRequest } = useChatStore.getState();
      if (currentAfterRequest?.id !== currentConversationId) return;
      
      // ✅ Verificar se refresh-info trouxe participantes (para grupos)
      if (response.data.conversation && activeConversation.conversation_type === 'group') {
        const updatedConversation = response.data.conversation;
        const updatedGroupMetadata = updatedConversation.group_metadata || {};
        const updatedParticipants = updatedGroupMetadata.participants || [];
        
        // ✅ Se refresh-info não trouxe participantes, tentar get_participants como fallback
        if (updatedParticipants.length === 0) {
          console.log(`🔄 [GRUPO] refresh-info não trouxe participantes, tentando get_participants...`);
          try {
            const participantsResponse = await api.get(
              `/chat/conversations/${currentConversationId}/participants/`
            );
            if (participantsResponse.data.participants?.length > 0) {
              console.log(`✅ [GRUPO] get_participants trouxe ${participantsResponse.data.participants.length} participantes`);
              // Atualizar conversation com participantes do get_participants
              const { updateConversation } = useChatStore.getState();
              updateConversation({
                ...updatedConversation,
                group_metadata: {
                  ...updatedGroupMetadata,
                  participants: participantsResponse.data.participants
                }
              });
            }
          } catch (error) {
            console.warn('⚠️ Erro ao buscar participantes via get_participants:', error);
          }
        }
      }
      
      // ✅ Atualizar activeConversation com dados do refresh-info
      if (response.data.conversation) {
        const updatedConversation = response.data.conversation;
        const { updateConversation } = useChatStore.getState();
        updateConversation(updatedConversation);
      }
      
      // ... (resto do código)
    } catch (error: any) {
      if (isCancelled) return;
      console.warn('⚠️ Erro ao atualizar:', error.response?.data?.error || error.message);
    }
  };
  
  // ✅ Debounce: aguardar 300ms antes de executar (evita múltiplas chamadas)
  if (refreshTimeoutRef.current) {
    clearTimeout(refreshTimeoutRef.current);
  }
  
  refreshTimeoutRef.current = setTimeout(() => {
    refreshInfo();
  }, 300);
  
  return () => {
    isCancelled = true;
    if (refreshTimeoutRef.current) {
      clearTimeout(refreshTimeoutRef.current);
    }
  };
}, [activeConversation?.id, activeConversation?.conversation_type, activeConversation?.group_metadata]);
```

### 🎯 Camada 3: Backend - Fallback Inteligente no get_participants

**Localização**: `backend/apps/chat/api/views.py` - método `get_participants`

**Melhorias**:
1. ✅ Já existe lógica de fallback para `refresh-info`
2. ✅ Adicionar verificação de timestamp antes de buscar da API
3. ✅ Cache mais inteligente (considerar timestamp)

```python
# ✅ MELHORIA: Verificar timestamp antes de buscar da API
group_metadata = conversation.group_metadata or {}
participants_raw = group_metadata.get('participants', [])
participants_updated_at = group_metadata.get('participants_updated_at')

# ✅ Se participantes foram atualizados recentemente (< 5 min), usar cache
if participants_updated_at and participants_raw:
    try:
        from dateutil.parser import parse as parse_dt
        updated_dt = parse_dt(participants_updated_at)
        if timezone.is_naive(updated_dt):
            updated_dt = timezone.make_aware(updated_dt, timezone.utc)
        elapsed_minutes = (timezone.now() - updated_dt).total_seconds() / 60
        
        if elapsed_minutes < 5:  # Atualizado há menos de 5 minutos
            logger.info(f"✅ [PARTICIPANTS] Usando participantes recentes ({elapsed_minutes:.1f}min atrás)")
            participants = clean_participants_for_metadata(participants_raw)
            # Salvar no cache
            cache.set(cache_key, participants, 300)  # 5 minutos
            return Response({
                'participants': participants,
                'count': len(participants),
                'cached': False,  # Não é cache Redis, mas é recente
                'from_metadata': True
            })
    except Exception as e:
        logger.warning(f"⚠️ [PARTICIPANTS] Erro ao verificar timestamp: {e}")

# ... (resto da lógica existente)
```

## 🎯 Vantagens da Solução Ultra-Refinada

1. ✅ **3 Camadas de Proteção**: Backend (verificação + timestamp), Frontend (verificação + debounce), Fallback (get_participants)
2. ✅ **Timestamp Inteligente**: Participantes desatualizados (> 1 hora) são atualizados automaticamente
3. ✅ **Verificação de Qualidade**: Não apenas presença, mas validade dos dados (50% válidos)
4. ✅ **Debounce**: Evita múltiplas chamadas simultâneas
5. ✅ **Fallback Robusto**: Se refresh-info não trouxer participantes, tenta get_participants
6. ✅ **Cache Inteligente**: Considera timestamp antes de buscar da API
7. ✅ **Zero Impacto**: Contatos individuais não são afetados
8. ✅ **Performance**: Só busca quando realmente necessário

## 📋 Checklist de Implementação

- [ ] Backend: Adicionar verificação de timestamp no `refresh_info`
- [ ] Backend: Salvar `participants_updated_at` quando participantes são atualizados
- [ ] Backend: Melhorar verificação de qualidade (50% válidos)
- [ ] Frontend: Adicionar verificação de qualidade e timestamp
- [ ] Frontend: Adicionar debounce (300ms)
- [ ] Frontend: Adicionar fallback para `get_participants`
- [ ] Backend: Melhorar cache no `get_participants` com verificação de timestamp
- [ ] Testar: Grupo com participantes faltando
- [ ] Testar: Grupo com participantes desatualizados (> 1 hora)
- [ ] Testar: Grupo com participantes de baixa qualidade
- [ ] Testar: Contato individual (não deve ser afetado)
- [ ] Testar: Cache funcionando corretamente

