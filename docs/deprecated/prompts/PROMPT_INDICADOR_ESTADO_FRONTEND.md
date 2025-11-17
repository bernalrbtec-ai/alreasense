# 🗺️ PROMPT: Indicador de Estados x Contatos no Frontend

## 🎯 **OBJETIVO**

Adicionar um indicador visual simples mas funcional na página de contatos (`ContactsPage.tsx`) que mostre a distribuição de contatos por estado (UF).

## 📍 **LOCALIZAÇÃO ATUAL**

**Arquivo:** `frontend/src/pages/ContactsPage.tsx`

**Seção de Stats (linhas 257-281):**
```tsx
{/* Stats */}
<div className="grid grid-cols-1 md:grid-cols-4 gap-4">
  <Card className="p-4">
    <div className="text-sm text-gray-500">Total de Contatos</div>
    <div className="text-2xl font-bold">{contacts.length}</div>
  </Card>
  <Card className="p-4">
    <div className="text-sm text-gray-500">Leads</div>
    <div className="text-2xl font-bold text-blue-600">
      {contacts.filter(c => c.lifecycle_stage === 'lead').length}
    </div>
  </Card>
  <Card className="p-4">
    <div className="text-sm text-gray-500">Clientes</div>
    <div className="text-2xl font-bold text-green-600">
      {contacts.filter(c => c.lifecycle_stage === 'customer').length}
    </div>
  </Card>
  <Card className="p-4">
    <div className="text-sm text-gray-500">Opt-out</div>
    <div className="text-2xl font-bold text-red-600">
      {contacts.filter(c => c.opted_out).length}
    </div>
  </Card>
</div>
```

---

## 💡 **SOLUÇÃO PROPOSTA: Card com Top Estados**

Adicionar um **5º card** ou uma **nova linha** logo abaixo dos stats atuais, mostrando a distribuição por estado.

### **Opção 1: Card Simples (Recomendado - Mais Rápido)**

Um card adicional mostrando os **top 5 estados** com mais contatos:

```tsx
<Card className="p-4">
  <div className="flex items-center justify-between mb-2">
    <div className="text-sm text-gray-500">Por Estado</div>
    <div className="text-xs text-gray-400">Top 5</div>
  </div>
  <div className="space-y-1">
    {getTopStates(5).map(([state, count]) => (
      <div key={state} className="flex items-center justify-between text-sm">
        <span className="font-medium text-gray-700">{state || 'Não informado'}</span>
        <span className="text-gray-500">{count}</span>
      </div>
    ))}
  </div>
</Card>
```

### **Opção 2: Card com Mini Barras (Mais Visual)**

Um card com barras horizontais mostrando a proporção:

```tsx
<Card className="p-4 md:col-span-2">
  <div className="flex items-center justify-between mb-3">
    <div className="text-sm font-medium text-gray-700">Distribuição por Estado</div>
    <div className="text-xs text-gray-400">{getUniqueStatesCount()} estados</div>
  </div>
  <div className="space-y-2">
    {getTopStates(5).map(([state, count]) => {
      const percentage = (count / contacts.length) * 100
      return (
        <div key={state} className="space-y-1">
          <div className="flex items-center justify-between text-sm">
            <span className="font-medium text-gray-700 min-w-[40px]">
              {state || 'N/A'}
            </span>
            <span className="text-gray-500 text-xs">
              {count} ({percentage.toFixed(0)}%)
            </span>
          </div>
          <div className="w-full bg-gray-200 rounded-full h-1.5">
            <div
              className="bg-blue-500 h-1.5 rounded-full transition-all"
              style={{ width: `${percentage}%` }}
            />
          </div>
        </div>
      )
    })}
  </div>
</Card>
```

---

## 📝 **IMPLEMENTAÇÃO COMPLETA**

### **1. Adicionar função helper no componente**

**Localização:** Dentro do componente `ContactsPage`, logo após os `useEffect`

```tsx
// Função para calcular distribuição por estado
const getTopStates = (limit: number = 5): [string, number][] => {
  const stateCounts = contacts.reduce((acc, contact) => {
    const state = contact.state || ''
    acc[state] = (acc[state] || 0) + 1
    return acc
  }, {} as Record<string, number>)

  return Object.entries(stateCounts)
    .sort(([, a], [, b]) => b - a)
    .slice(0, limit)
}

// Função para contar estados únicos
const getUniqueStatesCount = (): number => {
  const states = new Set(contacts.map(c => c.state).filter(Boolean))
  return states.size
}

// Função para obter total de contatos sem estado
const getContactsWithoutState = (): number => {
  return contacts.filter(c => !c.state || c.state.trim() === '').length
}
```

