"""
Models para horários de atendimento e mensagens automáticas fora de horário.
"""
import uuid
from django.db import models
from django.utils import timezone
from datetime import time


class BusinessHours(models.Model):
    """
    Horários de atendimento por tenant ou departamento.
    
    Se department=None → horário geral do tenant
    Se department preenchido → horário específico do departamento
    """
    
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False
    )
    
    tenant = models.ForeignKey(
        'tenancy.Tenant',
        on_delete=models.CASCADE,
        related_name='business_hours',
        verbose_name='Tenant'
    )
    
    department = models.ForeignKey(
        'authn.Department',
        on_delete=models.CASCADE,
        related_name='business_hours',
        null=True,
        blank=True,
        verbose_name='Departamento',
        help_text='Se None, é horário geral do tenant'
    )
    
    timezone = models.CharField(
        max_length=50,
        default='America/Sao_Paulo',
        verbose_name='Fuso Horário',
        help_text='Ex: America/Sao_Paulo, America/New_York'
    )
    
    # Segunda-feira
    monday_enabled = models.BooleanField(default=True, verbose_name='Segunda Ativo')
    monday_start = models.TimeField(default=time(9, 0), verbose_name='Segunda Início')
    monday_end = models.TimeField(default=time(18, 0), verbose_name='Segunda Fim')
    
    # Terça-feira
    tuesday_enabled = models.BooleanField(default=True, verbose_name='Terça Ativo')
    tuesday_start = models.TimeField(default=time(9, 0), verbose_name='Terça Início')
    tuesday_end = models.TimeField(default=time(18, 0), verbose_name='Terça Fim')
    
    # Quarta-feira
    wednesday_enabled = models.BooleanField(default=True, verbose_name='Quarta Ativo')
    wednesday_start = models.TimeField(default=time(9, 0), verbose_name='Quarta Início')
    wednesday_end = models.TimeField(default=time(18, 0), verbose_name='Quarta Fim')
    
    # Quinta-feira
    thursday_enabled = models.BooleanField(default=True, verbose_name='Quinta Ativo')
    thursday_start = models.TimeField(default=time(9, 0), verbose_name='Quinta Início')
    thursday_end = models.TimeField(default=time(18, 0), verbose_name='Quinta Fim')
    
    # Sexta-feira
    friday_enabled = models.BooleanField(default=True, verbose_name='Sexta Ativo')
    friday_start = models.TimeField(default=time(9, 0), verbose_name='Sexta Início')
    friday_end = models.TimeField(default=time(18, 0), verbose_name='Sexta Fim')
    
    # Sábado
    saturday_enabled = models.BooleanField(default=False, verbose_name='Sábado Ativo')
    saturday_start = models.TimeField(default=time(9, 0), verbose_name='Sábado Início')
    saturday_end = models.TimeField(default=time(18, 0), verbose_name='Sábado Fim')
    
    # Domingo
    sunday_enabled = models.BooleanField(default=False, verbose_name='Domingo Ativo')
    sunday_start = models.TimeField(default=time(9, 0), verbose_name='Domingo Início')
    sunday_end = models.TimeField(default=time(18, 0), verbose_name='Domingo Fim')
    
    holidays = models.JSONField(
        default=list,
        blank=True,
        verbose_name='Feriados',
        help_text='Lista de datas no formato YYYY-MM-DD (ex: ["2025-12-25", "2026-01-01"])'
    )
    
    is_active = models.BooleanField(
        default=True,
        db_index=True,
        verbose_name='Ativo'
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'chat_business_hours'
        verbose_name = 'Horário de Atendimento'
        verbose_name_plural = 'Horários de Atendimento'
        unique_together = [['tenant', 'department']]
        indexes = [
            models.Index(fields=['tenant', 'department', 'is_active']),
            models.Index(fields=['tenant', 'is_active']),
        ]
    
    def __str__(self):
        if self.department:
            return f"{self.tenant.name} - {self.department.name}"
        return f"{self.tenant.name} - Geral"


class AfterHoursMessage(models.Model):
    """
    Mensagem automática enviada quando cliente entra em contato fora de horário.
    """
    
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False
    )
    
    tenant = models.ForeignKey(
        'tenancy.Tenant',
        on_delete=models.CASCADE,
        related_name='after_hours_messages',
        verbose_name='Tenant'
    )
    
    department = models.ForeignKey(
        'authn.Department',
        on_delete=models.CASCADE,
        related_name='after_hours_messages',
        null=True,
        blank=True,
        verbose_name='Departamento',
        help_text='Se None, é mensagem geral do tenant'
    )
    
    message_template = models.TextField(
        verbose_name='Mensagem',
        help_text='Template da mensagem. Variáveis: {contact_name}, {department_name}, {next_open_time}'
    )
    
    reply_to_groups = models.BooleanField(
        default=False,
        verbose_name='Responder em Grupos',
        help_text='Se habilitado, envia mensagem automática também para grupos. Se desabilitado, apenas para conversas individuais.'
    )
    
    is_active = models.BooleanField(
        default=True,
        db_index=True,
        verbose_name='Ativo'
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'chat_after_hours_message'
        verbose_name = 'Mensagem Fora de Horário'
        verbose_name_plural = 'Mensagens Fora de Horário'
        unique_together = [['tenant', 'department']]
        indexes = [
            models.Index(fields=['tenant', 'department', 'is_active']),
            models.Index(fields=['tenant', 'is_active']),
        ]
    
    def __str__(self):
        if self.department:
            return f"{self.tenant.name} - {self.department.name}"
        return f"{self.tenant.name} - Geral"


class AfterHoursTaskConfig(models.Model):
    """
    Configuração para criação automática de tarefas quando mensagem chega fora de horário.
    """
    
    PRIORITY_CHOICES = [
        ('low', 'Baixa'),
        ('medium', 'Média'),
        ('high', 'Alta'),
        ('urgent', 'Urgente'),
    ]
    
    TASK_TYPE_CHOICES = [
        ('task', 'Tarefa'),
        ('agenda', 'Agenda'),
    ]
    
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False
    )
    
    tenant = models.ForeignKey(
        'tenancy.Tenant',
        on_delete=models.CASCADE,
        related_name='after_hours_task_configs',
        verbose_name='Tenant'
    )
    
    department = models.ForeignKey(
        'authn.Department',
        on_delete=models.CASCADE,
        related_name='after_hours_task_configs',
        null=True,
        blank=True,
        verbose_name='Departamento',
        help_text='Se None, é configuração geral do tenant'
    )
    
    create_task_enabled = models.BooleanField(
        default=True,
        verbose_name='Criar Tarefa Automaticamente'
    )
    
    task_title_template = models.CharField(
        max_length=255,
        default='Retornar contato de {contact_name}',
        verbose_name='Título da Tarefa',
        help_text='Template. Variáveis: {contact_name}, {department_name}, {message_time}'
    )
    
    task_description_template = models.TextField(
        default='Cliente entrou em contato fora do horário de atendimento.\n\nHorário: {message_time}\nMensagem: {message_content}\n\nPróximo horário: {next_open_time}',
        verbose_name='Descrição da Tarefa',
        help_text='Template. Variáveis: {contact_name}, {contact_phone}, {message_time}, {message_content}, {next_open_time}, {department_name}'
    )
    
    task_priority = models.CharField(
        max_length=20,
        choices=PRIORITY_CHOICES,
        default='high',
        verbose_name='Prioridade'
    )
    
    task_due_date_offset_hours = models.IntegerField(
        default=2,
        verbose_name='Vencimento (horas)',
        help_text='Tarefa vence em X horas após recebimento da mensagem'
    )
    
    task_type = models.CharField(
        max_length=10,
        choices=TASK_TYPE_CHOICES,
        default='task',
        verbose_name='Tipo de Tarefa'
    )
    
    auto_assign_to_department = models.BooleanField(
        default=True,
        verbose_name='Atribuir ao Departamento'
    )
    
    task_department = models.ForeignKey(
        'authn.Department',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='after_hours_tasks',
        verbose_name='Departamento da Tarefa',
        help_text='Departamento onde a tarefa será criada. Se não preenchido, usa o departamento da conversa.'
    )
    
    auto_assign_to_agent = models.ForeignKey(
        'authn.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='auto_assigned_after_hours_tasks',
        verbose_name='Atribuir a Agente Específico',
        help_text='Se preenchido, atribui sempre a este agente'
    )
    
    include_message_preview = models.BooleanField(
        default=True,
        verbose_name='Incluir Preview da Mensagem'
    )
    
    is_active = models.BooleanField(
        default=True,
        db_index=True,
        verbose_name='Ativo'
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'chat_after_hours_task_config'
        verbose_name = 'Configuração de Tarefa Fora de Horário'
        verbose_name_plural = 'Configurações de Tarefa Fora de Horário'
        unique_together = [['tenant', 'department']]
        indexes = [
            models.Index(fields=['tenant', 'department', 'is_active']),
            models.Index(fields=['tenant', 'is_active']),
        ]
    
    def __str__(self):
        if self.department:
            return f"{self.tenant.name} - {self.department.name}"
        return f"{self.tenant.name} - Geral"

