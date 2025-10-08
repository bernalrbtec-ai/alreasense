from django.db import models
from apps.tenancy.models import Tenant
from apps.chat_messages.models import Message


class PromptTemplate(models.Model):
    """Prompt template for AI experiments."""
    
    version = models.CharField(max_length=64, unique=True)
    body = models.TextField()
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.CharField(max_length=100, blank=True)
    
    class Meta:
        db_table = 'experiments_prompttemplate'
        verbose_name = 'Prompt Template'
        verbose_name_plural = 'Prompt Templates'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.version} ({'active' if self.is_active else 'inactive'})"
    
    def save(self, *args, **kwargs):
        # Ensure only one template is active at a time
        if self.is_active:
            PromptTemplate.objects.filter(is_active=True).update(is_active=False)
        super().save(*args, **kwargs)


class Inference(models.Model):
    """AI inference results for experiments."""
    
    tenant = models.ForeignKey(
        Tenant, 
        on_delete=models.CASCADE,
        related_name='inferences'
    )
    message = models.ForeignKey(
        Message, 
        on_delete=models.CASCADE, 
        related_name='inferences'
    )
    model_name = models.CharField(max_length=64)
    prompt_version = models.CharField(max_length=64)
    template_hash = models.CharField(max_length=64)
    latency_ms = models.IntegerField()
    sentiment = models.FloatField()
    emotion = models.CharField(max_length=40)
    satisfaction = models.IntegerField()
    is_shadow = models.BooleanField(default=False)
    run_id = models.CharField(max_length=64, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'experiments_inference'
        verbose_name = 'Inference'
        verbose_name_plural = 'Inferences'
        indexes = [
            models.Index(fields=['run_id']),
            models.Index(fields=['created_at']),
            models.Index(fields=['is_shadow']),
            models.Index(fields=['prompt_version']),
        ]
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.message.id} - {self.prompt_version} ({'shadow' if self.is_shadow else 'champion'})"


class ExperimentRun(models.Model):
    """Experiment run tracking."""
    
    STATUS_CHOICES = [
        ('running', 'Running'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
        ('cancelled', 'Cancelled'),
    ]
    
    tenant = models.ForeignKey(
        Tenant, 
        on_delete=models.CASCADE,
        related_name='experiment_runs'
    )
    run_id = models.CharField(max_length=64, unique=True)
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    prompt_version = models.CharField(max_length=64)
    start_date = models.DateTimeField()
    end_date = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default='running')
    total_messages = models.IntegerField(default=0)
    processed_messages = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'experiments_experimentrun'
        verbose_name = 'Experiment Run'
        verbose_name_plural = 'Experiment Runs'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.name} ({self.run_id})"
    
    @property
    def progress_percentage(self):
        """Calculate progress percentage."""
        if self.total_messages == 0:
            return 0
        return (self.processed_messages / self.total_messages) * 100
