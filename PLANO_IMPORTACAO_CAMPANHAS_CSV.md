# 📋 PLANO - Importação de Campanhas via CSV

**Data:** 2025-01-27  
**Status:** 🟡 Em Análise

---

## 🎯 OBJETIVO

Criar um sistema genérico de importação de campanhas via CSV que:
1. **Não precise ajustar código toda vez** que mudar o formato do CSV
2. **Mapeie campos customizados** automaticamente para `custom_fields`
3. **Crie contatos + campanha** em um único processo
4. **Seja flexível** para diferentes formatos de CSV

---

## 📊 ANÁLISE DO CSV FORNECIDO

### Estrutura do CSV "MODELO - cobrança RA.csv"

```csv
Nome;DDD;Telefone;email;Clinica;data_compra;Valor
```

**Campos identificados:**
- ✅ `Nome` → `Contact.name` (já mapeado)
- ✅ `DDD` → Combinar com Telefone → `Contact.phone` (já mapeado)
- ✅ `Telefone` → Combinar com DDD → `Contact.phone` (já mapeado)
- ✅ `email` → `Contact.email` (já mapeado)
- 🆕 `Clinica` → **NOVO** → `Contact.custom_fields['clinica']`
- ✅ `data_compra` → `Contact.last_purchase_date` (já mapeado)
- ✅ `Valor` → `Contact.last_purchase_value` (já mapeado)

---

## 🔍 ANÁLISE DO SISTEMA ATUAL

### ✅ O que já existe:

1. **Importação de Contatos** (`ContactImportService`)
   - ✅ Auto-detecção de delimitador (`;` ou `,`)
   - ✅ Mapeamento automático de colunas básicas
   - ✅ Preview antes de importar
   - ✅ Validações robustas
   - ✅ Suporte a DDD separado

2. **Modelo Contact**
   - ✅ Campo `custom_fields` (JSONField) - **PERFEITO para campos genéricos!**
   - ✅ Campos comerciais: `last_purchase_date`, `last_purchase_value`
   - ✅ Suporte a tags e listas

3. **Campanhas**
   - ✅ Criação via API com contatos selecionados
   - ✅ Suporte a tags, listas e contatos manuais

### ❌ O que falta:

1. **Mapeamento genérico de campos customizados**
   - Atualmente só mapeia campos conhecidos
   - Campos não reconhecidos são ignorados

2. **Importação direta para campanha**
   - Hoje: Importar contatos → Criar campanha separadamente
   - Necessário: Importar CSV → Criar contatos + campanha em um passo

3. **Templates de mapeamento**
   - Não há como salvar configurações de mapeamento para reutilizar

---

## 🎨 OPÇÕES DE IMPLEMENTAÇÃO

### **OPÇÃO 1: Estender ContactImportService (RECOMENDADO)**

**Vantagens:**
- ✅ Reutiliza código existente
- ✅ Mantém consistência com sistema atual
- ✅ Menos código novo

**Como funciona:**
1. Estender `_auto_map_columns()` para detectar campos não mapeados
2. Campos não reconhecidos → `custom_fields['nome_do_campo']`
3. Criar novo endpoint `/api/campaigns/campaigns/import_csv/` que:
   - Importa contatos do CSV
   - Cria campanha automaticamente
   - Associa contatos importados à campanha

**Estrutura:**
```python
# backend/apps/campaigns/services.py
class CampaignImportService:
    def import_csv_and_create_campaign(self, file, campaign_data, column_mapping=None):
        # 1. Importar contatos (reutilizar ContactImportService)
        # 2. Criar campanha
        # 3. Associar contatos à campanha
        pass
```

**Endpoint:**
```
POST /api/campaigns/campaigns/import_csv/
Body:
- file: CSV
- campaign_name: string
- campaign_description: string
- messages: array
- instances: array
- column_mapping: object (opcional)
```

---

### **OPÇÃO 2: Sistema de Templates de Mapeamento**

**Vantagens:**
- ✅ Usuário pode salvar configurações
- ✅ Reutilizável para múltiplos imports
- ✅ Mais flexível

