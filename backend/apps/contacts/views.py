from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.shortcuts import get_object_or_404
from apps.contacts.models import Contact, ContactGroup
from apps.contacts.serializers import (
    ContactSerializer, ContactGroupSerializer, ContactGroupDetailSerializer
)
from apps.billing.decorators import require_product


@require_product('flow')
class ContactViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    serializer_class = ContactSerializer
    
    def get_queryset(self):
        return Contact.objects.filter(tenant=self.request.tenant)
    
    def perform_create(self, serializer):
        serializer.save(tenant=self.request.tenant)
    
    @action(detail=False, methods=['post'])
    def bulk_create(self, request):
        """Criar múltiplos contatos de uma vez"""
        contacts_data = request.data.get('contacts', [])
        
        if not contacts_data:
            return Response(
                {'error': 'Nenhum contato fornecido'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        created = []
        errors = []
        
        for idx, contact_data in enumerate(contacts_data):
            serializer = ContactSerializer(data=contact_data, context={'request': request})
            if serializer.is_valid():
                contact = serializer.save(tenant=request.tenant)
                created.append(contact)
            else:
                errors.append({'index': idx, 'errors': serializer.errors})
        
        return Response({
            'created': len(created),
            'errors': errors,
            'contacts': ContactSerializer(created, many=True).data
        }, status=status.HTTP_201_CREATED if created else status.HTTP_400_BAD_REQUEST)


@require_product('flow')
class ContactGroupViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        return ContactGroup.objects.filter(tenant=self.request.tenant)
    
    def get_serializer_class(self):
        if self.action == 'retrieve':
            return ContactGroupDetailSerializer
        return ContactGroupSerializer
    
    def perform_create(self, serializer):
        serializer.save(tenant=self.request.tenant)
    
    @action(detail=True, methods=['post'])
    def add_contacts(self, request, pk=None):
        """Adicionar contatos ao grupo"""
        group = self.get_object()
        contact_ids = request.data.get('contact_ids', [])
        
        contacts = Contact.objects.filter(
            id__in=contact_ids,
            tenant=request.tenant
        )
        
        group.contacts.add(*contacts)
        
        return Response({
            'message': f'{contacts.count()} contatos adicionados',
            'total_contacts': group.contacts.count()
        })
    
    @action(detail=True, methods=['post'])
    def remove_contacts(self, request, pk=None):
        """Remover contatos do grupo"""
        group = self.get_object()
        contact_ids = request.data.get('contact_ids', [])
        
        contacts = Contact.objects.filter(
            id__in=contact_ids,
            tenant=request.tenant
        )
        
        group.contacts.remove(*contacts)
        
        return Response({
            'message': f'{contacts.count()} contatos removidos',
            'total_contacts': group.contacts.count()
        })

