# Guia de Implementação - Sistema de Conversas Privadas por Usuário

## 📋 Visão Geral

Este documento contém instruções passo a passo para implementar o sistema onde conversas atribuídas a um usuário ficam disponíveis somente para ele, separadas das conversas dos departamentos.

**Tempo estimado**: 14-21 horas (2-3 dias úteis)

## ⚠️ AVISOS CRÍTICOS

1. **NÃO criar migrations do Django** - Use apenas scripts SQL opcionais se necessário
2. **Implementar medidas de segurança PRIMEIRO** - Feature flag e fallback antes de qualquer mudança
3. **Manter comportamento atual por padrão** - Nova funcionalidade apenas com parâmetro explícito
4. **Testar extensivamente** - Especialmente segurança e compatibilidade

## 🎯 Objetivo

Quando uma conversa é atribuída ou iniciada por um usuário:
- Conversa sai do departamento (`department=None`)
- Conversa aparece apenas na aba "Minhas Conversas" desse usuário
- Outros usuários não veem a conversa (exceto admins)

## 📦 Arquivos a Modificar

### Backend

1. `backend/apps/authn/views.py` - Corrigir `pending_count_annotated`
2. `backend/apps/chat/api/views.py` - Múltiplas modificações
3. `backend/apps/contacts/models.py` - Adicionar `conversation_started`
4. `backend/apps/contacts/signals.py` - Não requer modificações (signals existentes já funcionam)

### Frontend

1. `frontend/src/modules/chat/components/DepartmentTabs.tsx`
2. `frontend/src/modules/chat/components/ConversationList.tsx`
3. `frontend/src/modules/chat/components/ChatWindow.tsx`
4. `frontend/src/modules/chat/components/TransferModal.tsx`

### Scripts SQL (Opcionais)

1. `scripts/sql/add_conversation_assignment_indexes.sql`
2. `scripts/sql/check_conversation_indexes.sql`
3. `scripts/sql/remove_conversation_assignment_indexes.sql`

## 🔧 Implementação Passo a Passo

### FASE 1: Medidas de Segurança (CRÍTICO - FAZER PRIMEIRO)

#### 1.1 Adicionar Feature Flag

**Arquivo**: `backend/alrea_sense/settings.py` ou variável de ambiente

```python
# Adicionar ao settings.py (após outras configurações de feature flags)
ENABLE_MY_CONVERSATIONS = config('ENABLE_MY_CONVERSATIONS', default=False, cast=bool)
```

**Variável de ambiente**:
```bash
ENABLE_MY_CONVERSATIONS=false  # Iniciar desabilitado
```

#### 1.2 Criar Método de Fallback

**Arquivo**: `backend/apps/chat/api/views.py`

**IMPORTANTE**: Adicionar este método ANTES do método `get_queryset()` (após o método `get_serializer_class()`).

Adicionar método privado que mantém comportamento atual:

```python
def _get_queryset_current_behavior(self, queryset, user):
    """
    Comportamento atual garantido - nunca muda.
    Usado como fallback em caso de erro ou quando feature flag está desabilitado.
    
    Lógica atual:
    - Admin: vê tudo do tenant
    - Gerente/Agente: vê conversas dos seus departamentos + atribuídas a ele + inbox (pending sem department)
    """
    # Admin vê tudo (incluindo pending)
    if user.is_admin:
        return queryset
    
    # Gerente e Agente vêem:
    # 1. Conversas dos seus departamentos
    # 2. Conversas atribuídas diretamente a eles
    # 3. Conversas pending (sem departamento) do tenant
    department_ids = list(user.departments.values_list('id', flat=True))
    
    if department_ids:
        # ✅ Usuário tem departamentos: ver conversas dos departamentos OU atribuídas a ele
        return queryset.filter(
            Q(department__in=department_ids) |  # Conversas dos departamentos
            Q(assigned_to=user) |  # Conversas atribuídas diretamente ao usuário
            Q(department__isnull=True, status='pending')  # Inbox do tenant
        ).distinct()
    else:
        # ✅ Usuário SEM departamentos: ver apenas conversas atribuídas diretamente a ele OU inbox
        return queryset.filter(
            Q(assigned_to=user) |  # Conversas atribuídas diretamente ao usuário
            Q(department__isnull=True, status='pending')  # Inbox do tenant
        ).distinct()
```

