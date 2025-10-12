# 👥 ALREA CONTACTS - Especificação Técnica Completa

> **Projeto:** ALREA - Plataforma Multi-Produto SaaS  
> **Módulo:** Sistema de Contatos Enriquecidos  
> **Versão:** 1.0.0  
> **Data:** 2025-10-10  
> **Prioridade:** 🔥 ALTA - Base para Campanhas

---

## 📋 ÍNDICE

1. [Visão Geral](#visão-geral)
2. [Objetivos e Requisitos](#objetivos-e-requisitos)
3. [Modelagem de Dados](#modelagem-de-dados)
4. [Regras de Negócio](#regras-de-negócio)
5. [API REST](#api-rest)
6. [Importação e Exportação](#importação-e-exportação)
7. [Segmentação e Filtros](#segmentação-e-filtros)
8. [Integração com Campanhas](#integração-com-campanhas)
9. [Frontend Components](#frontend-components)
10. [Métricas e Insights](#métricas-e-insights)

---

## 🎯 VISÃO GERAL

### Propósito

O módulo **ALREA Contacts** é o **coração do sistema de engajamento**, fornecendo uma base de contatos enriquecida que alimenta:

- ✅ Campanhas de disparo em massa
- ✅ Disparos agendados individuais
- ✅ Segmentação avançada
- ✅ Análise RFM (Recency, Frequency, Monetary)
- ✅ Automações baseadas em comportamento
- ✅ Insights de negócio para o cliente

### Diferencial

Ao contrário de sistemas tradicionais que armazenam apenas **nome + telefone**, o ALREA Contacts mantém um **perfil 360° do cliente**, incluindo:

- Dados demográficos (nascimento, localização)
- Histórico comercial (compras, visitas)
- Comportamento (engajamento, respostas)
- Segmentação (tags, listas)
- Campos customizados (flexibilidade total)

---

## 📊 OBJETIVOS E REQUISITOS

### Objetivos de Negócio

1. **Permitir segmentação avançada** para campanhas direcionadas
2. **Gerar insights automáticos** (churn, aniversários, etc)
3. **Facilitar importação em massa** via CSV/Excel
4. **Manter histórico de interações** com cada contato
5. **Integrar com WhatsApp Gateway** para sincronização automática

### Requisitos Funcionais

| ID | Requisito | Prioridade |
|----|-----------|------------|
| RF01 | CRUD completo de contatos | 🔥 Crítica |
| RF02 | Importação CSV com validação | 🔥 Crítica |
| RF03 | Tags e listas para segmentação | 🔥 Crítica |
| RF04 | Campos customizados (JSONField) | 🟡 Alta |
| RF05 | Detecção de duplicatas | 🟡 Alta |
| RF06 | Exportação para CSV/Excel | 🟡 Alta |
| RF07 | Busca full-text | 🟡 Alta |
| RF08 | Filtros avançados | 🟡 Alta |
| RF09 | Métricas RFM automáticas | 🟢 Média |
| RF10 | Sincronização com WhatsApp | 🟢 Média |

### Requisitos Não-Funcionais

| ID | Requisito | Meta |
|----|-----------|------|
| RNF01 | Importação de 10k contatos | < 30 segundos |
| RNF02 | Busca em 100k contatos | < 500ms |
| RNF03 | Isolamento multi-tenant | 100% (RLS) |
| RNF04 | Backup automático | Diário |

---

## 🗄️ MODELAGEM DE DADOS

### 1. Contact (Principal)

```python
# apps/contacts/models.py

from django.db import models
from django.core.validators import RegexValidator
from django.utils import timezone
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
```

### 2. Tag (Segmentação)

```python
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
```

### 3. ContactList (Listas de Campanhas)

```python
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
```

### 4. ContactImport (Histórico de Importações)

```python
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
```

---

## 📐 REGRAS DE NEGÓCIO

### RN01: Unicidade de Telefone

**Regra:** Cada telefone pode existir apenas **uma vez por tenant**

```python
# Validação no serializer
def validate_phone(self, value):
    # Normalizar telefone (remover espaços, parênteses, etc)
    normalized = re.sub(r'[^\d+]', '', value)
    
    # Adicionar +55 se não tiver código de país
    if not normalized.startswith('+'):
        normalized = f'+55{normalized}'
    
    # Verificar duplicata
    if Contact.objects.filter(
        tenant=self.context['request'].user.tenant,
        phone=normalized
    ).exclude(pk=self.instance.pk if self.instance else None).exists():
        raise ValidationError('Telefone já cadastrado neste tenant')
    
    return normalized
```

### RN02: Opt-Out (LGPD)

**Regra:** Contatos com `opted_out=True` **não podem** receber mensagens de campanhas

```python
# Validação em campanhas
def can_receive_campaign(contact):
    """Verifica se contato pode receber mensagem de campanha"""
    if contact.opted_out:
        return False, "Contato pediu para não receber mensagens (opt-out)"
    
    if not contact.is_active:
        return False, "Contato inativo"
    
    return True, None
```

### RN03: Atualização Automática de Métricas

**Regra:** Métricas de engajamento são atualizadas **automaticamente** via signals

```python
# apps/contacts/signals.py

from django.db.models.signals import post_save
from django.dispatch import receiver
from apps.chat_messages.models import ChatMessage

@receiver(post_save, sender=ChatMessage)
def update_contact_interaction(sender, instance, created, **kwargs):
    """Atualiza last_interaction_date quando mensagem é criada"""
    if created and instance.contact:
        instance.contact.update_interaction()
        
        # Incrementar contadores
        if instance.is_from_contact:
            instance.contact.total_messages_sent += 1
        else:
            instance.contact.total_messages_received += 1
        
        instance.contact.save(update_fields=[
            'total_messages_sent',
            'total_messages_received'
        ])
```

### RN04: Detecção de Duplicatas na Importação

**Regra:** Durante importação CSV, detectar duplicatas por:
1. Telefone (principal)
2. Email (secundário)

```python
# Estratégias de merge
MERGE_STRATEGIES = {
    'skip': 'Pular duplicatas',
    'update': 'Atualizar dados existentes',
    'create_new': 'Criar novo mesmo se duplicado'
}
```

### RN05: Validação de Campos Obrigatórios

**Regra:** Campos mínimos obrigatórios:
- `phone` (sempre)
- `name` (sempre)
- `tenant` (sempre, inferido do usuário logado)

Todos os outros campos são **opcionais**.

### RN06: Normalização de Telefone

**Regra:** Todos os telefones são armazenados no formato **E.164** (+5511999999999)

```python
def normalize_phone(phone):
    """
    Normaliza telefone para formato E.164
    
    Exemplos:
    - (11) 99999-9999  → +5511999999999
    - 11999999999      → +5511999999999
    - +5511999999999   → +5511999999999 (já correto)
    """
    # Remover formatação
    clean = re.sub(r'[^\d+]', '', phone)
    
    # Adicionar +55 se não tiver código de país
    if not clean.startswith('+'):
        if clean.startswith('55'):
            clean = f'+{clean}'
        else:
            clean = f'+55{clean}'
    
    return clean
```

---

## 🔌 API REST

### Endpoints

```python
# apps/contacts/urls.py

from rest_framework.routers import DefaultRouter
from .views import ContactViewSet, TagViewSet, ContactListViewSet

router = DefaultRouter()
router.register(r'contacts', ContactViewSet, basename='contact')
router.register(r'tags', TagViewSet, basename='tag')
router.register(r'lists', ContactListViewSet, basename='contact-list')

urlpatterns = router.urls
```

### ContactViewSet

```python
# apps/contacts/views.py

from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend
from django.db.models import Q

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
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['is_active', 'opted_out', 'source']
    search_fields = ['name', 'phone', 'email']
    
    def get_queryset(self):
        """Retorna apenas contatos do tenant do usuário"""
        tenant = self.request.user.tenant
        qs = Contact.objects.filter(tenant=tenant).prefetch_related('tags', 'lists')
        
        # Filtros customizados
        tags = self.request.query_params.get('tags')
        if tags:
            tag_ids = tags.split(',')
            qs = qs.filter(tags__id__in=tag_ids)
        
        lists = self.request.query_params.get('lists')
        if lists:
            list_ids = lists.split(',')
            qs = qs.filter(lists__id__in=list_ids)
        
        # Busca full-text
        search = self.request.query_params.get('search')
        if search:
            qs = qs.filter(
                Q(name__icontains=search) |
                Q(phone__icontains=search) |
                Q(email__icontains=search)
            )
        
        return qs
    
    def perform_create(self, serializer):
        """Associa tenant e usuário na criação"""
        serializer.save(
            tenant=self.request.user.tenant,
            created_by=self.request.user
        )
    
    @action(detail=False, methods=['post'])
    def import_csv(self, request):
        """
        Importação em massa via CSV
        
        POST /api/contacts/contacts/import_csv/
        Body: multipart/form-data
        - file: CSV file
        - update_existing: bool
        - auto_tag_id: UUID (optional)
        """
        file = request.FILES.get('file')
        if not file:
            return Response(
                {'error': 'Arquivo CSV não fornecido'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Processar CSV (pode ser async com Celery)
        from .services import ContactImportService
        
        service = ContactImportService(
            tenant=request.user.tenant,
            user=request.user
        )
        
        result = service.process_csv(
            file=file,
            update_existing=request.data.get('update_existing', False),
            auto_tag_id=request.data.get('auto_tag_id')
        )
        
        return Response(result)
    
    @action(detail=False, methods=['get'])
    def export_csv(self, request):
        """
        Exportação para CSV
        
        GET /api/contacts/contacts/export_csv/
        Query params: mesmos filtros do list
        """
        from .services import ContactExportService
        
        contacts = self.filter_queryset(self.get_queryset())
        
        service = ContactExportService()
        csv_file = service.export_to_csv(contacts)
        
        response = HttpResponse(csv_file, content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="contacts.csv"'
        return response
    
    @action(detail=False, methods=['get'])
    def insights(self, request):
        """
        Métricas e insights dos contatos
        
        GET /api/contacts/contacts/insights/
        """
        tenant = request.user.tenant
        contacts = Contact.objects.filter(tenant=tenant, is_active=True)
        
        # Segmentação por lifecycle
        lifecycle_breakdown = {
            'lead': contacts.filter(total_purchases=0).count(),
            'customer': 0,  # Calcular via query complexa ou Python
            'at_risk': 0,
            'churned': 0
        }
        
        # Aniversariantes próximos (7 dias)
        upcoming_birthdays = []
        for contact in contacts.exclude(birth_date__isnull=True):
            if contact.is_birthday_soon(7):
                upcoming_birthdays.append({
                    'id': contact.id,
                    'name': contact.name,
                    'phone': contact.phone,
                    'days_until': contact.days_until_birthday
                })
        
        # Churn alerts (90+ dias sem compra)
        from datetime import timedelta
        churn_date = timezone.now().date() - timedelta(days=90)
        churn_alerts = contacts.filter(
            last_purchase_date__lt=churn_date,
            total_purchases__gte=1
        ).count()
        
        return Response({
            'total_contacts': contacts.count(),
            'opted_out': contacts.filter(opted_out=True).count(),
            'lifecycle_breakdown': lifecycle_breakdown,
            'upcoming_birthdays': upcoming_birthdays,
            'churn_alerts': churn_alerts,
            'average_ltv': contacts.aggregate(avg_ltv=models.Avg('lifetime_value'))['avg_ltv']
        })
    
    @action(detail=True, methods=['post'])
    def opt_out(self, request, pk=None):
        """Marca contato como opted-out"""
        contact = self.get_object()
        contact.opt_out()
        return Response({'status': 'opted_out'})
    
    @action(detail=True, methods=['post'])
    def opt_in(self, request, pk=None):
        """Reverte opt-out"""
        contact = self.get_object()
        contact.opt_in()
        return Response({'status': 'opted_in'})
```

### Serializers

```python
# apps/contacts/serializers.py

from rest_framework import serializers
from .models import Contact, Tag, ContactList

class TagSerializer(serializers.ModelSerializer):
    contact_count = serializers.ReadOnlyField()
    
    class Meta:
        model = Tag
        fields = ['id', 'name', 'color', 'description', 'contact_count', 'created_at']
        read_only_fields = ['id', 'created_at']


class ContactListSerializer(serializers.ModelSerializer):
    contact_count = serializers.ReadOnlyField()
    opted_out_count = serializers.ReadOnlyField()
    
    class Meta:
        model = ContactList
        fields = [
            'id', 'name', 'description', 'is_active',
            'contact_count', 'opted_out_count',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class ContactSerializer(serializers.ModelSerializer):
    # Computed fields
    age = serializers.ReadOnlyField()
    days_since_last_purchase = serializers.ReadOnlyField()
    days_until_birthday = serializers.ReadOnlyField()
    lifecycle_stage = serializers.ReadOnlyField()
    rfm_segment = serializers.ReadOnlyField()
    engagement_score = serializers.ReadOnlyField()
    
    # Relations
    tags = TagSerializer(many=True, read_only=True)
    tag_ids = serializers.PrimaryKeyRelatedField(
        many=True,
        queryset=Tag.objects.all(),
        write_only=True,
        required=False
    )
    
    lists = ContactListSerializer(many=True, read_only=True)
    list_ids = serializers.PrimaryKeyRelatedField(
        many=True,
        queryset=ContactList.objects.all(),
        write_only=True,
        required=False
    )
    
    class Meta:
        model = Contact
        fields = [
            # IDs
            'id', 'tenant',
            
            # Básico
            'phone', 'name', 'email',
            
            # Demográficos
            'birth_date', 'gender', 'city', 'state', 'country', 'zipcode',
            
            # Comerciais
            'last_purchase_date', 'last_purchase_value', 'total_purchases',
            'average_ticket', 'lifetime_value', 'last_visit_date',
            
            # Engajamento
            'last_interaction_date', 'total_messages_received', 'total_messages_sent',
            'total_campaigns_participated', 'total_campaigns_responded',
            
            # Observações
            'notes', 'custom_fields',
            
            # Segmentação
            'tags', 'tag_ids', 'lists', 'list_ids',
            
            # Controle
            'is_active', 'opted_out', 'opted_out_at', 'source',
            
            # Computed
            'age', 'days_since_last_purchase', 'days_until_birthday',
            'lifecycle_stage', 'rfm_segment', 'engagement_score',
            
            # Meta
            'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'tenant', 'created_at', 'updated_at',
            'total_messages_received', 'total_messages_sent',
            'total_campaigns_participated', 'total_campaigns_responded',
            'opted_out_at'
        ]
    
    def validate_phone(self, value):
        """Normaliza e valida telefone"""
        from .utils import normalize_phone
        return normalize_phone(value)
    
    def create(self, validated_data):
        # Extrair tags e lists
        tag_ids = validated_data.pop('tag_ids', [])
        list_ids = validated_data.pop('list_ids', [])
        
        # Criar contato
        contact = Contact.objects.create(**validated_data)
        
        # Associar tags e lists
        if tag_ids:
            contact.tags.set(tag_ids)
        if list_ids:
            contact.lists.set(list_ids)
        
        return contact
    
    def update(self, instance, validated_data):
        # Extrair tags e lists
        tag_ids = validated_data.pop('tag_ids', None)
        list_ids = validated_data.pop('list_ids', None)
        
        # Atualizar campos
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        
        # Atualizar tags e lists
        if tag_ids is not None:
            instance.tags.set(tag_ids)
        if list_ids is not None:
            instance.lists.set(list_ids)
        
        return instance
```

---

## 📥 IMPORTAÇÃO E EXPORTAÇÃO

### Formato CSV Esperado

```csv
name,phone,email,birth_date,city,state,last_purchase_date,last_purchase_value,notes
Maria Silva,11999999999,maria@email.com,1990-05-15,São Paulo,SP,2024-10-01,150.00,Cliente VIP
João Santos,11988888888,joao@email.com,1985-03-20,Rio de Janeiro,RJ,,,Lead qualificado
```

### Regras de Importação

1. **Campos obrigatórios:** `name`, `phone`
2. **Detecção de duplicatas:** Por telefone (após normalização)
3. **Estratégias:**
   - `skip`: Pula duplicatas
   - `update`: Atualiza contato existente
4. **Auto-tag:** Opcionalmente adiciona tag automática em todos os importados
5. **Validação:** Emails, datas e telefones são validados

### Service de Importação

```python
# apps/contacts/services.py

import csv
import io
from django.db import transaction
from .models import Contact, ContactImport, Tag

class ContactImportService:
    def __init__(self, tenant, user):
        self.tenant = tenant
        self.user = user
    
    def process_csv(self, file, update_existing=False, auto_tag_id=None):
        """
        Processa arquivo CSV e importa contatos
        
        Args:
            file: Arquivo CSV (UploadedFile)
            update_existing: Se True, atualiza contatos duplicados
            auto_tag_id: ID da tag para adicionar automaticamente
        
        Returns:
            dict: Resultado da importação
        """
        # Criar registro de importação
        import_record = ContactImport.objects.create(
            tenant=self.tenant,
            file_name=file.name,
            created_by=self.user,
            update_existing=update_existing
        )
        
        if auto_tag_id:
            import_record.auto_tag_id = auto_tag_id
            import_record.save()
        
        try:
            # Ler CSV
            decoded_file = file.read().decode('utf-8')
            csv_reader = csv.DictReader(io.StringIO(decoded_file))
            
            rows = list(csv_reader)
            import_record.total_rows = len(rows)
            import_record.status = ContactImport.Status.PROCESSING
            import_record.save()
            
            # Processar cada linha
            for i, row in enumerate(rows):
                try:
                    self._process_row(row, import_record)
                    import_record.processed_rows = i + 1
                    import_record.save()
                except Exception as e:
                    import_record.error_count += 1
                    import_record.errors.append({
                        'row': i + 1,
                        'data': row,
                        'error': str(e)
                    })
                    import_record.save()
            
            # Finalizar
            import_record.status = ContactImport.Status.COMPLETED
            import_record.completed_at = timezone.now()
            import_record.save()
            
            return {
                'status': 'success',
                'import_id': import_record.id,
                'total_rows': import_record.total_rows,
                'created': import_record.created_count,
                'updated': import_record.updated_count,
                'skipped': import_record.skipped_count,
                'errors': import_record.error_count
            }
        
        except Exception as e:
            import_record.status = ContactImport.Status.FAILED
            import_record.errors.append({'error': str(e)})
            import_record.save()
            
            return {
                'status': 'failed',
                'error': str(e)
            }
    
    def _process_row(self, row, import_record):
        """Processa uma linha do CSV"""
        from .utils import normalize_phone
        
        # Validar campos obrigatórios
        if not row.get('name') or not row.get('phone'):
            raise ValueError('Campos obrigatórios: name, phone')
        
        # Normalizar telefone
        phone = normalize_phone(row['phone'])
        
        # Verificar duplicata
        existing = Contact.objects.filter(
            tenant=self.tenant,
            phone=phone
        ).first()
        
        if existing:
            if import_record.update_existing:
                # Atualizar
                self._update_contact(existing, row)
                import_record.updated_count += 1
            else:
                # Pular
                import_record.skipped_count += 1
        else:
            # Criar novo
            contact = self._create_contact(row, phone)
            import_record.created_count += 1
            
            # Adicionar auto-tag
            if import_record.auto_tag:
                contact.tags.add(import_record.auto_tag)
    
    def _create_contact(self, row, phone):
        """Cria novo contato a partir do CSV"""
        from datetime import datetime
        
        contact = Contact.objects.create(
            tenant=self.tenant,
            phone=phone,
            name=row['name'],
            email=row.get('email') or None,
            birth_date=self._parse_date(row.get('birth_date')),
            city=row.get('city'),
            state=row.get('state'),
            last_purchase_date=self._parse_date(row.get('last_purchase_date')),
            last_purchase_value=self._parse_decimal(row.get('last_purchase_value')),
            notes=row.get('notes', ''),
            source='import',
            created_by=self.user
        )
        
        return contact
    
    def _update_contact(self, contact, row):
        """Atualiza contato existente"""
        # Atualizar apenas campos não vazios
        if row.get('name'):
            contact.name = row['name']
        if row.get('email'):
            contact.email = row['email']
        # ... outros campos
        
        contact.save()
    
    def _parse_date(self, value):
        """Parse date string to date object"""
        if not value:
            return None
        try:
            from datetime import datetime
            return datetime.strptime(value, '%Y-%m-%d').date()
        except:
            return None
    
    def _parse_decimal(self, value):
        """Parse decimal string"""
        if not value:
            return None
        try:
            return Decimal(value)
        except:
            return None
```

---

## 🔍 SEGMENTAÇÃO E FILTROS

### Filtros Disponíveis na UI

```typescript
// frontend/src/pages/ContactsPage.tsx

interface ContactFilters {
  search: string           // Busca em name, phone, email
  tags: string[]          // IDs de tags
  lists: string[]         // IDs de listas
  lifecycleStage: 'lead' | 'customer' | 'at_risk' | 'churned'
  optedOut: boolean
  isActive: boolean
  birthMonth: number      // Aniversariantes do mês
  churAlert: boolean      // 90+ dias sem compra
  purchaseRange: {
    from: Date
    to: Date
  }
}
```

### Query Builder Inteligente

```python
# apps/contacts/filters.py

from django_filters import rest_framework as filters
from .models import Contact

class ContactFilter(filters.FilterSet):
    """Filtros avançados para contatos"""
    
    # Busca full-text
    search = filters.CharFilter(method='search_filter')
    
    # Segmentação
    tags = filters.CharFilter(method='tags_filter')
    lists = filters.CharFilter(method='lists_filter')
    
    # Lifecycle
    lifecycle_stage = filters.ChoiceFilter(
        method='lifecycle_filter',
        choices=[
            ('lead', 'Lead'),
            ('customer', 'Customer'),
            ('at_risk', 'At Risk'),
            ('churned', 'Churned')
        ]
    )
    
    # Aniversariantes
    birth_month = filters.NumberFilter(method='birth_month_filter')
    birthday_soon = filters.NumberFilter(method='birthday_soon_filter')
    
    # Churn alert
    churn_alert = filters.BooleanFilter(method='churn_alert_filter')
    
    class Meta:
        model = Contact
        fields = ['is_active', 'opted_out', 'source', 'gender']
    
    def search_filter(self, queryset, name, value):
        return queryset.filter(
            Q(name__icontains=value) |
            Q(phone__icontains=value) |
            Q(email__icontains=value)
        )
    
    def tags_filter(self, queryset, name, value):
        tag_ids = value.split(',')
        return queryset.filter(tags__id__in=tag_ids)
    
    def lists_filter(self, queryset, name, value):
        list_ids = value.split(',')
        return queryset.filter(lists__id__in=list_ids)
    
    def lifecycle_filter(self, queryset, name, value):
        # Filtro complexo baseado em lógica de lifecycle_stage
        # Precisa ser implementado via annotation ou Python
        pass
    
    def birth_month_filter(self, queryset, name, value):
        return queryset.filter(birth_date__month=value)
    
    def birthday_soon_filter(self, queryset, name, value):
        # value = número de dias
        # Complexo: precisa calcular "next birthday"
        pass
    
    def churn_alert_filter(self, queryset, name, value):
        if value:
            from datetime import timedelta
            churn_date = timezone.now().date() - timedelta(days=90)
            return queryset.filter(
                last_purchase_date__lt=churn_date,
                total_purchases__gte=1
            )
        return queryset
```

---

## 🔗 INTEGRAÇÃO COM CAMPANHAS

### Uso em Campanhas

```python
# apps/campaigns/models.py

class Campaign(models.Model):
    # ... outros campos ...
    
    # Seleção de contatos
    contact_selection_type = models.CharField(
        max_length=20,
        choices=[
            ('all', 'Todos os Contatos'),
            ('tags', 'Por Tags'),
            ('lists', 'Por Listas'),
            ('manual', 'Seleção Manual'),
            ('filter', 'Filtro Avançado')
        ]
    )
    
    # Se type = 'tags'
    selected_tags = models.ManyToManyField('contacts.Tag', blank=True)
    
    # Se type = 'lists'
    selected_lists = models.ManyToManyField('contacts.ContactList', blank=True)
    
    # Se type = 'manual'
    selected_contacts = models.ManyToManyField('contacts.Contact', blank=True)
    
    # Se type = 'filter'
    filter_config = models.JSONField(default=dict)  # Filtros salvos
    
    def get_target_contacts(self):
        """Retorna queryset de contatos-alvo da campanha"""
        tenant = self.tenant
        base_qs = Contact.objects.filter(
            tenant=tenant,
            is_active=True,
            opted_out=False  # Nunca enviar para opted-out!
        )
        
        if self.contact_selection_type == 'all':
            return base_qs
        
        elif self.contact_selection_type == 'tags':
            return base_qs.filter(tags__in=self.selected_tags.all()).distinct()
        
        elif self.contact_selection_type == 'lists':
            return base_qs.filter(lists__in=self.selected_lists.all()).distinct()
        
        elif self.contact_selection_type == 'manual':
            return base_qs.filter(id__in=self.selected_contacts.all())
        
        elif self.contact_selection_type == 'filter':
            # Aplicar filtros salvos
            # Exemplo: {'lifecycle_stage': 'at_risk', 'tags': ['uuid1']}
            return self._apply_saved_filters(base_qs)
        
        return base_qs.none()
```

### Variáveis de Mensagem

```python
# apps/campaigns/services.py

class MessageVariableService:
    """Renderiza variáveis em mensagens de campanha"""
    
    @staticmethod
    def render_message(template, contact, extra_vars=None):
        """
        Renderiza template de mensagem com dados do contato
        
        Variáveis disponíveis:
        - {name}: Nome do contato
        - {greeting}: Saudação (Bom dia/Boa tarde/Boa noite)
        - {first_name}: Primeiro nome
        - {email}: Email
        - {city}: Cidade
        - {custom.campo}: Campos customizados
        
        Args:
            template (str): Template da mensagem
            contact (Contact): Contato
            extra_vars (dict): Variáveis extras
        
        Returns:
            str: Mensagem renderizada
        """
        from datetime import datetime
        
        # Determinar saudação
        hour = datetime.now().hour
        if 5 <= hour < 12:
            greeting = 'Bom dia'
        elif 12 <= hour < 18:
            greeting = 'Boa tarde'
        else:
            greeting = 'Boa noite'
        
        # Variáveis base
        variables = {
            'name': contact.name,
            'first_name': contact.name.split()[0] if contact.name else '',
            'greeting': greeting,
            'email': contact.email or '',
            'city': contact.city or '',
            'state': contact.state or '',
        }
        
        # Adicionar custom fields
        for key, value in contact.custom_fields.items():
            variables[f'custom.{key}'] = value
        
        # Adicionar variáveis extras
        if extra_vars:
            variables.update(extra_vars)
        
        # Renderizar
        rendered = template
        for key, value in variables.items():
            rendered = rendered.replace(f'{{{key}}}', str(value))
        
        return rendered
```

---

## 🎨 FRONTEND COMPONENTS

### ContactsPage (Lista)

```tsx
// frontend/src/pages/ContactsPage.tsx

import { useState, useEffect } from 'react'
import { Search, Plus, Upload, Download, Filter } from 'lucide-react'
import { Button } from '@/components/ui/Button'
import { api } from '@/lib/api'
import ContactCard from '@/components/contacts/ContactCard'
import ContactFilters from '@/components/contacts/ContactFilters'
import ImportContactsModal from '@/components/contacts/ImportContactsModal'

export default function ContactsPage() {
  const [contacts, setContacts] = useState([])
  const [filters, setFilters] = useState({})
  const [showImportModal, setShowImportModal] = useState(false)
  
  const fetchContacts = async () => {
    const params = new URLSearchParams(filters)
    const response = await api.get(`/contacts/contacts/?${params}`)
    setContacts(response.data.results)
  }
  
  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-2xl font-bold">Contatos</h1>
          <p className="text-gray-500">Gerencie sua base de contatos</p>
        </div>
        
        <div className="flex gap-2">
          <Button variant="outline" onClick={() => exportContacts()}>
            <Download className="h-4 w-4 mr-2" />
            Exportar
          </Button>
          
          <Button variant="outline" onClick={() => setShowImportModal(true)}>
            <Upload className="h-4 w-4 mr-2" />
            Importar CSV
          </Button>
          
          <Button onClick={() => navigate('/contacts/new')}>
            <Plus className="h-4 w-4 mr-2" />
            Novo Contato
          </Button>
        </div>
      </div>
      
      {/* Filters */}
      <ContactFilters filters={filters} onChange={setFilters} />
      
      {/* Contact List */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {contacts.map(contact => (
          <ContactCard key={contact.id} contact={contact} />
        ))}
      </div>
      
      {/* Import Modal */}
      {showImportModal && (
        <ImportContactsModal
          onClose={() => setShowImportModal(false)}
          onSuccess={fetchContacts}
        />
      )}
    </div>
  )
}
```

### ContactCard (Item da Lista)

```tsx
// frontend/src/components/contacts/ContactCard.tsx

import { Phone, Mail, MapPin, Calendar, TrendingUp } from 'lucide-react'
import { Card } from '@/components/ui/Card'
import { Badge } from '@/components/ui/Badge'

interface ContactCardProps {
  contact: Contact
}

export default function ContactCard({ contact }: ContactCardProps) {
  const lifecycleColors = {
    lead: 'gray',
    customer: 'green',
    at_risk: 'yellow',
    churned: 'red'
  }
  
  return (
    <Card className="p-4 hover:shadow-lg transition-shadow cursor-pointer">
      {/* Header */}
      <div className="flex justify-between items-start mb-3">
        <div>
          <h3 className="font-semibold text-lg">{contact.name}</h3>
          <p className="text-sm text-gray-500">{contact.phone}</p>
        </div>
        
        <Badge color={lifecycleColors[contact.lifecycle_stage]}>
          {contact.lifecycle_stage}
        </Badge>
      </div>
      
      {/* Tags */}
      {contact.tags.length > 0 && (
        <div className="flex flex-wrap gap-1 mb-3">
          {contact.tags.map(tag => (
            <Badge key={tag.id} size="sm" color={tag.color}>
              {tag.name}
            </Badge>
          ))}
        </div>
      )}
      
      {/* Info */}
      <div className="space-y-2 text-sm text-gray-600">
        {contact.email && (
          <div className="flex items-center gap-2">
            <Mail className="h-4 w-4" />
            {contact.email}
          </div>
        )}
        
        {contact.city && (
          <div className="flex items-center gap-2">
            <MapPin className="h-4 w-4" />
            {contact.city}, {contact.state}
          </div>
        )}
        
        {contact.days_until_birthday !== null && contact.days_until_birthday <= 7 && (
          <div className="flex items-center gap-2 text-blue-600">
            <Calendar className="h-4 w-4" />
            Aniversário em {contact.days_until_birthday} dias! 🎂
          </div>
        )}
        
        {contact.lifetime_value > 0 && (
          <div className="flex items-center gap-2">
            <TrendingUp className="h-4 w-4" />
            LTV: R$ {contact.lifetime_value.toFixed(2)}
          </div>
        )}
      </div>
      
      {/* Engagement Score */}
      <div className="mt-3 pt-3 border-t">
        <div className="flex justify-between items-center text-xs">
          <span className="text-gray-500">Engajamento</span>
          <span className="font-semibold">{contact.engagement_score}/100</span>
        </div>
        <div className="w-full bg-gray-200 rounded-full h-2 mt-1">
          <div 
            className="bg-blue-600 h-2 rounded-full transition-all"
            style={{ width: `${contact.engagement_score}%` }}
          />
        </div>
      </div>
    </Card>
  )
}
```

---

## 📊 MÉTRICAS E INSIGHTS

### Dashboard de Insights

```python
# GET /api/contacts/contacts/insights/

{
  "total_contacts": 1250,
  "opted_out": 15,
  
  "lifecycle_breakdown": {
    "lead": 450,
    "customer": 600,
    "at_risk": 150,
    "churned": 50
  },
  
  "rfm_segments": {
    "champions": 120,
    "loyal": 200,
    "at_risk": 150,
    "hibernating": 100,
    "lost": 80
  },
  
  "upcoming_birthdays": [
    {
      "id": "uuid",
      "name": "Maria Silva",
      "phone": "+5511999999999",
      "days_until": 3
    }
  ],
  
  "churn_alerts": 45,
  
  "average_ltv": 850.50,
  
  "engagement_distribution": {
    "high": 300,    // 70-100
    "medium": 600,  // 30-69
    "low": 350      // 0-29
  }
}
```

---

## 🚀 PRÓXIMOS PASSOS

### Fase 1 (MVP)
- ✅ Models (Contact, Tag, ContactList)
- ✅ API CRUD completa
- ✅ Importação CSV básica
- ✅ Frontend: Lista e CRUD

### Fase 2 (Insights)
- ✅ Properties calculadas (lifecycle, RFM)
- ✅ Endpoint de insights
- ✅ Dashboard de métricas

### Fase 3 (Avançado)
- ⏳ Segmentação dinâmica
- ⏳ Filtros salvos
- ⏳ Automações (ex: auto-tag baseado em comportamento)
- ⏳ Sincronização com WhatsApp Gateway

---

**Este módulo é a base de TODO o sistema de engajamento do ALREA!** 🎯