**Como funciona:**
1. Criar modelo `ImportMappingTemplate`
2. Usuário configura mapeamento uma vez
3. Salva como template
4. Reutiliza em imports futuros

**Estrutura:**
```python
class ImportMappingTemplate(models.Model):
    tenant = ForeignKey
    name = CharField  # "Cobrança RA", "Black Friday 2024"
    column_mapping = JSONField  # {"Clinica": "custom_fields.clinica"}
    created_at = DateTimeField
```

**Fluxo:**
1. Usuário faz preview do CSV
2. Ajusta mapeamento manualmente
3. Salva como template (opcional)
4. Importa usando template ou mapeamento customizado

---

### **OPÇÃO 3: Auto-detecção Inteligente + custom_fields**

**Vantagens:**
- ✅ Zero configuração manual
- ✅ Funciona para qualquer CSV
- ✅ Mais simples para o usuário

**Como funciona:**
1. Detectar campos conhecidos automaticamente
2. Campos não reconhecidos → `custom_fields['nome_do_campo']`
3. Usuário pode ajustar mapeamento no preview

**Implementação:**
```python
def _auto_map_columns(self, headers):
    mapping = {}
    known_fields = ['name', 'phone', 'email', 'last_purchase_date', ...]
    
    for header in headers:
        if header in known_fields:
            mapping[header] = header
        else:
            # Campo customizado → custom_fields
            mapping[header] = f"custom_fields.{header.lower()}"
    
    return mapping
```

---

## 🎯 RECOMENDAÇÃO FINAL

### **Abordagem Híbrida: OPÇÃO 1 + OPÇÃO 3**

1. **Estender ContactImportService** para mapear campos customizados automaticamente
2. **Criar CampaignImportService** para importação direta de campanhas
3. **Usar custom_fields** para campos não padrão (como "Clinica")
4. **Manter preview** para usuário ajustar mapeamento antes de importar

### **Fluxo Proposto:**

```
1. Usuário faz upload do CSV
   ↓
2. Preview mostra:
   - Headers detectados
   - Mapeamento automático (campos conhecidos + custom_fields)
   - Amostra de dados
   ↓
3. Usuário ajusta mapeamento (opcional):
   - Pode mapear "Clinica" → custom_fields.clinica
   - Pode mapear "Valor" → last_purchase_value
   ↓
4. Usuário configura campanha:
   - Nome da campanha
   - Mensagens
   - Instâncias WhatsApp
   ↓
5. Sistema importa:
   - Cria/atualiza contatos
   - Armazena campos customizados em custom_fields
   - Cria campanha
   - Associa contatos à campanha
```

---

## 📝 IMPLEMENTAÇÃO DETALHADA

### **FASE 1: Estender Mapeamento Automático**

**Arquivo:** `backend/apps/contacts/services.py`

**Mudanças:**
```python
def _auto_map_columns(self, headers):
    mapping = {}
    
    # Campos conhecidos (como antes)
    known_mappings = {
        'nome': 'name',
        'ddd': 'ddd',
        'telefone': 'phone',
        'email': 'email',
        'data_compra': 'last_purchase_date',
        'valor': 'last_purchase_value',
        # ... outros
    }
    
    for header in headers:
        header_lower = header.lower().strip()
        
        if header_lower in known_mappings:
            mapping[header] = known_mappings[header_lower]
        else:
            # Campo customizado → custom_fields
            mapping[header] = f"custom_fields.{header_lower}"
    
    return mapping
```

**Processar campos customizados:**
```python
def _process_row(self, row, import_record):
    # ... código existente ...
    
    # Processar custom_fields
    custom_fields = {}
    for key, value in row.items():
        if key.startswith('custom_fields.'):
            field_name = key.replace('custom_fields.', '')
            if value and value.strip():
                custom_fields[field_name] = value.strip()
    
    # Criar contato com custom_fields
    contact = Contact.objects.create(
        # ... campos padrão ...
        custom_fields=custom_fields
    )
```

---