### FASE 2: Correções Críticas

#### 2.1 Corrigir `pending_count_annotated`

**Arquivo**: `backend/apps/authn/views.py` (linha ~341)

**ANTES**:
```python
pending_count_annotated=Count(
    'conversations',
    filter=Q(
        conversations__status='pending',
        conversations__tenant=user.tenant
    ),
    distinct=True
)
```

**DEPOIS**:
```python
pending_count_annotated=Count(
    'conversations',
    filter=Q(
        conversations__status='pending',
        conversations__tenant=user.tenant,
        conversations__assigned_to__isnull=True  # ✅ NOVO: Excluir atribuídas
    ),
    distinct=True
)
```

#### 2.2 Modificar Método `assign()`

**Arquivo**: `backend/apps/chat/api/views.py` (linha ~2506)

**ANTES**:
```python
user = User.objects.get(
    id=user_id,
    tenant=conversation.tenant,
    departments=conversation.department  # ❌ Requer department
)
```

**DEPOIS**:
```python
# Tornar department opcional
user = User.objects.get(
    id=user_id,
    tenant=conversation.tenant
)

# Validar department apenas se conversa tiver department
if conversation.department:
    if not user.departments.filter(id=conversation.department_id).exists():
        return Response(
            {'error': 'Usuário não pertence ao departamento da conversa'},
            status=status.HTTP_400_BAD_REQUEST
        )
```

### FASE 3: Nova Funcionalidade Backend

#### 3.1 Modificar `get_queryset()`

**Arquivo**: `backend/apps/chat/api/views.py` (linha ~244)

**IMPORTANTE**: Modificar o FINAL do método `get_queryset()`, ANTES do return final. O código existente de filtro por tenant, annotate, etc. deve permanecer.

**Localização**: Substituir o bloco final que contém a lógica de filtro por departamento (após linha ~352).

**ANTES** (código atual no final do método):
```python
# Admin vê tudo (incluindo pending)
if user.is_admin:
    return queryset

# Gerente e Agente vêem:
# 1. Conversas dos seus departamentos
# 2. Conversas atribuídas diretamente a eles
# 3. Conversas pending (sem departamento) do tenant
department_ids = list(user.departments.values_list('id', flat=True))

if department_ids:
    # ✅ Usuário tem departamentos: ver conversas dos departamentos OU atribuídas a ele
    return queryset.filter(
        Q(department__in=department_ids) |  # Conversas dos departamentos
        Q(assigned_to=user) |  # Conversas atribuídas diretamente ao usuário
        Q(department__isnull=True, status='pending')  # Inbox do tenant
    ).distinct()
else:
    # ✅ Usuário SEM departamentos: ver apenas conversas atribuídas diretamente a ele OU inbox
    return queryset.filter(
        Q(assigned_to=user) |  # Conversas atribuídas diretamente ao usuário
        Q(department__isnull=True, status='pending')  # Inbox do tenant
    ).distinct()
```

**DEPOIS** (código modificado):
```python
# ✅ SEGURANÇA: Feature flag - se desabilitado, usar comportamento atual
from django.conf import settings
if not settings.ENABLE_MY_CONVERSATIONS:
    return self._get_queryset_current_behavior(queryset, user)

# ✅ SEGURANÇA: Nova funcionalidade apenas com parâmetro explícito
assigned_to_me = self.request.query_params.get('assigned_to_me') == 'true'

try:
    if assigned_to_me:
        # Nova funcionalidade: apenas conversas atribuídas ao usuário E sem departamento
        # Isso garante que apenas conversas "privadas" apareçam
        return queryset.filter(
            assigned_to=user,
            department__isnull=True,  # ✅ CRÍTICO: Sem departamento
            status='open'  # Apenas conversas abertas
        )
    else:
        # ✅ SEGURANÇA: Comportamento atual (garantido)
        return self._get_queryset_current_behavior(queryset, user)
except Exception as e:
    logger.error(f"❌ [QUERYSET] Erro ao filtrar conversas: {e}", exc_info=True)
    # ✅ SEGURANÇA: Fallback garantido
    return self._get_queryset_current_behavior(queryset, user)
```

