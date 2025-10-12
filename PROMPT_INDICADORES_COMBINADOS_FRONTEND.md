# 📊 PROMPT: Indicadores Combinados - Estados + Opt-in/Opt-out

## 🎯 **OBJETIVO**

Criar uma seção de **indicadores visuais** na página de contatos combinando:
1. **📍 Distribuição Geográfica** (Estados)
2. **✅ Taxa de Opt-in/Opt-out** (Compliance LGPD)

## 💡 **CONCEITO**

Esses dois indicadores juntos mostram:
- **Geografia:** Onde estão seus contatos
- **Compliance:** Quantos podem receber campanhas

---

## 🎨 **LAYOUT PROPOSTO**

### **Opção 1: Duas Colunas (Recomendado)** ⭐

```
┌────────────────────────────────────────────────────────────┐
│  [Stats linha 1: Total, Leads, Clientes, Opt-out]         │
└────────────────────────────────────────────────────────────┘

┌──────────────────────────────┬─────────────────────────────┐
│ 📍 Distribuição Geográfica   │ ✅ Status de Consentimento  │
├──────────────────────────────┼─────────────────────────────┤
│ 3 estados  2 sem UF          │ 320 aptos   30 opt-out      │
│                              │                             │
│ SP    150 (45%) ████████░░░  │      [Gráfico Pizza]        │
│ RJ    100 (30%) █████░░░░░░  │         91.4%               │
│ MG     50 (15%) ██░░░░░░░░░  │       opt-in                │
│ N/A    30 (9%)  █░░░░░░░░░░  │                             │
│                              │  320 podem receber msgs     │
│                              │  30 bloqueados (LGPD)       │
└──────────────────────────────┴─────────────────────────────┘
```

### **Opção 2: Linha Única com Cards** 🎴

```
┌─────────────────────────────────────────────────────────────┐
│ 📊 INDICADORES DE BASE                                      │
├─────────────────────────────────────────────────────────────┤
│ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐       │
│ │ SP: 150  │ │ RJ: 100  │ │ MG: 50   │ │ 91% OK   │       │
│ │ 45%      │ │ 30%      │ │ 15%      │ │ opt-in   │       │
│ └──────────┘ └──────────┘ └──────────┘ └──────────┘       │
└─────────────────────────────────────────────────────────────┘
```

### **Opção 3: Card Único Expandido** 📈

```
┌─────────────────────────────────────────────────────────────┐
│ 📊 VISÃO GERAL DA BASE                                      │
├─────────────────────────────────────────────────────────────┤
│ Geográfico                  │ Consentimento                 │
│ • SP: 150 (45%)             │ • ✅ Opt-in: 320 (91.4%)     │
│ • RJ: 100 (30%)             │ • ❌ Opt-out: 30 (8.6%)      │
│ • MG: 50 (15%)              │ • ⚠️  Pendente: 0 (0%)       │
│ • 3 estados ativos          │ • 📩 Aptos p/ campanha: 320  │
└─────────────────────────────────────────────────────────────┘
```

---

## 📝 **IMPLEMENTAÇÃO COMPLETA**

### **1. Adicionar funções helper para Opt-in/Opt-out**

```typescript
// Contatos que podem receber mensagens (opt-in)
const getOptInContacts = () => {
  return contacts.filter(c => !c.opted_out && c.is_active).length
}

// Contatos que NÃO podem receber mensagens (opt-out)
const getOptOutContacts = () => {
  return contacts.filter(c => c.opted_out).length
}

// Taxa de opt-in em %
const getOptInRate = () => {
  if (contacts.length === 0) return 0
  return ((getOptInContacts() / contacts.length) * 100).toFixed(1)
}

// Taxa de opt-out em %
const getOptOutRate = () => {
  if (contacts.length === 0) return 0
  return ((getOptOutContacts() / contacts.length) * 100).toFixed(1)
}

// Contatos inativos (não estão opt-out mas estão inativos)
const getInactiveContacts = () => {
  return contacts.filter(c => !c.is_active && !c.opted_out).length
}
```

---

### **2. Layout Recomendado: Duas Colunas**

**Localização:** Logo após os stats atuais (após linha 281)