### **FASE 2: Criar CampaignImportService**

**Arquivo:** `backend/apps/campaigns/services.py` (NOVO)

```python
from apps.contacts.services import ContactImportService
from apps.contacts.models import Contact
from .models import Campaign, CampaignContact, CampaignMessage

class CampaignImportService:
    """Service para importar CSV e criar campanha automaticamente"""
    
    def __init__(self, tenant, user):
        self.tenant = tenant
        self.user = user
        self.contact_service = ContactImportService(tenant, user)
    
    def import_csv_and_create_campaign(
        self,
        file,
        campaign_name,
        campaign_description=None,
        messages=None,
        instances=None,
        column_mapping=None,
        update_existing=False,
        auto_tag_id=None
    ):
        """
        Importa CSV e cria campanha em um único processo
        
        Args:
            file: Arquivo CSV
            campaign_name: Nome da campanha
            campaign_description: Descrição (opcional)
            messages: Lista de mensagens [{content: "...", order: 1}]
            instances: Lista de IDs de instâncias WhatsApp
            column_mapping: Mapeamento customizado (opcional)
            update_existing: Atualizar contatos existentes?
            auto_tag_id: Tag para adicionar automaticamente
        
        Returns:
            dict: {campaign_id, import_id, contacts_created, contacts_updated}
        """
        # 1. Importar contatos
        import_result = self.contact_service.process_csv(
            file=file,
            update_existing=update_existing,
            auto_tag_id=auto_tag_id,
            column_mapping=column_mapping
        )
        
        if import_result['status'] != 'success':
            return import_result
        
        # 2. Buscar contatos importados (via import_record)
        import_record = ContactImport.objects.get(id=import_result['import_id'])
        # Contatos criados/atualizados no período da importação
        recent_contacts = Contact.objects.filter(
            tenant=self.tenant,
            created_at__gte=import_record.created_at
        )
        
        # 3. Criar campanha
        campaign = Campaign.objects.create(
            tenant=self.tenant,
            name=campaign_name,
            description=campaign_description,
            created_by=self.user,
            status='draft'
        )
        
        # 4. Adicionar instâncias
        if instances:
            campaign.instances.set(instances)
        
        # 5. Criar mensagens
        if messages:
            for msg_data in messages:
                CampaignMessage.objects.create(
                    campaign=campaign,
                    content=msg_data.get('content', ''),
                    order=msg_data.get('order', 1)
                )
        
        # 6. Associar contatos à campanha
        campaign_contacts = []
        for contact in recent_contacts:
            campaign_contacts.append(
                CampaignContact(
                    campaign=campaign,
                    contact=contact,
                    status='pending'
                )
            )
        
        CampaignContact.objects.bulk_create(campaign_contacts)
        
        # 7. Atualizar contador
        campaign.total_contacts = len(campaign_contacts)
        campaign.save()
        
        return {
            'status': 'success',
            'campaign_id': str(campaign.id),
            'import_id': str(import_record.id),
            'contacts_created': import_result['created'],
            'contacts_updated': import_result['updated'],
            'total_contacts': len(campaign_contacts)
        }
```

---

### **FASE 3: Criar Endpoint**

**Arquivo:** `backend/apps/campaigns/views.py`

