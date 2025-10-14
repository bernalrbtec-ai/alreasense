"""
Views para o módulo de contatos
"""

from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.http import HttpResponse
from django.db.models import Q, Avg
from django.utils import timezone
from datetime import timedelta

from .models import Contact, Tag, ContactList, ContactImport
from .serializers import (
    ContactSerializer,
    TagSerializer,
    ContactListSerializer,
    ContactImportSerializer
)
from .services import ContactImportService, ContactExportService


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
        print(f"🔍 CREATE REQUEST DATA: {request.data}")
        try:
            return super().create(request, *args, **kwargs)
        except Exception as e:
            print(f"❌ CREATE ERROR: {type(e).__name__}: {str(e)}")
            import traceback
            traceback.print_exc()
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
        column_mapping = None
        if request.data.get('column_mapping'):
            import json
            try:
                column_mapping = json.loads(request.data.get('column_mapping'))
                print(f"📋 Column mapping recebido: {column_mapping}")
            except Exception as e:
                print(f"❌ Erro ao parsear column_mapping: {e}")
                pass
        else:
            print(f"⚠️ Nenhum column_mapping recebido do frontend")
        
        delimiter = request.data.get('delimiter')
        print(f"📋 Delimiter recebido: {delimiter}")
        print(f"📋 Auto tag ID: {request.data.get('auto_tag_id')}")
        print(f"📋 Update existing: {request.data.get('update_existing')}")
        
        result = service.process_csv(
            file=file,
            update_existing=request.data.get('update_existing', 'false').lower() == 'true',
            auto_tag_id=request.data.get('auto_tag_id'),
            delimiter=delimiter,
            column_mapping=column_mapping
        )
        
        # Log detalhado da resposta para debug
        print(f"📤 RESPOSTA do process_csv:")
        print(f"   Status: {result.get('status')}")
        print(f"   Total rows: {result.get('total_rows', 0)}")
        print(f"   Created: {result.get('created', 0)}")
        print(f"   Errors: {result.get('errors', 0)}")
        
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
        user = request.user
        
        # Aplicar mesmos filtros do get_queryset
        contacts = self.filter_queryset(self.get_queryset())
        
        # Contadores básicos
        total = contacts.count()
        opted_out = contacts.filter(opted_out=True).count()
        active = contacts.filter(is_active=True).count()
        
        # Segmentação por lifecycle
        leads = contacts.filter(total_purchases=0).count()
        customers = contacts.filter(total_purchases__gte=1).count()
        
        # Contatos com problemas de entrega (usando campos disponíveis)
        # Por enquanto, usar opted_out como proxy para problemas de entrega
        delivery_problems = contacts.filter(opted_out=True).count()
        
        return Response({
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
        })
    
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
        
        # Contadores básicos
        total = contacts.count()
        opted_out = contacts.filter(opted_out=True).count()
        
        # Segmentação por lifecycle (simplificada)
        leads = contacts.filter(total_purchases=0).count()
        customers = contacts.filter(total_purchases__gte=1).count()
        
        # Aniversariantes próximos (7 dias)
        upcoming_birthdays = []
        for contact in contacts.exclude(birth_date__isnull=True)[:100]:  # Limitar para performance
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
        
        # LTV médio
        avg_ltv = contacts.aggregate(avg_ltv=Avg('lifetime_value'))['avg_ltv'] or 0
        
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
        
        return Tag.objects.filter(tenant=user.tenant)
    
    def perform_create(self, serializer):
        """Associa tenant na criação"""
        serializer.save(tenant=self.request.user.tenant)
    
    @action(detail=False, methods=['get'])
    def stats(self, request):
        """
        Estatísticas das tags com contagem real de contatos
        
        GET /api/contacts/tags/stats/
        """
        user = request.user
        
        if not user.tenant:
            return Response({'tags': []})
        
        tags = Tag.objects.filter(tenant=user.tenant)
        
        # Calcular contagem real de contatos para cada tag
        tags_stats = []
        for tag in tags:
            # Contagem real sem paginação
            total_contacts = tag.contacts.filter(is_active=True).count()
            opted_out_contacts = tag.contacts.filter(is_active=True, opted_out=True).count()
            
            tags_stats.append({
                'id': str(tag.id),
                'name': tag.name,
                'color': tag.color,
                'description': tag.description,
                'contact_count': total_contacts,
                'opted_out_count': opted_out_contacts,
                'active_count': total_contacts - opted_out_contacts,
                'created_at': tag.created_at
            })
        
        return Response({
            'tags': tags_stats,
            'total_tags': len(tags_stats)
        })


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
