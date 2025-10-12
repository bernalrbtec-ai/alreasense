# 📋 Correções Pendentes - WhatsApp

> **Problemas reportados pelo usuário:**
> 1. QR Code modal não fecha após conectar
> 2. Status não atualiza em tempo real
> 3. Limite não desconta após criar instância

---

## ✅ JÁ IMPLEMENTADO

### 1. Polling de Conexão
```typescript
// frontend/src/pages/ConfigurationsPage.tsx

const startConnectionPolling = (instanceId: string) => {
  const intervalId = setInterval(async () => {
    const response = await api.post(`/.../${instanceId}/check_status/`)
    
    // Atualiza lista em tempo real
    fetchInstances()
    
    // Se conectou, fecha modal
    if (response.data.connection_state === 'open') {
      stopConnectionPolling()
      setQrCodeInstance(null)  // Fecha modal
      showSuccessToast('conectar', 'WhatsApp')
      limits?.refetch()  // Atualiza limites
    }
  }, 3000)
}
```

### 2. Atualização de Limites
```typescript
// Após criar instância
await Promise.all([
  fetchInstances(),
  limits?.refetch()  // Atualiza contador
])
```

### 3. Logs de Debug
- Console mostra cada verificação de status
- Fácil identificar se polling está rodando

---

## 🧪 TESTE NECESSÁRIO

### Fluxo Completo:
1. Cliente acessa `/configurations`
2. Clica "Nova Instância"
3. Preenche "WhatsApp Vendas"
4. Clica "Criar"
5. **Verifica:**
   - ✅ Toast: "Criando..." → "✅ Criado!"
   - ✅ Limite atualiza (ex: 0/3 → 1/3)
6. Clica botão "QR Code" na instância
7. **Verifica:**
   - ✅ Toast: "Criando QR Code..." → "✅ QR Code criado!"
   - ✅ Modal abre com QR Code
   - ✅ Console mostra: "🔄 Iniciando polling..."
8. Escaneia QR Code no WhatsApp
9. **Verifica:**
   - ✅ Console mostra: "⏱️ Verificando..." a cada 3s
   - ✅ Status muda: Desconectado → Conectando
   - ✅ Lista atualiza mostrando "Conectando"
10. Quando conecta:
    - ✅ Console: "✅ WhatsApp conectado!"
    - ✅ Modal fecha automaticamente
    - ✅ Toast: "✅ WhatsApp conectado com sucesso!"
    - ✅ Status muda para "Conectado"
    - ✅ Telefone aparece

---

## 🔍 DEBUG

### Se polling não funcionar:
1. Abrir console do navegador (F12)
2. Verificar se aparece: "🔄 Iniciando polling..."
3. Verificar se aparece: "⏱️ Verificando..." a cada 3s
4. Verificar se há erros de API

### Se modal não fechar:
1. Verificar console: deve aparecer "✅ WhatsApp conectado!"
2. Verificar se `connection_state === 'open'` no response
3. Verificar se `setQrCodeInstance(null)` está sendo chamado

### Se limite não atualizar:
1. Verificar se `limits?.refetch()` está sendo chamado
2. Verificar endpoint `/tenants/tenants/limits/` no Network
3. Verificar se backend está contando corretamente

---

## 📊 ESTADO ATUAL

- ✅ Polling implementado
- ✅ Logs de debug adicionados
- ✅ Atualização de limites implementada
- ✅ Modal com lógica de fechamento
- ⏳ **AGUARDANDO TESTE MANUAL**

---

**Aguardando feedback do teste para validar se está 100% funcional!**


