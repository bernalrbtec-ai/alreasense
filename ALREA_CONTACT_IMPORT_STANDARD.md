# 📥 ALREA - Padrão de Importação de Contatos

> **Projeto:** ALREA - Plataforma Multi-Produto SaaS  
> **Módulo:** Importação de Contatos via CSV  
> **Versão:** 1.0.0  
> **Data:** 2025-10-10  
> **Objetivo:** Padronizar processo de importação com compliance LGPD

---

## 📋 ÍNDICE

1. [Visão Geral](#visão-geral)
2. [Formato Padrão CSV](#formato-padrão-csv)
3. [Mapeamento de Colunas](#mapeamento-de-colunas)
4. [Validações](#validações)
5. [Estratégias de Merge](#estratégias-de-merge)
6. [Tratamento de Erros](#tratamento-de-erros)
7. [Compliance LGPD](#compliance-lgpd)
8. [Fluxo Completo](#fluxo-completo)
9. [Interface Web](#interface-web)
10. [Processamento Assíncrono](#processamento-assíncrono)

---

## 🎯 VISÃO GERAL

### Objetivo

Permitir que clientes do ALREA importem suas bases de contatos existentes de forma:
- ✅ **Segura** (validações rigorosas)
- ✅ **Rápida** (processamento assíncrono)
- ✅ **Compliance** (respeito ao LGPD)
- ✅ **Inteligente** (detecção de duplicatas)
- ✅ **Auditável** (logs completos)

### Premissas Importantes

⚠️ **CRÍTICO:** Importação de contatos **NÃO significa opt-in automático**!

```
❌ ERRADO: Cliente importou → pode enviar mensagens
✅ CORRETO: Cliente importou → precisa VALIDAR consentimento primeiro
```

---

## 📄 FORMATO PADRÃO CSV

### Template Oficial

```csv
name,phone,email,birth_date,city,state,last_purchase_date,last_purchase_value,notes,tags,opt_in_confirmed
Maria Silva,11999999999,maria@email.com,1990-05-15,São Paulo,SP,2024-10-01,150.00,Cliente VIP,"vip,cliente_ativo",sim
João Santos,11988888888,joao@email.com,1985-03-20,Rio de Janeiro,RJ,,,Lead qualificado,"lead",nao
Ana Costa,21977777777,,,Niterói,RJ,2024-09-15,89.90,,"cliente_ativo",sim
```

### Campos Disponíveis

| Campo | Obrigatório | Formato | Exemplo | Descrição |
|-------|-------------|---------|---------|-----------|
| **name** | ✅ SIM | Texto (max 200) | "Maria Silva" | Nome completo |
| **phone** | ✅ SIM | Números (10-11 dígitos) | "11999999999" | Telefone (sem formatação) |
| **email** | ❌ Não | email@domain.com | "maria@email.com" | Email válido |
| **birth_date** | ❌ Não | YYYY-MM-DD | "1990-05-15" | Data de nascimento |
| **gender** | ❌ Não | M/F/O/N | "F" | Gênero |
| **city** | ❌ Não | Texto (max 100) | "São Paulo" | Cidade |
| **state** | ❌ Não | UF (2 letras) | "SP" | Estado |
| **zipcode** | ❌ Não | 8 dígitos | "01310100" | CEP (sem hífen) |
| **last_purchase_date** | ❌ Não | YYYY-MM-DD | "2024-10-01" | Última compra |
| **last_purchase_value** | ❌ Não | Decimal | "150.00" | Valor da compra |
| **total_purchases** | ❌ Não | Inteiro | "5" | Total de compras |
| **lifetime_value** | ❌ Não | Decimal | "750.00" | LTV total |
| **notes** | ❌ Não | Texto | "Cliente VIP" | Observações |
| **tags** | ❌ Não | Separado por vírgula | "vip,cliente_ativo" | Tags (serão criadas se não existirem) |
| **opt_in_confirmed** | ⚠️ IMPORTANTE | sim/nao | "sim" | Se tem consentimento LGPD |
| **opt_in_date** | ❌ Não | YYYY-MM-DD | "2024-01-15" | Data do consentimento |
| **opt_in_source** | ❌ Não | Texto | "loja_fisica" | Onde obteve consentimento |

### Encodings Suportados

```
✅ UTF-8 (recomendado)
✅ UTF-8 with BOM
✅ ISO-8859-1 (Latin-1)
⚠️ Windows-1252 (suporte limitado)
```

### Delimitadores

```
✅ Vírgula (,) - Padrão
✅ Ponto-e-vírgula (;) - Alternativo
✅ Tab (\t) - TSV
```

---

## 🗺️ MAPEAMENTO DE COLUNAS

### Nomes Alternativos Aceitos

O sistema reconhece automaticamente variações comuns:

```python
FIELD_ALIASES = {
    'phone': ['telefone', 'celular', 'whatsapp', 'fone', 'tel'],
    'name': ['nome', 'cliente', 'contato'],
    'email': ['e-mail', 'mail', 'email'],
    'birth_date': ['data_nascimento', 'nascimento', 'aniversario', 'birthday'],
    'city': ['cidade', 'municipio'],
    'state': ['estado', 'uf'],
    'zipcode': ['cep', 'zip', 'postal_code'],
    'notes': ['observacoes', 'obs', 'comentarios', 'anotacoes'],
    'tags': ['etiquetas', 'categorias', 'grupos']
}
```

**Exemplo:** CSV pode ter coluna "telefone" ou "celular" que será mapeada para "phone"

### Mapeamento Flexível na UI

```tsx
// Cliente pode mapear colunas manualmente
<ColumnMapper>
  <div>Coluna no CSV: "Fone" → Campo: [phone ▼]</div>
  <div>Coluna no CSV: "Nome Completo" → Campo: [name ▼]</div>
  <div>Coluna no CSV: "Data Nasc" → Campo: [birth_date ▼]</div>
  <div>Coluna no CSV: "Observação" → Campo: [notes ▼]</div>
</ColumnMapper>
```

---

## ✅ VALIDAÇÕES

### 1. Validação de Telefone

```python
def validate_phone(phone_str):
    """
    Valida e normaliza telefone brasileiro
    
    Aceita:
    - 11999999999
    - (11) 99999-9999
    - +55 11 99999-9999
    - 5511999999999
    
    Retorna: +5511999999999 (E.164)
    """
    import re
    
    # Remover formatação
    clean = re.sub(r'[^\d+]', '', phone_str)
    
    # Remover zeros à esquerda (exceto código do país)
    if clean.startswith('0'):
        clean = clean.lstrip('0')
    
    # Adicionar +55 se não tiver código de país
    if not clean.startswith('+'):
        if clean.startswith('55'):
            clean = f'+{clean}'
        else:
            clean = f'+55{clean}'
    
    # Validar comprimento (Brasil: +55 + DDD(2) + Número(8-9))
    # Total: 13-14 dígitos com +
    if len(clean) < 13 or len(clean) > 14:
        raise ValidationError(
            f'Telefone inválido: {phone_str}. '
            'Deve ter 10-11 dígitos (DDD + número)'
        )
    
    # Validar DDD (11-99)
    ddd = clean[3:5]  # Após +55
    if not (11 <= int(ddd) <= 99):
        raise ValidationError(f'DDD inválido: {ddd}')
    
    return clean
```

**Exemplos de validação:**

| Input | Output | Status |
|-------|--------|--------|
| "11999999999" | "+5511999999999" | ✅ |
| "(11) 99999-9999" | "+5511999999999" | ✅ |
| "+55 11 9999-9999" | "+5511999999999" | ✅ |
| "999999999" | - | ❌ Sem DDD |
| "00999999999" | - | ❌ DDD inválido |
| "11 9999-999" | - | ❌ Muito curto |

### 2. Validação de Email

```python
from django.core.validators import validate_email as django_validate_email

def validate_email(email_str):
    """Valida formato de email"""
    if not email_str or pd.isna(email_str):
        return None
    
    email_str = email_str.strip().lower()
    
    try:
        django_validate_email(email_str)
        return email_str
    except ValidationError:
        raise ValidationError(f'Email inválido: {email_str}')
```

### 3. Validação de Data

```python
from datetime import datetime

def validate_date(date_str, field_name):
    """
    Valida data em múltiplos formatos
    
    Aceita:
    - 2024-10-10 (ISO)
    - 10/10/2024 (BR)
    - 10-10-2024
    """
    if not date_str or pd.isna(date_str):
        return None
    
    # Formatos aceitos
    formats = [
        '%Y-%m-%d',      # 2024-10-10
        '%d/%m/%Y',      # 10/10/2024
        '%d-%m-%Y',      # 10-10-2024
        '%Y/%m/%d',      # 2024/10/10
    ]
    
    for fmt in formats:
        try:
            return datetime.strptime(date_str, fmt).date()
        except ValueError:
            continue
    
    raise ValidationError(
        f'{field_name} inválido: {date_str}. '
        'Use formato YYYY-MM-DD ou DD/MM/YYYY'
    )
```

### 4. Validação de Estado (UF)

```python
VALID_STATES = [
    'AC', 'AL', 'AP', 'AM', 'BA', 'CE', 'DF', 'ES', 'GO', 'MA',
    'MT', 'MS', 'MG', 'PA', 'PB', 'PR', 'PE', 'PI', 'RJ', 'RN',
    'RS', 'RO', 'RR', 'SC', 'SP', 'SE', 'TO'
]

def validate_state(state_str):
    """Valida UF brasileira"""
    if not state_str or pd.isna(state_str):
        return None
    
    state_str = state_str.strip().upper()
    
    if state_str not in VALID_STATES:
        raise ValidationError(
            f'Estado inválido: {state_str}. '
            f'Use UF válida: {", ".join(VALID_STATES)}'
        )
    
    return state_str
```

### 5. Validação de Valores Decimais

```python
from decimal import Decimal, InvalidOperation

def validate_decimal(value_str, field_name):
    """Valida e converte valores monetários"""
    if not value_str or pd.isna(value_str):
        return None
    
    # Limpar formatação
    clean = str(value_str).replace(',', '.').replace('R$', '').strip()
    
    try:
        value = Decimal(clean)
        
        if value < 0:
            raise ValidationError(f'{field_name} não pode ser negativo')
        
        return value
    except (InvalidOperation, ValueError):
        raise ValidationError(f'{field_name} inválido: {value_str}')
```

---

## 🔄 ESTRATÉGIAS DE MERGE

### Opções Disponíveis

```python
class MergeStrategy(models.TextChoices):
    SKIP = 'skip', 'Pular Duplicatas'
    UPDATE = 'update', 'Atualizar Existentes'
    CREATE_DUPLICATE = 'create_duplicate', 'Criar Duplicado (não recomendado)'
```

### 1. SKIP (Padrão - Mais Seguro)

**Comportamento:**
- Se telefone já existe → **ignora linha**
- Se telefone é novo → **cria contato**

**Quando usar:**
- Primeira importação
- Não quer sobrescrever dados existentes
- Lista tem muitos duplicados

```python
if Contact.objects.filter(tenant=tenant, phone=phone).exists():
    import_record.skipped_count += 1
    import_record.errors.append({
        'row': row_number,
        'phone': phone,
        'reason': 'Telefone já existe (SKIP)'
    })
    continue  # Pula para próxima linha
```

**Relatório:**
```
✅ 850 contatos criados
⏭️ 150 contatos pulados (já existiam)
❌ 0 erros
```

### 2. UPDATE (Atualizar)

**Comportamento:**
- Se telefone já existe → **atualiza campos**
- Se telefone é novo → **cria contato**

**Regras de atualização:**
- Campos vazios no CSV → **não altera** campo existente
- Campos preenchidos no CSV → **sobrescreve** campo existente
- Tags → **adiciona** (não remove tags antigas)

**Quando usar:**
- Atualizar base existente com novos dados
- Corrigir informações desatualizadas
- Enriquecer contatos

```python
existing = Contact.objects.filter(tenant=tenant, phone=phone).first()

if existing:
    # Atualizar apenas campos não vazios no CSV
    if row.get('name'):
        existing.name = row['name']
    
    if row.get('email'):
        existing.email = row['email']
    
    if row.get('city'):
        existing.city = row['city']
    
    # ... outros campos
    
    existing.save()
    import_record.updated_count += 1
```

**Relatório:**
```
✅ 200 contatos criados
🔄 500 contatos atualizados
⏭️ 0 contatos pulados
❌ 0 erros
```

### 3. CREATE_DUPLICATE (Não Recomendado)

**Comportamento:**
- **Sempre cria** novo contato, mesmo se telefone existe

⚠️ **CUIDADO:** Vai criar múltiplos contatos com mesmo telefone!

**Quando usar:**
- Quase nunca
- Apenas se realmente quer duplicatas (ex: histórico de versões)

---

## ⚠️ TRATAMENTO DE ERROS

### Tipos de Erros

```python
class ImportError(TypedDict):
    row: int                    # Número da linha (1-based)
    field: str                  # Campo com erro
    value: str                  # Valor que causou erro
    error: str                  # Mensagem de erro
    severity: str               # 'critical' | 'warning'
```

### 1. Erros Críticos (Linha Ignorada)

```python
CRITICAL_ERRORS = {
    'missing_phone': 'Telefone obrigatório não informado',
    'missing_name': 'Nome obrigatório não informado',
    'invalid_phone': 'Telefone em formato inválido',
    'duplicate_in_csv': 'Telefone duplicado no mesmo CSV',
}

# Exemplo de erro crítico
{
    'row': 45,
    'field': 'phone',
    'value': '999999',
    'error': 'Telefone inválido (muito curto)',
    'severity': 'critical'
}
```

### 2. Warnings (Linha Processada, Campo Ignorado)

```python
WARNINGS = {
    'invalid_email': 'Email ignorado (formato inválido)',
    'invalid_date': 'Data ignorada (formato inválido)',
    'invalid_state': 'Estado ignorado (UF inválida)',
    'negative_value': 'Valor negativo ignorado',
}

# Exemplo de warning
{
    'row': 67,
    'field': 'email',
    'value': 'email@invalido',
    'error': 'Email em formato inválido - campo ignorado',
    'severity': 'warning'
}
# Contato É criado, mas sem email
```

### Relatório de Erros Estruturado

```json
{
  "import_id": "uuid",
  "status": "completed_with_errors",
  "summary": {
    "total_rows": 1000,
    "processed": 950,
    "created": 850,
    "updated": 100,
    "skipped": 30,
    "errors": 20
  },
  "errors": [
    {
      "row": 5,
      "field": "phone",
      "value": "999",
      "error": "Telefone muito curto",
      "severity": "critical"
    },
    {
      "row": 12,
      "field": "email",
      "value": "email@invalido",
      "error": "Email inválido - campo ignorado",
      "severity": "warning"
    }
  ]
}
```

---

## 🔒 COMPLIANCE LGPD

### Marcação de Consentimento na Importação

**⚠️ CRÍTICO:** Ao importar contatos, você **DEVE** indicar se eles têm consentimento.

#### Opção 1: Coluna `opt_in_confirmed` no CSV

```csv
name,phone,opt_in_confirmed,opt_in_date,opt_in_source
Maria Silva,11999999999,sim,2024-01-15,loja_fisica
João Santos,11988888888,nao,,
```

#### Opção 2: Checkbox na UI (Aplicar a Todos)

```tsx
<div className="p-4 bg-yellow-50 border border-yellow-200 rounded">
  <h4 className="font-semibold text-yellow-800 mb-2">
    ⚠️ Consentimento LGPD
  </h4>
  
  <label className="flex items-start gap-2">
    <input type="checkbox" name="all_have_consent" />
    <span className="text-sm">
      Confirmo que <strong>TODOS os contatos deste arquivo</strong> 
      autorizaram explicitamente receber mensagens via WhatsApp.
    </span>
  </label>
  
  {allHaveConsent && (
    <div className="mt-3 space-y-2">
      <input
        type="text"
        placeholder="Onde obteve consentimento? (ex: loja física, site, evento)"
        className="w-full px-3 py-2 border rounded text-sm"
      />
      
      <input
        type="date"
        placeholder="Data do consentimento"
        className="w-full px-3 py-2 border rounded text-sm"
      />
    </div>
  )}
  
  {!allHaveConsent && (
    <p className="mt-2 text-xs text-red-600">
      ⚠️ Contatos sem consentimento NÃO poderão receber campanhas até que 
      seja confirmado individualmente.
    </p>
  )}
</div>
```

#### Opção 3: Revisão Pós-Importação

```tsx
// Após importar, mostrar lista de contatos sem opt-in
<div className="mt-4">
  <h4 className="font-semibold text-red-600 mb-2">
    ⚠️ 150 contatos importados SEM consentimento
  </h4>
  
  <p className="text-sm text-gray-600 mb-3">
    Estes contatos NÃO receberão campanhas até que seja confirmado o opt-in.
  </p>
  
  <div className="space-y-2">
    {contactsWithoutOptIn.map(contact => (
      <div className="flex items-center justify-between p-2 bg-gray-50 rounded">
        <span>{contact.name} - {contact.phone}</span>
        <Button 
          size="sm" 
          onClick={() => confirmOptIn(contact.id)}
        >
          Confirmar Opt-In
        </Button>
      </div>
    ))}
  </div>
</div>
```

### Lógica no Backend

```python
def process_import_row(row, import_config):
    """Processa uma linha do CSV"""
    
    # Determinar opt-in
    opt_in_confirmed = False
    opt_in_date = None
    opt_in_source = 'import'
    
    # Prioridade 1: Coluna no CSV
    if 'opt_in_confirmed' in row:
        opt_in_confirmed = row['opt_in_confirmed'].lower() in ['sim', 'yes', 'true', '1']
        opt_in_date = parse_date(row.get('opt_in_date')) or timezone.now()
        opt_in_source = row.get('opt_in_source', 'import')
    
    # Prioridade 2: Configuração global da importação
    elif import_config.get('all_have_consent'):
        opt_in_confirmed = True
        opt_in_date = import_config.get('consent_date') or timezone.now()
        opt_in_source = import_config.get('consent_source', 'import')
    
    # Criar contato
    contact = Contact.objects.create(
        tenant=tenant,
        name=row['name'],
        phone=row['phone'],
        # ... outros campos ...
        
        # Opt-in
        opted_out=False,  # Importação nunca cria opted-out
        opt_in_date=opt_in_date if opt_in_confirmed else None,
        opt_in_source=opt_in_source if opt_in_confirmed else None,
        consent_text=(
            import_config.get('consent_text', 'Consentimento fornecido em importação de lista')
            if opt_in_confirmed else None
        ),
        
        source='import'
    )
    
    # Se NÃO tem opt-in, criar alerta
    if not opt_in_confirmed:
        ContactAlert.objects.create(
            contact=contact,
            alert_type='missing_opt_in',
            message='Contato importado sem confirmação de consentimento LGPD',
            created_by=import_config['user']
        )
    
    return contact
```

### Dashboard de Compliance Pós-Importação

```python
# GET /api/contacts/imports/{import_id}/compliance/

{
  "import_id": "uuid",
  "total_imported": 1000,
  "with_opt_in": 850,        # 85% OK ✅
  "without_opt_in": 150,     # 15% ⚠️ Precisa confirmar
  "opted_out": 0,
  
  "recommendations": [
    "150 contatos precisam de confirmação de opt-in antes de receber campanhas",
    "Envie email/SMS para confirmar consentimento ou marque manualmente"
  ],
  
  "next_steps": [
    {
      "action": "Confirmar opt-in em massa",
      "endpoint": "POST /api/contacts/bulk-opt-in/",
      "contacts": [/* IDs dos 150 contatos */]
    }
  ]
}
```

---

## 🔄 FLUXO COMPLETO DE IMPORTAÇÃO

### Diagrama de Processo

```
┌─────────────────────────────────────────────────────────────┐
│ 1. UPLOAD                                                   │
├─────────────────────────────────────────────────────────────┤
│ Cliente faz upload do CSV                                   │
│ ├─ Frontend: Validação inicial (tamanho, formato)          │
│ ├─ Backend: Salva arquivo (S3 ou local)                    │
│ └─ Cria registro ContactImport (status: pending)           │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│ 2. PREVIEW (Opcional)                                       │
├─────────────────────────────────────────────────────────────┤
│ Mostra primeiras 10 linhas                                  │
│ ├─ Cliente revisa mapeamento de colunas                    │
│ ├─ Cliente confirma estratégia de merge                    │
│ ├─ Cliente confirma opt-in (se aplicável)                  │
│ └─ Cliente confirma tags automáticas                       │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│ 3. PROCESSAMENTO (Celery Task Assíncrono)                  │
├─────────────────────────────────────────────────────────────┤
│ ContactImport.status = 'processing'                         │
│                                                             │
│ Para cada linha do CSV:                                     │
│   ├─ Validar campos obrigatórios                           │
│   ├─ Normalizar telefone                                   │
│   ├─ Validar email, datas, valores                         │
│   ├─ Verificar duplicatas                                  │
│   │   ├─ Se SKIP: pular linha                              │
│   │   ├─ Se UPDATE: atualizar existente                    │
│   │   └─ Se CREATE: criar duplicado                        │
│   ├─ Criar/atualizar contato                               │
│   ├─ Associar tags                                         │
│   ├─ Registrar opt-in (se aplicável)                       │
│   ├─ Criar log de sucesso/erro                             │
│   └─ Atualizar progresso (10%, 20%, ...)                   │
│                                                             │
│ ContactImport.status = 'completed'                          │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│ 4. RELATÓRIO                                                │
├─────────────────────────────────────────────────────────────┤
│ ✅ 850 criados                                              │
│ 🔄 100 atualizados                                          │
│ ⏭️ 30 pulados (duplicatas)                                  │
│ ❌ 20 erros (telefones inválidos)                           │
│                                                             │
│ ⚠️ 150 sem opt-in confirmado                                │
│                                                             │
│ [Download Relatório Completo] [Ver Erros]                  │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│ 5. PÓS-IMPORTAÇÃO                                           │
├─────────────────────────────────────────────────────────────┤
│ ├─ Adicionar tags automáticas (se configurado)             │
│ ├─ Criar alertas para contatos sem opt-in                  │
│ ├─ Enviar notificação para usuário (email/push)            │
│ └─ Atualizar estatísticas do tenant                        │
└─────────────────────────────────────────────────────────────┘
```

---

## 🎨 INTERFACE WEB

### 1. Página de Upload

```tsx
// frontend/src/components/contacts/ImportContactsModal.tsx

export default function ImportContactsModal() {
  const [step, setStep] = useState(1) // 1=upload, 2=config, 3=preview, 4=processing, 5=result
  const [file, setFile] = useState(null)
  const [config, setConfig] = useState({
    merge_strategy: 'skip',
    all_have_consent: false,
    consent_source: '',
    consent_date: null,
    auto_tag: null,
    column_mapping: {}
  })
  
  return (
    <Modal size="xl">
      {/* Progress Indicator */}
      <StepIndicator current={step} total={5} />
      
      {/* Step 1: Upload */}
      {step === 1 && (
        <div className="space-y-4">
          <h3 className="text-xl font-semibold">Importar Contatos</h3>
          
          <div className="border-2 border-dashed border-gray-300 rounded-lg p-8 text-center">
            <Upload className="mx-auto h-12 w-12 text-gray-400 mb-4" />
            
            <input
              type="file"
              accept=".csv,.txt"
              onChange={handleFileSelect}
              className="hidden"
              id="file-upload"
            />
            
            <label htmlFor="file-upload" className="cursor-pointer">
              <span className="text-blue-600 hover:text-blue-700 font-medium">
                Clique para selecionar arquivo
              </span>
              <span className="text-gray-500"> ou arraste aqui</span>
            </label>
            
            <p className="text-sm text-gray-500 mt-2">
              CSV, máximo 10 MB (até 50.000 contatos)
            </p>
          </div>
          
          {file && (
            <div className="bg-gray-50 p-4 rounded">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <FileText className="h-8 w-8 text-blue-600" />
                  <div>
                    <p className="font-medium">{file.name}</p>
                    <p className="text-sm text-gray-500">
                      {(file.size / 1024).toFixed(1)} KB
                    </p>
                  </div>
                </div>
                <Button variant="ghost" onClick={() => setFile(null)}>
                  <X className="h-4 w-4" />
                </Button>
              </div>
            </div>
          )}
          
          {/* Template Download */}
          <div className="bg-blue-50 p-4 rounded">
            <p className="text-sm text-blue-800 mb-2">
              📥 Não tem um CSV? Baixe nosso template padrão
            </p>
            <Button variant="outline" size="sm" onClick={downloadTemplate}>
              <Download className="h-4 w-4 mr-2" />
              Baixar Template CSV
            </Button>
          </div>
          
          <div className="flex justify-end">
            <Button onClick={() => setStep(2)} disabled={!file}>
              Próximo
            </Button>
          </div>
        </div>
      )}
      
      {/* Step 2: Configurações */}
      {step === 2 && (
        <div className="space-y-6">
          <h3 className="text-xl font-semibold">Configurações de Importação</h3>
          
          {/* Estratégia de Merge */}
          <div>
            <label className="block text-sm font-medium mb-2">
              O que fazer com contatos duplicados?
            </label>
            <RadioGroup value={config.merge_strategy} onChange={handleMergeChange}>
              <Radio value="skip">
                <div>
                  <p className="font-medium">Pular duplicatas (Recomendado)</p>
                  <p className="text-sm text-gray-500">
                    Contatos que já existem serão ignorados
                  </p>
                </div>
              </Radio>
              
              <Radio value="update">
                <div>
                  <p className="font-medium">Atualizar existentes</p>
                  <p className="text-sm text-gray-500">
                    Sobrescrever dados de contatos que já existem
                  </p>
                </div>
              </Radio>
            </RadioGroup>
          </div>
          
          {/* Consentimento LGPD */}
          <div className="border-l-4 border-yellow-400 bg-yellow-50 p-4">
            <h4 className="font-semibold text-yellow-800 mb-3">
              ⚠️ Consentimento LGPD Obrigatório
            </h4>
            
            <label className="flex items-start gap-3">
              <input
                type="checkbox"
                checked={config.all_have_consent}
                onChange={e => setConfig({
                  ...config,
                  all_have_consent: e.target.checked
                })}
              />
              <div>
                <p className="text-sm font-medium text-gray-900">
                  Confirmo que TODOS os contatos autorizaram receber mensagens
                </p>
                <p className="text-xs text-gray-600 mt-1">
                  Sem essa confirmação, os contatos não receberão campanhas
                </p>
              </div>
            </label>
            
            {config.all_have_consent && (
              <div className="mt-4 space-y-3">
                <div>
                  <label className="block text-sm mb-1">
                    Onde obteve o consentimento?
                  </label>
                  <input
                    type="text"
                    value={config.consent_source}
                    onChange={e => setConfig({
                      ...config,
                      consent_source: e.target.value
                    })}
                    placeholder="Ex: Loja física, Evento, Site, Formulário"
                    className="w-full px-3 py-2 border rounded"
                  />
                </div>
                
                <div>
                  <label className="block text-sm mb-1">
                    Data do consentimento
                  </label>
                  <input
                    type="date"
                    value={config.consent_date}
                    onChange={e => setConfig({
                      ...config,
                      consent_date: e.target.value
                    })}
                    className="w-full px-3 py-2 border rounded"
                  />
                </div>
              </div>
            )}
          </div>
          
          {/* Tag Automática */}
          <div>
            <label className="block text-sm font-medium mb-2">
              Adicionar tag automática a todos os importados?
            </label>
            <TagSelector
              value={config.auto_tag}
              onChange={tag => setConfig({ ...config, auto_tag: tag })}
              placeholder="Selecione uma tag (opcional)"
            />
            <p className="text-xs text-gray-500 mt-1">
              Útil para identificar origem: "Importação Out/2024"
            </p>
          </div>
          
          <div className="flex justify-between">
            <Button variant="outline" onClick={() => setStep(1)}>
              Voltar
            </Button>
            <Button onClick={() => setStep(3)}>
              Próximo: Preview
            </Button>
          </div>
        </div>
      )}
      
      {/* Step 3: Preview */}
      {step === 3 && (
        <div className="space-y-4">
          <h3 className="text-xl font-semibold">Preview dos Dados</h3>
          
          <p className="text-sm text-gray-600">
            Mostrando primeiras 10 linhas do arquivo
          </p>
          
          {/* Mapeamento de Colunas */}
          <div className="border rounded overflow-hidden">
            <table className="w-full text-sm">
              <thead className="bg-gray-50">
                <tr>
                  <th className="px-4 py-2 text-left">Coluna no CSV</th>
                  <th className="px-4 py-2 text-left">Campo no Sistema</th>
                  <th className="px-4 py-2 text-left">Preview</th>
                </tr>
              </thead>
              <tbody>
                {Object.entries(previewData.column_mapping).map(([csvCol, sysField]) => (
                  <tr key={csvCol} className="border-t">
                    <td className="px-4 py-2 font-mono text-xs">{csvCol}</td>
                    <td className="px-4 py-2">
                      <select
                        value={sysField}
                        onChange={e => updateMapping(csvCol, e.target.value)}
                        className="text-sm border rounded px-2 py-1"
                      >
                        <option value="">Ignorar</option>
                        <option value="name">Nome</option>
                        <option value="phone">Telefone</option>
                        <option value="email">Email</option>
                        {/* ... outros campos */}
                      </select>
                    </td>
                    <td className="px-4 py-2 text-xs text-gray-600">
                      {previewData.samples[csvCol][0]}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          
          {/* Preview de Linhas */}
          <div>
            <h4 className="font-medium mb-2">Primeiras linhas</h4>
            <div className="border rounded overflow-auto max-h-64">
              <table className="w-full text-xs">
                <thead className="bg-gray-50 sticky top-0">
                  <tr>
                    {previewData.headers.map(header => (
                      <th key={header} className="px-3 py-2 text-left font-medium">
                        {header}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {previewData.rows.map((row, i) => (
                    <tr key={i} className="border-t hover:bg-gray-50">
                      {Object.values(row).map((value, j) => (
                        <td key={j} className="px-3 py-2">
                          {value}
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
          
          <div className="flex justify-between">
            <Button variant="outline" onClick={() => setStep(2)}>
              Voltar
            </Button>
            <Button onClick={startImport}>
              Iniciar Importação
            </Button>
          </div>
        </div>
      )}
      
      {/* Step 4: Processando */}
      {step === 4 && (
        <div className="text-center py-8">
          <Loader className="h-16 w-16 text-blue-600 animate-spin mx-auto mb-4" />
          
          <h3 className="text-xl font-semibold mb-2">
            Importando Contatos...
          </h3>
          
          <p className="text-gray-600 mb-6">
            Processando linha {progress.current} de {progress.total}
          </p>
          
          {/* Progress Bar */}
          <div className="max-w-md mx-auto">
            <div className="w-full bg-gray-200 rounded-full h-3">
              <div
                className="bg-blue-600 h-3 rounded-full transition-all"
                style={{ width: `${progress.percentage}%` }}
              />
            </div>
            <p className="text-sm text-gray-500 mt-2">
              {progress.percentage}%
            </p>
          </div>
          
          {/* Stats em Tempo Real */}
          <div className="grid grid-cols-3 gap-4 mt-8 max-w-lg mx-auto">
            <div className="bg-green-50 p-3 rounded">
              <p className="text-2xl font-bold text-green-600">
                {progress.created}
              </p>
              <p className="text-xs text-gray-600">Criados</p>
            </div>
            
            <div className="bg-blue-50 p-3 rounded">
              <p className="text-2xl font-bold text-blue-600">
                {progress.updated}
              </p>
              <p className="text-xs text-gray-600">Atualizados</p>
            </div>
            
            <div className="bg-red-50 p-3 rounded">
              <p className="text-2xl font-bold text-red-600">
                {progress.errors}
              </p>
              <p className="text-xs text-gray-600">Erros</p>
            </div>
          </div>
        </div>
      )}
      
      {/* Step 5: Resultado */}
      {step === 5 && (
        <div className="space-y-6">
          <div className="text-center">
            <CheckCircle className="h-16 w-16 text-green-500 mx-auto mb-4" />
            <h3 className="text-2xl font-semibold mb-2">
              Importação Concluída!
            </h3>
          </div>
          
          {/* Summary Cards */}
          <div className="grid grid-cols-2 gap-4">
            <Card className="p-4 bg-green-50 border-green-200">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm text-gray-600">Criados</p>
                  <p className="text-3xl font-bold text-green-600">
                    {result.created}
                  </p>
                </div>
                <PlusCircle className="h-8 w-8 text-green-500" />
              </div>
            </Card>
            
            <Card className="p-4 bg-blue-50 border-blue-200">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm text-gray-600">Atualizados</p>
                  <p className="text-3xl font-bold text-blue-600">
                    {result.updated}
                  </p>
                </div>
                <RefreshCw className="h-8 w-8 text-blue-500" />
              </div>
            </Card>
            
            <Card className="p-4 bg-gray-50 border-gray-200">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm text-gray-600">Pulados</p>
                  <p className="text-3xl font-bold text-gray-600">
                    {result.skipped}
                  </p>
                </div>
                <SkipForward className="h-8 w-8 text-gray-500" />
              </div>
            </Card>
            
            <Card className="p-4 bg-red-50 border-red-200">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm text-gray-600">Erros</p>
                  <p className="text-3xl font-bold text-red-600">
                    {result.errors}
                  </p>
                </div>
                <AlertCircle className="h-8 w-8 text-red-500" />
              </div>
            </Card>
          </div>
          
          {/* Alertas */}
          {result.without_opt_in > 0 && (
            <Alert variant="warning">
              <AlertTriangle className="h-4 w-4" />
              <div>
                <p className="font-medium">
                  {result.without_opt_in} contatos sem confirmação de opt-in
                </p>
                <p className="text-sm">
                  Estes contatos não receberão campanhas até que seja confirmado o consentimento.
                </p>
              </div>
            </Alert>
          )}
          
          {/* Actions */}
          <div className="flex gap-2">
            <Button onClick={downloadReport} variant="outline" className="flex-1">
              <Download className="h-4 w-4 mr-2" />
              Baixar Relatório Completo
            </Button>
            
            {result.errors > 0 && (
              <Button onClick={viewErrors} variant="outline" className="flex-1">
                <AlertCircle className="h-4 w-4 mr-2" />
                Ver Erros ({result.errors})
              </Button>
            )}
          </div>
          
          <div className="flex justify-end">
            <Button onClick={onClose}>
              Concluir
            </Button>
          </div>
        </div>
      )}
    </Modal>
  )
}
```

---

## ⚙️ PROCESSAMENTO ASSÍNCRONO

### Celery Task

```python
# apps/contacts/tasks.py

from celery import shared_task
import pandas as pd
from io import StringIO

@shared_task(bind=True)
def process_contact_import(self, import_id):
    """
    Processa importação de contatos de forma assíncrona
    
    Args:
        import_id: UUID do ContactImport
    """
    try:
        import_record = ContactImport.objects.get(id=import_id)
    except ContactImport.DoesNotExist:
        logger.error(f'Import {import_id} não encontrado')
        return
    
    # Marcar como processando
    import_record.status = ContactImport.Status.PROCESSING
    import_record.save()
    
    try:
        # Ler arquivo CSV
        with open(import_record.file_path, 'r', encoding='utf-8') as f:
            df = pd.read_csv(f)
        
        import_record.total_rows = len(df)
        import_record.save()
        
        # Processar cada linha
        for index, row in df.iterrows():
            try:
                process_import_row(
                    row=row,
                    import_record=import_record,
                    row_number=index + 2  # +2 porque: 1=header, index é 0-based
                )
                
                # Atualizar progresso
                import_record.processed_rows = index + 1
                import_record.save()
                
                # Atualizar progresso no Celery (para UI)
                self.update_state(
                    state='PROGRESS',
                    meta={
                        'current': index + 1,
                        'total': import_record.total_rows,
                        'created': import_record.created_count,
                        'updated': import_record.updated_count,
                        'errors': import_record.error_count
                    }
                )
                
            except Exception as e:
                # Log erro mas continua processando
                logger.error(f'Erro na linha {index + 2}: {e}')
                import_record.error_count += 1
                import_record.errors.append({
                    'row': index + 2,
                    'error': str(e),
                    'severity': 'critical'
                })
                import_record.save()
        
        # Concluir
        import_record.status = ContactImport.Status.COMPLETED
        import_record.completed_at = timezone.now()
        import_record.save()
        
        # Enviar notificação
        send_import_completion_notification(import_record)
        
        return {
            'status': 'success',
            'created': import_record.created_count,
            'updated': import_record.updated_count,
            'errors': import_record.error_count
        }
        
    except Exception as e:
        logger.error(f'Erro fatal no import {import_id}: {e}')
        import_record.status = ContactImport.Status.FAILED
        import_record.errors.append({
            'row': 0,
            'error': f'Erro fatal: {str(e)}',
            'severity': 'critical'
        })
        import_record.save()
        
        raise


def process_import_row(row, import_record, row_number):
    """Processa uma linha individual do CSV"""
    from .services import ContactImportService
    
    service = ContactImportService(
        tenant=import_record.tenant,
        user=import_record.created_by
    )
    
    return service.process_row(
        row=row.to_dict(),
        import_record=import_record,
        row_number=row_number
    )
```

---

## 📊 RELATÓRIO PÓS-IMPORTAÇÃO

### Estrutura do Relatório

```json
{
  "import_summary": {
    "import_id": "uuid",
    "file_name": "contatos_outubro_2024.csv",
    "imported_at": "2024-10-10T14:30:00Z",
    "imported_by": "usuario@email.com",
    "processing_time": "2m 15s",
    
    "totals": {
      "rows": 1000,
      "processed": 980,
      "created": 850,
      "updated": 100,
      "skipped": 30,
      "errors": 20
    },
    
    "compliance": {
      "with_opt_in": 850,
      "without_opt_in": 130,
      "opt_in_percentage": 86.7
    }
  },
  
  "errors": [
    {
      "row": 5,
      "field": "phone",
      "value": "999",
      "error": "Telefone inválido - muito curto"
    }
  ],
  
  "warnings": [
    {
      "row": 12,
      "field": "email",
      "value": "email@invalido",
      "error": "Email ignorado - formato inválido"
    }
  ]
}
```

---

Quer que eu continue detalhando alguma parte específica ou já ficou claro o processo de importação? 🎯



