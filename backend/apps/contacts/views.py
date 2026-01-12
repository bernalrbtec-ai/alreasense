"""
Views para o módulo de contatos
"""

from rest_framework import viewsets, status, serializers
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.http import HttpResponse
from django.db.models import Q, Avg
from django.utils import timezone
from datetime import timedelta

from .models import Contact, Tag, ContactList, ContactImport, ContactHistory, Task
from .serializers import (
    ContactSerializer,
    TagSerializer,
    ContactListSerializer,
    ContactImportSerializer,
    ContactHistorySerializer,
    ContactHistoryCreateSerializer,
    TaskSerializer,
    TaskCreateSerializer
)
from .services import ContactImportService, ContactExportService
from apps.common.rate_limiting import rate_limit_by_user


class ContactViewSet(viewsets.ModelViewSet):
    """
    ViewSet para CRUD de contatos
    
    Filtros disponíveis:
    - ?tags=uuid1,uuid2
    - ?lists=uuid1,uuid2
    - ?lifecycle_stage=customer
    - ?opted_out=false
    - ?search=maria
    """
    
    permission_classes = [IsAuthenticated]
    serializer_class = ContactSerializer
    search_fields = ['name', 'phone', 'email']
    
    def create(self, request, *args, **kwargs):
        """Override create to add detailed error logging"""
        import logging
        logger = logging.getLogger(__name__)
        
        logger.debug("Contact create request", extra={'data': request.data})
        try:
            return super().create(request, *args, **kwargs)
        except Exception as e:
            logger.error(
                f"Contact create error: {type(e).__name__}", 
                exc_info=True,
                extra={'error_message': str(e)}
            )
            raise
    
    def update(self, request, *args, **kwargs):
        """Override update to add detailed error logging"""
        import logging
        logger = logging.getLogger(__name__)
        
        logger.info(f"📝 [CONTACT UPDATE] Iniciando atualização. ID: {kwargs.get('pk')}")
        logger.debug(f"📝 [CONTACT UPDATE] Dados recebidos: {request.data}")
        
        try:
            instance = self.get_object()
            logger.debug(f"📝 [CONTACT UPDATE] Instância encontrada: {instance.name} ({instance.phone})")
            
            serializer = self.get_serializer(instance, data=request.data, partial=kwargs.get('partial', False))
            
            if serializer.is_valid():
                logger.debug(f"📝 [CONTACT UPDATE] Serializer válido, salvando...")
                self.perform_update(serializer)
                logger.info(f"✅ [CONTACT UPDATE] Contato atualizado com sucesso: {instance.id}")
                
                # ✅ CORREÇÃO: Recarregar instância do banco para garantir dados atualizados
                instance.refresh_from_db()
                serializer = self.get_serializer(instance)
                
                return Response(serializer.data)
            else:
                logger.error(f"❌ [CONTACT UPDATE] Erros de validação: {serializer.errors}")
                return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
                
        except Exception as e:
            logger.error(
                f"❌ [CONTACT UPDATE] Erro ao atualizar contato: {type(e).__name__}: {str(e)}", 
                exc_info=True,
                extra={'error_message': str(e), 'request_data': request.data}
            )
            raise
    
    def get_queryset(self):
        """Retorna apenas contatos do tenant do usuário"""
        user = self.request.user
        
        # REGRA: Cada cliente vê APENAS seus dados
        # Superadmin NÃO vê dados individuais de clientes
        if not user.tenant:
            return Contact.objects.none()
        
        qs = Contact.objects.filter(tenant=user.tenant).select_related('tenant', 'created_by')
        
        qs = qs.prefetch_related('tags', 'lists')
        
        # Filtros customizados
        tags = self.request.query_params.get('tags')
        if tags:
            tag_ids = tags.split(',')
            qs = qs.filter(tags__id__in=tag_ids).distinct()
        
        lists = self.request.query_params.get('lists')
        if lists:
            list_ids = lists.split(',')
            qs = qs.filter(lists__id__in=list_ids).distinct()
        
        # Busca full-text
        search = self.request.query_params.get('search')
        if search:
            qs = qs.filter(
                Q(name__icontains=search) |
                Q(phone__icontains=search) |
                Q(email__icontains=search)
            )
        
        # Filtro por lifecycle_stage
        lifecycle_stage = self.request.query_params.get('lifecycle_stage')
        if lifecycle_stage:
            qs = qs.filter(lifecycle_stage=lifecycle_stage)
        
        # Filtro por estado
        state = self.request.query_params.get('state')
        if state:
            qs = qs.filter(state=state)
        
        # Filtro opted_out
        opted_out = self.request.query_params.get('opted_out')
        if opted_out is not None:
            qs = qs.filter(opted_out=opted_out.lower() == 'true')
        
        # Filtro is_active
        is_active = self.request.query_params.get('is_active')
        if is_active is not None:
            qs = qs.filter(is_active=is_active.lower() == 'true')
        
        return qs
    
    def perform_create(self, serializer):
        """Associa tenant e usuário na criação"""
        serializer.save(
            tenant=self.request.user.tenant,
            created_by=self.request.user
        )
    
    def perform_update(self, serializer):
        """Atualiza contato - signal faz broadcast automaticamente"""
        # ✅ CORREÇÃO: Signal já faz broadcast, não precisa duplicar aqui
        # O signal update_conversations_on_contact_change já:
        # 1. Atualiza contact_name nas conversas
        # 2. Faz broadcast via WebSocket
        # 3. Invalida cache de tags
        instance = serializer.save()
        return instance
    
    @action(detail=False, methods=['post'])
    def preview_csv(self, request):
        """
        Preview do CSV antes de importar
        
        POST /api/contacts/contacts/preview_csv/
        Body: multipart/form-data
        - file: CSV file
        """
        file = request.FILES.get('file')
        if not file:
            return Response(
                {'error': 'Arquivo CSV não fornecido'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Validar extensão
        if not file.name.endswith('.csv'):
            return Response(
                {'error': 'Arquivo deve ser CSV'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Validar tamanho (max 10 MB)
        if file.size > 10 * 1024 * 1024:
            return Response(
                {'error': 'Arquivo muito grande. Máximo: 10 MB'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Gerar preview
        service = ContactImportService(
            tenant=request.user.tenant,
            user=request.user
        )
        
        result = service.preview_csv(file)
        
        if result['status'] == 'error':
            return Response(result, status=status.HTTP_400_BAD_REQUEST)
        
        return Response(result)
    
    @action(detail=False, methods=['post'])
    @rate_limit_by_user(rate='10/h', method='POST')  # ✅ CRITICAL: Rate limit - 10 importações por hora
    def import_csv(self, request):
        """
        Importação em massa via CSV
        
        POST /api/contacts/contacts/import_csv/
        Body: multipart/form-data
        - file: CSV file
        - update_existing: bool
        - auto_tag_id: UUID (optional)
        - async_processing: bool (default: True para >100 linhas)
        """
        file = request.FILES.get('file')
        if not file:
            return Response(
                {'error': 'Arquivo CSV não fornecido'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Validar extensão
        if not file.name.endswith('.csv'):
            return Response(
                {'error': 'Arquivo deve ser CSV'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Validar tamanho (max 10 MB)
        if file.size > 10 * 1024 * 1024:
            return Response(
                {'error': 'Arquivo muito grande. Máximo: 10 MB'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Determinar se processa assíncrono ou síncrono
        # DESABILITAR async temporariamente até corrigir passagem de column_mapping
        async_processing = False  # request.data.get('async_processing', 'true').lower() == 'true'
        
        # Se for assíncrono, disparar Celery task
        if async_processing:
            # from .tasks import process_contact_import_async  # Removido - Celery deletado
            
            # Salvar arquivo temporariamente
            import os
            from django.conf import settings
            
            temp_dir = os.path.join(settings.MEDIA_ROOT, 'temp_imports')
            os.makedirs(temp_dir, exist_ok=True)
            
            temp_file_path = os.path.join(temp_dir, f'{request.user.tenant.id}_{file.name}')
            
            with open(temp_file_path, 'wb+') as destination:
                for chunk in file.chunks():
                    destination.write(chunk)
            
            # Criar registro de importação
            import_record = ContactImport.objects.create(
                tenant=request.user.tenant,
                file_name=file.name,
                file_path=temp_file_path,
                created_by=request.user,
                update_existing=request.data.get('update_existing', 'false').lower() == 'true',
                status=ContactImport.Status.PENDING
            )
            
            if request.data.get('auto_tag_id'):
                try:
                    import_record.auto_tag_id = request.data.get('auto_tag_id')
                    import_record.save()
                except:
                    pass
            
            # Disparar task assíncrona
            # process_contact_import_async.delay(  # Removido - Celery deletado
            #     import_id=str(import_record.id),
            #     tenant_id=str(request.user.tenant.id),
            #     user_id=str(request.user.id)
            # )
            # TODO: Implementar com RabbitMQ
            
            return Response({
                'status': 'processing',
                'import_id': str(import_record.id),
                'message': 'Importação iniciada. Você será notificado quando concluir.'
            })
        
        # Processar síncrono (para arquivos pequenos)
        service = ContactImportService(
            tenant=request.user.tenant,
            user=request.user
        )
        
        # Extrair column_mapping se fornecido
        import logging
        logger = logging.getLogger(__name__)
        
        column_mapping = None
        if request.data.get('column_mapping'):
            import json
            try:
                column_mapping = json.loads(request.data.get('column_mapping'))
                logger.debug("Column mapping recebido", extra={'column_mapping': column_mapping})
            except Exception as e:
                logger.warning("Erro ao parsear column_mapping", exc_info=True, extra={'error': str(e)})
                pass
        else:
            logger.debug("Nenhum column_mapping recebido do frontend")
        
        delimiter = request.data.get('delimiter')
        logger.debug("Parâmetros de importação", extra={
            'delimiter': delimiter,
            'auto_tag_id': request.data.get('auto_tag_id'),
            'update_existing': request.data.get('update_existing')
        })
        
        result = service.process_csv(
            file=file,
            update_existing=request.data.get('update_existing', 'false').lower() == 'true',
            auto_tag_id=request.data.get('auto_tag_id'),
            delimiter=delimiter,
            column_mapping=column_mapping
        )
        
        # Log detalhado da resposta para debug
        # ✅ CORREÇÃO: Não usar 'created' no extra (campo reservado do LogRecord)
        logger.info("Importação CSV processada", extra={
            'status': result.get('status'),
            'total_rows': result.get('total_rows', 0),
            'created_count': result.get('created', 0),  # ✅ Mudado de 'created' para 'created_count'
            'errors_count': result.get('errors', 0)  # ✅ Mudado de 'errors' para 'errors_count'
        })
        
        return Response(result)
    
    @action(detail=False, methods=['get'])
    def export_csv(self, request):
        """
        Exportação para CSV
        
        GET /api/contacts/contacts/export_csv/
        Query params: mesmos filtros do list
        """
        contacts = self.filter_queryset(self.get_queryset())
        
        service = ContactExportService()
        csv_content = service.export_to_csv(contacts)
        
        response = HttpResponse(csv_content, content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="contacts_{timezone.now().strftime("%Y%m%d")}.csv"'
        return response
    
    @action(detail=False, methods=['get'])
    def stats(self, request):
        """
        Estatísticas básicas dos contatos para dashboard
        
        GET /api/contacts/contacts/stats/
        Query params: mesmos filtros do list (tags, state, search, etc.)
        """
        from apps.common.cache_manager import CacheManager
        import hashlib
        
        user = request.user
        
        # ✅ PERFORMANCE: Gerar chave de cache baseada nos filtros
        filter_params = {
            'tags': request.query_params.get('tags'),
            'lists': request.query_params.get('lists'),
            'search': request.query_params.get('search'),
            'lifecycle_stage': request.query_params.get('lifecycle_stage'),
            'state': request.query_params.get('state'),
            'opted_out': request.query_params.get('opted_out'),
            'is_active': request.query_params.get('is_active'),
        }
        filter_hash = hashlib.md5(str(filter_params).encode()).hexdigest()
        cache_key = CacheManager.make_key('contact_stats', user.tenant_id, filter_hash)
        
        def calculate_stats():
            # Aplicar mesmos filtros do get_queryset
            contacts = self.filter_queryset(self.get_queryset())
            
            # ✅ FIX: Usar queries separadas para evitar conflitos com aggregates
            # Isso evita o erro "opted_out is an aggregate" que pode ocorrer
            # quando há annotations ou aggregates pré-existentes no queryset
            from django.db.models import Q
            
            # Criar queryset base limpo (sem annotations)
            base_queryset = Contact.objects.filter(
                tenant=user.tenant
            )
            
            # Aplicar mesmos filtros do get_queryset manualmente
            tags = request.query_params.get('tags')
            if tags:
                tag_ids = tags.split(',')
                base_queryset = base_queryset.filter(tags__id__in=tag_ids).distinct()
            
            lists = request.query_params.get('lists')
            if lists:
                list_ids = lists.split(',')
                base_queryset = base_queryset.filter(lists__id__in=list_ids).distinct()
            
            search = request.query_params.get('search')
            if search:
                base_queryset = base_queryset.filter(
                    Q(name__icontains=search) |
                    Q(phone__icontains=search) |
                    Q(email__icontains=search)
                )
            
            lifecycle_stage = request.query_params.get('lifecycle_stage')
            if lifecycle_stage:
                base_queryset = base_queryset.filter(lifecycle_stage=lifecycle_stage)
            
            state = request.query_params.get('state')
            if state:
                base_queryset = base_queryset.filter(state=state)
            
            opted_out_param = request.query_params.get('opted_out')
            if opted_out_param is not None:
                base_queryset = base_queryset.filter(opted_out=opted_out_param.lower() == 'true')
            
            is_active_param = request.query_params.get('is_active')
            if is_active_param is not None:
                base_queryset = base_queryset.filter(is_active=is_active_param.lower() == 'true')
            
            # ✅ PERFORMANCE: Calcular estatísticas com queryset limpo
            total = base_queryset.count()
            opted_out = base_queryset.filter(opted_out=True).count()
            active = base_queryset.filter(is_active=True).count()
            leads = base_queryset.filter(total_purchases=0).count()
            customers = base_queryset.filter(total_purchases__gte=1).count()
            delivery_problems = base_queryset.filter(opted_out=True).count()  # Usando opted_out como proxy
            
            return {
                'total': total,
                'active': active,
                'opted_out': opted_out,
                'leads': leads,
                'customers': customers,
                'delivery_problems': delivery_problems,
                'filters_applied': {
                    'search': bool(request.query_params.get('search')),
                    'tags': bool(request.query_params.get('tags')),
                    'state': bool(request.query_params.get('state')),
                    'lifecycle_stage': bool(request.query_params.get('lifecycle_stage')),
                    'opted_out': bool(request.query_params.get('opted_out')),
                    'is_active': bool(request.query_params.get('is_active'))
                }
            }
        
        # ✅ PERFORMANCE: Cache por 2 minutos (stats podem mudar rapidamente)
        stats_data = CacheManager.get_or_set(
            cache_key,
            calculate_stats,
            ttl=CacheManager.TTL_MINUTE * 2
        )
        
        return Response(stats_data)
    
    @action(detail=False, methods=['get'])
    def insights(self, request):
        """
        Métricas e insights dos contatos
        
        GET /api/contacts/contacts/insights/
        """
        user = request.user
        
        if user.is_superuser:
            contacts = Contact.objects.filter(is_active=True)
        else:
            contacts = Contact.objects.filter(tenant=user.tenant, is_active=True)
        
        # ✅ PERFORMANCE: Usar aggregate em vez de múltiplos count() separados
        from django.db.models import Count, Q, Avg
        stats = contacts.aggregate(
            total=Count('id'),
            opted_out=Count('id', filter=Q(opted_out=True)),
            leads=Count('id', filter=Q(total_purchases=0)),
            customers=Count('id', filter=Q(total_purchases__gte=1)),
            avg_ltv=Avg('lifetime_value')
        )
        
        total = stats['total']
        opted_out = stats['opted_out']
        leads = stats['leads']
        customers = stats['customers']
        
        # ✅ PERFORMANCE: Aniversariantes próximos (7 dias) - otimizado
        # Calcular aniversariantes usando queryset ao invés de loop Python
        from datetime import timedelta
        today = timezone.now().date()
        seven_days_later = today + timedelta(days=7)
        
        # Filtrar contatos com aniversário nos próximos 7 dias
        upcoming_birthdays_qs = contacts.exclude(birth_date__isnull=True).filter(
            birth_date__month__in=[
                today.month if today.month <= 12 else 1,
                (today.month + 1) if today.month < 12 else 1
            ]
        )[:10]  # Limitar a 10 resultados
        
        upcoming_birthdays = []
        for contact in upcoming_birthdays_qs:
            if contact.is_birthday_soon(7):
                upcoming_birthdays.append({
                    'id': str(contact.id),
                    'name': contact.name,
                    'phone': contact.phone,
                    'days_until': contact.days_until_birthday
                })
        
        # Churn alerts (90+ dias sem compra)
        churn_date = timezone.now().date() - timedelta(days=90)
        churn_alerts = contacts.filter(
            last_purchase_date__lt=churn_date,
            total_purchases__gte=1
        ).count()
        
        # ✅ PERFORMANCE: avg_ltv já foi calculado no aggregate acima
        avg_ltv = stats['avg_ltv'] or 0
        
        return Response({
            'total_contacts': total,
            'opted_out': opted_out,
            'lifecycle_breakdown': {
                'lead': leads,
                'customer': customers,
                'at_risk': 0,  # Calcular via Python seria muito custoso
                'churned': 0
            },
            'upcoming_birthdays': upcoming_birthdays[:10],  # Top 10
            'churn_alerts': churn_alerts,
            'average_ltv': float(avg_ltv)
        })
    
    @action(detail=True, methods=['post'])
    def opt_out(self, request, pk=None):
        """Marca contato como opted-out"""
        contact = self.get_object()
        contact.opt_out()
        return Response({'status': 'opted_out', 'message': 'Contato marcado como opted-out'})
    
    @action(detail=True, methods=['post'])
    def opt_in(self, request, pk=None):
        """Reverte opt-out"""
        contact = self.get_object()
        contact.opt_in()
        return Response({'status': 'opted_in', 'message': 'Contato reativado'})
    
    @action(detail=True, methods=['post'])
    def add_purchase(self, request, pk=None):
        """
        Registra uma compra para o contato
        
        POST /api/contacts/contacts/{id}/add_purchase/
        Body: {"value": 150.00, "date": "2024-10-10"}
        """
        contact = self.get_object()
        
        value = request.data.get('value')
        date_str = request.data.get('date')
        
        if not value:
            return Response(
                {'error': 'Campo "value" é obrigatório'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        from decimal import Decimal
        from datetime import datetime
        
        try:
            value = Decimal(str(value))
        except:
            return Response(
                {'error': 'Valor inválido'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        date = None
        if date_str:
            try:
                date = datetime.strptime(date_str, '%Y-%m-%d').date()
            except:
                return Response(
                    {'error': 'Data inválida. Use formato YYYY-MM-DD'},
                    status=status.HTTP_400_BAD_REQUEST
                )
        
        contact.add_purchase(value, date)
        
        return Response({
            'status': 'success',
            'message': 'Compra registrada',
            'contact': ContactSerializer(contact).data
        })


class TagViewSet(viewsets.ModelViewSet):
    """ViewSet para gerenciar tags de contatos"""
    
    permission_classes = [IsAuthenticated]
    serializer_class = TagSerializer
    
    def get_queryset(self):
        """Retorna apenas tags do tenant do usuário"""
        user = self.request.user
        
        if not user.tenant:
            return Tag.objects.none()
        
        return Tag.objects.filter(tenant=user.tenant).prefetch_related('contacts')
    
    def perform_create(self, serializer):
        """Associa tenant na criação com tratamento de duplicação"""
        from django.db import IntegrityError
        
        try:
            serializer.save(tenant=self.request.user.tenant)
        except IntegrityError as e:
            if 'unique constraint' in str(e).lower() and 'tenant_id_name' in str(e):
                # Tag já existe para este tenant
                tag_name = serializer.validated_data.get('name', '')
                raise serializers.ValidationError({
                    'name': f'A tag "{tag_name}" já existe. Escolha um nome diferente.'
                })
            else:
                # Outro erro de integridade
                raise serializers.ValidationError({
                    'non_field_errors': ['Erro ao criar tag. Tente novamente.']
                })
    
    @action(detail=True, methods=['delete'])
    def delete_with_options(self, request, pk=None):
        """
        Deleta tag com opções:
        - delete_contacts: Se True, deleta todos os contatos associados
        - migrate_to_tag_id: ID da tag para migrar os contatos antes de deletar
        - Se ambos False/None, apenas remove a tag dos contatos
        
        DELETE /api/contacts/tags/{id}/delete_with_options/?delete_contacts=true
        DELETE /api/contacts/tags/{id}/delete_with_options/?migrate_to_tag_id=uuid
        """
        tag = self.get_object()
        delete_contacts = request.query_params.get('delete_contacts', 'false').lower() == 'true'
        migrate_to_tag_id = request.query_params.get('migrate_to_tag_id')
        
        # Contar contatos antes de deletar
        contact_count = tag.contacts.count()
        
        if delete_contacts:
            # Deletar todos os contatos associados
            tag.contacts.all().delete()
            message = f'Tag "{tag.name}" e {contact_count} contatos associados foram deletados.'
            contacts_deleted = contact_count
            contacts_migrated = 0
        elif migrate_to_tag_id:
            # Migrar contatos para outra tag antes de deletar
            try:
                target_tag = Tag.objects.get(id=migrate_to_tag_id, tenant=request.user.tenant)
                contacts = tag.contacts.all()
                
                # Adicionar a nova tag aos contatos (sem remover outras tags)
                for contact in contacts:
                    contact.tags.add(target_tag)
                
                # Remover a tag antiga dos contatos
                tag.contacts.clear()
                
                message = f'Tag "{tag.name}" foi deletada. {contact_count} contato(s) foram migrado(s) para a tag "{target_tag.name}".'
                contacts_deleted = 0
                contacts_migrated = contact_count
            except Tag.DoesNotExist:
                return Response({
                    'status': 'error',
                    'message': f'Tag de destino não encontrada.',
                    'error': 'TAG_NOT_FOUND'
                }, status=status.HTTP_404_NOT_FOUND)
        else:
            # Apenas remover a tag dos contatos (não deletar os contatos)
            tag.contacts.clear()
            message = f'Tag "{tag.name}" foi deletada. {contact_count} contato(s) foram atualizado(s).'
            contacts_deleted = 0
            contacts_migrated = 0
        
        # Deletar a tag
        tag.delete()
        
        return Response({
            'status': 'success',
            'message': message,
            'contacts_affected': contact_count,
            'contacts_deleted': contacts_deleted,
            'contacts_migrated': contacts_migrated
        })
    
    @action(detail=False, methods=['get'])
    def stats(self, request):
        """
        Estatísticas das tags com contagem real de contatos
        
        GET /api/contacts/tags/stats/
        """
        from apps.common.cache_manager import CacheManager
        
        user = request.user
        
        if not user.tenant:
            return Response({'tags': []})
        
        cache_key = CacheManager.make_key('tag_stats', user.tenant_id)
        
        def calculate_stats():
            # ✅ PERFORMANCE: Usar annotate para calcular contagens em uma query
            from django.db.models import Count, Q
            
            tags = Tag.objects.filter(tenant=user.tenant).annotate(
                total_contacts=Count('contacts', filter=Q(contacts__is_active=True), distinct=True),
                opted_out_contacts=Count('contacts', filter=Q(contacts__is_active=True, contacts__opted_out=True), distinct=True)
            )
            
            # Converter para lista de dicionários
            tags_stats = [
                {
                    'id': str(tag.id),
                    'name': tag.name,
                    'color': tag.color,
                    'description': tag.description,
                    'contact_count': tag.total_contacts,
                    'opted_out_count': tag.opted_out_contacts,
                    'active_count': tag.total_contacts - tag.opted_out_contacts,
                    'created_at': tag.created_at
                }
                for tag in tags
            ]
            
            return {
                'tags': tags_stats,
                'total_tags': len(tags_stats)
            }
        
        # ✅ PERFORMANCE: Cache por 5 minutos (tags mudam menos frequentemente)
        stats_data = CacheManager.get_or_set(
            cache_key,
            calculate_stats,
            ttl=CacheManager.TTL_MINUTE * 5
        )
        
        return Response(stats_data)


class ContactListViewSet(viewsets.ModelViewSet):
    """ViewSet para gerenciar listas de contatos"""
    
    permission_classes = [IsAuthenticated]
    serializer_class = ContactListSerializer
    
    def get_queryset(self):
        """Retorna apenas listas do tenant do usuário"""
        user = self.request.user
        
        if not user.tenant:
            return ContactList.objects.none()
        
        return ContactList.objects.filter(tenant=user.tenant)
    
    def perform_create(self, serializer):
        """Associa tenant e usuário na criação"""
        serializer.save(
            tenant=self.request.user.tenant,
            created_by=self.request.user
        )


class ContactImportViewSet(viewsets.ReadOnlyModelViewSet):
    """ViewSet para visualizar histórico de importações"""
    
    permission_classes = [IsAuthenticated]
    serializer_class = ContactImportSerializer
    
    def get_queryset(self):
        """Retorna apenas importações do tenant do usuário"""
        user = self.request.user
        
        if user.is_superuser:
            return ContactImport.objects.all()
        
        return ContactImport.objects.filter(tenant=user.tenant)


class ContactHistoryViewSet(viewsets.ModelViewSet):
    """
    ViewSet para histórico de contatos.
    Permite listar, criar (anotações) e editar (apenas anotações editáveis).
    """
    
    permission_classes = [IsAuthenticated]
    serializer_class = ContactHistorySerializer
    
    def get_queryset(self):
        """Retorna histórico do contato especificado"""
        user = self.request.user
        contact_id = self.request.query_params.get('contact_id')
        
        if not contact_id:
            return ContactHistory.objects.none()
        
        # Verificar se o contato pertence ao tenant do usuário
        try:
            contact = Contact.objects.get(id=contact_id, tenant=user.tenant)
        except Contact.DoesNotExist:
            return ContactHistory.objects.none()
        
        # Retornar histórico ordenado por data (mais recente primeiro)
        return ContactHistory.objects.filter(
            contact=contact,
            tenant=user.tenant
        ).select_related('created_by', 'related_conversation', 'related_campaign', 'related_message')
    
    def get_serializer_class(self):
        """Usa serializer de criação para POST"""
        if self.action == 'create':
            return ContactHistoryCreateSerializer
        return ContactHistorySerializer
    
    def perform_create(self, serializer):
        """Cria anotação manual"""
        contact_id = self.request.data.get('contact_id')
        if not contact_id:
            raise serializers.ValidationError({'contact_id': 'Este campo é obrigatório'})
        
        try:
            contact = Contact.objects.get(id=contact_id, tenant=self.request.user.tenant)
        except Contact.DoesNotExist:
            raise serializers.ValidationError({'contact_id': 'Contato não encontrado'})
        
        # Passar contexto para o serializer
        serializer.context['contact'] = contact
        serializer.context['tenant'] = self.request.user.tenant
        serializer.context['user'] = self.request.user
        
        serializer.save()
    
    def perform_update(self, serializer):
        """Permite editar apenas anotações editáveis"""
        instance = self.get_object()
        
        if not instance.is_editable:
            raise serializers.ValidationError('Apenas anotações manuais podem ser editadas')
        
        serializer.save()
    
    def perform_destroy(self, instance):
        """Permite deletar apenas anotações editáveis"""
        if not instance.is_editable:
            raise serializers.ValidationError('Apenas anotações manuais podem ser deletadas')
        
        instance.delete()


from apps.billing.decorators import require_product
from apps.authn.permissions import CanAccessAgenda


class TaskViewSet(viewsets.ModelViewSet):
    """
    ViewSet para tarefas e agenda.
    
    Acesso permitido se:
    - Usuário tem acesso ao chat (admin, gerente ou agente) OU
    - Tenant tem produto workflow ativo
    
    Filtros disponíveis:
    - ?status=pending
    - ?assigned_to=<user_id>
    - ?department=<department_id>
    - ?my_tasks=true (apenas tarefas atribuídas para mim)
    - ?created_by_me=true (apenas tarefas que criei)
    - ?has_due_date=true (apenas tarefas com data agendada)
    - ?overdue=true (apenas tarefas atrasadas)
    - ?contact_id=<contact_id> (tarefas relacionadas a um contato)
    """
    
    permission_classes = [IsAuthenticated, CanAccessAgenda]
    serializer_class = TaskSerializer
    filterset_fields = ['status', 'priority', 'department', 'assigned_to']
    search_fields = ['title', 'description']
    ordering_fields = ['created_at', 'due_date', 'priority', 'status']
    ordering = ['-created_at']
    
    def get_queryset(self):
        """Retorna tarefas dos departamentos do usuário"""
        user = self.request.user
        
        # Base: tarefas do tenant
        queryset = Task.objects.filter(tenant=user.tenant)
        
        # ✅ CORREÇÃO: Usar is_admin ao invés de role != 'admin' para consistência
        # Admin vê tudo do tenant, outros usuários vêem baseado em departamento OU atribuição
        if not user.is_admin:
            # Pegar IDs dos departamentos do usuário
            department_ids = list(user.departments.values_list('id', flat=True))
            
            if department_ids:
                # ✅ Usuário tem departamentos: ver tarefas dos departamentos OU atribuídas diretamente a ele
                queryset = queryset.filter(
                    Q(department__in=department_ids) | 
                    Q(assigned_to=user)  # Sempre mostrar tarefas atribuídas diretamente ao usuário
                ).distinct()
            else:
                # ✅ Usuário SEM departamentos: ver apenas tarefas atribuídas diretamente a ele
                # Isso garante que usuários sem departamentos vejam suas próprias tarefas
                queryset = queryset.filter(assigned_to=user)
        
        # Filtros adicionais
        my_tasks = self.request.query_params.get('my_tasks', '').lower() == 'true'
        if my_tasks:
            queryset = queryset.filter(assigned_to=user)
        
        created_by_me = self.request.query_params.get('created_by_me', '').lower() == 'true'
        if created_by_me:
            queryset = queryset.filter(created_by=user)
        
        has_due_date = self.request.query_params.get('has_due_date', '').lower() == 'true'
        if has_due_date:
            queryset = queryset.exclude(due_date__isnull=True)
        
        overdue = self.request.query_params.get('overdue', '').lower() == 'true'
        if overdue:
            from django.utils import timezone
            queryset = queryset.filter(
                due_date__lt=timezone.now(),
                status__in=['pending', 'in_progress']
            )
        
        contact_id = self.request.query_params.get('contact_id')
        if contact_id:
            queryset = queryset.filter(related_contacts__id=contact_id).distinct()
        
        return queryset.select_related(
            'tenant', 'department', 'assigned_to', 'created_by'
        ).prefetch_related('related_contacts')
    
    def get_serializer_class(self):
        """Usa serializer de criação para POST/PUT"""
        if self.action in ['create', 'update', 'partial_update']:
            return TaskCreateSerializer
        return TaskSerializer
    
    def perform_create(self, serializer):
        """Cria tarefa com tenant e criador"""
        serializer.save(
            tenant=self.request.user.tenant,
            created_by=self.request.user
        )
    
    def perform_update(self, serializer):
        """Atualiza tarefa e passa usuário para o signal"""
        # ✅ NOVO: Passar usuário que fez a mudança para o signal
        task = serializer.instance
        task._changed_by = self.request.user
        serializer.save()
    
    @action(detail=True, methods=['get'])
    def history(self, request, pk=None):
        """Retorna histórico de mudanças da tarefa"""
        task = self.get_object()
        from apps.contacts.models import TaskHistory
        from apps.contacts.serializers import TaskHistorySerializer
        
        history = TaskHistory.objects.filter(task=task).select_related(
            'changed_by', 'old_assigned_to', 'new_assigned_to'
        ).order_by('-created_at')
        serializer = TaskHistorySerializer(history, many=True)
        return Response(serializer.data)
    
    @action(detail=True, methods=['post'])
    def complete(self, request, pk=None):
        """Marca tarefa como concluída"""
        task = self.get_object()
        
        if task.status == 'completed':
            return Response(
                {'detail': 'Tarefa já está concluída'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        task.mark_completed(user=request.user)
        
        serializer = self.get_serializer(task)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def stats(self, request):
        """Estatísticas de tarefas do usuário"""
        from apps.common.cache_manager import CacheManager
        
        user = request.user
        
        # ✅ PERFORMANCE: Gerar chave de cache baseada no usuário e departamentos
        dept_ids = list(user.departments.values_list('id', flat=True))
        cache_key = CacheManager.make_key('task_stats', user.tenant_id, user.id, dept_ids=dept_ids)
        
        def calculate_stats():
            # Base: tarefas dos departamentos do usuário
            queryset = Task.objects.filter(tenant=user.tenant)
            
            if not user.is_superuser and user.role != 'admin':
                user_departments = user.departments.all()
                queryset = queryset.filter(department__in=user_departments)
            
            # ✅ PERFORMANCE: Usar aggregate em vez de múltiplos count() separados
            from django.db.models import Count, Q
            from django.utils import timezone
            now = timezone.now()
            
            stats_dict = queryset.aggregate(
                total=Count('id'),
                pending=Count('id', filter=Q(status='pending')),
                in_progress=Count('id', filter=Q(status='in_progress')),
                completed=Count('id', filter=Q(status='completed')),
                cancelled=Count('id', filter=Q(status='cancelled')),
                my_assigned=Count('id', filter=Q(assigned_to=user, status__in=['pending', 'in_progress'])),
                overdue=Count('id', filter=Q(due_date__lt=now, status__in=['pending', 'in_progress'])),
                with_due_date=Count('id', filter=~Q(due_date__isnull=True))
            )
            
            return {
                'total': stats_dict['total'],
                'pending': stats_dict['pending'],
                'in_progress': stats_dict['in_progress'],
                'completed': stats_dict['completed'],
                'cancelled': stats_dict['cancelled'],
                'my_assigned': stats_dict['my_assigned'],
                'overdue': stats_dict['overdue'],
                'with_due_date': stats_dict['with_due_date'],
            }
        
        # ✅ PERFORMANCE: Cache por 2 minutos (tarefas mudam frequentemente)
        stats_data = CacheManager.get_or_set(
            cache_key,
            calculate_stats,
            ttl=CacheManager.TTL_MINUTE * 2
        )
        
        return Response(stats_data)
