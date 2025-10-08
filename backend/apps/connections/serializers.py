from rest_framework import serializers
from .models import EvolutionConnection


class EvolutionConnectionSerializer(serializers.ModelSerializer):
    """Serializer for Evolution Connection."""
    
    class Meta:
        model = EvolutionConnection
        fields = [
            'id', 'name', 'base_url', 'api_key', 'webhook_url', 
            'is_active', 'status', 'last_check', 'last_error',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at', 'last_check', 'last_error']
    
    def to_representation(self, instance):
        """Mask API key in response."""
        data = super().to_representation(instance)
        if data.get('api_key'):
            # Show only last 4 characters
            api_key = data['api_key']
            if len(api_key) > 4:
                data['api_key'] = '*' * (len(api_key) - 4) + api_key[-4:]
            else:
                data['api_key'] = '*' * len(api_key)
        return data