#### 3.2 Criar Action `start()`

**Arquivo**: `backend/apps/chat/api/views.py` (após método `claim()`)

```python
@action(detail=True, methods=['post'])
def start(self, request, pk=None):
    """
    Inicia atendimento de uma conversa pendente, atribuindo-a ao usuário atual.
    Remove a conversa do departamento e atribui diretamente ao usuário.
    """
    import logging
    logger = logging.getLogger(__name__)
    
    conversation = self.get_object()
    user = request.user
    
    # Validar que conversa pode ser iniciada
    if conversation.assigned_to and conversation.assigned_to != user:
        logger.warning(
            f"⚠️ [START] Tentativa de iniciar conversa já atribuída: {conversation.id} "
            f"(atribuída para: {conversation.assigned_to.email})"
        )
        return Response(
            {'error': 'Conversa já está atribuída a outro usuário'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    # Salvar valores anteriores para logs
    old_department = conversation.department
    old_status = conversation.status
    
    # Atribuir ao usuário atual
    conversation.assigned_to = user
    conversation.department = None  # Remover do departamento
    conversation.status = 'open'
    conversation.save(update_fields=['assigned_to', 'department', 'status'])
    
    # ✅ LOGS: Log detalhado
    logger.info(
        f"✅ [START CONVERSATION] Conversa {conversation.id} iniciada por {user.email} "
        f"(tenant: {user.tenant.name})"
    )
    logger.info(f"   📋 Contato: {conversation.contact_name} ({conversation.contact_phone})")
    logger.info(f"   👤 Atribuído para: {user.get_full_name() or user.email}")
    logger.info(f"   📊 Status anterior: {old_status} → Status novo: {conversation.status}")
    logger.info(f"   🏢 Departamento anterior: {old_department.name if old_department else 'Nenhum'} → Departamento novo: Nenhum (atribuído diretamente)")
    
    # Criar mensagem interna
    try:
        from apps.chat.models import Message
        Message.objects.create(
            conversation=conversation,
            sender=user,
            content=f"Atendimento iniciado por {user.get_full_name() or user.email}",
            direction='outgoing',
            status='sent',
            is_internal=True
        )
    except Exception as e:
        logger.error(f"❌ [START] Erro ao criar mensagem interna: {e}", exc_info=True)
    
    # ✅ CONTACT HISTORY: Criar evento
    try:
        from apps.contacts.models import Contact, ContactHistory
        from apps.contacts.signals import normalize_phone_for_search
        
        normalized_phone = normalize_phone_for_search(conversation.contact_phone)
        contact = Contact.objects.filter(
            tenant=conversation.tenant,
            phone=normalized_phone
        ).first()
        
        if contact:
            ContactHistory.objects.create(
                contact=contact,
                tenant=conversation.tenant,
                event_type='conversation_started',  # ✅ NOVO tipo
                title=f'Atendimento iniciado por {user.get_full_name() or user.email}',
                description=f'Conversa atribuída diretamente para {user.get_full_name() or user.email}',
                created_by=user,
                is_editable=False,
                metadata={
                    'assigned_to_id': str(user.id),
                    'assigned_to_name': user.get_full_name() or user.email,
                    'old_department_id': str(old_department.id) if old_department else None,
                    'old_status': old_status,
                },
                related_conversation=conversation
            )
    except Exception as e:
        logger.error(f"❌ [START] Erro ao criar ContactHistory: {e}", exc_info=True)
    
    # Broadcast WebSocket
    try:
        from channels.layers import get_channel_layer
        from asgiref.sync import async_to_sync
        from apps.chat.utils.serialization import serialize_conversation_for_ws
        
        channel_layer = get_channel_layer()
        tenant_group = f"chat_tenant_{conversation.tenant_id}"
        
        conv_data_serializable = serialize_conversation_for_ws(conversation)
        async_to_sync(channel_layer.group_send)(
            tenant_group,
            {
                'type': 'conversation_updated',
                'conversation': conv_data_serializable
            }
        )
    except Exception as e:
        logger.error(f"❌ [START] Erro ao fazer broadcast: {e}", exc_info=True)
    
    serializer = self.get_serializer(conversation)
    return Response(serializer.data)
```