```python
@action(detail=False, methods=['post'])
def import_csv(self, request):
    """
    Importar CSV e criar campanha automaticamente
    
    POST /api/campaigns/campaigns/import_csv/
    Body: multipart/form-data
    - file: CSV file
    - campaign_name: string
    - campaign_description: string (opcional)
    - messages: JSON array (opcional)
    - instances: JSON array de IDs (opcional)
    - column_mapping: JSON object (opcional)
    - update_existing: bool
    - auto_tag_id: UUID (opcional)
    """
    file = request.FILES.get('file')
    if not file:
        return Response(
            {'error': 'Arquivo CSV não fornecido'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    campaign_name = request.data.get('campaign_name')
    if not campaign_name:
        return Response(
            {'error': 'Nome da campanha é obrigatório'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    # Parse messages
    messages = None
    if request.data.get('messages'):
        import json
        messages = json.loads(request.data['messages'])
    
    # Parse instances
    instances = None
    if request.data.get('instances'):
        import json
        instances = json.loads(request.data['instances'])
    
    # Parse column_mapping
    column_mapping = None
    if request.data.get('column_mapping'):
        import json
        column_mapping = json.loads(request.data['column_mapping'])
    
    # Importar
    from .services import CampaignImportService
    
    service = CampaignImportService(
        tenant=request.user.tenant,
        user=request.user
    )
    
    result = service.import_csv_and_create_campaign(
        file=file,
        campaign_name=campaign_name,
        campaign_description=request.data.get('campaign_description'),
        messages=messages,
        instances=instances,
        column_mapping=column_mapping,
        update_existing=request.data.get('update_existing', 'false').lower() == 'true',
        auto_tag_id=request.data.get('auto_tag_id')
    )
    
    return Response(result)
```

---

### **FASE 4: Frontend (Opcional - para depois)**

Criar componente `ImportCampaignModal` similar ao `ImportContactsModal`, mas que:
1. Permite configurar campanha durante importação
2. Mostra preview do CSV
3. Permite ajustar mapeamento
4. Cria campanha automaticamente após importar

---

## 🔄 FLUXO COMPLETO

### **Cenário: Importar CSV "MODELO - cobrança RA.csv"**

1. **Usuário faz upload do CSV**
   ```
   POST /api/campaigns/campaigns/preview_csv/
   Body: { file: CSV }
   ```

2. **Sistema retorna preview:**
   ```json
   {
     "headers": ["Nome", "DDD", "Telefone", "email", "Clinica", "data_compra", "Valor"],
     "column_mapping": {
       "Nome": "name",
       "DDD": "ddd",
       "Telefone": "phone",
       "email": "email",
       "Clinica": "custom_fields.clinica",
       "data_compra": "last_purchase_date",
       "Valor": "last_purchase_value"
     },
     "sample_rows": [...]
   }
   ```

3. **Usuário ajusta mapeamento (opcional) e importa:**
   ```
   POST /api/campaigns/campaigns/import_csv/
   Body:
   - file: CSV
   - campaign_name: "Cobrança RA - Janeiro 2025"
   - campaign_description: "Campanha de cobrança para clientes RA"
   - messages: [{"content": "Olá {name}, você tem uma pendência de R$ {valor}...", "order": 1}]
   - instances: ["uuid-instance-1"]
   - column_mapping: {...}
   ```

4. **Sistema:**
   - ✅ Importa contatos (cria/atualiza)
   - ✅ Armazena "Clinica" em `custom_fields.clinica`
   - ✅ Cria campanha
   - ✅ Associa contatos à campanha
   - ✅ Retorna resultado

---

## ✅ CHECKLIST DE IMPLEMENTAÇÃO

### Backend
- [ ] Estender `_auto_map_columns()` para campos customizados
- [ ] Atualizar `_process_row()` para processar `custom_fields`
- [ ] Criar `CampaignImportService`
- [ ] Criar endpoint `/api/campaigns/campaigns/import_csv/`
- [ ] Criar endpoint `/api/campaigns/campaigns/preview_csv/` (reutilizar ContactImportService)
- [ ] Testes unitários
- [ ] Script de teste local

### Frontend (Futuro)
- [ ] Componente `ImportCampaignModal`
- [ ] Integração com wizard de campanha
- [ ] Preview de mapeamento

---

## 🧪 TESTES NECESSÁRIOS

1. **Teste CSV fornecido:**
   - Verificar mapeamento automático
   - Verificar campos customizados em `custom_fields`
   - Verificar criação de campanha

2. **Teste com diferentes formatos:**
   - CSV com delimitador `;`
   - CSV com delimitador `,`
   - CSV com campos diferentes

3. **Teste de validação:**
   - CSV sem telefone
   - CSV sem nome
   - CSV com dados inválidos

---

## 📚 PRÓXIMOS PASSOS

