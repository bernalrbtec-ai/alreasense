from rest_framework import serializers
from .models import PromptTemplate, Inference, ExperimentRun


class PromptTemplateSerializer(serializers.ModelSerializer):
    """Serializer for PromptTemplate model."""
    
    class Meta:
        model = PromptTemplate
        fields = [
            'id', 'version', 'body', 'description', 'is_active',
            'created_at', 'created_by'
        ]
        read_only_fields = ['id', 'created_at']


class PromptTemplateCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating PromptTemplate."""
    
    class Meta:
        model = PromptTemplate
        fields = ['version', 'body', 'description', 'is_active']
    
    def create(self, validated_data):
        # Set created_by from request user
        validated_data['created_by'] = self.context['request'].user.username
        return super().create(validated_data)


class InferenceSerializer(serializers.ModelSerializer):
    """Serializer for Inference model."""
    
    message_text = serializers.CharField(source='message.text', read_only=True)
    message_chat_id = serializers.CharField(source='message.chat_id', read_only=True)
    
    class Meta:
        model = Inference
        fields = [
            'id', 'message', 'message_text', 'message_chat_id',
            'model_name', 'prompt_version', 'template_hash',
            'latency_ms', 'sentiment', 'emotion', 'satisfaction',
            'is_shadow', 'run_id', 'created_at'
        ]
        read_only_fields = ['id', 'created_at']


class ExperimentRunSerializer(serializers.ModelSerializer):
    """Serializer for ExperimentRun model."""
    
    progress_percentage = serializers.ReadOnlyField()
    
    class Meta:
        model = ExperimentRun
        fields = [
            'id', 'run_id', 'name', 'description', 'prompt_version',
            'start_date', 'end_date', 'status', 'total_messages',
            'processed_messages', 'progress_percentage', 'created_at'
        ]
        read_only_fields = ['id', 'created_at']


class ExperimentRunCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating ExperimentRun."""
    
    class Meta:
        model = ExperimentRun
        fields = ['name', 'description', 'prompt_version', 'start_date', 'end_date']
    
    def create(self, validated_data):
        # Set tenant from request user
        validated_data['tenant'] = self.context['request'].user.tenant
        
        # Generate run_id
        import uuid
        validated_data['run_id'] = str(uuid.uuid4())[:8]
        
        return super().create(validated_data)


class ReplayRequestSerializer(serializers.Serializer):
    """Serializer for replay experiment requests."""
    
    start_date = serializers.DateTimeField()
    end_date = serializers.DateTimeField()
    prompt_version = serializers.CharField(max_length=64)
    name = serializers.CharField(max_length=200, required=False)
    description = serializers.CharField(required=False)