#### 3.3 Modificar `claim()` para Tornar Department Opcional

**Arquivo**: `backend/apps/chat/api/views.py` (linha ~376)

**ANTES**:
```python
if not department_id:
    return Response(
        {'error': 'department é obrigatório'},
        status=status.HTTP_400_BAD_REQUEST
    )
```

**DEPOIS**:
```python
# ✅ NOVO: Department opcional - se não fornecido, atribuir apenas ao usuário
if not department_id:
    # Atribuir apenas ao usuário (remover do departamento)
    conversation.assigned_to = assigned_to
    conversation.department = None  # ✅ NOVO: Remover department
    conversation.status = 'open'
    conversation.save(update_fields=['assigned_to', 'department', 'status'])
    
    serializer = self.get_serializer(conversation)
    return Response(serializer.data)
```

#### 3.4 Modificar `transfer()` com Lógica Condicional

**Arquivo**: `backend/apps/chat/api/views.py` (linha ~3327)

**IMPORTANTE**: Modificar ANTES de salvar a conversa (após linha ~3327, antes de `conversation.save()`).

**Localização**: Adicionar lógica após a validação do novo agente e antes de `conversation.save()`.

**Código a adicionar** (após linha ~3327, antes de `conversation.save()`):
```python
# ✅ NOVO: Se transferir apenas para agente (sem department), remover department
if new_agent_id and not new_department_id:
    # Transferir para usuário específico - remover do departamento
    conversation.department = None
    logger.info(
        f"✅ [TRANSFER] Conversa {conversation.id} atribuída diretamente a {new_agent.email} "
        f"(department removido - conversa privada)"
    )
elif new_agent_id and new_department_id:
    # Transferir para agente E departamento - manter ambos
    # (comportamento atual mantido)
    logger.info(
        f"✅ [TRANSFER] Conversa {conversation.id} transferida para departamento {new_dept.name} "
        f"e agente {new_agent.email}"
    )
```

### FASE 4: Frontend

#### 4.1 Adicionar Tab "Minhas Conversas"

**Arquivo**: `frontend/src/modules/chat/components/DepartmentTabs.tsx`

**Adicionar após tab Inbox** (linha ~129):
```tsx
{/* Tab Minhas Conversas */}
<button
  onClick={() => setActiveDepartment({ id: 'my_conversations', name: 'Minhas Conversas', color: '#3b82f6' } as Department)}
  className={`
    flex items-center gap-1.5 px-2.5 sm:px-3 py-1.5 rounded-md text-xs sm:text-sm font-medium transition-all whitespace-nowrap flex-shrink-0
    ${activeDepartment?.id === 'my_conversations'
      ? 'bg-[#3b82f6] text-white'
      : 'text-gray-600 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700 active:scale-95'
    }
  `}
>
  <User className="w-3.5 h-3.5 sm:w-4 sm:h-4" />
  <span className="hidden sm:inline">
    Minhas Conversas
    {getMyConversationsCount() > 0 && (
      <span className="ml-1.5 px-1.5 py-0.5 rounded-full bg-white/20 text-xs font-semibold">
        {getMyConversationsCount()}
      </span>
    )}
  </span>
</button>
```

**Adicionar função de contador** (após `getPendingCount`, antes do `useEffect`):
```tsx
const getMyConversationsCount = () => {
  const { user } = useAuthStore.getState();
  if (!user) return 0;
  
  // Contar apenas conversas atribuídas ao usuário, sem departamento e abertas
  return conversations.filter(conv => 
    conv.assigned_to === user.id && 
    conv.status === 'open' &&
    (!conv.department || conv.department === null)  // ✅ CRÍTICO: Sem departamento
  ).length;
};
```