```tsx
{/* Indicadores Avançados */}
{contacts.length > 0 && (
  <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
    {/* Card 1: Distribuição Geográfica */}
    <Card className="p-4">
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2">
          <span className="text-lg">📍</span>
          <span className="text-sm font-semibold text-gray-700">
            Distribuição Geográfica
          </span>
        </div>
        <div className="flex items-center gap-2 text-xs">
          <span className="px-2 py-1 bg-blue-100 text-blue-700 rounded-full font-medium">
            {getUniqueStatesCount()} estados
          </span>
          {getContactsWithoutState() > 0 && (
            <span className="px-2 py-1 bg-amber-100 text-amber-700 rounded-full font-medium">
              {getContactsWithoutState()} sem UF
            </span>
          )}
        </div>
      </div>
      
      <div className="space-y-2.5">
        {getTopStates(6).map(([state, count]) => {
          const percentage = (count / contacts.length) * 100
          return (
            <div key={state}>
              <div className="flex items-center justify-between mb-1">
                <span className="text-sm font-medium text-gray-700 min-w-[60px]">
                  {state || 'Não informado'}
                </span>
                <span className="text-xs text-gray-500">
                  {count} ({percentage.toFixed(1)}%)
                </span>
              </div>
              <div className="w-full bg-gray-200 rounded-full h-2">
                <div
                  className={`h-2 rounded-full transition-all ${
                    state ? 'bg-blue-500' : 'bg-gray-400'
                  }`}
                  style={{ width: `${percentage}%` }}
                />
              </div>
            </div>
          )
        })}
      </div>
      
      {getUniqueStatesCount() > 6 && (
        <div className="mt-3 text-center text-xs text-gray-400">
          +{getUniqueStatesCount() - 6} outros estados
        </div>
      )}
    </Card>

    {/* Card 2: Status de Consentimento (Opt-in/Opt-out) */}
    <Card className="p-4">
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2">
          <span className="text-lg">✅</span>
          <span className="text-sm font-semibold text-gray-700">
            Status de Consentimento
          </span>
        </div>
        <div className="text-xs text-gray-500">
          LGPD Compliance
        </div>
      </div>

      {/* Gráfico Pizza Visual */}
      <div className="flex items-center justify-center mb-4">
        <div className="relative w-32 h-32">
          {/* Círculo base */}
          <svg className="w-32 h-32 transform -rotate-90">
            {/* Opt-out (vermelho) */}
            <circle
              cx="64"
              cy="64"
              r="56"
              fill="none"
              stroke="#FEE2E2"
              strokeWidth="16"
            />
            {/* Opt-in (verde) */}
            <circle
              cx="64"
              cy="64"
              r="56"
              fill="none"
              stroke="#10B981"
              strokeWidth="16"
              strokeDasharray={`${(getOptInRate() / 100) * 352} 352`}
              className="transition-all duration-500"
            />
          </svg>
          {/* Texto central */}
          <div className="absolute inset-0 flex flex-col items-center justify-center">
            <div className="text-2xl font-bold text-green-600">
              {getOptInRate()}%
            </div>
            <div className="text-xs text-gray-500">opt-in</div>
          </div>
        </div>
      </div>

      {/* Estatísticas detalhadas */}
      <div className="space-y-2.5">
        <div className="flex items-center justify-between p-2.5 bg-green-50 rounded-lg">
          <div className="flex items-center gap-2">
            <div className="w-3 h-3 bg-green-500 rounded-full"></div>
            <span className="text-sm font-medium text-gray-700">Opt-in (Aptos)</span>
          </div>
          <span className="text-sm font-bold text-green-600">
            {getOptInContacts()} contatos
          </span>
        </div>

        <div className="flex items-center justify-between p-2.5 bg-red-50 rounded-lg">
          <div className="flex items-center gap-2">
            <div className="w-3 h-3 bg-red-500 rounded-full"></div>
            <span className="text-sm font-medium text-gray-700">Opt-out (Bloqueados)</span>
          </div>
          <span className="text-sm font-bold text-red-600">
            {getOptOutContacts()} contatos
          </span>
        </div>

        {getInactiveContacts() > 0 && (
          <div className="flex items-center justify-between p-2.5 bg-gray-50 rounded-lg">
            <div className="flex items-center gap-2">
              <div className="w-3 h-3 bg-gray-400 rounded-full"></div>
              <span className="text-sm font-medium text-gray-700">Inativos</span>
            </div>
            <span className="text-sm font-bold text-gray-600">
              {getInactiveContacts()} contatos
            </span>
          </div>
        )}
      </div>

      {/* Alerta de campanha */}
      <div className="mt-4 p-3 bg-blue-50 border border-blue-200 rounded-lg">
        <div className="flex items-start gap-2">
          <span className="text-blue-600">📩</span>
          <div className="flex-1">
            <div className="text-xs font-medium text-blue-900 mb-0.5">
              Audiência disponível
            </div>
            <div className="text-xs text-blue-700">
              <span className="font-bold">{getOptInContacts()}</span> contatos podem 
              receber campanhas de WhatsApp
            </div>
          </div>
        </div>
      </div>
    </Card>
  </div>
)}
```

