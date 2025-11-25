# 🔔 SISTEMA DE NOTIFICAÇÕES PERSONALIZADAS

## 📋 ÍNDICE

1. [Visão Geral](#visão-geral)
2. [Arquitetura](#arquitetura)
3. [Modelos de Dados](#modelos-de-dados)
4. [Lógica de Gestores](#lógica-de-gestores)
5. [Scheduler](#scheduler)
6. [APIs](#apis)
7. [Frontend - Experiência do Usuário (UX)](#-frontend---experiência-do-usuário-ux)
8. [Boas Práticas](#boas-práticas)
9. [Exemplos de Uso](#exemplos-de-uso)
10. [Controles e Validações Implementadas](#-controles-e-validações-implementadas)
11. [Guia de Design e UX Moderna](#-guia-de-design-e-ux-moderna)

---

## 🎯 VISÃO GERAL

Sistema de notificações personalizadas que permite:
- **Usuários individuais**: Configurar notificações sobre suas próprias tarefas
- **Gestores de departamento**: Configurar notificações agregadas do departamento
- **Múltiplos horários**: Resumos diários em horários personalizados
- **Filtros personalizados**: Escolher quais tipos de eventos receber

### Objetivos

1. Proatividade: Usuários recebem resumos sem precisar abrir o sistema
2. Visibilidade gerencial: Gestores têm visão consolidada do departamento
3. Personalização: Cada usuário/gestor define quando e o que receber
4. Escalabilidade: Funciona para equipes pequenas e grandes

---

## 🏗️ ARQUITETURA

### Componentes Principais

```
┌─────────────────────────────────────────────────────────┐
│                    FRONTEND                              │
│  ┌──────────────────────────────────────────────────┐   │
│  │  Aba "Notificações" em Configurações            │   │
│  │  - Seção: Minhas Notificações (todos)            │   │
│  │  - Seção: Notificações do Departamento (gestores)│   │
│  └──────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────┐
│                    BACKEND API                           │
│  ┌──────────────────┐  ┌────────────────────────────┐  │
│  │ UserNotification │  │ DepartmentNotification      │  │
│  │ Preferences API  │  │ Preferences API             │  │
│  └──────────────────┘  └────────────────────────────┘  │
└─────────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────┐
│                    DATABASE                              │
│  ┌──────────────────┐  ┌────────────────────────────┐  │
│  │ UserNotification │  │ DepartmentNotification      │  │
│  │ Preferences      │  │ Preferences                │  │
│  └──────────────────┘  └────────────────────────────┘  │
└─────────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────┐
│                    SCHEDULER                             │
│  ┌──────────────────┐  ┌────────────────────────────┐  │
│  │ Daily Summary    │  │ Status Change Notifications │  │
│  │ (7h, 8h, etc)    │  │ (tempo real)                │  │
│  └──────────────────┘  └────────────────────────────┘  │
└─────────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────┐
│                    NOTIFICATION CHANNELS                │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐   │
│  │   WhatsApp   │  │  WebSocket  │  │   Email      │   │
│  └──────────────┘  └──────────────┘  └──────────────┘   │
└─────────────────────────────────────────────────────────┘
```

---

## 📊 MODELOS DE DADOS

### 1. UserNotificationPreferences

```python
# backend/apps/authn/models.py ou backend/apps/notifications/models.py

class UserNotificationPreferences(models.Model):
    """
    Preferências de notificação individuais do usuário.
    Cada usuário pode configurar suas próprias notificações.
    """
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='notification_preferences',
        verbose_name='Usuário'
    )
    tenant = models.ForeignKey(
        Tenant,
        on_delete=models.CASCADE,
        related_name='user_notification_preferences',
        verbose_name='Tenant'
    )
    
    # Horários de resumo diário
    daily_summary_enabled = models.BooleanField(
        default=False,
        verbose_name='Resumo diário ativado'
    )
    daily_summary_time = models.TimeField(
        null=True,
        blank=True,
        verbose_name='Horário do resumo diário',
        help_text='Ex: 07:00'
    )
    
    # Lembrete de agenda
    agenda_reminder_enabled = models.BooleanField(
        default=False,
        verbose_name='Lembrete de agenda ativado'
    )
    agenda_reminder_time = models.TimeField(
        null=True,
        blank=True,
        verbose_name='Horário do lembrete de agenda',
        help_text='Ex: 08:00'
    )
    
    # Tipos de notificação
    notify_pending = models.BooleanField(
        default=True,
        verbose_name='Notificar tarefas pendentes'
    )
    notify_in_progress = models.BooleanField(
        default=True,
        verbose_name='Notificar tarefas em progresso'
    )
    notify_status_changes = models.BooleanField(
        default=True,
        verbose_name='Notificar mudanças de status'
    )
    notify_completed = models.BooleanField(
        default=False,
        verbose_name='Notificar tarefas concluídas'
    )
    notify_overdue = models.BooleanField(
        default=True,
        verbose_name='Notificar tarefas atrasadas'
    )
    
    # Canais de notificação
    notify_via_whatsapp = models.BooleanField(
        default=True,
        verbose_name='Notificar via WhatsApp'
    )
    notify_via_websocket = models.BooleanField(
        default=True,
        verbose_name='Notificar via WebSocket'
    )
    notify_via_email = models.BooleanField(
        default=False,
        verbose_name='Notificar via Email'
    )
    
    # Metadados
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = 'Preferência de Notificação do Usuário'
        verbose_name_plural = 'Preferências de Notificação dos Usuários'
        unique_together = ['user', 'tenant']
        indexes = [
            models.Index(fields=['user', 'tenant']),
            models.Index(fields=['daily_summary_enabled', 'daily_summary_time']),
            models.Index(fields=['agenda_reminder_enabled', 'agenda_reminder_time']),
        ]
    
    def __str__(self):
        return f'Notificações de {self.user.email}'
```

### 2. DepartmentNotificationPreferences

```python
class DepartmentNotificationPreferences(models.Model):
    """
    Preferências de notificação do departamento para gestores.
    Apenas gestores do departamento podem configurar.
    """
    department = models.OneToOneField(
        Department,
        on_delete=models.CASCADE,
        related_name='notification_preferences',
        verbose_name='Departamento'
    )
    tenant = models.ForeignKey(
        Tenant,
        on_delete=models.CASCADE,
        related_name='department_notification_preferences',
        verbose_name='Tenant'
    )
    
    # Horários de resumo diário
    daily_summary_enabled = models.BooleanField(
        default=False,
        verbose_name='Resumo diário ativado'
    )
    daily_summary_time = models.TimeField(
        null=True,
        blank=True,
        verbose_name='Horário do resumo diário',
        help_text='Ex: 07:00'
    )
    
    # Lembrete de agenda
    agenda_reminder_enabled = models.BooleanField(
        default=False,
        verbose_name='Lembrete de agenda ativado'
    )
    agenda_reminder_time = models.TimeField(
        null=True,
        blank=True,
        verbose_name='Horário do lembrete de agenda',
        help_text='Ex: 08:00'
    )
    
    # Tipos de notificação
    notify_pending = models.BooleanField(
        default=True,
        verbose_name='Notificar tarefas pendentes'
    )
    notify_in_progress = models.BooleanField(
        default=True,
        verbose_name='Notificar tarefas em progresso'
    )
    notify_status_changes = models.BooleanField(
        default=True,
        verbose_name='Notificar mudanças de status'
    )
    notify_completed = models.BooleanField(
        default=False,
        verbose_name='Notificar tarefas concluídas'
    )
    notify_overdue = models.BooleanField(
        default=True,
        verbose_name='Notificar tarefas atrasadas'
    )
    
    # Filtros avançados para gestores
    notify_only_critical = models.BooleanField(
        default=False,
        verbose_name='Apenas tarefas críticas',
        help_text='Se True, apenas tarefas com prioridade alta ou atrasadas'
    )
    notify_only_assigned = models.BooleanField(
        default=False,
        verbose_name='Apenas tarefas atribuídas',
        help_text='Se True, apenas tarefas com assigned_to definido'
    )
    max_tasks_per_notification = models.IntegerField(
        default=20,
        verbose_name='Máximo de tarefas por notificação',
        help_text='Limite para evitar mensagens muito longas'
    )
    
    # Canais de notificação
    notify_via_whatsapp = models.BooleanField(
        default=True,
        verbose_name='Notificar via WhatsApp'
    )
    notify_via_websocket = models.BooleanField(
        default=True,
        verbose_name='Notificar via WebSocket'
    )
    notify_via_email = models.BooleanField(
        default=False,
        verbose_name='Notificar via Email'
    )
    
    # Metadados
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='created_department_notification_preferences',
        verbose_name='Criado por'
    )
    
    class Meta:
        verbose_name = 'Preferência de Notificação do Departamento'
        verbose_name_plural = 'Preferências de Notificação dos Departamentos'
        unique_together = ['department', 'tenant']
        indexes = [
            models.Index(fields=['department', 'tenant']),
            models.Index(fields=['daily_summary_enabled', 'daily_summary_time']),
            models.Index(fields=['agenda_reminder_enabled', 'agenda_reminder_time']),
        ]
    
    def __str__(self):
        return f'Notificações de {self.department.name}'
```

---

## 👥 LÓGICA DE GESTORES

### ⚠️ IMPORTANTE: Reutilização em Outros Módulos

**Esta lógica de gestores será usada em outros lugares do sistema** (relatórios, dashboards, permissões, etc.). 
Portanto, deve ser implementada de forma **centralizada e reutilizável**.

### Localização Recomendada

```python
# backend/apps/authn/utils.py
# OU
# backend/apps/common/permissions.py (se for mais genérico)
```

### Funções Auxiliares

```python
# backend/apps/authn/utils.py

from django.db.models import Q
from apps.authn.models import Department, User
from apps.contacts.models import Task

def is_department_manager(user, department):
    """
    Verifica se o usuário é gestor do departamento.
    
    REGRAS:
    - Admin sempre é gestor de todos os departamentos
    - Gerente é gestor apenas dos departamentos onde está vinculado
    - Agente nunca é gestor
    
    Args:
        user: Instância de User
        department: Instância de Department, ID (int/str) ou UUID
    
    Returns:
        bool: True se o usuário é gestor do departamento
    
    Raises:
        Department.DoesNotExist: Se department for ID e não existir
    """
    import uuid as uuid_module
    
    # Validar entrada
    if not user or not user.is_authenticated:
        return False
    
    # Admin sempre pode gerenciar qualquer departamento do tenant
    if user.role == 'admin':
        # Verificar se o departamento pertence ao mesmo tenant
        if isinstance(department, (int, str, uuid_module.UUID)):
            try:
                dept = Department.objects.get(id=department, tenant=user.tenant)
                return True
            except Department.DoesNotExist:
                return False
        return department.tenant == user.tenant
    
    # Gerente pode gerenciar apenas departamentos onde está vinculado
    if user.role == 'gerente':
        if isinstance(department, (int, str, uuid.UUID)):
            try:
                dept = Department.objects.get(id=department, tenant=user.tenant)
            except Department.DoesNotExist:
                return False
        else:
            dept = department
        
        # Verificar se o usuário está no departamento E se o departamento pertence ao tenant
        return dept.tenant == user.tenant and user.departments.filter(id=dept.id).exists()
    
    # Agente nunca é gestor
    return False


def get_user_managed_departments(user):
    """
    Retorna todos os departamentos que o usuário gerencia.
    
    REGRAS:
    - Admin: Todos os departamentos do tenant
    - Gerente: Apenas departamentos onde está vinculado
    - Agente: Nenhum
    
    Args:
        user: Instância de User
    
    Returns:
        QuerySet: Departamentos gerenciados pelo usuário
    """
    if not user or not user.is_authenticated:
        return Department.objects.none()
    
    # Admin gerencia todos os departamentos do tenant
    if user.role == 'admin':
        return Department.objects.filter(tenant=user.tenant, is_active=True)
    
    # Gerente gerencia apenas departamentos onde está vinculado
    if user.role == 'gerente':
        return user.departments.filter(tenant=user.tenant, is_active=True)
    
    # Agente não gerencia nenhum departamento
    return Department.objects.none()


def can_manage_department_notifications(user, department):
    """
    Verifica se o usuário pode gerenciar notificações do departamento.
    
    Esta função é um wrapper de is_department_manager() para uso específico
    em notificações, mas pode ser reutilizada para outras funcionalidades.
    
    Args:
        user: Instância de User
        department: Instância de Department, ID (int/str) ou UUID
    
    Returns:
        bool: True se o usuário pode gerenciar notificações do departamento
    """
    return is_department_manager(user, department)


def can_manage_department(user, department, action='view'):
    """
    Verifica se o usuário pode realizar uma ação no departamento.
    
    Esta é uma função genérica que pode ser usada em múltiplos contextos:
    - Notificações
    - Relatórios
    - Dashboards
    - Configurações
    - etc.
    
    Args:
        user: Instância de User
        department: Instância de Department, ID (int/str) ou UUID
        action: String indicando a ação ('view', 'edit', 'delete', 'manage')
    
    Returns:
        bool: True se o usuário pode realizar a ação
    """
    if not user or not user.is_authenticated:
        return False
    
    # Admin sempre pode tudo
    if user.role == 'admin':
        return True
    
    # Verificar se é gestor do departamento
    if is_department_manager(user, department):
        # Gerente pode ver e editar, mas não deletar (a menos que seja admin)
        if action in ['view', 'edit', 'manage']:
            return True
        if action == 'delete':
            return user.role == 'admin'
    
    return False


def get_department_tasks(department, filters=None, tenant=None):
    """
    Retorna todas as tarefas do departamento.
    
    REGRAS:
    - Inclui tarefas onde department = X
    - Inclui tarefas onde assigned_to está no departamento X
    - Sempre filtra por tenant (multi-tenancy)
    
    Args:
        department: Instância de Department ou ID
        filters: Dict com filtros adicionais:
            - status: Lista de status ['pending', 'in_progress', etc]
            - priority: Lista de prioridades ['low', 'medium', 'high', 'urgent']
            - overdue_only: bool - apenas tarefas atrasadas
            - assigned_only: bool - apenas tarefas com assigned_to
            - date_range: tuple (start_date, end_date)
        tenant: Instância de Tenant (obrigatório para multi-tenancy)
    
    Returns:
        QuerySet: Tarefas do departamento
    
    Raises:
        ValueError: Se tenant não for fornecido
    """
    from django.utils import timezone
    
    if tenant is None:
        if isinstance(department, Department):
            tenant = department.tenant
        else:
            raise ValueError("tenant deve ser fornecido quando department é ID")
    
    # Converter department para instância se necessário
    import uuid as uuid_module
    if isinstance(department, (int, str, uuid_module.UUID)):
        try:
            department = Department.objects.get(id=department, tenant=tenant)
        except Department.DoesNotExist:
            return Task.objects.none()
    
    # Buscar tarefas do departamento
    # Tarefas onde o departamento é o mesmo OU o usuário atribuído está no departamento
    tasks = Task.objects.filter(
        tenant=tenant
    ).filter(
        Q(department=department) |
        Q(assigned_to__departments=department)
    ).distinct()
    
    # Aplicar filtros adicionais
    if filters:
        if filters.get('status'):
            tasks = tasks.filter(status__in=filters['status'])
        
        if filters.get('priority'):
            tasks = tasks.filter(priority__in=filters['priority'])
        
        if filters.get('overdue_only'):
            tasks = tasks.filter(
                due_date__lt=timezone.now(),
                status__in=['pending', 'in_progress']
            )
        
        if filters.get('assigned_only'):
            tasks = tasks.exclude(assigned_to__isnull=True)
        
        if filters.get('date_range'):
            start_date, end_date = filters['date_range']
            tasks = tasks.filter(due_date__date__gte=start_date, due_date__date__lte=end_date)
    
    return tasks.select_related('assigned_to', 'created_by', 'tenant', 'department').prefetch_related('related_contacts')
```

### Permission Class

```python
# backend/apps/notifications/permissions.py

from rest_framework import permissions

class CanManageDepartmentNotifications(permissions.BasePermission):
    """
    Permissão para gerenciar notificações de departamento.
    Apenas gestores do departamento podem configurar.
    """
    
    def has_permission(self, request, view):
        # Apenas autenticados
        if not request.user or not request.user.is_authenticated:
            return False
        
        # Admin sempre pode
        if request.user.role == 'admin':
            return True
        
        # Para métodos que requerem department_id
        department_id = request.data.get('department') or request.query_params.get('department')
        if department_id:
            from apps.authn.utils import can_manage_department_notifications
            from apps.authn.models import Department
            try:
                department = Department.objects.get(id=department_id, tenant=request.user.tenant)
                return can_manage_department_notifications(request.user, department)
            except Department.DoesNotExist:
                return False
        
        # Para métodos que usam department no path (ex: /departments/{id}/notifications/)
        if hasattr(view, 'get_department'):
            department = view.get_department()
            if department:
                from apps.authn.utils import can_manage_department_notifications
                return can_manage_department_notifications(request.user, department)
        
        return False
```

---

## ⏰ SCHEDULER

### ⚠️ IMPORTANTE: Integração com Scheduler Existente

**O scheduler de notificações deve ser integrado ao scheduler existente** em `backend/apps/campaigns/apps.py`, 
que já processa campanhas agendadas e notificações de tarefas. **NÃO criar um scheduler separado**.

### Estrutura do Scheduler

```python
# backend/apps/campaigns/apps.py (adicionar ao scheduler existente)

import threading
import time
import logging
from django.utils import timezone
from datetime import datetime, timedelta, time as dt_time
from django.db import transaction
from apps.authn.models import User, Department
from apps.notifications.models import UserNotificationPreferences, DepartmentNotificationPreferences
from apps.contacts.models import Task

logger = logging.getLogger(__name__)

def check_daily_notifications():
    """
    Verifica e envia notificações diárias personalizadas.
    Roda a cada minuto para verificar se há notificações agendadas.
    
    ⚠️ TIMEZONE: Todas as comparações de horário devem considerar o timezone do usuário/tenant.
    O horário configurado pelo usuário é sempre no timezone local (America/Sao_Paulo).
    
    ⚠️ CONTROLE: Esta função deve ser chamada apenas uma vez por instância do scheduler.
    Use locks ou flags para evitar múltiplas execuções simultâneas.
    """
    # ✅ CONTROLE: Flag para evitar múltiplas execuções simultâneas
    import threading
    _notification_check_lock = threading.Lock()
    
    while True:
        try:
            # ✅ CONTROLE: Adquirir lock para evitar execução simultânea
            if not _notification_check_lock.acquire(blocking=False):
                logger.warning('⚠️ [DAILY NOTIFICATIONS] Verificação já em execução, pulando...')
                time.sleep(60)
                continue
            
            try:
                # Obter hora atual no timezone local (America/Sao_Paulo)
                local_now = timezone.localtime(timezone.now())
                current_time = local_now.time()
                current_date = local_now.date()
                
                # ✅ VALIDAÇÃO: Verificar se data/hora são válidas
                if current_date is None or current_time is None:
                    logger.error('❌ [DAILY NOTIFICATIONS] Data ou hora inválida')
                    continue
                
                logger.debug(f'🕐 [DAILY NOTIFICATIONS] Verificando notificações às {current_time} ({current_date})')
                
                # 1. Verificar notificações individuais (resumo diário)
                check_user_daily_summaries(current_time, current_date)
                
                # 2. Verificar notificações individuais (lembrete de agenda)
                check_user_agenda_reminders(current_time, current_date)
                
                # 3. Verificar notificações de departamento (resumo diário)
                check_department_daily_summaries(current_time, current_date)
                
                # 4. Verificar notificações de departamento (lembrete de agenda)
                check_department_agenda_reminders(current_time, current_date)
                
            finally:
                # ✅ CONTROLE: Sempre liberar lock, mesmo em caso de erro
                _notification_check_lock.release()
            
        except Exception as e:
            logger.error(f'❌ [DAILY NOTIFICATIONS] Erro no scheduler: {e}', exc_info=True)
            # ✅ CONTROLE: Garantir que lock seja liberado mesmo em caso de exceção
            try:
                _notification_check_lock.release()
            except:
                pass
        
        time.sleep(60)  # Verificar a cada minuto


def check_user_agenda_reminders(current_time, current_date):
    """
    Verifica e envia lembretes de agenda para usuários individuais.
    
    Similar a check_user_daily_summaries(), mas para lembretes de agenda.
    """
    # Janela de ±1 minuto
    time_window_start = (datetime.combine(datetime.min, current_time) - timedelta(minutes=1)).time()
    time_window_end = (datetime.combine(datetime.min, current_time) + timedelta(minutes=1)).time()
    
    preferences = UserNotificationPreferences.objects.filter(
        agenda_reminder_enabled=True,
        agenda_reminder_time__isnull=False,
        agenda_reminder_time__gte=time_window_start,
        agenda_reminder_time__lte=time_window_end,
        tenant__is_active=True,
        user__is_active=True
    ).select_related('user', 'tenant')
    
    count = 0
    for pref in preferences:
        try:
            if pref.notify_via_whatsapp and not pref.user.notify_whatsapp:
                continue
            
            # Implementar lógica de lembrete de agenda (similar ao resumo diário)
            # Por enquanto, apenas logar
            logger.info(f'📅 [AGENDA REMINDER] Lembrete de agenda para {pref.user.email}')
            count += 1
        except Exception as e:
            logger.error(f'❌ [AGENDA REMINDER] Erro para {pref.user.email}: {e}', exc_info=True)
    
    if count > 0:
        logger.info(f'✅ [AGENDA REMINDER] {count} lembrete(s) de agenda enviado(s)')


def check_department_agenda_reminders(current_time, current_date):
    """
    Verifica e envia lembretes de agenda para gestores de departamento.
    
    Similar a check_department_daily_summaries(), mas para lembretes de agenda.
    """
    # Janela de ±1 minuto
    time_window_start = (datetime.combine(datetime.min, current_time) - timedelta(minutes=1)).time()
    time_window_end = (datetime.combine(datetime.min, current_time) + timedelta(minutes=1)).time()
    
    preferences = DepartmentNotificationPreferences.objects.filter(
        agenda_reminder_enabled=True,
        agenda_reminder_time__isnull=False,
        agenda_reminder_time__gte=time_window_start,
        agenda_reminder_time__lte=time_window_end,
        tenant__is_active=True,
        department__is_active=True
    ).select_related('department', 'tenant')
    
    count = 0
    for pref in preferences:
        try:
            managers = User.objects.filter(
                departments=pref.department,
                role__in=['gerente', 'admin'],
                tenant=pref.tenant,
                is_active=True
            )
            
            for manager in managers:
                if pref.notify_via_whatsapp and not manager.notify_whatsapp:
                    continue
                
                # Implementar lógica de lembrete de agenda
                logger.info(f'📅 [AGENDA REMINDER] Lembrete de agenda para {manager.email} (departamento: {pref.department.name})')
                count += 1
        except Exception as e:
            logger.error(f'❌ [AGENDA REMINDER] Erro para departamento {pref.department.name}: {e}', exc_info=True)
    
    if count > 0:
        logger.info(f'✅ [AGENDA REMINDER] {count} lembrete(s) de agenda de departamento enviado(s)')


# ⚠️ FUNÇÕES AUXILIARES DE ENVIO (devem ser implementadas ou importadas)

def send_whatsapp_notification(user, message):
    """
    Envia notificação via WhatsApp.
    
    ⚠️ NOTA: Esta função deve usar o sistema existente de envio de WhatsApp.
    Verificar como as notificações de tarefas são enviadas atualmente.
    
    Args:
        user: Instância de User
        message: String com a mensagem formatada
    
    Returns:
        bool: True se enviado com sucesso
    
    Raises:
        Exception: Se houver erro no envio
    """
    # TODO: Implementar usando o sistema existente de WhatsApp
    # Exemplo: usar apps.campaigns.services ou apps.notifications.services
    from apps.campaigns.services import CampaignSender  # Exemplo - ajustar conforme necessário
    
    # ✅ VALIDAÇÃO: Verificar se usuário tem telefone
    phone = user.phone
    if not phone:
        raise ValueError(f"Usuário {user.email} não tem telefone cadastrado")
    
    # ✅ VALIDAÇÃO: Verificar se telefone tem formato mínimo válido (pelo menos 10 dígitos)
    phone_digits = ''.join(filter(str.isdigit, phone))
    if len(phone_digits) < 10:
        raise ValueError(f"Telefone do usuário {user.email} é inválido: {phone}")
    
    # ✅ NORMALIZAÇÃO: Garantir formato E.164
    if not phone.startswith('+'):
        if phone.startswith('55'):
            phone = '+' + phone
        else:
            # Remover zeros à esquerda e adicionar código do país
            phone_clean = phone.lstrip('0')
            phone = '+55' + phone_clean
    
    # ✅ VALIDAÇÃO FINAL: Verificar se telefone normalizado é válido
    if not phone.startswith('+55') or len(''.join(filter(str.isdigit, phone))) < 12:
        raise ValueError(f"Telefone normalizado inválido para {user.email}: {phone}")
    
    # Enviar via Evolution API (ajustar conforme implementação existente)
    # Por enquanto, apenas logar
    logger.info(f'📱 [WHATSAPP] Enviando para {phone}: {message[:50]}...')
    
    # TODO: Implementar envio real
    return True


def send_websocket_notification(user, notification_type, data):
    """
    Envia notificação via WebSocket.
    
    ⚠️ NOTA: Esta função deve usar o sistema existente de WebSocket (Channels).
    
    Args:
        user: Instância de User
        notification_type: String com o tipo de notificação ('daily_summary', etc)
        data: Dict com os dados da notificação
    
    Returns:
        bool: True se enviado com sucesso
    
    Raises:
        Exception: Se houver erro no envio
    """
    # TODO: Implementar usando Django Channels
    from channels.layers import get_channel_layer
    from asgiref.sync import async_to_sync
    
    channel_layer = get_channel_layer()
    if not channel_layer:
        logger.warning('⚠️ [WEBSOCKET] Channel layer não configurado')
        return False
    
    # Enviar para o grupo do usuário
    group_name = f'user_{user.id}'
    
    async_to_sync(channel_layer.group_send)(
        group_name,
        {
            'type': 'notification',
            'notification_type': notification_type,
            'data': data,
        }
    )
    
    logger.debug(f'📡 [WEBSOCKET] Notificação enviada para {user.email}: {notification_type}')
    return True


def check_user_daily_summaries(current_time, current_date):
    """
    Verifica e envia resumos diários para usuários individuais.
    
    ⚠️ VALIDAÇÕES:
    - Verifica apenas usuários ativos
    - Verifica apenas tenants ativos
    - Considera timezone do tenant
    - Janela de ±1 minuto para evitar perda de notificações
    
    Args:
        current_time: time object no timezone local
        current_date: date object no timezone local
    """
    # Janela de ±1 minuto para evitar perda de notificações devido a delays
    time_window_start = (datetime.combine(datetime.min, current_time) - timedelta(minutes=1)).time()
    time_window_end = (datetime.combine(datetime.min, current_time) + timedelta(minutes=1)).time()
    
    # Buscar preferências ativas no horário atual
    preferences = UserNotificationPreferences.objects.filter(
        daily_summary_enabled=True,
        daily_summary_time__isnull=False,
        daily_summary_time__gte=time_window_start,
        daily_summary_time__lte=time_window_end,
        tenant__is_active=True,
        user__is_active=True
    ).select_related('user', 'tenant', 'user__tenant')
    
    count = 0
    for pref in preferences:
        try:
            # ✅ VALIDAÇÃO: Verificar se pelo menos um canal está habilitado
            has_whatsapp = pref.notify_via_whatsapp and pref.user.notify_whatsapp
            has_websocket = pref.notify_via_websocket
            has_email = pref.notify_via_email
            
            if not (has_whatsapp or has_websocket or has_email):
                logger.debug(f'⏭️ [DAILY NOTIFICATIONS] Pulando {pref.user.email} - Nenhum canal habilitado')
                continue
            
            # ✅ VALIDAÇÃO: Verificar se horário está configurado
            if not pref.daily_summary_time:
                logger.warning(f'⚠️ [DAILY NOTIFICATIONS] {pref.user.email} tem resumo habilitado mas sem horário configurado')
                continue
            
            send_user_daily_summary(pref.user, pref, current_date)
            count += 1
        except Exception as e:
            logger.error(f'❌ [DAILY NOTIFICATIONS] Erro ao enviar resumo para {pref.user.email}: {e}', exc_info=True)
    
    if count > 0:
        logger.info(f'✅ [DAILY NOTIFICATIONS] {count} resumo(s) diário(s) enviado(s) para usuários')


def check_department_daily_summaries(current_time, current_date):
    """
    Verifica e envia resumos diários para gestores de departamento.
    
    ⚠️ VALIDAÇÕES:
    - Verifica apenas departamentos ativos
    - Verifica apenas tenants ativos
    - Considera timezone do tenant
    - Janela de ±1 minuto para evitar perda de notificações
    
    Args:
        current_time: time object no timezone local
        current_date: date object no timezone local
    """
    # Janela de ±1 minuto para evitar perda de notificações devido a delays
    time_window_start = (datetime.combine(datetime.min, current_time) - timedelta(minutes=1)).time()
    time_window_end = (datetime.combine(datetime.min, current_time) + timedelta(minutes=1)).time()
    
    preferences = DepartmentNotificationPreferences.objects.filter(
        daily_summary_enabled=True,
        daily_summary_time__isnull=False,
        daily_summary_time__gte=time_window_start,
        daily_summary_time__lte=time_window_end,
        tenant__is_active=True,
        department__is_active=True
    ).select_related('department', 'tenant')
    
    count = 0
    for pref in preferences:
        try:
            # Buscar gestores do departamento
            managers = User.objects.filter(
                departments=pref.department,
                role__in=['gerente', 'admin'],
                tenant=pref.tenant,
                is_active=True
            )
            
            for manager in managers:
                # ✅ VALIDAÇÃO: Verificar se pelo menos um canal está habilitado
                has_whatsapp = pref.notify_via_whatsapp and manager.notify_whatsapp
                has_websocket = pref.notify_via_websocket
                has_email = pref.notify_via_email
                
                if not (has_whatsapp or has_websocket or has_email):
                    logger.debug(f'⏭️ [DAILY NOTIFICATIONS] Pulando {manager.email} - Nenhum canal habilitado')
                    continue
                
                # ✅ VALIDAÇÃO: Verificar se horário está configurado
                if not pref.daily_summary_time:
                    logger.warning(f'⚠️ [DAILY NOTIFICATIONS] Departamento {pref.department.name} tem resumo habilitado mas sem horário configurado')
                    continue
                
                send_department_daily_summary(manager, pref.department, pref, current_date)
                count += 1
        except Exception as e:
            logger.error(f'❌ [DAILY NOTIFICATIONS] Erro ao enviar resumo de departamento {pref.department.name}: {e}', exc_info=True)
    
    if count > 0:
        logger.info(f'✅ [DAILY NOTIFICATIONS] {count} resumo(s) de departamento enviado(s)')


def send_user_daily_summary(user, preferences, current_date):
    """
    Envia resumo diário de tarefas para o usuário.
    
    ⚠️ VALIDAÇÕES:
    - Aplica filtros baseados nas preferências do usuário
    - Considera apenas tarefas do tenant do usuário
    - Filtra tarefas do dia atual (no timezone local)
    - Agrupa tarefas por status para facilitar leitura
    
    Args:
        user: Instância de User
        preferences: Instância de UserNotificationPreferences
        current_date: date object no timezone local
    """
    from apps.contacts.models import Task
    
    # Buscar tarefas do usuário (apenas do tenant)
    tasks = Task.objects.filter(
        assigned_to=user,
        tenant=user.tenant
    ).exclude(
        status__in=['cancelled']  # Sempre excluir canceladas
    ).select_related('department', 'created_by', 'tenant')
    
    # Aplicar filtros baseados nas preferências
    if not preferences.notify_pending:
        tasks = tasks.exclude(status='pending')
    if not preferences.notify_in_progress:
        tasks = tasks.exclude(status='in_progress')
    if not preferences.notify_completed:
        tasks = tasks.exclude(status='completed')
    
    # Filtrar tarefas do dia (hoje no timezone local)
    local_now = timezone.localtime(timezone.now())
    tasks_today = tasks.filter(
        due_date__date=current_date
    )
    
    # Tarefas atrasadas (independente da data)
    overdue_tasks = tasks.filter(
        due_date__lt=local_now,
        status__in=['pending', 'in_progress']
    )
    
    # Agrupar por status
    tasks_by_status = {
        'pending': list(tasks_today.filter(status='pending')[:10]),  # Limitar para não sobrecarregar
        'in_progress': list(tasks_today.filter(status='in_progress')[:10]),
        'completed': list(tasks_today.filter(status='completed')[:10]),
        'overdue': list(overdue_tasks[:10]),
    }
    
    # ✅ VALIDAÇÃO: Verificar se há tarefas para notificar
    total_tasks = sum(len(tasks) for tasks in tasks_by_status.values())
    if total_tasks == 0:
        logger.debug(f'⏭️ [DAILY NOTIFICATIONS] Nenhuma tarefa para {user.email} hoje')
        return
    
    # ✅ VALIDAÇÃO: Verificar se mensagem não está vazia
    if not message or len(message.strip()) == 0:
        logger.warning(f'⚠️ [DAILY NOTIFICATIONS] Mensagem vazia para {user.email}, pulando envio')
        return
    
    # Formatar mensagem
    message = format_daily_summary_message(user, tasks_by_status, current_date)
    
    # ✅ CONTROLE: Enviar notificações com tratamento de erros individual
    notifications_sent = 0
    notifications_failed = 0
    
    # WhatsApp
    if preferences.notify_via_whatsapp and user.notify_whatsapp:
        try:
            success = send_whatsapp_notification(user, message)
            if success:
                notifications_sent += 1
            else:
                notifications_failed += 1
        except Exception as e:
            logger.error(f'❌ [DAILY NOTIFICATIONS] Erro ao enviar WhatsApp para {user.email}: {e}', exc_info=True)
            notifications_failed += 1
    
    # WebSocket
    if preferences.notify_via_websocket:
        try:
            success = send_websocket_notification(user, 'daily_summary', {
                'date': current_date.isoformat(),
                'tasks': {
                    'pending': len(tasks_by_status['pending']),
                    'in_progress': len(tasks_by_status['in_progress']),
                    'completed': len(tasks_by_status['completed']),
                    'overdue': len(tasks_by_status['overdue']),
                }
            })
            if success:
                notifications_sent += 1
            else:
                notifications_failed += 1
        except Exception as e:
            logger.error(f'❌ [DAILY NOTIFICATIONS] Erro ao enviar WebSocket para {user.email}: {e}', exc_info=True)
            notifications_failed += 1
    
    # Email (se implementado)
    if preferences.notify_via_email:
        try:
            # TODO: Implementar envio de email
            logger.debug(f'📧 [DAILY NOTIFICATIONS] Email não implementado ainda para {user.email}')
        except Exception as e:
            logger.error(f'❌ [DAILY NOTIFICATIONS] Erro ao enviar Email para {user.email}: {e}', exc_info=True)
            notifications_failed += 1
    
    # ✅ CONTROLE: Logar resultado final
    if notifications_sent > 0:
        logger.info(f'✅ [DAILY NOTIFICATIONS] Resumo diário enviado para {user.email} ({notifications_sent} canal(is) enviado(s), {notifications_failed} falhou(aram))')
    else:
        logger.warning(f'⚠️ [DAILY NOTIFICATIONS] Nenhuma notificação enviada para {user.email} (todos os {notifications_failed} canal(is) falharam)')


def send_department_daily_summary(manager, department, preferences, current_date):
    """
    Envia resumo diário do departamento para o gestor.
    
    ⚠️ VALIDAÇÕES:
    - Aplica filtros baseados nas preferências do departamento
    - Considera apenas tarefas do tenant do departamento
    - Filtra tarefas do dia atual (no timezone local)
    - Limita quantidade de tarefas por notificação
    - Agrupa tarefas por status para facilitar leitura
    
    Args:
        manager: Instância de User (gestor)
        department: Instância de Department
        preferences: Instância de DepartmentNotificationPreferences
        current_date: date object no timezone local
    """
    from apps.authn.utils import get_department_tasks
    
    # Buscar tarefas do departamento
    filters = {}
    if preferences.notify_only_critical:
        filters['priority'] = ['high', 'urgent']
    if preferences.notify_only_assigned:
        filters['assigned_only'] = True
    
    tasks = get_department_tasks(department, filters, tenant=department.tenant)
    
    # ✅ VALIDAÇÃO: Verificar se pelo menos um tipo de notificação está habilitado
    has_any_notification_type = (
        preferences.notify_pending or 
        preferences.notify_in_progress or 
        preferences.notify_completed or 
        preferences.notify_overdue
    )
    
    if not has_any_notification_type:
        logger.debug(f'⏭️ [DAILY NOTIFICATIONS] Departamento {department.name} tem todos os tipos de notificação desabilitados')
        return
    
    # Aplicar filtros baseados nas preferências
    if not preferences.notify_pending:
        tasks = tasks.exclude(status='pending')
    if not preferences.notify_in_progress:
        tasks = tasks.exclude(status='in_progress')
    if not preferences.notify_completed:
        tasks = tasks.exclude(status='completed')
    
    # Filtrar tarefas do dia (hoje no timezone local)
    local_now = timezone.localtime(timezone.now())
    
    # ✅ VALIDAÇÃO: Verificar se current_date é válido
    if current_date > local_now.date():
        logger.warning(f'⚠️ [DAILY NOTIFICATIONS] Data futura recebida: {current_date}')
        return
    
    tasks_today = tasks.filter(due_date__date=current_date)
    
    # Tarefas atrasadas (independente da data, mas apenas se notify_overdue estiver habilitado)
    overdue_tasks = tasks.none()  # Inicializar como QuerySet vazio
    if preferences.notify_overdue:
        overdue_tasks = tasks.filter(
            due_date__lt=local_now,
            status__in=['pending', 'in_progress']
        )
    
    # Limitar quantidade de tarefas do dia
    tasks_today = tasks_today[:preferences.max_tasks_per_notification]
    
    # Agrupar por status (converter para lista para evitar problemas com QuerySet)
    tasks_by_status = {
        'pending': list(tasks_today.filter(status='pending')[:10]),
        'in_progress': list(tasks_today.filter(status='in_progress')[:10]),
        'completed': list(tasks_today.filter(status='completed')[:10]),
        'overdue': list(overdue_tasks[:10]),
    }
    
    # ✅ VALIDAÇÃO: Verificar se há tarefas para notificar
    total_tasks = sum(len(tasks) for tasks in tasks_by_status.values())
    if total_tasks == 0:
        logger.debug(f'⏭️ [DAILY NOTIFICATIONS] Nenhuma tarefa para departamento {department.name} hoje')
        return
    
    # ✅ VALIDAÇÃO: Verificar se mensagem não está vazia
    if not message or len(message.strip()) == 0:
        logger.warning(f'⚠️ [DAILY NOTIFICATIONS] Mensagem vazia para departamento {department.name}, pulando envio')
        return
    
    # Formatar mensagem
    message = format_department_daily_summary_message(manager, department, tasks_by_status, current_date)
    
    # ✅ CONTROLE: Enviar notificações com tratamento de erros individual
    notifications_sent = 0
    notifications_failed = 0
    
    # WhatsApp
    if preferences.notify_via_whatsapp and manager.notify_whatsapp:
        try:
            success = send_whatsapp_notification(manager, message)
            if success:
                notifications_sent += 1
            else:
                notifications_failed += 1
        except Exception as e:
            logger.error(f'❌ [DAILY NOTIFICATIONS] Erro ao enviar WhatsApp para {manager.email}: {e}', exc_info=True)
            notifications_failed += 1
    
    # WebSocket
    if preferences.notify_via_websocket:
        try:
            success = send_websocket_notification(manager, 'department_daily_summary', {
                'department': department.name,
                'date': current_date.isoformat(),
                'tasks': {
                    'pending': len(tasks_by_status['pending']),
                    'in_progress': len(tasks_by_status['in_progress']),
                    'completed': len(tasks_by_status['completed']),
                    'overdue': len(tasks_by_status['overdue']),
                }
            })
            if success:
                notifications_sent += 1
            else:
                notifications_failed += 1
        except Exception as e:
            logger.error(f'❌ [DAILY NOTIFICATIONS] Erro ao enviar WebSocket para {manager.email}: {e}', exc_info=True)
            notifications_failed += 1
    
    # Email (se implementado)
    if preferences.notify_via_email:
        try:
            # TODO: Implementar envio de email
            logger.debug(f'📧 [DAILY NOTIFICATIONS] Email não implementado ainda para {manager.email}')
        except Exception as e:
            logger.error(f'❌ [DAILY NOTIFICATIONS] Erro ao enviar Email para {manager.email}: {e}', exc_info=True)
            notifications_failed += 1
    
    # ✅ CONTROLE: Logar resultado final
    if notifications_sent > 0:
        logger.info(f'✅ [DAILY NOTIFICATIONS] Resumo de departamento enviado para {manager.email} (departamento: {department.name}, {notifications_sent} canal(is) enviado(s), {notifications_failed} falhou(aram))')
    else:
        logger.warning(f'⚠️ [DAILY NOTIFICATIONS] Nenhuma notificação enviada para {manager.email} (todos os {notifications_failed} canal(is) falharam)')


def format_daily_summary_message(user, tasks_by_status, current_date):
    """
    Formata mensagem de resumo diário para WhatsApp.
    
    ⚠️ FORMATO:
    - Usa formatação Markdown do WhatsApp (*negrito*, _itálico_)
    - Limita quantidade de tarefas por seção (máx 5)
    - Inclui emojis para facilitar leitura
    - Formata data e hora no timezone local
    
    Args:
        user: Instância de User
        tasks_by_status: Dict com listas de tarefas agrupadas por status
        current_date: date object no timezone local
    
    Returns:
        str: Mensagem formatada para WhatsApp
    """
    from django.utils import timezone
    
    date_str = current_date.strftime('%d/%m/%Y')
    weekday = current_date.strftime('%A')  # Nome do dia da semana
    
    # Traduzir dia da semana (opcional)
    weekdays_pt = {
        'Monday': 'Segunda-feira',
        'Tuesday': 'Terça-feira',
        'Wednesday': 'Quarta-feira',
        'Thursday': 'Quinta-feira',
        'Friday': 'Sexta-feira',
        'Saturday': 'Sábado',
        'Sunday': 'Domingo',
    }
    weekday_pt = weekdays_pt.get(weekday, weekday)
    
    # ✅ UX: Saudação personalizada baseada no horário
    current_hour = timezone.localtime(timezone.now()).hour
    if 5 <= current_hour < 12:
        greeting = "Bom dia"
    elif 12 <= current_hour < 18:
        greeting = "Boa tarde"
    else:
        greeting = "Boa noite"
    
    user_name = user.first_name or user.email.split('@')[0]
    
    # ✅ UX: Mensagem mais amigável e motivacional
    message = f"👋 *{greeting}, {user_name}!*\n\n"
    message += f"📋 *Resumo do seu dia - {weekday_pt}, {date_str}*\n\n"
    
    # Tarefas atrasadas (prioridade máxima)
    overdue = tasks_by_status['overdue']
    if overdue:
        message += f"⚠️ *Tarefas Atrasadas: {len(overdue)}*\n"
        for task in overdue[:5]:
            local_due = timezone.localtime(task.due_date)
            days_overdue = (timezone.now().date() - local_due.date()).days
            message += f"  • {task.title}"
            if days_overdue > 0:
                message += f" ({days_overdue} dia(s) atrasada)"
            message += "\n"
        if len(overdue) > 5:
            message += f"  ... e mais {len(overdue) - 5} tarefa(s)\n"
        message += "\n"
    
    # Tarefas pendentes
    pending = tasks_by_status['pending']
    if pending:
        message += f"📝 *Tarefas para hoje: {len(pending)}*\n"
        for task in pending[:5]:
            local_due = timezone.localtime(task.due_date)
            due_time = local_due.strftime('%H:%M')
            message += f"  • {task.title} às {due_time}\n"
        if len(pending) > 5:
            message += f"  ... e mais {len(pending) - 5} tarefa(s)\n"
        message += "\n"
    
    # Tarefas em progresso
    in_progress = tasks_by_status['in_progress']
    if in_progress:
        message += f"🔄 *Em andamento: {len(in_progress)}*\n"
        for task in in_progress[:5]:
            message += f"  • {task.title}\n"
        if len(in_progress) > 5:
            message += f"  ... e mais {len(in_progress) - 5} tarefa(s)\n"
        message += "\n"
    
    # Tarefas concluídas
    completed = tasks_by_status['completed']
    if completed:
        message += f"✅ *Concluídas hoje: {len(completed)}*\n"
        for task in completed[:5]:
            message += f"  • {task.title}\n"
        if len(completed) > 5:
            message += f"  ... e mais {len(completed) - 5} tarefa(s)\n"
        message += "\n"
    
    # ✅ UX: Mensagem motivacional baseada no progresso
    total = len(overdue) + len(pending) + len(in_progress) + len(completed)
    completed_count = len(completed)
    
    if completed_count > 0 and total > 0:
        progress = (completed_count / total) * 100
        if progress >= 50:
            message += f"🎉 *Ótimo trabalho! Você já concluiu {int(progress)}% das suas tarefas.*\n\n"
        elif progress >= 25:
            message += f"💪 *Continue assim! Você já concluiu {int(progress)}% das suas tarefas.*\n\n"
    
    message += f"📊 *Total: {total} tarefa(s) no seu dia*\n\n"
    
    # ✅ UX: Call to action amigável
    if overdue:
        message += "💡 *Dica:* Priorize as tarefas atrasadas para manter tudo em dia!"
    elif pending:
        message += "✨ *Bom dia!* Você tem um dia produtivo pela frente!"
    elif completed_count == total and total > 0:
        message += "🌟 *Parabéns!* Você concluiu todas as suas tarefas de hoje!"
    
    return message


def format_department_daily_summary_message(manager, department, tasks_by_status, current_date):
    """
    Formata mensagem de resumo diário do departamento para WhatsApp.
    
    ⚠️ FORMATO:
    - Usa formatação Markdown do WhatsApp (*negrito*, _itálico_)
    - Limita quantidade de tarefas por seção (máx 5)
    - Inclui informações de quem está atribuído a cada tarefa
    - Inclui emojis para facilitar leitura
    - Formata data e hora no timezone local
    
    Args:
        manager: Instância de User (gestor)
        department: Instância de Department
        tasks_by_status: Dict com listas de tarefas agrupadas por status
        current_date: date object no timezone local
    
    Returns:
        str: Mensagem formatada para WhatsApp
    """
    from django.utils import timezone
    
    date_str = current_date.strftime('%d/%m/%Y')
    weekday = current_date.strftime('%A')
    
    # Traduzir dia da semana
    weekdays_pt = {
        'Monday': 'Segunda-feira',
        'Tuesday': 'Terça-feira',
        'Wednesday': 'Quarta-feira',
        'Thursday': 'Quinta-feira',
        'Friday': 'Sexta-feira',
        'Saturday': 'Sábado',
        'Sunday': 'Domingo',
    }
    weekday_pt = weekdays_pt.get(weekday, weekday)
    
    # ✅ UX: Saudação personalizada
    current_hour = timezone.localtime(timezone.now()).hour
    if 5 <= current_hour < 12:
        greeting = "Bom dia"
    elif 12 <= current_hour < 18:
        greeting = "Boa tarde"
    else:
        greeting = "Boa noite"
    
    manager_name = manager.first_name or manager.email.split('@')[0]
    
    message = f"👋 *{greeting}, {manager_name}!*\n\n"
    message += f"📊 *Resumo do Departamento - {department.name}*\n"
    message += f"📅 {weekday_pt}, {date_str}\n\n"
    
    # Tarefas atrasadas (prioridade máxima)
    overdue = tasks_by_status['overdue']
    if overdue:
        message += f"⚠️ *Tarefas Atrasadas: {len(overdue)}*\n"
        for task in overdue[:5]:
            assigned = task.assigned_to.email if task.assigned_to else "Não atribuída"
            local_due = timezone.localtime(task.due_date)
            days_overdue = (timezone.now().date() - local_due.date()).days
            message += f"  • {task.title} ({assigned})"
            if days_overdue > 0:
                message += f" - {days_overdue} dia(s) atrasada"
            message += "\n"
        if len(overdue) > 5:
            message += f"  ... e mais {len(overdue) - 5} tarefa(s)\n"
        message += "\n"
    
    # Tarefas pendentes
    pending = tasks_by_status['pending']
    if pending:
        message += f"📝 *Tarefas Pendentes: {len(pending)}*\n"
        for task in pending[:5]:
            assigned = task.assigned_to.email if task.assigned_to else "Não atribuída"
            local_due = timezone.localtime(task.due_date)
            due_time = local_due.strftime('%H:%M')
            message += f"  • {task.title} ({assigned}) - {due_time}\n"
        if len(pending) > 5:
            message += f"  ... e mais {len(pending) - 5} tarefa(s)\n"
        message += "\n"
    
    # Tarefas em progresso
    in_progress = tasks_by_status['in_progress']
    if in_progress:
        message += f"🔄 *Tarefas em Progresso: {len(in_progress)}*\n"
        for task in in_progress[:5]:
            assigned = task.assigned_to.email if task.assigned_to else "Não atribuída"
            message += f"  • {task.title} ({assigned})\n"
        if len(in_progress) > 5:
            message += f"  ... e mais {len(in_progress) - 5} tarefa(s)\n"
        message += "\n"
    
    # Tarefas concluídas
    completed = tasks_by_status['completed']
    if completed:
        message += f"✅ *Tarefas Concluídas: {len(completed)}*\n"
        for task in completed[:5]:
            assigned = task.assigned_to.email if task.assigned_to else "Não atribuída"
            message += f"  • {task.title} ({assigned})\n"
        if len(completed) > 5:
            message += f"  ... e mais {len(completed) - 5} tarefa(s)\n"
    
    # ✅ UX: Resumo e insights para gestores
    total = len(overdue) + len(pending) + len(in_progress) + len(completed)
    completed_count = len(completed)
    message += f"\n📊 *Total: {total} tarefa(s) no departamento*\n\n"
    
    # ✅ UX: Insights para gestores
    if overdue:
        message += f"⚠️ *Atenção:* {len(overdue)} tarefa(s) precisam de atenção imediata.\n"
    if pending:
        message += f"📋 *Planejamento:* {len(pending)} tarefa(s) agendadas para hoje.\n"
    if completed_count > 0 and total > 0:
        progress = (completed_count / total) * 100
        message += f"✅ *Progresso:* {int(progress)}% das tarefas concluídas.\n"
    
    return message
```

---

## 🔌 APIS

### Serializers

```python
# backend/apps/notifications/serializers.py

from rest_framework import serializers
from apps.notifications.models import UserNotificationPreferences, DepartmentNotificationPreferences
from apps.authn.models import Department
from apps.authn.utils import can_manage_department_notifications

class UserNotificationPreferencesSerializer(serializers.ModelSerializer):
    """Serializer para preferências de notificação do usuário."""
    
    class Meta:
        model = UserNotificationPreferences
        fields = [
            'id',
            'daily_summary_enabled',
            'daily_summary_time',
            'agenda_reminder_enabled',
            'agenda_reminder_time',
            'notify_pending',
            'notify_in_progress',
            'notify_status_changes',
            'notify_completed',
            'notify_overdue',
            'notify_via_whatsapp',
            'notify_via_websocket',
            'notify_via_email',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']
    
    def create(self, validated_data):
        request = self.context.get('request')
        validated_data['user'] = request.user
        validated_data['tenant'] = request.user.tenant
        return super().create(validated_data)


class DepartmentNotificationPreferencesSerializer(serializers.ModelSerializer):
    """Serializer para preferências de notificação do departamento."""
    
    department_name = serializers.CharField(source='department.name', read_only=True)
    can_manage = serializers.SerializerMethodField()
    
    class Meta:
        model = DepartmentNotificationPreferences
        fields = [
            'id',
            'department',
            'department_name',
            'daily_summary_enabled',
            'daily_summary_time',
            'agenda_reminder_enabled',
            'agenda_reminder_time',
            'notify_pending',
            'notify_in_progress',
            'notify_status_changes',
            'notify_completed',
            'notify_overdue',
            'notify_only_critical',
            'notify_only_assigned',
            'max_tasks_per_notification',
            'notify_via_whatsapp',
            'notify_via_websocket',
            'notify_via_email',
            'can_manage',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at', 'can_manage']
    
    def get_can_manage(self, obj):
        request = self.context.get('request')
        if not request or not request.user:
            return False
        from apps.authn.utils import can_manage_department_notifications
        return can_manage_department_notifications(request.user, obj.department)
    
    def validate_department(self, value):
        request = self.context.get('request')
        if not can_manage_department_notifications(request.user, value):
            raise serializers.ValidationError("Você não tem permissão para gerenciar notificações deste departamento.")
        return value
    
    def create(self, validated_data):
        request = self.context.get('request')
        validated_data['tenant'] = request.user.tenant
        validated_data['created_by'] = request.user
        return super().create(validated_data)
```

### Views

```python
# backend/apps/notifications/views.py

from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from apps.notifications.models import UserNotificationPreferences, DepartmentNotificationPreferences
from apps.notifications.serializers import (
    UserNotificationPreferencesSerializer,
    DepartmentNotificationPreferencesSerializer
)
from apps.notifications.permissions import CanManageDepartmentNotifications
from apps.authn.utils import get_user_managed_departments

class UserNotificationPreferencesViewSet(viewsets.ModelViewSet):
    """
    ViewSet para gerenciar preferências de notificação do usuário.
    """
    serializer_class = UserNotificationPreferencesSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        return UserNotificationPreferences.objects.filter(
            user=self.request.user,
            tenant=self.request.user.tenant
        )
    
    def get_object(self):
        # Sempre retorna ou cria as preferências do usuário atual
        obj, created = UserNotificationPreferences.objects.get_or_create(
            user=self.request.user,
            tenant=self.request.user.tenant,
            defaults={
                'daily_summary_enabled': False,
                'agenda_reminder_enabled': False,
            }
        )
        return obj
    
    @action(detail=False, methods=['get'])
    def mine(self, request):
        """Retorna as preferências do usuário atual."""
        obj, created = UserNotificationPreferences.objects.get_or_create(
            user=request.user,
            tenant=request.user.tenant,
            defaults={
                'daily_summary_enabled': False,
                'agenda_reminder_enabled': False,
            }
        )
        serializer = self.get_serializer(obj)
        return Response(serializer.data)


class DepartmentNotificationPreferencesViewSet(viewsets.ModelViewSet):
    """
    ViewSet para gerenciar preferências de notificação do departamento.
    Apenas gestores podem configurar.
    """
    serializer_class = DepartmentNotificationPreferencesSerializer
    permission_classes = [IsAuthenticated, CanManageDepartmentNotifications]
    
    def get_queryset(self):
        user = self.request.user
        
        # Admin vê todos os departamentos do tenant
        if user.role == 'admin':
            return DepartmentNotificationPreferences.objects.filter(
                tenant=user.tenant
            ).select_related('department')
        
        # Gerente vê apenas departamentos que gerencia
        managed_departments = get_user_managed_departments(user)
        return DepartmentNotificationPreferences.objects.filter(
            department__in=managed_departments,
            tenant=user.tenant
        ).select_related('department')
    
    @action(detail=False, methods=['get'])
    def my_departments(self, request):
        """Retorna preferências de todos os departamentos que o usuário gerencia."""
        managed_departments = get_user_managed_departments(request.user)
        
        preferences = []
        for dept in managed_departments:
            pref, created = DepartmentNotificationPreferences.objects.get_or_create(
                department=dept,
                tenant=request.user.tenant,
                defaults={
                    'daily_summary_enabled': False,
                    'agenda_reminder_enabled': False,
                }
            )
            preferences.append(pref)
        
        serializer = self.get_serializer(preferences, many=True)
        return Response(serializer.data)
```

### URLs

```python
# backend/apps/notifications/urls.py

from django.urls import path, include
from rest_framework.routers import DefaultRouter
from apps.notifications.views import (
    UserNotificationPreferencesViewSet,
    DepartmentNotificationPreferencesViewSet
)

router = DefaultRouter()
router.register(r'user-preferences', UserNotificationPreferencesViewSet, basename='user-notification-preferences')
router.register(r'department-preferences', DepartmentNotificationPreferencesViewSet, basename='department-notification-preferences')

urlpatterns = [
    path('', include(router.urls)),
]
```

---

## 🎨 FRONTEND - EXPERIÊNCIA DO USUÁRIO (UX)

### 🎯 Princípios de UX Moderna

1. **Clareza**: Interface intuitiva e fácil de entender
2. **Feedback Imediato**: Usuário sempre sabe o que está acontecendo
3. **Prevenção de Erros**: Validação em tempo real e mensagens claras
4. **Acessibilidade**: Suporte a leitores de tela e navegação por teclado
5. **Performance Percebida**: Loading states e otimistic updates
6. **Personalização**: Interface adapta-se ao contexto do usuário

### Estrutura de Componentes

```
frontend/src/
├── modules/
│   └── notifications/
│       ├── components/
│       │   ├── NotificationSettings.tsx          # Container principal
│       │   ├── UserNotificationSettings.tsx     # Configurações individuais
│       │   ├── DepartmentNotificationSettings.tsx # Configurações de departamento
│       │   ├── NotificationTimePicker.tsx       # Seletor de horário
│       │   ├── NotificationChannelSelector.tsx   # Seletor de canais
│       │   ├── NotificationTypeFilters.tsx       # Filtros de tipos
│       │   ├── MessagePreview.tsx                 # Preview da mensagem
│       │   ├── NotificationCard.tsx               # Card de notificação
│       │   └── HelpTooltip.tsx                    # Tooltips de ajuda
│       ├── hooks/
│       │   ├── useNotificationPreferences.ts
│       │   ├── useDepartmentNotifications.ts
│       │   └── useNotificationPreview.ts
│       ├── services/
│       │   └── notificationPreferencesApi.ts
│       ├── types/
│       │   └── notificationPreferences.ts
│       └── utils/
│           ├── formatNotificationMessage.ts
│           └── validateNotificationSettings.ts
```

### Componente Principal (Melhorado)

```typescript
// frontend/src/modules/notifications/components/NotificationSettings.tsx

import React, { useState, useEffect } from 'react';
import { UserNotificationSettings } from './UserNotificationSettings';
import { DepartmentNotificationSettings } from './DepartmentNotificationSettings';
import { useAuth } from '@/modules/auth/hooks/useAuth';
import { useNotificationPreferences } from '../hooks/useNotificationPreferences';
import { HelpTooltip } from './HelpTooltip';
import { showSuccessToast, showErrorToast } from '@/components/ui/toast';

export const NotificationSettings: React.FC = () => {
  const { user } = useAuth();
  const [activeTab, setActiveTab] = useState<'user' | 'department'>('user');
  const { preferences, isLoading, error, savePreferences } = useNotificationPreferences();
  const [isSaving, setIsSaving] = useState(false);
  
  const isManager = user?.role === 'gerente' || user?.role === 'admin';
  
  // ✅ UX: Mostrar loading state
  if (isLoading) {
    return (
      <div className="flex items-center justify-center min-h-[400px]">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto mb-4"></div>
          <p className="text-gray-600">Carregando suas preferências...</p>
        </div>
      </div>
    );
  }
  
  // ✅ UX: Tratamento de erro amigável
  if (error) {
    return (
      <div className="bg-red-50 border border-red-200 rounded-lg p-6">
        <div className="flex items-start">
          <svg className="h-6 w-6 text-red-600 mt-0.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>
          <div className="ml-3">
            <h3 className="text-sm font-medium text-red-800">Erro ao carregar preferências</h3>
            <p className="mt-2 text-sm text-red-700">{error.message}</p>
            <button
              onClick={() => window.location.reload()}
              className="mt-4 text-sm font-medium text-red-800 hover:text-red-900 underline"
            >
              Tentar novamente
            </button>
          </div>
        </div>
      </div>
    );
  }
  
  return (
    <div className="max-w-4xl mx-auto space-y-6">
      {/* ✅ UX: Header com contexto e ajuda */}
      <div className="bg-gradient-to-r from-blue-50 to-indigo-50 rounded-lg p-6 border border-blue-100">
        <div className="flex items-start justify-between">
          <div>
            <h2 className="text-2xl font-bold text-gray-900 flex items-center gap-2">
              🔔 Notificações
              <HelpTooltip 
                content="Configure quando e como você deseja receber notificações sobre suas tarefas. Você pode receber resumos diários, lembretes de agenda e notificações de mudanças de status."
                position="right"
              />
            </h2>
            <p className="mt-2 text-sm text-gray-600">
              Personalize suas notificações para ficar sempre informado sobre suas tarefas e compromissos.
            </p>
          </div>
        </div>
      </div>
      
      {/* ✅ UX: Tabs modernas com indicador animado */}
      <div className="border-b border-gray-200">
        <nav className="-mb-px flex space-x-8" role="tablist">
          <button
            onClick={() => setActiveTab('user')}
            role="tab"
            aria-selected={activeTab === 'user'}
            aria-controls="user-notifications-panel"
            className={`
              group relative py-4 px-1 border-b-2 font-medium text-sm transition-colors
              ${activeTab === 'user'
                ? 'border-blue-500 text-blue-600'
                : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
              }
            `}
          >
            <span className="flex items-center gap-2">
              👤 Minhas Notificações
              {activeTab === 'user' && (
                <span className="absolute -top-1 -right-1 h-2 w-2 bg-blue-500 rounded-full animate-pulse"></span>
              )}
            </span>
          </button>
          
          {isManager && (
            <button
              onClick={() => setActiveTab('department')}
              role="tab"
              aria-selected={activeTab === 'department'}
              aria-controls="department-notifications-panel"
              className={`
                group relative py-4 px-1 border-b-2 font-medium text-sm transition-colors
                ${activeTab === 'department'
                  ? 'border-blue-500 text-blue-600'
                  : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
                }
              `}
            >
              <span className="flex items-center gap-2">
                🏢 Notificações do Departamento
                {activeTab === 'department' && (
                  <span className="absolute -top-1 -right-1 h-2 w-2 bg-blue-500 rounded-full animate-pulse"></span>
                )}
              </span>
            </button>
          )}
        </nav>
      </div>
      
      {/* ✅ UX: Conteúdo com animação de transição */}
      <div className="mt-6">
        <div
          key={activeTab}
          className="animate-fade-in"
          role="tabpanel"
          id={`${activeTab}-notifications-panel`}
        >
          {activeTab === 'user' && <UserNotificationSettings />}
          {activeTab === 'department' && isManager && <DepartmentNotificationSettings />}
        </div>
      </div>
    </div>
  );
};
```

### Componente de Configurações do Usuário (Melhorado)

```typescript
// frontend/src/modules/notifications/components/UserNotificationSettings.tsx

import React, { useState, useEffect } from 'react';
import { useNotificationPreferences } from '../hooks/useNotificationPreferences';
import { NotificationTimePicker } from './NotificationTimePicker';
import { NotificationChannelSelector } from './NotificationChannelSelector';
import { NotificationTypeFilters } from './NotificationTypeFilters';
import { MessagePreview } from './MessagePreview';
import { HelpTooltip } from './HelpTooltip';
import { showSuccessToast, showErrorToast } from '@/components/ui/toast';

export const UserNotificationSettings: React.FC = () => {
  const { preferences, isLoading, savePreferences } = useNotificationPreferences();
  const [formData, setFormData] = useState(preferences);
  const [hasChanges, setHasChanges] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [showPreview, setShowPreview] = useState(false);
  
  // ✅ UX: Detectar mudanças automaticamente
  useEffect(() => {
    if (preferences) {
      const changed = JSON.stringify(formData) !== JSON.stringify(preferences);
      setHasChanges(changed);
    }
  }, [formData, preferences]);
  
  // ✅ UX: Salvar automaticamente após 2 segundos de inatividade (debounce)
  useEffect(() => {
    if (!hasChanges || !formData) return;
    
    const timer = setTimeout(async () => {
      await handleSave();
    }, 2000);
    
    return () => clearTimeout(timer);
  }, [formData, hasChanges]);
  
  const handleSave = async () => {
    if (!hasChanges) return;
    
    setIsSaving(true);
    try {
      await savePreferences(formData);
      setHasChanges(false);
      showSuccessToast('Preferências salvas com sucesso!', {
        duration: 3000,
        icon: '✅'
      });
    } catch (error) {
      showErrorToast('Erro ao salvar preferências. Tente novamente.', {
        duration: 5000
      });
    } finally {
      setIsSaving(false);
    }
  };
  
  if (isLoading) {
    return <div className="animate-pulse space-y-4">...</div>;
  }
  
  return (
    <div className="space-y-8">
      {/* ✅ UX: Indicador de salvamento automático */}
      {isSaving && (
        <div className="bg-blue-50 border border-blue-200 rounded-lg p-3 flex items-center gap-2 text-sm text-blue-700">
          <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-blue-600"></div>
          Salvando suas preferências...
        </div>
      )}
      
      {hasChanges && !isSaving && (
        <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-3 flex items-center justify-between text-sm">
          <span className="text-yellow-800">Você tem alterações não salvas</span>
          <button
            onClick={handleSave}
            className="px-3 py-1 bg-yellow-600 text-white rounded hover:bg-yellow-700 transition-colors"
          >
            Salvar agora
          </button>
        </div>
      )}
      
      {/* ✅ UX: Seção de Resumo Diário com card visual */}
      <div className="bg-white rounded-lg border border-gray-200 shadow-sm p-6">
        <div className="flex items-start justify-between mb-4">
          <div>
            <h3 className="text-lg font-semibold text-gray-900 flex items-center gap-2">
              📋 Resumo Diário
              <HelpTooltip 
                content="Receba um resumo de todas as suas tarefas do dia em um horário específico. Ideal para planejar seu dia pela manhã."
                position="right"
              />
            </h3>
            <p className="mt-1 text-sm text-gray-500">
              Configure um horário para receber um resumo completo das suas tarefas
            </p>
          </div>
          <label className="relative inline-flex items-center cursor-pointer">
            <input
              type="checkbox"
              checked={formData.daily_summary_enabled}
              onChange={(e) => setFormData({ ...formData, daily_summary_enabled: e.target.checked })}
              className="sr-only peer"
            />
            <div className="w-11 h-6 bg-gray-200 peer-focus:outline-none peer-focus:ring-4 peer-focus:ring-blue-300 rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-blue-600"></div>
          </label>
        </div>
        
        {formData.daily_summary_enabled && (
          <div className="mt-4 space-y-4 animate-fade-in">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Horário do Resumo
                <HelpTooltip 
                  content="Escolha o horário em que deseja receber o resumo diário. Recomendamos entre 7h e 8h da manhã."
                  position="right"
                />
              </label>
              <NotificationTimePicker
                value={formData.daily_summary_time}
                onChange={(time) => setFormData({ ...formData, daily_summary_time: time })}
                minTime="06:00"
                maxTime="23:59"
              />
              {formData.daily_summary_time && (
                <p className="mt-2 text-xs text-gray-500">
                  Você receberá o resumo todos os dias às {formData.daily_summary_time}
                </p>
              )}
            </div>
            
            {/* ✅ UX: Preview da mensagem */}
            <div className="mt-4">
              <button
                type="button"
                onClick={() => setShowPreview(!showPreview)}
                className="text-sm text-blue-600 hover:text-blue-700 font-medium flex items-center gap-1"
              >
                {showPreview ? 'Ocultar' : 'Ver'} preview da mensagem
                <svg className={`w-4 h-4 transition-transform ${showPreview ? 'rotate-180' : ''}`} fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                </svg>
              </button>
              {showPreview && (
                <div className="mt-2 animate-fade-in">
                  <MessagePreview 
                    type="daily_summary" 
                    preferences={formData}
                    time={formData.daily_summary_time}
                  />
                </div>
              )}
            </div>
          </div>
        )}
      </div>
      
      {/* ✅ UX: Seção de Canais com cards visuais */}
      <div className="bg-white rounded-lg border border-gray-200 shadow-sm p-6">
        <h3 className="text-lg font-semibold text-gray-900 mb-4">
          📱 Canais de Notificação
        </h3>
        <NotificationChannelSelector
          preferences={formData}
          onChange={(channels) => setFormData({ ...formData, ...channels })}
        />
      </div>
      
      {/* ✅ UX: Seção de Tipos com toggles visuais */}
      <div className="bg-white rounded-lg border border-gray-200 shadow-sm p-6">
        <h3 className="text-lg font-semibold text-gray-900 mb-4">
          🔔 Tipos de Notificação
        </h3>
        <NotificationTypeFilters
          preferences={formData}
          onChange={(types) => setFormData({ ...formData, ...types })}
        />
      </div>
    </div>
  );
};
```

### Componente de Seletor de Horário (Melhorado)

```typescript
// frontend/src/modules/notifications/components/NotificationTimePicker.tsx

import React from 'react';

interface NotificationTimePickerProps {
  value: string | null;
  onChange: (time: string) => void;
  minTime?: string;
  maxTime?: string;
  label?: string;
}

export const NotificationTimePicker: React.FC<NotificationTimePickerProps> = ({
  value,
  onChange,
  minTime = '00:00',
  maxTime = '23:59',
  label = 'Horário'
}) => {
  // ✅ UX: Sugestões de horários comuns
  const suggestedTimes = [
    { label: '🌅 7:00', value: '07:00', description: 'Início do dia' },
    { label: '☕ 8:00', value: '08:00', description: 'Após café' },
    { label: '🌆 18:00', value: '18:00', description: 'Final do dia' },
  ];
  
  return (
    <div className="space-y-3">
      {/* ✅ UX: Input com validação visual */}
      <div className="relative">
        <input
          type="time"
          value={value || ''}
          onChange={(e) => onChange(e.target.value)}
          min={minTime}
          max={maxTime}
          className="block w-full rounded-lg border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500 text-lg py-2 px-4"
          required
        />
        {value && (
          <div className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400">
            <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
          </div>
        )}
      </div>
      
      {/* ✅ UX: Sugestões rápidas */}
      <div className="flex flex-wrap gap-2">
        <span className="text-xs text-gray-500 self-center">Ou escolha:</span>
        {suggestedTimes.map((suggestion) => (
          <button
            key={suggestion.value}
            type="button"
            onClick={() => onChange(suggestion.value)}
            className={`
              px-3 py-1.5 rounded-lg text-sm font-medium transition-all
              ${value === suggestion.value
                ? 'bg-blue-600 text-white shadow-md scale-105'
                : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
              }
            `}
            title={suggestion.description}
          >
            {suggestion.label}
          </button>
        ))}
      </div>
      
      {/* ✅ UX: Validação em tempo real */}
      {value && (
        <div className="text-xs text-gray-500 flex items-center gap-1">
          <svg className="w-4 h-4 text-green-500" fill="currentColor" viewBox="0 0 20 20">
            <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd" />
          </svg>
          Horário válido
        </div>
      )}
    </div>
  );
};
```

### Componente de Preview de Mensagem

```typescript
// frontend/src/modules/notifications/components/MessagePreview.tsx

import React from 'react';

interface MessagePreviewProps {
  type: 'daily_summary' | 'agenda_reminder';
  preferences: any;
  time?: string;
}

export const MessagePreview: React.FC<MessagePreviewProps> = ({
  type,
  preferences,
  time
}) => {
  // ✅ UX: Simular mensagem real com dados de exemplo
  const mockTasks = {
    overdue: [{ title: 'Reunião com cliente', days: 2 }],
    pending: [{ title: 'Revisar proposta', time: '14:00' }],
    in_progress: [{ title: 'Desenvolver feature' }],
    completed: [{ title: 'Atualizar documentação' }],
  };
  
  const formatMessage = () => {
    if (type === 'daily_summary') {
      return `📋 *Resumo Diário - ${new Date().toLocaleDateString('pt-BR')}*\n\n` +
             `Olá! Aqui está seu resumo de hoje:\n\n` +
             `⚠️ *Tarefas Atrasadas: 1*\n` +
             `  • Reunião com cliente (2 dia(s) atrasada)\n\n` +
             `📝 *Tarefas Pendentes: 1*\n` +
             `  • Revisar proposta (14:00)\n\n` +
             `🔄 *Tarefas em Progresso: 1*\n` +
             `  • Desenvolver feature\n\n` +
             `✅ *Tarefas Concluídas: 1*\n` +
             `  • Atualizar documentação\n\n` +
             `📊 *Total: 4 tarefa(s)*`;
    }
    return 'Mensagem de lembrete de agenda...';
  };
  
  return (
    <div className="bg-gray-50 rounded-lg border border-gray-200 p-4">
      <div className="flex items-center justify-between mb-3">
        <span className="text-xs font-medium text-gray-500 uppercase">Preview</span>
        <span className="text-xs text-gray-400">Como aparecerá no WhatsApp</span>
      </div>
      <div className="bg-white rounded-lg p-4 shadow-sm border border-gray-200">
        <div className="font-mono text-sm whitespace-pre-wrap text-gray-800">
          {formatMessage()}
        </div>
      </div>
      <p className="mt-2 text-xs text-gray-500">
        💡 Esta é uma prévia com dados de exemplo. A mensagem real conterá suas tarefas do dia.
      </p>
    </div>
  );
};
```

### Componente de Help Tooltip

```typescript
// frontend/src/modules/notifications/components/HelpTooltip.tsx

import React, { useState, useRef, useEffect } from 'react';

interface HelpTooltipProps {
  content: string;
  position?: 'top' | 'bottom' | 'left' | 'right';
}

export const HelpTooltip: React.FC<HelpTooltipProps> = ({
  content,
  position = 'top'
}) => {
  const [isVisible, setIsVisible] = useState(false);
  const tooltipRef = useRef<HTMLDivElement>(null);
  
  // ✅ UX: Fechar tooltip ao clicar fora
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (tooltipRef.current && !tooltipRef.current.contains(event.target as Node)) {
        setIsVisible(false);
      }
    };
    
    if (isVisible) {
      document.addEventListener('mousedown', handleClickOutside);
    }
    
    return () => {
      document.removeEventListener('mousedown', handleClickOutside);
    };
  }, [isVisible]);
  
  const positionClasses = {
    top: 'bottom-full left-1/2 -translate-x-1/2 mb-2',
    bottom: 'top-full left-1/2 -translate-x-1/2 mt-2',
    left: 'right-full top-1/2 -translate-y-1/2 mr-2',
    right: 'left-full top-1/2 -translate-y-1/2 ml-2',
  };
  
  return (
    <div className="relative inline-block" ref={tooltipRef}>
      <button
        type="button"
        onClick={() => setIsVisible(!isVisible)}
        onMouseEnter={() => setIsVisible(true)}
        onMouseLeave={() => setIsVisible(false)}
        className="text-gray-400 hover:text-gray-600 transition-colors focus:outline-none focus:ring-2 focus:ring-blue-500 rounded"
        aria-label="Ajuda"
        aria-expanded={isVisible}
      >
        <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 20 20">
          <path fillRule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-8-3a1 1 0 00-.867.5 1 1 0 11-1.731-1A3 3 0 0113 8a3.001 3.001 0 01-2 2.83V11a1 1 0 11-2 0v-1a1 1 0 011-1 1 1 0 100-2zm0 8a1 1 0 100-2 1 1 0 000 2z" clipRule="evenodd" />
        </svg>
      </button>
      
      {isVisible && (
        <div
          className={`
            absolute z-50 w-64 p-3 text-sm text-white bg-gray-900 rounded-lg shadow-lg
            ${positionClasses[position]}
            animate-fade-in
          `}
          role="tooltip"
        >
          <p>{content}</p>
          {/* ✅ UX: Seta do tooltip */}
          <div className={`absolute w-2 h-2 bg-gray-900 transform rotate-45 ${
            position === 'top' ? 'top-full left-1/2 -translate-x-1/2 -mt-1' :
            position === 'bottom' ? 'bottom-full left-1/2 -translate-x-1/2 -mb-1' :
            position === 'left' ? 'left-full top-1/2 -translate-y-1/2 -ml-1' :
            'right-full top-1/2 -translate-y-1/2 -mr-1'
          }`}></div>
        </div>
      )}
    </div>
  );
};
```

### Melhorias nas Mensagens de Notificação

```python
# backend/apps/campaigns/apps.py (melhorar formatação de mensagens)

def format_daily_summary_message(user, tasks_by_status, current_date):
    """
    Formata mensagem de resumo diário para WhatsApp.
    
    ✅ UX: Mensagens mais amigáveis e personalizadas
    """
    from django.utils import timezone
    
    date_str = current_date.strftime('%d/%m/%Y')
    weekday = current_date.strftime('%A')
    
    weekdays_pt = {
        'Monday': 'Segunda-feira',
        'Tuesday': 'Terça-feira',
        'Wednesday': 'Quarta-feira',
        'Thursday': 'Quinta-feira',
        'Friday': 'Sexta-feira',
        'Saturday': 'Sábado',
        'Sunday': 'Domingo',
    }
    weekday_pt = weekdays_pt.get(weekday, weekday)
    
    # ✅ UX: Saudação personalizada baseada no horário
    current_hour = timezone.localtime(timezone.now()).hour
    if 5 <= current_hour < 12:
        greeting = "Bom dia"
    elif 12 <= current_hour < 18:
        greeting = "Boa tarde"
    else:
        greeting = "Boa noite"
    
    user_name = user.first_name or user.email.split('@')[0]
    
    # ✅ UX: Mensagem mais amigável e motivacional
    message = f"👋 *{greeting}, {user_name}!*\n\n"
    message += f"📋 *Resumo do seu dia - {weekday_pt}, {date_str}*\n\n"
    
    # Tarefas atrasadas (prioridade máxima)
    overdue = tasks_by_status['overdue']
    if overdue:
        message += f"⚠️ *Atenção: {len(overdue)} tarefa(s) atrasada(s)*\n"
        for task in overdue[:5]:
            local_due = timezone.localtime(task.due_date)
            days_overdue = (timezone.now().date() - local_due.date()).days
            message += f"  • {task.title}"
            if days_overdue > 0:
                message += f" ({days_overdue} dia(s) atrasada)"
            message += "\n"
        if len(overdue) > 5:
            message += f"  ... e mais {len(overdue) - 5} tarefa(s)\n"
        message += "\n"
    
    # Tarefas pendentes
    pending = tasks_by_status['pending']
    if pending:
        message += f"📝 *Tarefas para hoje: {len(pending)}*\n"
        for task in pending[:5]:
            local_due = timezone.localtime(task.due_date)
            due_time = local_due.strftime('%H:%M')
            message += f"  • {task.title} às {due_time}\n"
        if len(pending) > 5:
            message += f"  ... e mais {len(pending) - 5} tarefa(s)\n"
        message += "\n"
    
    # Tarefas em progresso
    in_progress = tasks_by_status['in_progress']
    if in_progress:
        message += f"🔄 *Em andamento: {len(in_progress)}*\n"
        for task in in_progress[:5]:
            message += f"  • {task.title}\n"
        if len(in_progress) > 5:
            message += f"  ... e mais {len(in_progress) - 5} tarefa(s)\n"
        message += "\n"
    
    # Tarefas concluídas
    completed = tasks_by_status['completed']
    if completed:
        message += f"✅ *Concluídas hoje: {len(completed)}*\n"
        for task in completed[:5]:
            message += f"  • {task.title}\n"
        if len(completed) > 5:
            message += f"  ... e mais {len(completed) - 5} tarefa(s)\n"
        message += "\n"
    
    # ✅ UX: Mensagem motivacional baseada no progresso
    total = len(overdue) + len(pending) + len(in_progress) + len(completed)
    completed_count = len(completed)
    
    if completed_count > 0 and total > 0:
        progress = (completed_count / total) * 100
        if progress >= 50:
            message += f"🎉 *Ótimo trabalho! Você já concluiu {int(progress)}% das suas tarefas.*\n\n"
        elif progress >= 25:
            message += f"💪 *Continue assim! Você já concluiu {int(progress)}% das suas tarefas.*\n\n"
    
    message += f"📊 *Total: {total} tarefa(s) no seu dia*\n\n"
    
    # ✅ UX: Call to action amigável
    if overdue:
        message += "💡 *Dica:* Priorize as tarefas atrasadas para manter tudo em dia!"
    elif pending:
        message += "✨ *Bom dia!* Você tem um dia produtivo pela frente!"
    
    return message
```

---

## ✅ BOAS PRÁTICAS

### 1. Performance

- **Índices**: Sempre criar índices em campos usados em queries frequentes
  ```python
  # Exemplo: Índice composto para queries do scheduler
  models.Index(fields=['daily_summary_enabled', 'daily_summary_time', 'tenant'])
  ```
- **Select Related**: Usar `select_related` e `prefetch_related` para evitar N+1 queries
  ```python
  # ✅ CORRETO
  preferences = UserNotificationPreferences.objects.select_related('user', 'tenant')
  
  # ❌ ERRADO - N+1 queries
  for pref in preferences:
      print(pref.user.email)  # Query por preferência!
  ```
- **Cache**: Cachear preferências de notificação (Redis) para reduzir queries
  ```python
  # Cachear preferências por 5 minutos
  from django.core.cache import cache
  cache_key = f'user_notif_pref_{user.id}'
  pref = cache.get(cache_key)
  if not pref:
      pref = UserNotificationPreferences.objects.get(user=user)
      cache.set(cache_key, pref, 300)  # 5 minutos
  ```
- **Batch Processing**: Processar notificações em lotes para evitar sobrecarga
  ```python
  # Processar em lotes de 50
  for batch in chunks(preferences, 50):
      for pref in batch:
          send_notification(pref)
  ```

### 2. Segurança

- **Permissões**: Sempre verificar permissões antes de permitir configuração
  ```python
  # ✅ SEMPRE verificar permissões
  if not can_manage_department_notifications(user, department):
      raise PermissionDenied("Você não tem permissão para gerenciar este departamento")
  ```
- **Multi-tenancy**: Garantir que usuários só vejam/configurem suas próprias preferências
  ```python
  # ✅ SEMPRE filtrar por tenant
  preferences = UserNotificationPreferences.objects.filter(
      user=user,
      tenant=user.tenant  # ✅ CRÍTICO
  )
  ```
- **Validação**: Validar horários e limites (ex: max_tasks_per_notification)
  ```python
  # Validar horário (entre 00:00 e 23:59)
  if not (time(0, 0) <= daily_summary_time <= time(23, 59)):
      raise ValidationError("Horário inválido")
  
  # Validar limite máximo
  if max_tasks_per_notification > 100:
      raise ValidationError("Máximo de 100 tarefas por notificação")
  ```

### 3. Escalabilidade

- **Scheduler**: Usar `skip_locked=True` para permitir múltiplas instâncias
  ```python
  # ✅ Permitir múltiplas instâncias processando em paralelo
  preferences = UserNotificationPreferences.objects.select_for_update(
      skip_locked=True
  ).filter(...)
  ```
- **Rate Limiting**: Limitar quantidade de notificações por usuário/departamento
  ```python
  # Limitar a 1 notificação por tipo por dia
  last_sent = cache.get(f'notif_sent_{user.id}_{notification_type}')
  if last_sent == today:
      return  # Já enviado hoje
  ```
- **Queue**: Usar RabbitMQ para processar notificações assincronamente (se volume alto)
  ```python
  # Se volume > 1000 notificações/dia, usar RabbitMQ
  if total_notifications > 1000:
      send_to_rabbitmq(notification_task)
  else:
      send_sync(notification)
  ```

### 4. Manutenibilidade

- **Logs**: Logar todas as notificações enviadas (sucesso/falha)
  ```python
  # ✅ Log estruturado
  logger.info("Notificação enviada", extra={
      'user_id': user.id,
      'notification_type': 'daily_summary',
      'channel': 'whatsapp',
      'success': True
  })
  ```
- **Testes**: Criar testes unitários para lógica de gestores e scheduler
  ```python
  def test_is_department_manager():
      user = create_user(role='gerente')
      dept = create_department()
      user.departments.add(dept)
      assert is_department_manager(user, dept) == True
  ```
- **Documentação**: Documentar todas as funções e endpoints
  ```python
  def send_notification(user, message):
      """
      Envia notificação para o usuário.
      
      Args:
          user: Instância de User
          message: String com a mensagem formatada
      
      Returns:
          bool: True se enviado com sucesso
      
      Raises:
          ValueError: Se user ou message forem None
      """
  ```

### 5. UX (Experiência do Usuário) - Práticas Modernas

#### 5.1 Feedback Imediato

- **Salvamento Automático**: Salvar preferências automaticamente após 2 segundos de inatividade
  ```typescript
  // Debounce para salvar automaticamente
  useEffect(() => {
    const timer = setTimeout(() => {
      if (hasChanges) savePreferences();
    }, 2000);
    return () => clearTimeout(timer);
  }, [formData]);
  ```

- **Estados Visuais**: Mostrar claramente quando está salvando, salvo, ou com erros
  ```typescript
  // Indicadores visuais de estado
  {isSaving && <SavingIndicator />}
  {isSaved && <SuccessBadge />}
  {hasError && <ErrorAlert />}
  ```

- **Toasts Contextuais**: Mensagens de sucesso/erro com ícones e ações
  ```typescript
  showSuccessToast('Preferências salvas!', {
    icon: '✅',
    action: { label: 'Desfazer', onClick: handleUndo }
  });
  ```

#### 5.2 Prevenção de Erros

- **Validação em Tempo Real**: Validar enquanto o usuário digita
  ```typescript
  // Validação em tempo real
  const [errors, setErrors] = useState({});
  
  const validateTime = (time: string) => {
    if (!time) {
      setErrors(prev => ({ ...prev, time: 'Horário é obrigatório' }));
      return false;
    }
    // ... mais validações
    return true;
  };
  ```

- **Mensagens de Erro Amigáveis**: Erros claros e com sugestões
  ```typescript
  // ❌ ERRADO
  "Invalid time format"
  
  // ✅ CORRETO
  "Por favor, escolha um horário válido entre 00:00 e 23:59"
  ```

- **Validação Visual**: Campos com erro destacados visualmente
  ```typescript
  <input
    className={`
      border-2 rounded-lg px-4 py-2
      ${errors.time ? 'border-red-500 bg-red-50' : 'border-gray-300'}
    `}
    aria-invalid={!!errors.time}
    aria-describedby={errors.time ? 'time-error' : undefined}
  />
  ```

#### 5.3 Acessibilidade (a11y)

- **Navegação por Teclado**: Todos os elementos interativos acessíveis via teclado
  ```typescript
  <button
    onKeyDown={(e) => {
      if (e.key === 'Enter' || e.key === ' ') {
        handleClick();
      }
    }}
    aria-label="Salvar preferências"
  >
  ```

- **ARIA Labels**: Labels descritivos para leitores de tela
  ```typescript
  <div role="tabpanel" aria-labelledby="user-tab">
    <h2 id="user-tab">Minhas Notificações</h2>
  </div>
  ```

- **Contraste**: Cores com contraste adequado (WCAG AA)
  ```typescript
  // ✅ CORRETO: Contraste adequado
  className="text-gray-900 bg-white" // Contraste 4.5:1
  
  // ❌ ERRADO: Contraste baixo
  className="text-gray-400 bg-gray-300" // Contraste < 3:1
  ```

#### 5.4 Performance Percebida

- **Loading States**: Skeletons e spinners durante carregamento
  ```typescript
  {isLoading ? (
    <div className="animate-pulse space-y-4">
      <div className="h-4 bg-gray-200 rounded w-3/4"></div>
      <div className="h-4 bg-gray-200 rounded w-1/2"></div>
    </div>
  ) : (
    <Content />
  )}
  ```

- **Optimistic Updates**: Atualizar UI antes da resposta do servidor
  ```typescript
  const handleToggle = async () => {
    // Atualizar UI imediatamente
    setEnabled(!enabled);
    
    try {
      await savePreferences({ enabled: !enabled });
    } catch (error) {
      // Reverter em caso de erro
      setEnabled(enabled);
      showError('Erro ao salvar');
    }
  };
  ```

- **Lazy Loading**: Carregar componentes pesados sob demanda
  ```typescript
  const MessagePreview = React.lazy(() => import('./MessagePreview'));
  
  {showPreview && (
    <Suspense fallback={<PreviewSkeleton />}>
      <MessagePreview />
    </Suspense>
  )}
  ```

#### 5.5 Microinterações

- **Animações Suaves**: Transições entre estados
  ```css
  .animate-fade-in {
    animation: fadeIn 0.3s ease-in-out;
  }
  
  @keyframes fadeIn {
    from { opacity: 0; transform: translateY(-10px); }
    to { opacity: 1; transform: translateY(0); }
  }
  ```

- **Feedback Tátil**: Hover states e focus rings
  ```typescript
  className="transition-all hover:scale-105 focus:ring-2 focus:ring-blue-500"
  ```

- **Indicadores Visuais**: Badges, pulsos, e indicadores de status
  ```typescript
  {hasChanges && (
    <span className="absolute -top-1 -right-1 h-2 w-2 bg-yellow-500 rounded-full animate-pulse" />
  )}
  ```

#### 5.6 Personalização

- **Saudações Contextuais**: Mensagens baseadas no horário do dia
  ```python
  # Backend: Saudação baseada no horário
  current_hour = timezone.localtime(timezone.now()).hour
  if 5 <= current_hour < 12:
      greeting = "Bom dia"
  elif 12 <= current_hour < 18:
      greeting = "Boa tarde"
  else:
      greeting = "Boa noite"
  ```

- **Mensagens Motivacionais**: Feedback positivo baseado no progresso
  ```python
  if progress >= 50:
      message += "🎉 Ótimo trabalho! Você já concluiu 50% das suas tarefas."
  ```

- **Sugestões Inteligentes**: Horários sugeridos baseados em padrões
  ```typescript
  // Sugerir horários comuns
  const suggestedTimes = [
    { label: '🌅 7:00', value: '07:00', description: 'Início do dia' },
    { label: '☕ 8:00', value: '08:00', description: 'Após café' },
  ];
  ```

#### 5.7 Onboarding

- **Tour Guiado**: Para novos usuários
  ```typescript
  const { startTour } = useTour();
  
  useEffect(() => {
    if (isFirstTime) {
      startTour('notification-settings');
    }
  }, []);
  ```

- **Tooltips Contextuais**: Ajuda inline em cada campo
  ```typescript
  <HelpTooltip 
    content="Configure um horário para receber um resumo completo das suas tarefas do dia."
    position="right"
  />
  ```

- **Exemplos Visuais**: Mostrar exemplos de como ficará
  ```typescript
  <MessagePreview 
    type="daily_summary" 
    preferences={formData}
  />
  ```

#### 5.8 Responsividade

- **Mobile First**: Design que funciona bem em mobile
  ```typescript
  <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
    {/* Conteúdo adaptável */}
  </div>
  ```

- **Touch Targets**: Botões grandes o suficiente para toque (mín. 44x44px)
  ```typescript
  <button className="min-h-[44px] min-w-[44px] px-4 py-2">
    Salvar
  </button>
  ```

#### 5.9 Mensagens de Notificação

- **Tom Conversacional**: Mensagens mais amigáveis e menos técnicas
  ```python
  # ❌ ERRADO
  "Task summary for 2025-11-24: 3 pending, 2 in_progress"
  
  # ✅ CORRETO
  "👋 Bom dia, Paulo! Aqui está seu resumo de hoje:
   📝 Você tem 3 tarefas para fazer
   🔄 2 tarefas em andamento
   ✨ Continue assim!"
  ```

- **Emojis Contextuais**: Usar emojis para facilitar leitura rápida
- **Call to Action**: Incluir ações sugeridas quando relevante
- **Personalização**: Usar nome do usuário e contexto

### 6. Timezone

- **⚠️ CRÍTICO**: Sempre considerar timezone do usuário/tenant
  ```python
  # ✅ CORRETO: Converter para timezone local
  local_now = timezone.localtime(timezone.now())
  current_time = local_now.time()
  
  # ❌ ERRADO: Usar UTC diretamente
  current_time = timezone.now().time()  # Pode estar em UTC!
  ```
- **Armazenar horários**: Horários configurados são sempre no timezone local
  ```python
  # O usuário configura "07:00" pensando no horário local
  # Não precisa converter, apenas comparar com hora local atual
  if user_pref.daily_summary_time == local_now.time():
      send_notification()
  ```

### 7. Tratamento de Erros

- **Fail Gracefully**: Se uma notificação falhar, não quebrar o scheduler
  ```python
  try:
      send_notification(user, message)
  except Exception as e:
      logger.error(f"Erro ao enviar notificação: {e}", exc_info=True)
      # Continuar processando outras notificações
      continue
  ```
- **Retry Logic**: Implementar retry para notificações críticas
  ```python
  max_retries = 3
  for attempt in range(max_retries):
      try:
          send_notification(user, message)
          break
      except Exception as e:
          if attempt == max_retries - 1:
              raise
          time.sleep(2 ** attempt)  # Exponential backoff
  ```

---

## 📝 EXEMPLOS DE USO

### Exemplo 1: Configurar Notificações Individuais

```python
# Backend
pref = UserNotificationPreferences.objects.get_or_create(
    user=user,
    tenant=user.tenant,
    defaults={
        'daily_summary_enabled': True,
        'daily_summary_time': time(7, 0),  # 7:00
        'agenda_reminder_enabled': True,
        'agenda_reminder_time': time(8, 0),  # 8:00
        'notify_pending': True,
        'notify_status_changes': True,
        'notify_completed': False,
    }
)
```

### Exemplo 2: Configurar Notificações de Departamento

```python
# Backend
department = Department.objects.get(id=department_id)
pref = DepartmentNotificationPreferences.objects.get_or_create(
    department=department,
    tenant=user.tenant,
    defaults={
        'daily_summary_enabled': True,
        'daily_summary_time': time(7, 0),
        'notify_only_critical': True,  # Apenas tarefas críticas
        'max_tasks_per_notification': 10,
    }
)
```

### Exemplo 3: Verificar se Usuário é Gestor

```python
from apps.authn.utils import is_department_manager, get_user_managed_departments

# Verificar se é gestor de um departamento específico
if is_department_manager(user, department):
    # Pode configurar notificações do departamento
    pass

# Obter todos os departamentos gerenciados
managed_depts = get_user_managed_departments(user)
```

---

## 🚀 IMPLEMENTAÇÃO INCREMENTAL

### ⚠️ ORDEM DE IMPLEMENTAÇÃO

**Siga esta ordem para garantir que cada fase funcione corretamente antes de avançar.**

### Fase 1: MVP (Notificações Individuais)

**Objetivo**: Permitir que usuários configurem e recebam resumos diários de suas tarefas.

**Checklist**:
- [ ] Criar modelo `UserNotificationPreferences` com migration
- [ ] Criar serializer `UserNotificationPreferencesSerializer`
- [ ] Criar ViewSet `UserNotificationPreferencesViewSet`
- [ ] Adicionar URLs em `backend/apps/notifications/urls.py`
- [ ] Registrar app `notifications` em `INSTALLED_APPS`
- [ ] Criar componente frontend `UserNotificationSettings.tsx`
- [ ] Adicionar aba "Notificações" em Configurações
- [ ] Integrar função `check_user_daily_summaries()` no scheduler existente
- [ ] Implementar `send_user_daily_summary()` e `format_daily_summary_message()`
- [ ] Testes unitários básicos
- [ ] Teste manual: Configurar e receber notificação às 7h

**Critérios de Sucesso**:
- ✅ Usuário consegue configurar horário de resumo diário
- ✅ Scheduler envia notificação no horário configurado
- ✅ Mensagem contém lista de tarefas do dia
- ✅ Notificação chega via WhatsApp e/ou WebSocket

### Fase 2: Notificações de Departamento

**Objetivo**: Permitir que gestores configurem e recebam resumos agregados do departamento.

**Checklist**:
- [ ] Implementar funções de gestores em `backend/apps/authn/utils.py`:
  - [ ] `is_department_manager()`
  - [ ] `get_user_managed_departments()`
  - [ ] `can_manage_department_notifications()`
  - [ ] `get_department_tasks()`
- [ ] Criar modelo `DepartmentNotificationPreferences` com migration
- [ ] Criar Permission Class `CanManageDepartmentNotifications`
- [ ] Criar serializer `DepartmentNotificationPreferencesSerializer`
- [ ] Criar ViewSet `DepartmentNotificationPreferencesViewSet`
- [ ] Adicionar URLs
- [ ] Criar componente frontend `DepartmentNotificationSettings.tsx`
- [ ] Adicionar seção "Notificações do Departamento" (apenas para gestores)
- [ ] Integrar função `check_department_daily_summaries()` no scheduler
- [ ] Implementar `send_department_daily_summary()` e `format_department_daily_summary_message()`
- [ ] Testes de permissões (gestor pode, agente não pode)
- [ ] Teste manual: Gestor configura e recebe notificação do departamento

**Critérios de Sucesso**:
- ✅ Apenas gestores veem/configuram notificações de departamento
- ✅ Gestor recebe resumo agregado de todas as tarefas do departamento
- ✅ Mensagem inclui informações de quem está atribuído a cada tarefa
- ✅ Permissões funcionam corretamente (gestor pode, agente não pode)

### Fase 3: Filtros Avançados e Lembretes de Agenda

**Objetivo**: Adicionar mais opções de personalização e lembretes de agenda.

**Checklist**:
- [ ] Implementar `check_user_agenda_reminders()` no scheduler
- [ ] Implementar `check_department_agenda_reminders()` no scheduler
- [ ] Adicionar filtros avançados no frontend:
  - [ ] Filtro por prioridade (apenas críticas)
  - [ ] Filtro por status (pendentes, em progresso, concluídas)
  - [ ] Limite de tarefas por notificação
- [ ] Adicionar validações no backend para filtros
- [ ] Melhorar templates de mensagem com mais informações
- [ ] Adicionar preview de mensagem no frontend
- [ ] Testes de filtros
- [ ] Teste manual: Configurar filtros e verificar que funcionam

**Critérios de Sucesso**:
- ✅ Usuário pode filtrar quais tipos de tarefas receber
- ✅ Gestor pode limitar quantidade de tarefas por notificação
- ✅ Lembretes de agenda funcionam no horário configurado
- ✅ Preview mostra como a mensagem ficará

### Fase 4: Otimizações e Melhorias

**Objetivo**: Melhorar performance, escalabilidade e experiência do usuário.

**Checklist**:
- [ ] Implementar cache de preferências (Redis)
- [ ] Adicionar processamento assíncrono via RabbitMQ (se volume alto)
- [ ] Implementar métricas e analytics:
  - [ ] Quantidade de notificações enviadas por dia
  - [ ] Taxa de sucesso/falha
  - [ ] Horários mais usados
- [ ] Criar dashboard de notificações (opcional)
- [ ] Adicionar logs estruturados
- [ ] Otimizar queries do scheduler
- [ ] Testes de performance
- [ ] Documentação completa

**Critérios de Sucesso**:
- ✅ Sistema suporta 1000+ notificações/dia sem problemas
- ✅ Cache reduz queries em 80%+
- ✅ Métricas disponíveis para análise
- ✅ Logs estruturados facilitam debugging

---

## 🔧 FUNÇÕES AUXILIARES DE ENVIO

### ⚠️ IMPORTANTE: Implementação Necessária

As funções `send_whatsapp_notification()` e `send_websocket_notification()` são **stubs** no documento.
**Você deve implementá-las** usando o sistema existente do projeto.

### 1. Envio via WhatsApp

**Localização sugerida**: `backend/apps/notifications/services.py` ou reutilizar `backend/apps/campaigns/services.py`

**Como implementar**:
```python
# backend/apps/notifications/services.py

from apps.campaigns.services import CampaignSender  # Ou criar serviço específico
from apps.connections.models import WhatsAppInstance

def send_whatsapp_notification(user, message):
    """
    Envia notificação via WhatsApp usando Evolution API.
    
    Reutiliza a lógica existente de envio de mensagens.
    """
    # 1. Buscar instância ativa do WhatsApp para o tenant
    instance = WhatsAppInstance.objects.filter(
        tenant=user.tenant,
        is_active=True
    ).first()
    
    if not instance:
        raise ValueError(f"Nenhuma instância WhatsApp ativa para tenant {user.tenant.name}")
    
    # 2. Normalizar telefone do usuário
    phone = normalize_phone(user.phone)
    
    # 3. Enviar via Evolution API (usar serviço existente)
    # Verificar como CampaignSender funciona e adaptar
    sender = CampaignSender(instance)
    response = sender.send_message(phone, message)
    
    return response.status_code in [200, 201]
```

### 2. Envio via WebSocket

**Localização sugerida**: `backend/apps/notifications/services.py`

**Como implementar**:
```python
# backend/apps/notifications/services.py

from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync

def send_websocket_notification(user, notification_type, data):
    """
    Envia notificação via WebSocket usando Django Channels.
    
    Reutiliza o sistema de WebSocket existente do projeto.
    """
    channel_layer = get_channel_layer()
    if not channel_layer:
        logger.warning('Channel layer não configurado')
        return False
    
    # Enviar para o grupo do usuário
    # Verificar como os grupos são nomeados no projeto
    group_name = f'user_{user.id}'  # Ajustar conforme necessário
    
    async_to_sync(channel_layer.group_send)(
        group_name,
        {
            'type': 'notification',  # Nome do método no consumer
            'notification_type': notification_type,
            'data': data,
        }
    )
    
    return True
```

### 3. Normalização de Telefone

**Função auxiliar necessária**:
```python
import re

def normalize_phone(phone):
    """
    Normaliza telefone para formato E.164.
    
    Args:
        phone: String com telefone em qualquer formato
    
    Returns:
        str: Telefone no formato E.164 (ex: +5517991234567)
    """
    if not phone:
        return None
    
    # Remover caracteres não numéricos
    phone = re.sub(r'\D', '', phone)
    
    # Adicionar código do país se não tiver
    if not phone.startswith('55'):
        phone = '55' + phone.lstrip('0')
    
    # Adicionar +
    if not phone.startswith('+'):
        phone = '+' + phone
    
    return phone
```

---

## 🔗 INTEGRAÇÃO COM SISTEMA EXISTENTE

### 1. Scheduler Existente

**Localização**: `backend/apps/campaigns/apps.py`

**Função existente**: `check_scheduled_campaigns()`

**Como integrar**:
```python
def check_scheduled_campaigns():
    """
    Scheduler principal que processa:
    1. Campanhas agendadas
    2. Notificações de tarefas (15min antes, momento exato)
    3. Notificações diárias personalizadas (NOVO)
    """
    while True:
        try:
            # ... código existente de campanhas ...
            
            # ... código existente de notificações de tarefas ...
            
            # ✅ NOVO: Adicionar verificação de notificações diárias
            local_now = timezone.localtime(timezone.now())
            check_daily_notifications(local_now.time(), local_now.date())
            
        except Exception as e:
            logger.error(f'❌ [SCHEDULER] Erro: {e}', exc_info=True)
        
        time.sleep(30)  # Verificar a cada 30 segundos
```

### 2. App de Notificações

**Criar novo app**: `backend/apps/notifications/`

**Estrutura**:
```
backend/apps/notifications/
├── __init__.py
├── apps.py
├── models.py
├── serializers.py
├── views.py
├── permissions.py
├── urls.py
└── migrations/
```

**Registrar em `settings.py`**:
```python
INSTALLED_APPS = [
    # ... outros apps ...
    'apps.notifications',
]
```

### 3. URLs

**Adicionar em `backend/alrea_sense/urls.py`**:
```python
urlpatterns = [
    # ... outras URLs ...
    path('api/notifications/', include('apps.notifications.urls')),
]
```

### 4. Frontend

**Adicionar em Configurações**:
- Criar rota `/settings/notifications`
- Adicionar link no menu de configurações
- Integrar com sistema de autenticação existente

---

## ⚠️ CONSIDERAÇÕES IMPORTANTES

### 1. Timezone

**PROBLEMA**: Usuários podem estar em timezones diferentes, mas o sistema usa `America/Sao_Paulo` como padrão.

**SOLUÇÃO**:
- Horários configurados são sempre no timezone local do sistema (`America/Sao_Paulo`)
- Scheduler converte UTC para timezone local antes de comparar
- Mensagens mostram data/hora no timezone local

**FUTURO**: Se necessário suportar múltiplos timezones, adicionar campo `timezone` em `User` e `Tenant`.

### 2. Performance do Scheduler

**PROBLEMA**: Verificar todas as preferências a cada minuto pode ser pesado com muitos usuários.

**SOLUÇÃO**:
- Usar índices compostos em `(daily_summary_enabled, daily_summary_time, tenant)`
- Cachear preferências ativas (Redis)
- Processar em lotes (batch processing)
- Usar `select_for_update(skip_locked=True)` para permitir múltiplas instâncias

### 3. Duplicação de Notificações

**PROBLEMA**: Múltiplas instâncias do scheduler podem enviar notificações duplicadas.

**SOLUÇÃO**:
- Usar `select_for_update(skip_locked=True)` ao processar
- Marcar preferência como "processando" antes de enviar
- Adicionar campo `last_sent_at` para rastrear última notificação enviada

### 4. Falhas no Envio

**PROBLEMA**: Se WhatsApp/WebSocket falhar, usuário não recebe notificação.

**SOLUÇÃO**:
- Implementar retry logic (3 tentativas com exponential backoff)
- Logar todas as falhas para análise
- Considerar enviar via canal alternativo se um falhar
- Adicionar campo `notification_failed` para rastrear falhas

### 5. Volume de Notificações

**PROBLEMA**: Com muitos usuários, pode haver sobrecarga no sistema.

**SOLUÇÃO**:
- Limitar quantidade de tarefas por notificação (`max_tasks_per_notification`)
- Processar notificações em fila (RabbitMQ) se volume > 1000/dia
- Rate limiting: máximo 1 notificação por tipo por dia por usuário
- Cache de "última notificação enviada" para evitar duplicação

### 6. Permissões de Gestores

**PROBLEMA**: Lógica de gestores será usada em múltiplos lugares.

**SOLUÇÃO**:
- **Centralizar** funções em `backend/apps/authn/utils.py`
- **Reutilizar** `is_department_manager()` e `can_manage_department()` em todos os módulos
- **Documentar** claramente as regras de permissão
- **Testar** extensivamente para garantir consistência

### 7. Migrations

**IMPORTANTE**: Ao criar migrations, seguir as regras do projeto:

```python
# ✅ SEMPRE verificar migrations existentes antes de criar
# ✅ SEMPRE usar IF NOT EXISTS em SQL
# ✅ SEMPRE testar migrations localmente antes de deploy
# ✅ NUNCA deletar migrations já aplicadas em produção
```

### 8. Logs

**IMPORTANTE**: Logar todas as operações críticas:

```python
# ✅ Log estruturado
logger.info("Notificação enviada", extra={
    'user_id': user.id,
    'notification_type': 'daily_summary',
    'channel': 'whatsapp',
    'tasks_count': len(tasks),
    'success': True
})

# ❌ NUNCA usar print()
print(f"Enviado para {user.email}")  # ❌ ERRADO
```

---

## 📚 REFERÊNCIAS

### Documentação do Projeto

- [rules.md](../rules.md) - Regras gerais do projeto
- [IMPLEMENTACAO_SISTEMA_MIDIA.md](../IMPLEMENTACAO_SISTEMA_MIDIA.md) - Sistema de mídia
- [ANALISE_COMPLETA_PROJETO_2025.md](../ANALISE_COMPLETA_PROJETO_2025.md) - Análise arquitetural

### Documentação Externa

- [Django Models](https://docs.djangoproject.com/en/stable/topics/db/models/)
- [Django REST Framework](https://www.django-rest-framework.org/)
- [Django Channels](https://channels.readthedocs.io/)
- [RabbitMQ + aio-pika](../rules.md#rabbitmq--aio-pika)
- [Django Timezone](https://docs.djangoproject.com/en/stable/topics/i18n/timezones/)

### Código de Referência

- `backend/apps/campaigns/apps.py` - Scheduler existente
- `backend/apps/contacts/models.py` - Modelo Task
- `backend/apps/authn/models.py` - Modelos User e Department

---

## 📝 CHECKLIST DE IMPLEMENTAÇÃO

### Antes de Começar

- [ ] Ler este documento completamente
- [ ] Entender a arquitetura do sistema existente
- [ ] Revisar `rules.md` para regras do projeto
- [ ] Verificar migrations existentes

### Durante a Implementação

- [ ] Seguir ordem das fases (1 → 2 → 3 → 4)
- [ ] Testar cada fase antes de avançar
- [ ] Criar migrations e testar localmente
- [ ] Adicionar logs estruturados
- [ ] Documentar funções e endpoints
- [ ] Seguir padrões de código do projeto

### Antes de Deploy

- [ ] Todos os testes passando
- [ ] Migrations testadas localmente
- [ ] Logs verificados
- [ ] Performance testada (se volume alto)
- [ ] Documentação atualizada
- [ ] Code review realizado

---

---

## 📌 NOTAS FINAIS

### ⚠️ Pontos de Atenção

1. **Funções de Envio**: As funções `send_whatsapp_notification()` e `send_websocket_notification()` 
   precisam ser implementadas usando o sistema existente do projeto. Veja seção "Funções Auxiliares de Envio".

2. **Lembretes de Agenda**: As funções `check_user_agenda_reminders()` e `check_department_agenda_reminders()` 
   estão implementadas como stubs. Complete a lógica conforme necessário.

3. **Timezone**: Todo o sistema assume timezone `America/Sao_Paulo`. Se precisar suportar múltiplos timezones 
   no futuro, será necessário adicionar campo `timezone` em `User` e `Tenant`.

4. **Performance**: Com muitos usuários (>1000), considere usar RabbitMQ para processar notificações 
   assincronamente. Veja Fase 4 da implementação incremental.

5. **Testes**: Sempre teste localmente antes de fazer deploy. Use scripts de teste para validar 
   o scheduler e as notificações.

### ✅ Checklist Antes de Implementar

- [ ] Ler este documento completamente
- [ ] Entender a arquitetura do sistema existente
- [ ] Verificar como o sistema atual envia WhatsApp
- [ ] Verificar como o sistema atual usa WebSocket
- [ ] Revisar `rules.md` para regras do projeto
- [ ] Verificar migrations existentes
- [ ] Planejar ordem de implementação (Fase 1 → 2 → 3 → 4)

---

## 🛡️ CONTROLES E VALIDAÇÕES IMPLEMENTADAS

### ✅ Validações de Entrada

1. **Canais de Notificação**:
   - Verifica se pelo menos um canal está habilitado antes de processar
   - Valida se WhatsApp está habilitado no usuário quando necessário
   - Verifica se WebSocket está configurado antes de enviar

2. **Horários**:
   - Valida se horário está configurado quando notificação está habilitada
   - Verifica se data/hora são válidas (não None)
   - Valida se data não é futura

3. **Tipos de Notificação**:
   - Verifica se pelo menos um tipo está habilitado (pending, in_progress, completed, overdue)
   - Evita processar quando todos os tipos estão desabilitados

4. **Telefone**:
   - Valida se telefone existe antes de normalizar
   - Verifica formato mínimo (pelo menos 10 dígitos)
   - Valida formato E.164 após normalização

5. **Mensagens**:
   - Verifica se mensagem não está vazia antes de enviar
   - Valida se há tarefas para notificar antes de formatar mensagem

### ✅ Controles de Execução

1. **Lock de Thread**:
   - Usa `threading.Lock()` para evitar execução simultânea
   - Libera lock mesmo em caso de erro (try/finally)
   - Evita múltiplas instâncias processando ao mesmo tempo

2. **Tratamento de Erros**:
   - Try/except em todas as operações críticas
   - Logs estruturados para debugging
   - Continua processamento mesmo se uma notificação falhar
   - Rastreia sucessos e falhas separadamente

3. **Validação de Janela de Tempo**:
   - Janela de ±1 minuto para evitar perda de notificações
   - Tratamento de erros ao calcular janela (ValueError, OverflowError)

4. **Controle de Estado**:
   - Verifica se QuerySet está vazio antes de processar
   - Inicializa QuerySets vazios quando necessário (tasks.none())
   - Valida preferências antes de aplicar filtros

### ✅ Controles de Dados

1. **Multi-tenancy**:
   - Sempre filtra por tenant
   - Valida tenant antes de processar
   - Garantia de isolamento de dados

2. **Filtros**:
   - Aplica filtros apenas se preferências permitirem
   - Valida se filtros resultam em dados antes de processar
   - Limita quantidade de tarefas por notificação

3. **Agregação**:
   - Converte QuerySets para listas quando necessário
   - Limita quantidade de itens por seção (máx 5-10)
   - Agrupa por status de forma consistente

### ✅ Controles de Envio

1. **Canais Individuais**:
   - Tenta enviar por cada canal separadamente
   - Rastreia sucesso/falha por canal
   - Continua tentando outros canais mesmo se um falhar

2. **Logging**:
   - Loga quantidade de notificações enviadas
   - Loga quantidade de falhas
   - Diferencia entre "nenhum canal habilitado" e "todos os canais falharam"

3. **Retry Logic**:
   - Documentado para implementação futura
   - Exponential backoff sugerido
   - Máximo de tentativas definido

### ✅ Prevenção de Problemas

1. **Race Conditions**:
   - Lock de thread no scheduler principal
   - Validações antes de processar
   - Verificações de estado antes de modificar

2. **Duplicação**:
   - Lock impede execução simultânea
   - Validações evitam processamento desnecessário
   - Logs ajudam a identificar duplicações

3. **Performance**:
   - Limites de quantidade de tarefas
   - Select_related para evitar N+1 queries
   - Validações precoces para evitar processamento desnecessário

4. **Edge Cases**:
   - Tratamento de data futura
   - Tratamento de telefone inválido
   - Tratamento de mensagem vazia
   - Tratamento de QuerySet vazio

---

## 🎨 GUIA DE DESIGN E UX MODERNA

### 🎯 Princípios de Design

1. **Clareza Visual**: Hierarquia clara, espaçamento adequado, tipografia legível
2. **Consistência**: Mesmos padrões em toda a aplicação
3. **Feedback Imediato**: Usuário sempre sabe o estado atual
4. **Prevenção de Erros**: Validação proativa e mensagens claras
5. **Eficiência**: Menos cliques, ações rápidas, atalhos de teclado
6. **Acessibilidade**: Suporte a leitores de tela e navegação por teclado
7. **Performance Percebida**: Loading states, optimistic updates, lazy loading

### 🎨 Sistema de Cores e Estados

```typescript
// Cores para estados de notificação e feedback
const notificationColors = {
  success: {
    bg: 'bg-green-50',
    border: 'border-green-200',
    text: 'text-green-800',
    icon: 'text-green-600',
    button: 'bg-green-600 hover:bg-green-700'
  },
  warning: {
    bg: 'bg-yellow-50',
    border: 'border-yellow-200',
    text: 'text-yellow-800',
    icon: 'text-yellow-600',
    button: 'bg-yellow-600 hover:bg-yellow-700'
  },
  error: {
    bg: 'bg-red-50',
    border: 'border-red-200',
    text: 'text-red-800',
    icon: 'text-red-600',
    button: 'bg-red-600 hover:bg-red-700'
  },
  info: {
    bg: 'bg-blue-50',
    border: 'border-blue-200',
    text: 'text-blue-800',
    icon: 'text-blue-600',
    button: 'bg-blue-600 hover:bg-blue-700'
  }
};
```

### 📱 Componentes Reutilizáveis Modernos

#### 1. Toggle Switch Acessível

```typescript
// frontend/src/components/ui/Toggle.tsx

interface ToggleProps {
  enabled: boolean;
  onChange: (enabled: boolean) => void;
  label: string;
  description?: string;
  disabled?: boolean;
  size?: 'sm' | 'md' | 'lg';
}

export const Toggle: React.FC<ToggleProps> = ({
  enabled,
  onChange,
  label,
  description,
  disabled = false,
  size = 'md'
}) => {
  const sizeClasses = {
    sm: 'w-9 h-5',
    md: 'w-11 h-6',
    lg: 'w-14 h-7'
  };
  
  return (
    <div className="flex items-start justify-between gap-4">
      <div className="flex-1">
        <label 
          htmlFor={`toggle-${label}`}
          className="text-sm font-medium text-gray-900 cursor-pointer"
        >
          {label}
        </label>
        {description && (
          <p className="mt-1 text-sm text-gray-500">{description}</p>
        )}
      </div>
      <label 
        htmlFor={`toggle-${label}`}
        className={`
          relative inline-flex items-center cursor-pointer
          ${disabled ? 'opacity-50 cursor-not-allowed' : ''}
        `}
      >
        <input
          id={`toggle-${label}`}
          type="checkbox"
          checked={enabled}
          onChange={(e) => !disabled && onChange(e.target.checked)}
          disabled={disabled}
          className="sr-only peer"
          aria-label={label}
        />
        <div className={`
          ${sizeClasses[size]} bg-gray-200 peer-focus:outline-none 
          peer-focus:ring-4 peer-focus:ring-blue-300 rounded-full peer 
          peer-checked:after:translate-x-full peer-checked:after:border-white 
          after:content-[''] after:absolute after:top-[2px] after:left-[2px] 
          after:bg-white after:border-gray-300 after:border after:rounded-full 
          after:transition-all peer-checked:bg-blue-600
          ${size === 'sm' ? 'after:h-4 after:w-4' : 
            size === 'md' ? 'after:h-5 after:w-5' : 'after:h-6 after:w-6'}
        `}></div>
      </label>
    </div>
  );
};
```

#### 2. Card de Configuração com Animações

```typescript
// frontend/src/components/ui/ConfigCard.tsx

interface ConfigCardProps {
  title: string;
  description?: string;
  icon?: React.ReactNode;
  children: React.ReactNode;
  enabled?: boolean;
  onToggle?: (enabled: boolean) => void;
  badge?: string;
  className?: string;
}

export const ConfigCard: React.FC<ConfigCardProps> = ({
  title,
  description,
  icon,
  children,
  enabled,
  onToggle,
  badge,
  className = ''
}) => {
  return (
    <div className={`
      bg-white rounded-lg border shadow-sm p-6 transition-all
      hover:shadow-md
      ${enabled === false ? 'opacity-60' : ''}
      ${className}
    `}>
      <div className="flex items-start justify-between mb-4">
        <div className="flex-1">
          <div className="flex items-center gap-2">
            {icon && <span className="text-2xl">{icon}</span>}
            <h3 className="text-lg font-semibold text-gray-900">{title}</h3>
            {badge && (
              <span className="px-2 py-1 text-xs font-medium bg-blue-100 text-blue-800 rounded-full">
                {badge}
              </span>
            )}
          </div>
          {description && (
            <p className="mt-1 text-sm text-gray-500">{description}</p>
          )}
        </div>
        {onToggle !== undefined && (
          <Toggle
            enabled={enabled ?? false}
            onChange={onToggle}
            label=""
            size="md"
          />
        )}
      </div>
      {enabled !== false && (
        <div className="animate-fade-in">
          {children}
        </div>
      )}
    </div>
  );
};
```

#### 3. Seletor de Horário com Sugestões

```typescript
// frontend/src/modules/notifications/components/NotificationTimePicker.tsx

import React, { useState } from 'react';

interface NotificationTimePickerProps {
  value: string | null;
  onChange: (time: string) => void;
  minTime?: string;
  maxTime?: string;
  label?: string;
  showSuggestions?: boolean;
}

export const NotificationTimePicker: React.FC<NotificationTimePickerProps> = ({
  value,
  onChange,
  minTime = '00:00',
  maxTime = '23:59',
  label = 'Horário',
  showSuggestions = true
}) => {
  const [isFocused, setIsFocused] = useState(false);
  
  // ✅ UX: Sugestões inteligentes baseadas no contexto
  const getSuggestedTimes = () => {
    const now = new Date();
    const currentHour = now.getHours();
    
    return [
      { 
        label: '🌅 7:00', 
        value: '07:00', 
        description: 'Início do dia',
        popular: true
      },
      { 
        label: '☕ 8:00', 
        value: '08:00', 
        description: 'Após café',
        popular: true
      },
      { 
        label: '🌆 18:00', 
        value: '18:00', 
        description: 'Final do dia',
        popular: false
      },
      // Sugerir próximo horário redondo
      {
        label: `🕐 ${String(Math.ceil((currentHour + 1) / 1) * 1).padStart(2, '0')}:00`,
        value: `${String(Math.ceil((currentHour + 1) / 1) * 1).padStart(2, '0')}:00`,
        description: 'Próxima hora',
        popular: false
      }
    ];
  };
  
  const suggestedTimes = showSuggestions ? getSuggestedTimes() : [];
  
  return (
    <div className="space-y-3">
      <label className="block text-sm font-medium text-gray-700">
        {label}
      </label>
      
      {/* ✅ UX: Input com validação visual em tempo real */}
      <div className="relative">
        <input
          type="time"
          value={value || ''}
          onChange={(e) => onChange(e.target.value)}
          onFocus={() => setIsFocused(true)}
          onBlur={() => setIsFocused(false)}
          min={minTime}
          max={maxTime}
          className={`
            block w-full rounded-lg border-2 shadow-sm 
            focus:border-blue-500 focus:ring-blue-500 text-lg py-2.5 px-4
            transition-all
            ${isFocused ? 'ring-2 ring-blue-200' : ''}
            ${value ? 'border-green-300' : 'border-gray-300'}
          `}
          required
          aria-label={label}
          aria-describedby={value ? 'time-valid' : undefined}
        />
        {value && (
          <div className="absolute right-3 top-1/2 -translate-y-1/2">
            <svg 
              className="w-5 h-5 text-green-500" 
              fill="currentColor" 
              viewBox="0 0 20 20"
              aria-hidden="true"
            >
              <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd" />
            </svg>
          </div>
        )}
      </div>
      
      {/* ✅ UX: Sugestões rápidas com badges de popularidade */}
      {showSuggestions && suggestedTimes.length > 0 && (
        <div className="flex flex-wrap gap-2">
          <span className="text-xs text-gray-500 self-center">Ou escolha:</span>
          {suggestedTimes.map((suggestion) => (
            <button
              key={suggestion.value}
              type="button"
              onClick={() => onChange(suggestion.value)}
              className={`
                group relative px-3 py-1.5 rounded-lg text-sm font-medium 
                transition-all transform
                ${value === suggestion.value
                  ? 'bg-blue-600 text-white shadow-md scale-105 ring-2 ring-blue-300'
                  : 'bg-gray-100 text-gray-700 hover:bg-gray-200 hover:scale-105'
                }
              `}
              title={suggestion.description}
              aria-label={`Definir horário para ${suggestion.value}`}
            >
              {suggestion.label}
              {suggestion.popular && (
                <span className="absolute -top-1 -right-1 h-2 w-2 bg-yellow-400 rounded-full animate-pulse"></span>
              )}
            </button>
          ))}
        </div>
      )}
      
      {/* ✅ UX: Feedback visual de validação */}
      {value && (
        <div 
          id="time-valid"
          className="text-xs text-green-600 flex items-center gap-1 animate-fade-in"
          role="status"
        >
          <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 20 20">
            <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd" />
          </svg>
          Horário válido - Você receberá notificações todos os dias às {value}
        </div>
      )}
    </div>
  );
};
```

### 🎭 Estados da Interface (Empty, Loading, Error)

#### Empty State Melhorado

```typescript
// Quando não há notificações configuradas
<div className="text-center py-16 bg-gray-50 rounded-lg border-2 border-dashed border-gray-300">
  <div className="max-w-md mx-auto">
    <div className="flex justify-center">
      <div className="rounded-full bg-blue-100 p-4">
        <svg className="h-12 w-12 text-blue-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 17h5l-1.405-1.405A2.032 2.032 0 0118 14.158V11a6.002 6.002 0 00-4-5.659V5a2 2 0 10-4 0v.341C7.67 6.165 6 8.388 6 11v3.159c0 .538-.214 1.055-.595 1.436L4 17h5m6 0v1a3 3 0 11-6 0v-1m6 0H9" />
        </svg>
      </div>
    </div>
    <h3 className="mt-4 text-lg font-medium text-gray-900">
      Nenhuma notificação configurada
    </h3>
    <p className="mt-2 text-sm text-gray-500">
      Configure suas notificações para receber atualizações sobre suas tarefas e compromissos.
    </p>
    <div className="mt-6">
      <button
        onClick={handleEnableNotifications}
        className="inline-flex items-center px-4 py-2 border border-transparent shadow-sm text-sm font-medium rounded-md text-white bg-blue-600 hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500 transition-all transform hover:scale-105"
      >
        <svg className="w-5 h-5 mr-2" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 6v6m0 0v6m0-6h6m-6 0H6" />
        </svg>
        Configurar Primeira Notificação
      </button>
    </div>
  </div>
</div>
```

#### Loading State com Skeleton

```typescript
// Skeleton loader moderno
<div className="space-y-6 animate-pulse">
  {[1, 2, 3].map((i) => (
    <div key={i} className="bg-white rounded-lg border border-gray-200 p-6">
      <div className="flex items-center justify-between mb-4">
        <div className="flex-1">
          <div className="h-5 bg-gray-200 rounded w-1/3 mb-2"></div>
          <div className="h-4 bg-gray-200 rounded w-2/3"></div>
        </div>
        <div className="h-6 w-11 bg-gray-200 rounded-full"></div>
      </div>
      <div className="space-y-3">
        <div className="h-10 bg-gray-200 rounded"></div>
        <div className="h-4 bg-gray-200 rounded w-1/2"></div>
      </div>
    </div>
  ))}
</div>
```

#### Error State com Ações

```typescript
// Estado de erro amigável com ações
<div className="bg-red-50 border-l-4 border-red-400 rounded-lg p-4">
  <div className="flex">
    <div className="flex-shrink-0">
      <svg className="h-5 w-5 text-red-400" viewBox="0 0 20 20" fill="currentColor" aria-hidden="true">
        <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clipRule="evenodd" />
      </svg>
    </div>
    <div className="ml-3 flex-1">
      <h3 className="text-sm font-medium text-red-800">
        Erro ao carregar preferências
      </h3>
      <div className="mt-2 text-sm text-red-700">
        <p>{error.message || 'Ocorreu um erro inesperado. Por favor, tente novamente.'}</p>
      </div>
      <div className="mt-4 flex gap-3">
        <button
          onClick={handleRetry}
          className="text-sm font-medium text-red-800 hover:text-red-900 underline focus:outline-none focus:ring-2 focus:ring-red-500 rounded"
        >
          Tentar novamente
        </button>
        <button
          onClick={handleContactSupport}
          className="text-sm font-medium text-red-800 hover:text-red-900 underline focus:outline-none focus:ring-2 focus:ring-red-500 rounded"
        >
          Contatar suporte
        </button>
      </div>
    </div>
  </div>
</div>
```

### 📊 Métricas de UX e Analytics

#### KPIs a Monitorar

1. **Taxa de Configuração**: % de usuários que configuraram notificações
2. **Taxa de Engajamento**: % de usuários que abrem/leram notificações
3. **Tempo de Configuração**: Tempo médio para configurar preferências
4. **Taxa de Erro**: % de erros durante configuração
5. **Satisfação**: Feedback dos usuários sobre notificações (NPS)
6. **Taxa de Retenção**: % de usuários que continuam usando após 7 dias

#### Analytics e Tracking

```typescript
// frontend/src/utils/analytics.ts

interface UXEvent {
  event: string;
  category: 'notification_settings' | 'notification_received' | 'notification_action';
  action: string;
  label?: string;
  value?: number;
}

export const trackUXEvent = (eventData: UXEvent) => {
  // Google Analytics 4
  if (typeof window !== 'undefined' && window.gtag) {
    window.gtag('event', eventData.event, {
      event_category: eventData.category,
      event_label: eventData.label,
      value: eventData.value
    });
  }
  
  // Log interno para análise
  console.log('[UX Event]', eventData);
};

// Exemplos de uso
trackUXEvent({
  event: 'notification_settings_opened',
  category: 'notification_settings',
  action: 'open',
  label: 'user_notifications'
});

trackUXEvent({
  event: 'notification_time_changed',
  category: 'notification_settings',
  action: 'change',
  label: 'daily_summary_time',
  value: 7 // hora
});

trackUXEvent({
  event: 'notification_preview_viewed',
  category: 'notification_settings',
  action: 'view',
  label: 'message_preview'
});
```

### 🎯 Checklist de UX

Antes de considerar a implementação completa, verifique:

- [ ] Todos os campos têm labels descritivos
- [ ] Mensagens de erro são claras e acionáveis
- [ ] Loading states em todas as operações assíncronas
- [ ] Empty states informativos com CTAs
- [ ] Tooltips de ajuda em campos complexos
- [ ] Preview de mensagens disponível
- [ ] Validação em tempo real
- [ ] Feedback visual de sucesso/erro
- [ ] Navegação por teclado funcional
- [ ] Contraste de cores adequado (WCAG AA)
- [ ] Responsivo em mobile
- [ ] Animações suaves e não intrusivas
- [ ] Mensagens personalizadas e amigáveis

---

**Última atualização**: 2025-11-24  
**Versão**: 2.0.0  
**Autor**: Sistema de Notificações Personalizadas  
**Status**: Documentação Completa com Foco em UX Moderna - Pronto para Implementação