1. ✅ **Revisar plano** com usuário
2. ⏳ **Implementar FASE 1** (mapeamento automático)
3. ⏳ **Implementar FASE 2** (CampaignImportService)
4. ⏳ **Implementar FASE 3** (endpoint)
5. ⏳ **Testar com CSV fornecido**
6. ⏳ **Criar script de teste local**
7. ⏳ **Documentar uso**

---

## 🎯 PARTE CRÍTICA: VARIÁVEIS DINÂMICAS NAS MENSAGENS

### **Problema Identificado:**

O sistema atual **NÃO suporta campos customizados como variáveis** nas mensagens!

**Código atual:**
- Usa variáveis hardcoded: `{{nome}}`, `{{primeiro_nome}}`, `{{saudacao}}`
- Não processa `custom_fields` dinamicamente
- `MessageVariableService` não existe (apenas na spec)

**Necessidade:**
- Usar campos do CSV como variáveis: `{{clinica}}`, `{{valor}}`, `{{data_compra}}`
- Sistema flexível que detecta automaticamente campos disponíveis
- Frontend mostra variáveis disponíveis dinamicamente

---

### **SOLUÇÃO: MessageVariableService com Suporte Dinâmico**

#### **FASE 5: Criar MessageVariableService**

**Arquivo:** `backend/apps/campaigns/services.py` (ADICIONAR)