---

### **3. Versão Simplificada (Card Único)**

```tsx
{/* Indicadores Combinados - Versão Simplificada */}
{contacts.length > 0 && (
  <Card className="p-4">
    <div className="flex items-center justify-between mb-4">
      <span className="text-sm font-semibold text-gray-700">
        📊 Visão Geral da Base
      </span>
      <span className="text-xs text-gray-500">
        {contacts.length} contatos totais
      </span>
    </div>

    <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
      {/* Top Estados */}
      {getTopStates(3).map(([state, count]) => (
        <div key={state} className="text-center p-3 bg-gray-50 rounded-lg">
          <div className="text-xs text-gray-500 mb-1">📍 {state || 'N/A'}</div>
          <div className="text-lg font-bold text-gray-700">{count}</div>
        </div>
      ))}

      {/* Opt-in Status */}
      <div className="text-center p-3 bg-green-50 rounded-lg border border-green-200">
        <div className="text-xs text-green-700 mb-1">✅ Opt-in</div>
        <div className="text-lg font-bold text-green-600">
          {getOptInRate()}%
        </div>
        <div className="text-xs text-green-600 mt-0.5">
          {getOptInContacts()} aptos
        </div>
      </div>
    </div>
  </Card>
)}
```

---

## 📊 **MÉTRICAS DE OPT-IN/OUT**

### **Principais Indicadores:**

| Métrica | Descrição | Cálculo |
|---------|-----------|---------|
| **Opt-in Total** | Contatos aptos para campanhas | `!opted_out && is_active` |
| **Opt-out Total** | Contatos bloqueados (LGPD) | `opted_out === true` |
| **Taxa Opt-in** | % da base que pode receber msgs | `(opt-in / total) * 100` |
| **Taxa Opt-out** | % da base bloqueada | `(opt-out / total) * 100` |
| **Audiência Disponível** | Base real para campanhas | `opt-in count` |
| **Inativos** | Contatos não opt-out mas inativos | `!opted_out && !is_active` |

---

## 🎨 **CORES E ÍCONES**

```tsx
// Cores do tema
const STATUS_COLORS = {
  optIn: {
    bg: 'bg-green-50',
    text: 'text-green-600',
    border: 'border-green-200',
    progress: 'bg-green-500'
  },
  optOut: {
    bg: 'bg-red-50',
    text: 'text-red-600',
    border: 'border-red-200',
    progress: 'bg-red-500'
  },
  inactive: {
    bg: 'bg-gray-50',
    text: 'text-gray-600',
    border: 'border-gray-200',
    progress: 'bg-gray-400'
  }
}

// Ícones
const ICONS = {
  optIn: '✅',
  optOut: '❌',
  inactive: '⏸️',
  geography: '📍',
  campaign: '📩',
  compliance: '🛡️'
}
```

---

## 🧮 **EXEMPLO DE CÁLCULOS**

```typescript
// Cenário: 350 contatos totais
const contacts = [
  { opted_out: false, is_active: true },   // 320 desses
  { opted_out: true, is_active: false },   // 30 desses
  // ...
]

// Resultados:
getOptInContacts()    // 320
getOptOutContacts()   // 30
getOptInRate()        // "91.4"
getOptOutRate()       // "8.6"
getInactiveContacts() // 0

// Para campanhas:
// Audiência disponível = 320 contatos (só esses podem receber msgs)
```

