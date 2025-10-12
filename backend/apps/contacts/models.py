"""
Models para o sistema de contatos enriquecidos
Base para campanhas, disparos e segmentação
"""

from django.db import models
from django.core.validators import RegexValidator
from django.utils import timezone
from decimal import Decimal
import uuid


class Contact(models.Model):
    """
    Contato enriquecido com dados demográficos e comerciais.
    
    Este é o modelo central do sistema de engajamento, usado por:
    - Campanhas de disparo em massa
    - Disparos agendados
    - Análise de comportamento
    - Segmentação avançada
    """
    
    # ==================== IDENTIFICAÇÃO ====================
    id = models.UUIDField(
        primary_key=True, 
        default=uuid.uuid4, 
        editable=False
    )
    
    tenant = models.ForeignKey(
        'tenancy.Tenant',
        on_delete=models.CASCADE,
        related_name='contacts',
        help_text="Tenant proprietário do contato"
    )
    
    # Telefone principal (formato E.164: +5511999999999)
    phone = models.CharField(
        max_length=20,
        validators=[
            RegexValidator(
                regex=r'^\+?[1-9]\d{1,14}$',
                message='Telefone deve estar no formato E.164 (ex: +5511999999999)'
            )
        ],
        help_text="Telefone no formato E.164"
    )
    
    name = models.CharField(
        max_length=200,
        help_text="Nome completo do contato"
    )
    
    email = models.EmailField(
        null=True, 
        blank=True,
        help_text="Email do contato (opcional)"
    )
    
    # ==================== DADOS DEMOGRÁFICOS ====================
    birth_date = models.DateField(
        null=True, 
        blank=True,
        help_text="Data de nascimento (usado para campanhas de aniversário)"
    )
    
    gender = models.CharField(
        max_length=1,
        choices=[
            ('M', 'Masculino'),
            ('F', 'Feminino'),
            ('O', 'Outro'),
            ('N', 'Prefiro não informar')
        ],
        null=True,
        blank=True
    )
    
    # Localização
    city = models.CharField(
        max_length=100, 
        null=True, 
        blank=True,
        help_text="Cidade"
    )
    
    state = models.CharField(
        max_length=2, 
        null=True, 
        blank=True,
        help_text="Estado (UF): SP, RJ, MG..."
    )
    
    country = models.CharField(
        max_length=2,
        default='BR',
        help_text="País (código ISO: BR, US, AR...)"
    )
    
    zipcode = models.CharField(
        max_length=10,
        null=True,
        blank=True,
        help_text="CEP"
    )
    
    # ==================== DADOS COMERCIAIS ====================
    
    # RFM - Recency
    last_purchase_date = models.DateField(
        null=True, 
        blank=True,
        db_index=True,
        help_text="Data da última compra (usado para análise RFM)"
    )
    
    last_visit_date = models.DateField(
        null=True, 
        blank=True,
        help_text="Data da última visita/interação"
    )
    
    # RFM - Frequency
    total_purchases = models.IntegerField(
        default=0,
        help_text="Total de compras realizadas"
    )
    
    # RFM - Monetary
    last_purchase_value = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Valor da última compra"
    )
    
    average_ticket = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
        help_text="Ticket médio de compras"
    )
    
    lifetime_value = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
        help_text="Valor total gasto (LTV)"
    )
    
    # ==================== ENGAJAMENTO ====================
    last_interaction_date = models.DateTimeField(
        null=True,
        blank=True,
        db_index=True,
        help_text="Última vez que interagiu (mensagem enviada ou recebida)"
    )
    
    total_messages_received = models.IntegerField(
        default=0,
        help_text="Total de mensagens enviadas ao contato"
    )
    
    total_messages_sent = models.IntegerField(
        default=0,
        help_text="Total de mensagens recebidas do contato"
    )
    
    total_campaigns_participated = models.IntegerField(
        default=0,
        help_text="Número de campanhas que participou"
    )
    
    total_campaigns_responded = models.IntegerField(
        default=0,
        help_text="Número de campanhas que respondeu"
    )
    
    # ==================== OBSERVAÇÕES E CUSTOMIZAÇÃO ====================
    notes = models.TextField(
        blank=True,
        help_text="Observações livres sobre o contato"
    )
    
    custom_fields = models.JSONField(
        default=dict,
        blank=True,
        help_text="Campos customizados pelo cliente. Ex: {'cargo': 'Gerente', 'empresa': 'ACME Ltd'}"
    )
    
    # ==================== SEGMENTAÇÃO ====================
    tags = models.ManyToManyField(
        'Tag',
        blank=True,
        related_name='contacts',
        help_text="Tags para segmentação (ex: VIP, Inadimplente, Lead Quente)"
    )
    
    lists = models.ManyToManyField(
        'ContactList',
        blank=True,
        related_name='contacts',
        help_text="Listas de contatos (ex: Black Friday 2024, Aniversariantes)"
    )
    
    # ==================== CONTROLE ====================
    is_active = models.BooleanField(
        default=True,
        db_index=True,
        help_text="Contato ativo no sistema"
    )
    
    opted_out = models.BooleanField(
        default=False,
        db_index=True,
        help_text="Contato pediu para não receber mensagens (LGPD)"
    )
    
    opted_out_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Data do opt-out"
    )
    
    # ==================== ORIGEM E METADADOS ====================
    source = models.CharField(
        max_length=50,
        default='manual',
        choices=[
            ('manual', 'Cadastro Manual'),
            ('import', 'Importação CSV'),
            ('whatsapp', 'WhatsApp Gateway'),
            ('api', 'API Pública'),
            ('form', 'Formulário Web')
        ],
        help_text="Origem do contato"
    )
    
    referred_by = models.CharField(
        max_length=200,
        null=True,
        blank=True,
        help_text="Nome de quem indicou o contato"
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    created_by = models.ForeignKey(
        'authn.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='contacts_created',
        help_text="Usuário que criou o contato"
    )
    
    # ==================== META ====================
    class Meta:
        db_table = 'contacts_contact'
        verbose_name = 'Contato'
        verbose_name_plural = 'Contatos'
        ordering = ['-created_at']
        
        # Garante que cada telefone é único por tenant
        unique_together = [['tenant', 'phone']]
        
        # Índices para performance
        indexes = [
            models.Index(fields=['tenant', 'phone']),
            models.Index(fields=['tenant', 'email']),
            models.Index(fields=['tenant', 'is_active']),
            models.Index(fields=['tenant', 'opted_out']),
            models.Index(fields=['last_purchase_date']),
            models.Index(fields=['birth_date']),
            models.Index(fields=['last_interaction_date']),
        ]
    
    def __str__(self):
        return f"{self.name} ({self.phone})"
    
    # ==================== PROPERTIES (Métricas Calculadas) ====================
    
    @property
    def days_since_last_purchase(self):
        """Quantos dias desde a última compra"""
        if not self.last_purchase_date:
            return None
        return (timezone.now().date() - self.last_purchase_date).days
    
    @property
    def days_since_last_interaction(self):
        """Quantos dias desde a última interação"""
        if not self.last_interaction_date:
            return None
        return (timezone.now() - self.last_interaction_date).days
    
    @property
    def lifecycle_stage(self):
        """
        Estágio do ciclo de vida do cliente
        
        Returns:
            str: 'lead', 'customer', 'at_risk', 'churned'
        """
        if self.total_purchases == 0:
            return 'lead'
        
        days = self.days_since_last_purchase
        if days is None:
            return 'lead'
        
        # Configuração: ajustar conforme negócio
        if days <= 30:
            return 'customer'  # Cliente ativo
        elif days <= 90:
            return 'at_risk'   # Em risco de churn
        else:
            return 'churned'   # Perdido
    
    @property
    def rfm_segment(self):
        """
        Segmento RFM simplificado
        
        Returns:
            str: 'champions', 'loyal', 'at_risk', 'hibernating', 'lost'
        """
        # Simplified RFM (pode evoluir para scoring completo)
        days = self.days_since_last_purchase or 9999
        frequency = self.total_purchases
        monetary = float(self.lifetime_value)
        
        # Champions: comprou recente, frequente e gasta bem
        if days <= 30 and frequency >= 5 and monetary >= 500:
            return 'champions'
        
        # Loyal: compra frequente mas não tão recente
        if days <= 60 and frequency >= 3:
            return 'loyal'
        
        # At Risk: era bom cliente mas sumiu
        if days <= 90 and frequency >= 3:
            return 'at_risk'
        
        # Hibernating: não compra há muito tempo
        if days <= 180:
            return 'hibernating'
        
        # Lost: perdido
        return 'lost'
    
    @property
    def engagement_score(self):
        """
        Score de engajamento (0-100)
        
        Baseado em:
        - Respostas a campanhas
        - Interações recentes
        - Frequência de compra
        """
        score = 0
        
        # Respondeu campanhas? (máx 30 pontos)
        if self.total_campaigns_participated > 0:
            response_rate = self.total_campaigns_responded / self.total_campaigns_participated
            score += int(response_rate * 30)
        
        # Compra recente? (máx 40 pontos)
        if self.last_purchase_date:
            days_ago = self.days_since_last_purchase
            if days_ago <= 7:
                score += 40
            elif days_ago <= 30:
                score += 30
            elif days_ago <= 90:
                score += 15
        
        # Interação recente? (máx 30 pontos)
        if self.last_interaction_date:
            days_ago = self.days_since_last_interaction
            if days_ago <= 7:
                score += 30
            elif days_ago <= 30:
                score += 20
            elif days_ago <= 90:
                score += 10
        
        return min(100, score)
    
    @property
    def age(self):
        """Idade calculada a partir da data de nascimento"""
        if not self.birth_date:
            return None
        
        today = timezone.now().date()
        return today.year - self.birth_date.year - (
            (today.month, today.day) < (self.birth_date.month, self.birth_date.day)
        )
    
    @property
    def next_birthday(self):
        """Próximo aniversário"""
        if not self.birth_date:
            return None
        
        today = timezone.now().date()
        this_year_birthday = self.birth_date.replace(year=today.year)
        
        if this_year_birthday < today:
            # Já passou, próximo é ano que vem
            return this_year_birthday.replace(year=today.year + 1)
        
        return this_year_birthday
    
    @property
    def days_until_birthday(self):
        """Quantos dias até o próximo aniversário"""
        if not self.next_birthday:
            return None
        
        today = timezone.now().date()
        return (self.next_birthday - today).days
    
    def is_birthday_soon(self, days=7):
        """
        Verifica se o aniversário está próximo
        
        Args:
            days (int): Janela de dias (default: 7)
        
        Returns:
            bool: True se aniversário está nos próximos X dias
        """
        days_until = self.days_until_birthday
        if days_until is None:
            return False
        
        return 0 <= days_until <= days
    
    # ==================== MÉTODOS DE NEGÓCIO ====================
    
    def opt_out(self):
        """Marca contato como opted-out (LGPD)"""
        self.opted_out = True
        self.opted_out_at = timezone.now()
        self.save(update_fields=['opted_out', 'opted_out_at', 'updated_at'])
    
    def opt_in(self):
        """Reverte opt-out"""
        self.opted_out = False
        self.opted_out_at = None
        self.save(update_fields=['opted_out', 'opted_out_at', 'updated_at'])
    
    def increment_campaign_participation(self, responded=False):
        """
        Incrementa contadores de participação em campanha
        
        Args:
            responded (bool): Se o contato respondeu
        """
        self.total_campaigns_participated += 1
        if responded:
            self.total_campaigns_responded += 1
        self.save(update_fields=[
            'total_campaigns_participated',
            'total_campaigns_responded',
            'updated_at'
        ])
    
    def update_interaction(self):
        """Atualiza timestamp de última interação"""
        self.last_interaction_date = timezone.now()
        self.save(update_fields=['last_interaction_date', 'updated_at'])
    
    def add_purchase(self, value, date=None):
        """
        Registra uma nova compra
        
        Args:
            value (Decimal): Valor da compra
            date (date): Data da compra (default: hoje)
        """
        if date is None:
            date = timezone.now().date()
        
        self.total_purchases += 1
        self.lifetime_value += value
        self.last_purchase_value = value
        self.last_purchase_date = date
        
        # Recalcular ticket médio
        if self.total_purchases > 0:
            self.average_ticket = self.lifetime_value / self.total_purchases
        
        self.save(update_fields=[
            'total_purchases',
            'lifetime_value',
            'last_purchase_value',
            'last_purchase_date',
            'average_ticket',
            'updated_at'
        ])


class Tag(models.Model):
    """
    Tags para segmentação de contatos
    
    Exemplos:
    - VIP
    - Inadimplente
    - Lead Quente
    - Black Friday 2024
    """
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    tenant = models.ForeignKey(
        'tenancy.Tenant',
        on_delete=models.CASCADE,
        related_name='contact_tags'
    )
    
    name = models.CharField(
        max_length=50,
        help_text="Nome da tag (ex: VIP, Lead Quente)"
    )
    
    color = models.CharField(
        max_length=7,
        default='#3B82F6',
        help_text="Cor em hexadecimal (ex: #3B82F6)"
    )
    
    description = models.TextField(
        blank=True,
        help_text="Descrição opcional da tag"
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'contacts_tag'
        verbose_name = 'Tag'
        verbose_name_plural = 'Tags'
        unique_together = [['tenant', 'name']]
        ordering = ['name']
    
    def __str__(self):
        return self.name
    
    @property
    def contact_count(self):
        """Número de contatos com esta tag"""
        return self.contacts.filter(is_active=True).count()


class ContactList(models.Model):
    """
    Listas de contatos para campanhas
    
    Diferente de Tags:
    - Tags são atributos (VIP, Inadimplente)
    - Lists são agrupamentos para campanhas (Black Friday, Newsletter Mensal)
    """
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    tenant = models.ForeignKey(
        'tenancy.Tenant',
        on_delete=models.CASCADE,
        related_name='contact_lists'
    )
    
    name = models.CharField(
        max_length=100,
        help_text="Nome da lista (ex: Black Friday 2024)"
    )
    
    description = models.TextField(
        blank=True,
        help_text="Descrição da lista"
    )
    
    is_active = models.BooleanField(
        default=True,
        help_text="Lista ativa"
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    created_by = models.ForeignKey(
        'authn.User',
        on_delete=models.SET_NULL,
        null=True,
        related_name='contact_lists_created'
    )
    
    class Meta:
        db_table = 'contacts_list'
        verbose_name = 'Lista de Contatos'
        verbose_name_plural = 'Listas de Contatos'
        ordering = ['-created_at']
    
    def __str__(self):
        return self.name
    
    @property
    def contact_count(self):
        """Número de contatos na lista"""
        return self.contacts.filter(is_active=True).count()
    
    @property
    def opted_out_count(self):
        """Número de contatos que deram opt-out"""
        return self.contacts.filter(opted_out=True).count()


class ContactImport(models.Model):
    """
    Registro de importações de contatos via CSV
    """
    
    class Status(models.TextChoices):
        PENDING = 'pending', 'Pendente'
        PROCESSING = 'processing', 'Processando'
        COMPLETED = 'completed', 'Concluído'
        FAILED = 'failed', 'Falhou'
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    tenant = models.ForeignKey(
        'tenancy.Tenant',
        on_delete=models.CASCADE,
        related_name='contact_imports'
    )
    
    file_name = models.CharField(max_length=255)
    file_path = models.CharField(max_length=500)  # S3 ou local
    
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING
    )
    
    # Contadores
    total_rows = models.IntegerField(default=0)
    processed_rows = models.IntegerField(default=0)
    created_count = models.IntegerField(default=0)
    updated_count = models.IntegerField(default=0)
    skipped_count = models.IntegerField(default=0)
    error_count = models.IntegerField(default=0)
    
    # Erros
    errors = models.JSONField(default=list)  # Lista de erros
    
    # Opções de importação
    update_existing = models.BooleanField(
        default=False,
        help_text="Atualizar contatos existentes ou apenas criar novos"
    )
    
    auto_tag = models.ForeignKey(
        'Tag',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        help_text="Tag automática para contatos importados"
    )
    
    # Meta
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    
    created_by = models.ForeignKey(
        'authn.User',
        on_delete=models.SET_NULL,
        null=True
    )
    
    class Meta:
        db_table = 'contacts_import'
        ordering = ['-created_at']
    
    @property
    def success_rate(self):
        """Taxa de sucesso da importação"""
        if self.total_rows == 0:
            return 0
        return ((self.created_count + self.updated_count) / self.total_rows) * 100