---

### **2. Modificar o grid de stats**

#### **Opção 2.1: Adicionar card na mesma linha (grid-cols-5)**

```tsx
{/* Stats */}
<div className="grid grid-cols-1 md:grid-cols-5 gap-4">
  {/* Cards existentes... */}
  <Card className="p-4">
    <div className="text-sm text-gray-500">Total de Contatos</div>
    <div className="text-2xl font-bold">{contacts.length}</div>
  </Card>
  <Card className="p-4">
    <div className="text-sm text-gray-500">Leads</div>
    <div className="text-2xl font-bold text-blue-600">
      {contacts.filter(c => c.lifecycle_stage === 'lead').length}
    </div>
  </Card>
  <Card className="p-4">
    <div className="text-sm text-gray-500">Clientes</div>
    <div className="text-2xl font-bold text-green-600">
      {contacts.filter(c => c.lifecycle_stage === 'customer').length}
    </div>
  </Card>
  <Card className="p-4">
    <div className="text-sm text-gray-500">Opt-out</div>
    <div className="text-2xl font-bold text-red-600">
      {contacts.filter(c => c.opted_out).length}
    </div>
  </Card>
  
  {/* 🆕 NOVO: Card de distribuição por estado */}
  <Card className="p-4">
    <div className="flex items-center justify-between mb-2">
      <div className="text-sm text-gray-500">Por Estado</div>
      <div className="text-xs text-gray-400">{getUniqueStatesCount()} UFs</div>
    </div>
    <div className="space-y-1 max-h-20 overflow-y-auto">
      {getTopStates(5).map(([state, count]) => (
        <div key={state} className="flex items-center justify-between text-xs">
          <span className="font-medium text-gray-700">
            {state || '∅'}
          </span>
          <span className="text-gray-500">{count}</span>
        </div>
      ))}
    </div>
  </Card>
</div>
```

#### **Opção 2.2: Adicionar nova linha abaixo (Recomendado)**

```tsx
{/* Stats - Linha 1 */}
<div className="grid grid-cols-1 md:grid-cols-4 gap-4">
  {/* ... cards existentes ... */}
</div>

{/* 🆕 NOVO: Stats - Linha 2 - Distribuição Geográfica */}
<Card className="p-4">
  <div className="flex items-center justify-between mb-3">
    <div className="flex items-center gap-2">
      <span className="text-sm font-medium text-gray-700">📍 Distribuição por Estado</span>
    </div>
    <div className="flex items-center gap-3 text-xs text-gray-500">
      <span>{getUniqueStatesCount()} estados</span>
      {getContactsWithoutState() > 0 && (
        <span className="text-amber-600">
          {getContactsWithoutState()} sem UF
        </span>
      )}
    </div>
  </div>
  
  <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
    {getTopStates(10).map(([state, count]) => {
      const percentage = (count / contacts.length) * 100
      return (
        <div key={state} className="text-center p-2 bg-gray-50 rounded-lg hover:bg-gray-100 transition-colors">
          <div className="text-lg font-bold text-blue-600">
            {state || '∅'}
          </div>
          <div className="text-xs text-gray-500">
            {count} ({percentage.toFixed(0)}%)
          </div>
        </div>
      )
    })}
  </div>
  
  {getTopStates(10).length === 0 && (
    <div className="text-center py-4 text-sm text-gray-400">
      Nenhum contato com estado cadastrado
    </div>
  )}
</Card>
```

---

### **3. Versão Completa Recomendada (com barra)**

```tsx
{/* Stats - Linha 1 */}
<div className="grid grid-cols-1 md:grid-cols-4 gap-4">
  {/* ... cards existentes ... */}
</div>

{/* 🆕 NOVO: Distribuição Geográfica */}
{contacts.length > 0 && (
  <Card className="p-4">
    <div className="flex items-center justify-between mb-4">
      <div className="flex items-center gap-2">
        <span className="text-sm font-medium text-gray-700">📍 Distribuição Geográfica</span>
      </div>
      <div className="flex items-center gap-3 text-xs">
        <span className="text-gray-500">{getUniqueStatesCount()} estados</span>
        {getContactsWithoutState() > 0 && (
          <span className="px-2 py-0.5 bg-amber-100 text-amber-700 rounded-full">
            {getContactsWithoutState()} sem UF
          </span>
        )}
      </div>
    </div>
    
    <div className="space-y-3">
      {getTopStates(8).map(([state, count]) => {
        const percentage = (count / contacts.length) * 100
        return (
          <div key={state}>
            <div className="flex items-center justify-between mb-1">
              <span className="text-sm font-medium text-gray-700 min-w-[50px]">
                {state || 'Não informado'}
              </span>
              <span className="text-xs text-gray-500">
                {count} contatos ({percentage.toFixed(1)}%)
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
    
    {getTopStates(8).length > 8 && (
      <div className="mt-3 text-center text-xs text-gray-400">
        +{getUniqueStatesCount() - 8} outros estados
      </div>
    )}
  </Card>
)}
```

