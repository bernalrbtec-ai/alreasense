"""
Views para respostas rápidas com cache Redis.
"""
import logging
from django.core.cache import cache
from rest_framework import viewsets, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from apps.chat.models import QuickReply
from apps.chat.api.serializers import QuickReplySerializer
from apps.authn.permissions import CanAccessChat
from apps.common.cache_manager import CacheManager

logger = logging.getLogger(__name__)

# ✅ Cache TTL: 5 minutos (respostas não mudam frequentemente)
CACHE_TTL_SECONDS = 300
CACHE_KEY_PREFIX = "quick_replies"


class QuickReplyViewSet(viewsets.ModelViewSet):
    """
    ViewSet para respostas rápidas com cache Redis.
    ✅ Segurança: IsAuthenticated + CanAccessChat + Multi-tenant automático
    ✅ Cache: Redis com TTL de 5 minutos
    ✅ Ordenação: Apenas por uso (use_count) e título (title)
    """
    permission_classes = [IsAuthenticated, CanAccessChat]
    serializer_class = QuickReplySerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['title', 'content']
    ordering_fields = ['use_count', 'title']
    ordering = ['-use_count', 'title']
    
    def _get_cache_key(self, tenant_id: str, search: str = '', ordering: str = '') -> str:
        """Gera chave de cache única baseada em tenant, busca e ordenação."""
        cache_key = f"{CACHE_KEY_PREFIX}:tenant:{tenant_id}"
        if search:
            cache_key += f":search:{search.lower()}"
        if ordering:
            cache_key += f":order:{ordering}"
        return cache_key
    
    def _invalidate_cache(self, tenant_id: str):
        """Invalida cache do tenant (chamado após criar/editar/deletar)."""
        # Invalidar todas as variações de cache deste tenant
        pattern = f"{CACHE_KEY_PREFIX}:tenant:{tenant_id}:*"
        try:
            CacheManager.invalidate_pattern(pattern)
            logger.info(f"🗑️ [QUICK REPLIES] Cache invalidado para tenant {tenant_id}")
        except Exception as e:
            logger.warning(f"⚠️ [QUICK REPLIES] Erro ao invalidar cache: {e}")
    
    def get_queryset(self):
        """Filtra por tenant automaticamente."""
        # ✅ OTIMIZAÇÃO: Usar select_related para evitar queries adicionais
        # ✅ SEGURANÇA: Verificar se usuário está autenticado antes de acessar tenant
        if not hasattr(self.request, 'user') or not self.request.user.is_authenticated:
            logger.warning("⚠️ [QUICK REPLIES] Usuário não autenticado")
            return QuickReply.objects.none()
        
        tenant = self.request.user.tenant
        
        # ✅ DEBUG: Verificar total de mensagens rápidas do tenant (antes do filtro is_active)
        total_all = QuickReply.objects.filter(tenant=tenant).count()
        total_active = QuickReply.objects.filter(tenant=tenant, is_active=True).count()
        total_inactive = QuickReply.objects.filter(tenant=tenant, is_active=False).count()
        
        logger.info(f"🔍 [QUICK REPLIES] Tenant {tenant.name} (ID: {tenant.id}): Total={total_all}, Ativas={total_active}, Inativas={total_inactive}")
        
        # ✅ Se não há mensagens ativas mas há inativas, logar aviso
        if total_active == 0 and total_inactive > 0:
            logger.warning(f"⚠️ [QUICK REPLIES] Tenant {tenant.name} tem {total_inactive} mensagens rápidas INATIVAS que não serão retornadas!")
        
        return QuickReply.objects.filter(
            tenant=tenant,
            is_active=True
        ).select_related('tenant', 'created_by').only(
            'id', 'title', 'content', 'category', 'use_count', 
            'is_active', 'created_at', 'updated_at',
            'tenant_id', 'created_by_id'
        )
    
    def list(self, request, *args, **kwargs):
        """
        Lista respostas rápidas com cache Redis.
        ✅ Cache: 5 minutos
        ✅ Invalidação: Automática após criar/editar/deletar
        """
        # ✅ SEGURANÇA: Verificar autenticação antes de acessar tenant
        if not request.user.is_authenticated:
            return Response({'results': [], 'count': 0}, status=status.HTTP_401_UNAUTHORIZED)
        
        tenant_id = str(request.user.tenant.id)
        search = request.query_params.get('search', '').strip()
        ordering = request.query_params.get('ordering', '-use_count,title')
        
        # ✅ Gerar chave de cache
        cache_key = self._get_cache_key(tenant_id, search, ordering)
        
        # ✅ Tentar buscar do cache
        cached_data = cache.get(cache_key)
        if cached_data is not None:
            logger.debug(f"✅ [QUICK REPLIES] Cache HIT: {cache_key}")
            return Response(cached_data)
        
        # ✅ Cache MISS: buscar do banco
        logger.debug(f"❌ [QUICK REPLIES] Cache MISS: {cache_key}")
        
        # ✅ OTIMIZAÇÃO: Usar apenas() para limitar campos buscados
        queryset = self.get_queryset()
        
        # ✅ DEBUG: Log para diagnóstico
        total_before_filters = queryset.count()
        logger.info(f"🔍 [QUICK REPLIES] Total antes de filtros: {total_before_filters} (tenant: {tenant_id})")
        
        # Aplicar filtros de busca manualmente (mais eficiente que filter_backends)
        if search:
            from django.db.models import Q
            queryset = queryset.filter(
                Q(title__icontains=search) | Q(content__icontains=search)
            )
            logger.debug(f"🔍 [QUICK REPLIES] Após busca '{search}': {queryset.count()}")
        
        # Aplicar ordenação
        if ordering:
            queryset = queryset.order_by(*ordering.split(','))
        else:
            queryset = queryset.order_by('-use_count', 'title')
        
        # ✅ OTIMIZAÇÃO: Usar list() para avaliar queryset uma vez
        queryset_list = list(queryset)
        
        # ✅ DEBUG: Log final
        logger.info(f"📊 [QUICK REPLIES] Total retornado: {len(queryset_list)} (tenant: {tenant_id})")
        
        # Serializar dados
        serializer = self.get_serializer(queryset_list, many=True)
        response_data = {
            'results': serializer.data,
            'count': len(serializer.data)
        }
        
        # ✅ Salvar no cache
        cache.set(cache_key, response_data, CACHE_TTL_SECONDS)
        logger.debug(f"💾 [QUICK REPLIES] Cache salvo: {cache_key} (TTL: {CACHE_TTL_SECONDS}s)")
        
        return Response(response_data)
    
    def perform_create(self, serializer):
        """Define tenant e criador, invalida cache."""
        instance = serializer.save(
            tenant=self.request.user.tenant,
            created_by=self.request.user
        )
        # ✅ Invalidar cache após criar
        self._invalidate_cache(str(self.request.user.tenant.id))
        logger.info(f"✅ [QUICK REPLIES] Criada: {instance.title} (cache invalidado)")
    
    def perform_update(self, serializer):
        """Invalida cache após atualizar."""
        instance = serializer.save()
        # ✅ Invalidar cache após editar
        self._invalidate_cache(str(self.request.user.tenant.id))
        logger.info(f"✅ [QUICK REPLIES] Atualizada: {instance.title} (cache invalidado)")
    
    def perform_destroy(self, instance):
        """Invalida cache após deletar."""
        tenant_id = str(instance.tenant.id)
        instance.delete()
        # ✅ Invalidar cache após deletar
        self._invalidate_cache(tenant_id)
        logger.info(f"✅ [QUICK REPLIES] Deletada (cache invalidado)")
    
    @action(detail=True, methods=['post'], url_path='use')
    def mark_as_used(self, request, pk=None):
        """
        Incrementa contador de uso (chamado ao usar no chat).
        ✅ Invalida cache para atualizar ordenação.
        """
        quick_reply = self.get_object()
        quick_reply.use_count += 1
        quick_reply.save(update_fields=['use_count'])
        
        # ✅ Invalidar cache para atualizar ordenação (mais usadas primeiro)
        self._invalidate_cache(str(quick_reply.tenant.id))
        
        logger.debug(f"📊 [QUICK REPLIES] Uso incrementado: {quick_reply.title} ({quick_reply.use_count}x)")
        
        return Response({
            'use_count': quick_reply.use_count,
            'message': 'Contador atualizado'
        })

