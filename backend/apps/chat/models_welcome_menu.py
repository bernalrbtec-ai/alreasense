"""
Modelo para configuração do Menu de Boas-Vindas Automático
"""
import uuid
from django.db import models
from django.core.validators import MinLengthValidator
from apps.tenancy.models import Tenant


class WelcomeMenuConfig(models.Model):
    """
    Configuração do Menu de Boas-Vindas Automático por tenant.
    
    Quando habilitado, envia mensagem automática com menu numerado
    para conversas novas ou fechadas, permitindo que o cliente escolha
    um departamento ou encerre a conversa.
    """
    
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False
    )
    tenant = models.OneToOneField(
        Tenant,
        on_delete=models.CASCADE,
        related_name='welcome_menu_config',
        verbose_name='Tenant',
        help_text='Tenant que possui esta configuração'
    )
    
    # Configurações básicas
    enabled = models.BooleanField(
        default=False,
        verbose_name='Menu Habilitado',
        help_text='Se True, envia menu automático para conversas novas/fechadas'
    )
    
    welcome_message = models.TextField(
        max_length=500,
        blank=True,
        default='',
        verbose_name='Mensagem de Boas-Vindas',
        help_text='Mensagem exibida antes do menu (ex: "Bem-vindo a {tenant_name}")'
    )
    
    # Configurações de departamentos
    departments = models.ManyToManyField(
        'authn.Department',
        related_name='welcome_menus',
        blank=True,
        verbose_name='Departamentos no Menu',
        help_text='Departamentos que aparecerão no menu (em ordem)'
    )
    
    # Opções do menu
    show_close_option = models.BooleanField(
        default=True,
        verbose_name='Mostrar Opção Encerrar',
        help_text='Se True, mostra opção para encerrar conversa no menu'
    )
    
    close_option_text = models.CharField(
        max_length=50,
        default='Encerrar',
        verbose_name='Texto da Opção Encerrar',
        help_text='Texto exibido para opção de encerrar conversa'
    )
    
    # Configurações avançadas
    send_to_new_conversations = models.BooleanField(
        default=True,
        verbose_name='Enviar para Conversas Novas',
        help_text='Se True, envia menu para conversas novas (status=pending)'
    )
    
    send_to_closed_conversations = models.BooleanField(
        default=True,
        verbose_name='Enviar para Conversas Fechadas',
        help_text='Se True, envia menu quando conversa fechada recebe nova mensagem'
    )
    
    # IA (futuro - bloqueado por enquanto)
    ai_enabled = models.BooleanField(
        default=False,
        verbose_name='IA Habilitada',
        help_text='⚠️ BLOQUEADO: Usar IA para processar respostas (addon futuro)'
    )
    
    # ✅ NOVO: Configurações de timeout de inatividade
    inactivity_timeout_enabled = models.BooleanField(
        default=True,
        verbose_name='Timeout de Inatividade',
        help_text='Fecha conversa automaticamente se cliente não responde'
    )
    
    first_reminder_minutes = models.IntegerField(
        default=5,
        verbose_name='Primeiro Lembrete (minutos)',
        help_text='Minutos até enviar primeiro lembrete'
    )
    
    auto_close_minutes = models.IntegerField(
        default=10,
        verbose_name='Fechamento Automático (minutos)',
        help_text='Minutos até fechar conversa automaticamente'
    )
    
    # Metadados
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Criado em')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='Atualizado em')
    
    class Meta:
        db_table = 'chat_welcome_menu_config'
        verbose_name = 'Configuração do Menu de Boas-Vindas'
        verbose_name_plural = 'Configurações dos Menus de Boas-Vindas'
    
    def __str__(self):
        status = "Habilitado" if self.enabled else "Desabilitado"
        return f"Menu {self.tenant.name} ({status})"
    
    def get_menu_text(self) -> str:
        """
        Gera o texto do menu baseado nas configurações.
        
        Returns:
            Texto formatado do menu (ex: "Bem-vindo...\n1- Comercial\n2- Suporte...")
        """
        from apps.authn.models import Department
        
        # Mensagem de boas-vindas
        tenant_name = self.tenant.name
        welcome = self.welcome_message or f"Bem-vindo a {tenant_name}!"
        
        # Buscar departamentos em ordem
        departments_list = list(self.departments.all().order_by('name'))
        
        # Montar menu
        menu_lines = [welcome]
        menu_lines.append("")
        menu_lines.append("Escolha uma opção para atendimento:")
        menu_lines.append("")
        
        # Adicionar departamentos numerados
        for idx, dept in enumerate(departments_list, start=1):
            menu_lines.append(f"{idx} - {dept.name}")
        
        # Adicionar opção de encerrar (se habilitada)
        if self.show_close_option:
            close_num = len(departments_list) + 1
            menu_lines.append(f"{close_num} - {self.close_option_text}")
        
        return "\n".join(menu_lines)
    
    def get_department_by_number(self, number: int) -> 'Department | None':
        """
        Retorna o departamento correspondente ao número escolhido.
        
        Args:
            number: Número escolhido pelo cliente (1, 2, 3, etc)
        
        Returns:
            Department correspondente ou None se número inválido
        """
        departments_list = list(self.departments.all().order_by('name'))
        
        # Validar número
        if number < 1 or number > len(departments_list):
            return None
        
        return departments_list[number - 1]
    
    def is_close_option(self, number: int) -> bool:
        """
        Verifica se o número escolhido corresponde à opção de encerrar.
        
        Args:
            number: Número escolhido pelo cliente
        
        Returns:
            True se for opção de encerrar, False caso contrário
        """
        if not self.show_close_option:
            return False
        
        departments_count = self.departments.count()
        return number == departments_count + 1


class WelcomeMenuTimeout(models.Model):
    """
    Rastreia timeouts ativos do menu de boas-vindas.
    Usado para enviar lembretes e fechar conversas automaticamente.
    """
    
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False
    )
    conversation = models.OneToOneField(
        'Conversation',
        on_delete=models.CASCADE,
        related_name='welcome_menu_timeout',
        verbose_name='Conversa'
    )
    menu_sent_at = models.DateTimeField(
        verbose_name='Menu Enviado Em',
        help_text='Quando o menu foi enviado pela última vez'
    )
    reminder_sent = models.BooleanField(
        default=False,
        verbose_name='Lembrete Enviado',
        help_text='Se já enviou o lembrete de 5 minutos'
    )
    reminder_sent_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='Lembrete Enviado Em',
        help_text='Quando o lembrete foi enviado'
    )
    is_active = models.BooleanField(
        default=True,
        db_index=True,
        verbose_name='Ativo',
        help_text='Se o timeout ainda está ativo (desativa se cliente responder)'
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Criado em')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='Atualizado em')
    
    class Meta:
        db_table = 'chat_welcome_menu_timeout'
        verbose_name = 'Timeout do Menu de Boas-Vindas'
        verbose_name_plural = 'Timeouts dos Menus de Boas-Vindas'
        indexes = [
            models.Index(fields=['is_active', 'menu_sent_at'], name='idx_timeout_active_sent'),
            models.Index(fields=['reminder_sent', 'reminder_sent_at'], name='idx_timeout_reminder'),
        ]
    
    def __str__(self):
        status = "Ativo" if self.is_active else "Inativo"
        return f"Timeout {self.conversation.contact_name or self.conversation.contact_phone} ({status})"