```python
class MessageVariableService:
    """
    Service para renderizar variáveis em mensagens de campanha
    Suporta campos padrão + custom_fields dinamicamente
    """
    
    # Variáveis padrão disponíveis
    STANDARD_VARIABLES = {
        'nome': lambda c: c.name or '',
        'primeiro_nome': lambda c: c.name.split()[0] if c.name else '',
        'email': lambda c: c.email or '',
        'cidade': lambda c: c.city or '',
        'estado': lambda c: c.state or '',
        'quem_indicou': lambda c: c.referred_by or '',
        'primeiro_nome_indicador': lambda c: c.referred_by.split()[0] if c.referred_by else '',
        'valor_compra': lambda c: f"R$ {c.last_purchase_value:.2f}" if c.last_purchase_value else '',
        'data_compra': lambda c: c.last_purchase_date.strftime('%d/%m/%Y') if c.last_purchase_date else '',
    }
    
    @staticmethod
    def get_greeting():
        """Retorna saudação baseada no horário"""
        from datetime import datetime
        hour = datetime.now().hour
        if hour < 12:
            return 'Bom dia'
        elif hour < 18:
            return 'Boa tarde'
        else:
            return 'Boa noite'
    
    @staticmethod
    def get_day_of_week():
        """Retorna dia da semana"""
        from datetime import datetime
        dias = ['Segunda-feira', 'Terça-feira', 'Quarta-feira', 'Quinta-feira', 
                'Sexta-feira', 'Sábado', 'Domingo']
        return dias[datetime.now().weekday()]
    
    @staticmethod
    def render_message(template: str, contact, extra_vars: dict = None) -> str:
        """
        Renderiza template de mensagem com dados do contato
        
        Variáveis suportadas:
        - Padrão: {{nome}}, {{primeiro_nome}}, {{email}}, etc.
        - Customizadas: {{clinica}}, {{valor}}, {{data_compra}}, etc.
        - Sistema: {{saudacao}}, {{dia_semana}}
        
        Args:
            template: Template da mensagem com variáveis {{variavel}}
            contact: Objeto Contact
            extra_vars: Variáveis extras (opcional)
        
        Returns:
            str: Mensagem renderizada
        """
        rendered = template
        
        # 1. Variáveis padrão
        for var_name, getter in MessageVariableService.STANDARD_VARIABLES.items():
            value = getter(contact)
            rendered = rendered.replace(f'{{{{{var_name}}}}}', str(value))
        
        # 2. Variáveis de custom_fields (DINÂMICO!)
        if contact.custom_fields:
            for key, value in contact.custom_fields.items():
                # Suporta tanto {{clinica}} quanto {{custom.clinica}}
                rendered = rendered.replace(f'{{{{{key}}}}}', str(value))
                rendered = rendered.replace(f'{{{{custom.{key}}}}}', str(value))
        
        # 3. Variáveis do sistema
        rendered = rendered.replace('{{saudacao}}', MessageVariableService.get_greeting())
        rendered = rendered.replace('{{dia_semana}}', MessageVariableService.get_day_of_week())
        
        # 4. Variáveis extras (sobrescreve se houver)
        if extra_vars:
            for key, value in extra_vars.items():
                rendered = rendered.replace(f'{{{{{key}}}}}', str(value))
        
        return rendered
    
    @staticmethod
    def get_available_variables(contact=None) -> list:
        """
        Retorna lista de variáveis disponíveis
        
        Args:
            contact: Contato opcional (para incluir custom_fields)
        
        Returns:
            list: Lista de dicts com {variable, display_name, description}
        """
        variables = [
            {
                'variable': '{{nome}}',
                'display_name': 'Nome Completo',
                'description': 'Nome completo do contato',
                'category': 'padrão'
            },
            {
                'variable': '{{primeiro_nome}}',
                'display_name': 'Primeiro Nome',
                'description': 'Primeiro nome do contato',
                'category': 'padrão'
            },
            {
                'variable': '{{email}}',
                'display_name': 'Email',
                'description': 'Email do contato',
                'category': 'padrão'
            },
            {
                'variable': '{{cidade}}',
                'display_name': 'Cidade',
                'description': 'Cidade do contato',
                'category': 'padrão'
            },
            {
                'variable': '{{estado}}',
                'display_name': 'Estado (UF)',
                'description': 'Estado do contato',
                'category': 'padrão'
            },
            {
                'variable': '{{valor_compra}}',
                'display_name': 'Valor da Última Compra',
                'description': 'Valor formatado da última compra',
                'category': 'padrão'
            },
            {
                'variable': '{{data_compra}}',
                'display_name': 'Data da Última Compra',
                'description': 'Data da última compra (DD/MM/YYYY)',
                'category': 'padrão'
            },
            {
                'variable': '{{saudacao}}',
                'display_name': 'Saudação',
                'description': 'Bom dia/Boa tarde/Boa noite (automático)',
                'category': 'sistema'
            },
            {
                'variable': '{{dia_semana}}',
                'display_name': 'Dia da Semana',
                'description': 'Dia da semana atual',
                'category': 'sistema'
            },
        ]
        
        # Adicionar custom_fields se contato fornecido
        if contact and contact.custom_fields:
            for key, value in contact.custom_fields.items():
                variables.append({
                    'variable': f'{{{{{key}}}}}',
                    'display_name': key.replace('_', ' ').title(),
                    'description': f'Campo customizado: {key}',
                    'category': 'customizado',
                    'example_value': str(value)
                })
        
        return variables
    
    @staticmethod
    def validate_template(template: str) -> tuple[bool, list]:
        """
        Valida template de mensagem
        
        Returns:
            tuple: (is_valid, errors)
        """
        errors = []
        
        # Verificar balanceamento de chaves
        open_count = template.count('{{')
        close_count = template.count('}}')
        
        if open_count != close_count:
            errors.append('Chaves desbalanceadas: número de {{ não corresponde a }}')
        
        # Verificar variáveis malformadas
        import re
        malformed = re.findall(r'\{\{[^}]*[^}]$', template)
        if malformed:
            errors.append(f'Variáveis malformadas: {malformed}')
        
        return len(errors) == 0, errors
```

---

#### **FASE 6: Atualizar CampaignSender para usar MessageVariableService**

**Arquivo:** `backend/apps/campaigns/services.py` (MODIFICAR)

**Substituir código hardcoded (linhas 280-310) por:**

```python
# Substituir variáveis na mensagem usando MessageVariableService
from .services import MessageVariableService

message_text = MessageVariableService.render_message(
    template=message.content,
    contact=contact
)
```

**Também atualizar RabbitMQConsumer:**

**Arquivo:** `backend/apps/campaigns/rabbitmq_consumer.py`