**Importar User icon**:
```tsx
import { Inbox, User } from 'lucide-react';
```

#### 4.2 Modificar Filtro em ConversationList

**Arquivo**: `frontend/src/modules/chat/components/ConversationList.tsx` (linha ~221)

**Adicionar após verificação de inbox**:
```tsx
if (activeDepartment.id === 'my_conversations') {
  // Minhas Conversas: apenas conversas atribuídas ao usuário atual
  const { user } = useAuthStore.getState();
  if (!user) return false;
  
  const passes = 
    conversationItem.assigned_to === user.id &&
    conversationItem.status === 'open' &&
    !conversationItem.department; // Sem department (atribuída diretamente)
  
  return passes;
}
```

**Modificar busca de conversas** (linha ~76, dentro da função `fetchConversations`):
```tsx
// Buscar conversas com parâmetro assigned_to_me se necessário
const params: any = { ordering: '-last_message_at' };
if (activeDepartment?.id === 'my_conversations') {
  params.assigned_to_me = 'true';
}

const response = await api.get('/chat/conversations/', { params });
```

**NOTA**: Esta modificação deve ser feita dentro da função `fetchConversations` que já existe no arquivo.

#### 4.3 Adicionar Botão "INICIAR ATENDIMENTO"

**Arquivo**: `frontend/src/modules/chat/components/ChatWindow.tsx`

**Adicionar botão no header da conversa** (onde mostra informações da conversa):
```tsx
{activeConversation && 
 !activeConversation.assigned_to && 
 activeConversation.status === 'pending' && 
 !activeConversation.department && (
  <button
    onClick={handleStartConversation}
    disabled={loading}
    className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
  >
    INICIAR ATENDIMENTO
  </button>
)}
```

**NOTA**: O botão só aparece para conversas pendentes sem departamento e sem atribuição.

**Adicionar handler** (dentro do componente, junto com outros handlers):
```tsx
const handleStartConversation = async () => {
  if (!activeConversation) return;
  
  try {
    setLoading(true);
    const response = await api.post(`/chat/conversations/${activeConversation.id}/start/`);
    
    // Atualizar conversa no store usando o método do store
    const { updateConversation } = useChatStore.getState();
    updateConversation(response.data);
    
    // Atualizar conversa ativa se necessário
    if (setActiveConversation) {
      setActiveConversation(response.data);
    }
    
    // Mostrar notificação de sucesso
    toast.success('Atendimento iniciado com sucesso');
  } catch (error: any) {
    console.error('Erro ao iniciar atendimento:', error);
    toast.error(error.response?.data?.error || 'Erro ao iniciar atendimento');
  } finally {
    setLoading(false);
  }
};
```

**NOTA**: Verificar se `toast` está importado. Se não estiver, adicionar: `import { toast } from 'react-toastify';` ou usar o sistema de notificações do projeto.

#### 4.4 Ajustar TransferModal

**Arquivo**: `frontend/src/modules/chat/components/TransferModal.tsx` (linha ~79)

**Modificar payload** (localizar onde o payload é criado antes do POST):
```tsx
const payload: any = { reason };
if (selectedDepartment) {
  payload.new_department = selectedDepartment;
}
if (selectedAgent) {
  payload.new_agent = selectedAgent;
  // ✅ NOVO: Se transferir apenas para agente (sem department), não enviar new_department
  // Backend vai remover department automaticamente quando new_agent existe mas new_department não
  // Não precisa fazer nada aqui - apenas não incluir new_department no payload
}
```

**NOTA**: A lógica já está correta - quando apenas `selectedAgent` é fornecido sem `selectedDepartment`, o backend remove o department automaticamente.

### FASE 5: Adicionar Event Type ao ContactHistory

**Arquivo**: `backend/apps/contacts/models.py` (linha ~726)