---

## ✅ **CHECKLIST DE IMPLEMENTAÇÃO**

### **Parte 1: Funções Helper**
- [ ] `getOptInContacts()` - Conta aptos
- [ ] `getOptOutContacts()` - Conta bloqueados
- [ ] `getOptInRate()` - Calcula % opt-in
- [ ] `getOptOutRate()` - Calcula % opt-out
- [ ] `getInactiveContacts()` - Conta inativos

### **Parte 2: Layout**
- [ ] Escolher layout (2 colunas recomendado)
- [ ] Adicionar card de distribuição geográfica
- [ ] Adicionar card de status de consentimento
- [ ] Adicionar gráfico pizza visual
- [ ] Adicionar estatísticas detalhadas

### **Parte 3: Visual**
- [ ] Cores verde/vermelho para opt-in/out
- [ ] Ícones adequados (✅ ❌ 📩)
- [ ] Responsividade mobile
- [ ] Alerta de audiência disponível

### **Parte 4: Testes**
- [ ] Testar com 0 contatos
- [ ] Testar com 100% opt-in
- [ ] Testar com 100% opt-out
- [ ] Testar com mix de estados
- [ ] Verificar cálculo das porcentagens

---

## 🎯 **BENEFÍCIOS DA COMBINAÇÃO**

| Indicador | Benefício |
|-----------|-----------|
| **Geografia** | Saber onde estão os contatos |
| **Opt-in/out** | Compliance LGPD + Audiência real |
| **Combinado** | Planejar campanhas por região E saber quantos podem receber |

### **Exemplo Prático:**
```
SP tem 150 contatos
Desses, 140 são opt-in (93%)
Então posso fazer campanha em SP para 140 pessoas
```

---

## 📱 **RESPONSIVIDADE**

```tsx
// Mobile: Cards empilhados verticalmente
<div className="grid grid-cols-1 lg:grid-cols-2 gap-4">

// Desktop: 2 colunas lado a lado
// Mobile: 1 coluna, geografia em cima, opt-in embaixo
```

---

## 🚀 **PRÓXIMAS EVOLUÇÕES**

1. **Filtro Combinado:** Clicar em "SP + Opt-in" mostra só esses
2. **Trend:** Mostrar evolução de opt-out ao longo do tempo
3. **Alerta:** Avisar se taxa de opt-out subir muito
4. **Export Segmentado:** Exportar "SP + Opt-in" direto
5. **Mapa Visual:** SVG do Brasil colorido por densidade

---

## 📚 **REFERÊNCIAS**

- **Arquivo:** `frontend/src/pages/ContactsPage.tsx`
- **Linha de inserção:** Após linha 281 (após stats atuais)
- **Interface Contact:** Já tem campos `opted_out` e `is_active`
- **LGPD:** Opt-out é obrigatório por lei no Brasil

---

## 🎨 **PREVIEW VISUAL ASCII**

```
╔══════════════════════════════════════════════════════════╗
║  📊 INDICADORES AVANÇADOS                                ║
╠════════════════════════════╦═════════════════════════════╣
║ 📍 GEOGRAFIA               ║ ✅ CONSENTIMENTO            ║
║ ──────────────────────     ║ ──────────────────────      ║
║ 3 estados | 2 sem UF       ║ LGPD Compliance             ║
║                            ║                             ║
║ SP    150 (45%) ████████░  ║      ┌─────────┐            ║
║ RJ    100 (30%) █████░░░░  ║      │  91.4%  │ 🎯         ║
║ MG     50 (15%) ██░░░░░░░  ║      │  opt-in │            ║
║ N/A    30 (9%)  █░░░░░░░░  ║      └─────────┘            ║
║                            ║                             ║
║                            ║ ✅ Opt-in:  320 contatos    ║
║                            ║ ❌ Opt-out:  30 contatos    ║
║                            ║                             ║
║                            ║ 📩 320 aptos p/ campanhas   ║
╚════════════════════════════╩═════════════════════════════╝
```

---

**✅ PROMPT COMPLETO - INDICADORES COMBINADOS PRONTOS!**