---

## ✅ **CHECKLIST DE IMPLEMENTAÇÃO**

### **Passo 1: Adicionar funções helper**
- [ ] Adicionar `getTopStates(limit)` no componente
- [ ] Adicionar `getUniqueStatesCount()` no componente
- [ ] Adicionar `getContactsWithoutState()` no componente

### **Passo 2: Escolher e implementar layout**
- [ ] **Opção A:** Card adicional na mesma linha (grid-cols-5)
- [ ] **Opção B:** Nova linha completa abaixo dos stats (Recomendado ✅)
- [ ] **Opção C:** Card com barras horizontais (Mais visual)

### **Passo 3: Testar**
- [ ] Verificar com 0 contatos
- [ ] Verificar com contatos sem estado
- [ ] Verificar com múltiplos estados
- [ ] Verificar responsividade mobile
- [ ] Verificar overflow com muitos estados

---

## 🎨 **VARIAÇÕES DE DESIGN**

### **Variação 1: Chips/Tags horizontais**
```tsx
<div className="flex flex-wrap gap-2">
  {getTopStates(10).map(([state, count]) => (
    <div
      key={state}
      className="px-3 py-1.5 bg-blue-100 text-blue-700 rounded-full text-sm font-medium"
    >
      {state || '∅'} • {count}
    </div>
  ))}
</div>
```

### **Variação 2: Tabela simples**
```tsx
<div className="overflow-x-auto">
  <table className="w-full text-sm">
    <thead>
      <tr className="border-b">
        <th className="text-left py-2">Estado</th>
        <th className="text-right py-2">Contatos</th>
        <th className="text-right py-2">%</th>
      </tr>
    </thead>
    <tbody>
      {getTopStates(10).map(([state, count]) => (
        <tr key={state} className="border-b hover:bg-gray-50">
          <td className="py-2 font-medium">{state || 'N/A'}</td>
          <td className="text-right">{count}</td>
          <td className="text-right text-gray-500">
            {((count / contacts.length) * 100).toFixed(0)}%
          </td>
        </tr>
      ))}
    </tbody>
  </table>
</div>
```

---

## 🧪 **EXEMPLO DE RESULTADO VISUAL**

```
┌─────────────────────────────────────────────────────────┐
│ 📍 Distribuição Geográfica        3 estados  2 sem UF  │
├─────────────────────────────────────────────────────────┤
│ SP                               150 contatos (45.5%)   │
│ ████████████████████████████████████████████░░░░░░░░░░ │
│                                                         │
│ RJ                               100 contatos (30.3%)   │
│ ██████████████████████████████░░░░░░░░░░░░░░░░░░░░░░░ │
│                                                         │
│ MG                                50 contatos (15.2%)   │
│ ███████████████░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░ │
│                                                         │
│ Não informado                     30 contatos (9.1%)    │
│ █████████░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░ │
└─────────────────────────────────────────────────────────┘
```

---

## 🎯 **RECOMENDAÇÃO FINAL**

**Use a Opção 2.2 (Nova linha com barras)** porque:
- ✅ Não quebra o layout atual (mantém grid-cols-4)
- ✅ Mais espaço para mostrar dados
- ✅ Visual atraente com barras de progresso
- ✅ Fácil de escanear visualmente
- ✅ Mostra até 8 estados sem poluir
- ✅ Destaca contatos sem estado

---

## 📚 **REFERÊNCIAS**

- **Arquivo:** `frontend/src/pages/ContactsPage.tsx`
- **Linha de inserção:** Entre linha 281 e 283 (após stats, antes do grid de contatos)
- **Componentes usados:** `Card` (já importado)
- **Estados do Brasil:** AC, AL, AP, AM, BA, CE, DF, ES, GO, MA, MT, MS, MG, PA, PB, PR, PE, PI, RJ, RN, RS, RO, RR, SC, SP, SE, TO

---

## 🚀 **PRÓXIMOS PASSOS OPCIONAIS**

1. **Adicionar filtro por estado:** Clicar no estado filtra a lista
2. **Tooltip com cidades:** Hover mostra cidades daquele estado
3. **Mapa do Brasil:** Versão visual com mapa SVG
4. **Export por estado:** Botão para exportar CSV de um estado específico

---

**✅ PROMPT COMPLETO - PRONTO PARA IMPLEMENTAR**