```python
async def _replace_variables(self, message_text, contact):
    """Substitui variáveis usando MessageVariableService"""
    from .services import MessageVariableService
    return MessageVariableService.render_message(message_text, contact)
```

---

#### **FASE 7: Frontend - Variáveis Dinâmicas**

**Arquivo:** `frontend/src/components/campaigns/MessageVariables.tsx` (ATUALIZAR)

**Adicionar:**
1. **Buscar variáveis disponíveis** do backend
2. **Mostrar campos customizados** dinamicamente
3. **Preview com dados reais** do contato

```typescript
// Adicionar função para buscar variáveis disponíveis
const fetchAvailableVariables = async (contactId?: string) => {
  const url = contactId 
    ? `/api/campaigns/variables/?contact_id=${contactId}`
    : '/api/campaigns/variables/'
  
  const response = await api.get(url)
  return response.data
}

// Componente atualizado para mostrar variáveis dinâmicas
const [availableVariables, setAvailableVariables] = useState([])

useEffect(() => {
  fetchAvailableVariables().then(setAvailableVariables)
}, [])
```

**Criar endpoint no backend:**

**Arquivo:** `backend/apps/campaigns/views.py`

```python
@action(detail=False, methods=['get'])
def variables(self, request):
    """
    Retorna variáveis disponíveis para mensagens
    
    GET /api/campaigns/campaigns/variables/?contact_id=uuid (opcional)
    """
    from .services import MessageVariableService
    
    contact = None
    contact_id = request.query_params.get('contact_id')
    if contact_id:
        try:
            contact = Contact.objects.get(
                id=contact_id,
                tenant=request.user.tenant
            )
        except Contact.DoesNotExist:
            pass
    
    variables = MessageVariableService.get_available_variables(contact)
    
    return Response({
        'variables': variables,
        'total': len(variables)
    })
```

---

### **EXEMPLO DE USO:**

**CSV importado:**
```csv
Nome;DDD;Telefone;email;Clinica;data_compra;Valor
Maria Silva;11;999999999;maria@email.com;Hospital Veterinário Santa Inês;25/03/2024;R$ 1.500,00
```

**Mensagem da campanha:**
```
{{saudacao}}, {{primeiro_nome}}!

Lembramos que você tem uma pendência de {{valor}} referente à sua compra em {{data_compra}} na {{clinica}}.

Entre em contato conosco para regularizar.
```

**Mensagem renderizada:**
```
Boa tarde, Maria!

Lembramos que você tem uma pendência de R$ 1.500,00 referente à sua compra em 25/03/2024 na Hospital Veterinário Santa Inês.

Entre em contato conosco para regularizar.
```

---

## 💡 CONSIDERAÇÕES FINAIS

### **Vantagens da Abordagem:**

1. ✅ **Reutiliza código existente** - Menos bugs, mais rápido
2. ✅ **Usa custom_fields** - Flexível para qualquer campo
3. ✅ **Mantém consistência** - Mesmo padrão do sistema atual
4. ✅ **Escalável** - Fácil adicionar novos campos conhecidos
5. ✅ **Variáveis dinâmicas** - Campos do CSV viram variáveis automaticamente
6. ✅ **Frontend inteligente** - Mostra variáveis disponíveis dinamicamente

### **Pontos de Atenção:**

1. ⚠️ **Performance** - Importações grandes podem ser lentas
2. ⚠️ **Validação** - Campos customizados não são validados
3. ⚠️ **Mapeamento** - Usuário pode precisar ajustar manualmente
4. ⚠️ **Variáveis não encontradas** - Se campo não existe, variável fica vazia

### **Melhorias Futuras:**

1. 🚀 **Templates de mapeamento** (OPÇÃO 2)
2. 🚀 **Validação de campos customizados**
3. 🚀 **Importação assíncrona** (RabbitMQ)
4. 🚀 **Preview mais rico** no frontend
5. 🚀 **Validação de variáveis** antes de salvar mensagem
6. 🚀 **Sugestões de variáveis** baseadas no CSV importado


