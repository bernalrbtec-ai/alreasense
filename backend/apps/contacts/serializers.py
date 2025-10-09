from rest_framework import serializers
from apps.contacts.models import Contact, ContactGroup


class ContactSerializer(serializers.ModelSerializer):
    groups_count = serializers.SerializerMethodField()
    
    class Meta:
        model = Contact
        fields = [
            'id', 'name', 'phone', 'email', 'quem_indicou',
            'tags', 'custom_vars', 'notes', 'is_active',
            'groups_count', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']
    
    def get_groups_count(self, obj):
        return obj.groups.count()
    
    def validate_phone(self, value):
        # Normalizar formato
        phone = value.strip().replace(' ', '').replace('-', '').replace('(', '').replace(')', '')
        if not phone.startswith('+'):
            phone = '+' + phone
        return phone


class ContactGroupSerializer(serializers.ModelSerializer):
    contacts_count = serializers.SerializerMethodField()
    
    class Meta:
        model = ContactGroup
        fields = ['id', 'name', 'description', 'contacts_count', 'created_at', 'updated_at']
        read_only_fields = ['id', 'created_at', 'updated_at']
    
    def get_contacts_count(self, obj):
        return obj.contacts.count()


class ContactGroupDetailSerializer(serializers.ModelSerializer):
    contacts = ContactSerializer(many=True, read_only=True)
    
    class Meta:
        model = ContactGroup
        fields = ['id', 'name', 'description', 'contacts', 'created_at', 'updated_at']
        read_only_fields = ['id', 'created_at', 'updated_at']