**Adicionar ao EVENT_TYPE_CHOICES**:
```python
EVENT_TYPE_CHOICES = [
    ('note', 'Anotação Manual'),
    ('message_sent', 'Mensagem Enviada (Chat)'),
    ('message_received', 'Mensagem Recebida (Chat)'),
    ('campaign_message_sent', 'Mensagem de Campanha Enviada'),
    ('campaign_message_delivered', 'Mensagem de Campanha Entregue'),
    ('campaign_message_read', 'Mensagem de Campanha Lida'),
    ('campaign_message_failed', 'Mensagem de Campanha Falhou'),
    ('department_transfer', 'Transferência de Departamento'),
    ('conversation_started', 'Atendimento Iniciado'),  # ✅ NOVO
    ('assigned_to', 'Atribuição de Atendente'),
    ('status_changed', 'Mudança de Status'),
    ('contact_created', 'Contato Criado'),
    ('contact_updated', 'Contato Atualizado'),
]
```

## ✅ Checklist de Implementação

### Backend
- [ ] Feature flag adicionado
- [ ] Método `_get_queryset_current_behavior()` criado
- [ ] `pending_count_annotated` corrigido
- [ ] Método `assign()` modificado
- [ ] `get_queryset()` modificado com segurança
- [ ] Action `start()` criada
- [ ] Método `claim()` modificado
- [ ] Método `transfer()` modificado
- [ ] `conversation_started` adicionado ao ContactHistory
- [ ] Logs detalhados implementados

### Frontend
- [ ] Tab "Minhas Conversas" adicionada
- [ ] Contador de minhas conversas implementado
- [ ] Filtro em ConversationList modificado
- [ ] Busca com `assigned_to_me=true` implementada
- [ ] Botão "INICIAR ATENDIMENTO" adicionado
- [ ] Handler de iniciar atendimento implementado
- [ ] TransferModal ajustado

### Testes
- [ ] Testes de segurança executados
- [ ] Testes de compatibilidade executados
- [ ] Testes de performance executados
- [ ] Contadores validados

### Deploy
- [ ] Feature flag desabilitado inicialmente
- [ ] Código deployado em staging
- [ ] Testes em staging executados
- [ ] Feature flag habilitado para 1 usuário teste
- [ ] Validado com usuário teste
- [ ] Feature flag habilitado para todos
- [ ] Monitoramento ativo

## 🚨 Plano de Rollback

### Rollback Rápido (< 5 minutos)

1. **Via Feature Flag**:
   ```bash
   export ENABLE_MY_CONVERSATIONS=false
   # Reiniciar aplicação
   ```

2. **Via Revert de Código**:
   ```bash
   git revert <commit-hash>
   git push
   ```

### Rollback Parcial

- Frontend pode simplesmente não usar `assigned_to_me=true`
- Backend continua funcionando com comportamento atual

## 📊 Monitoramento

Após deploy, monitorar:
- Tempo de resposta de `get_queryset()`
- Contagem de conversas retornadas
- Erros 500 em endpoints de conversas
- Taxa de uso de `assigned_to_me=true`
- Performance de queries

## 📝 Scripts SQL (Opcionais)

Aplicar apenas se monitoramento mostrar necessidade:

```bash
# Verificar índices existentes
railway run psql < scripts/sql/check_conversation_indexes.sql

# Aplicar índices opcionais (se necessário)
railway run psql < scripts/sql/add_conversation_assignment_indexes.sql

# Reverter índices (se necessário)
railway run psql < scripts/sql/remove_conversation_assignment_indexes.sql
```

## 🎯 Ordem de Implementação Recomendada

1. **FASE 1**: Medidas de segurança (feature flag, fallback)
2. **FASE 2**: Correções críticas (`pending_count`, `assign()`)
3. **FASE 3**: Backend com feature flag desabilitado
4. **FASE 4**: Testes em staging
5. **FASE 5**: Habilitar feature flag para 1 usuário
6. **FASE 6**: Validar com usuário teste
7. **FASE 7**: Habilitar para todos
8. **FASE 8**: Frontend usa nova funcionalidade
9. **FASE 9**: Monitorar e aplicar índices SQL se necessário

---

**Documento gerado automaticamente baseado no plano**: `sistema_de_conversas_privadas_por_usuário_0d45e5e1.plan.md`
