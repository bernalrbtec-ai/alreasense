/**
 * Helper centralizado para toasts padronizados em todo o projeto
 * 
 * Uso:
 * - showSuccessToast('criar', 'Cliente')
 * - showErrorToast('atualizar', 'Produto', error)
 */

import { toast } from 'sonner'

type Action = 'criar' | 'atualizar' | 'excluir' | 'salvar' | 'carregar' | 'importar' | 'exportar' | 'conectar' | 'desconectar' | 'testar' | 'buscar' | 'iniciar' | 'pausar' | 'retomar' | 'cancelar' | 'duplicar'
type Entity = string // 'Cliente', 'Produto', 'Contato', 'Instância', etc

/**
 * Toast de sucesso padronizado
 */
export function showSuccessToast(action: Action, entity: Entity) {
  const messages: Record<Action, string> = {
    criar: `✅ ${entity} criado com sucesso!`,
    atualizar: `✅ ${entity} atualizado com sucesso!`,
    salvar: `✅ ${entity} salvo com sucesso!`,
    excluir: `✅ ${entity} excluído com sucesso!`,
    carregar: `✅ ${entity} carregado com sucesso!`,
    importar: `✅ ${entity} importado com sucesso!`,
    exportar: `✅ ${entity} exportado com sucesso!`,
    conectar: `✅ ${entity} conectado com sucesso!`,
    desconectar: `✅ ${entity} desconectado com sucesso!`,
    testar: `✅ Teste de ${entity} realizado com sucesso!`,
    buscar: `✅ ${entity} encontrado com sucesso!`,
    iniciar: `✅ ${entity} iniciado com sucesso!`,
    pausar: `✅ ${entity} pausado com sucesso!`,
    retomar: `✅ ${entity} retomado com sucesso!`,
    cancelar: `✅ ${entity} cancelado com sucesso!`,
    duplicar: `✅ ${entity} duplicado com sucesso!`,
  }

  toast.success(messages[action] || `✅ ${action} realizado com sucesso!`)
}

/**
 * Toast de erro padronizado com extração de mensagem do erro
 */
export function showErrorToast(action: Action, entity: Entity, error?: any) {
  // Log detalhado para debug
  console.log(`🚨 showErrorToast chamado:`, { action, entity, error })
  
  // Extrair mensagem do erro
  let errorMessage = ''
  
  if (error?.response?.data) {
    const data = error.response.data
    console.log(`📋 Dados de resposta do erro:`, data)
    
    // Tentar extrair mensagens específicas
    if (typeof data === 'string') {
      errorMessage = data
    } else if (data.detail) {
      errorMessage = Array.isArray(data.detail) ? data.detail[0] : data.detail
    } else if (data.message) {
      errorMessage = Array.isArray(data.message) ? data.message[0] : data.message
    } else if (data.error) {
      errorMessage = Array.isArray(data.error) ? data.error[0] : data.error
    } else if (data.phone) {
      errorMessage = Array.isArray(data.phone) ? data.phone[0] : data.phone
    } else if (data.email) {
      errorMessage = Array.isArray(data.email) ? data.email[0] : data.email
    } else if (data.name) {
      errorMessage = Array.isArray(data.name) ? data.name[0] : data.name
    } else if (data.non_field_errors) {
      errorMessage = Array.isArray(data.non_field_errors) ? data.non_field_errors[0] : data.non_field_errors
    } else {
      // Pegar primeiro erro encontrado
      const firstKey = Object.keys(data)[0]
      if (firstKey && data[firstKey]) {
        const value = data[firstKey]
        errorMessage = Array.isArray(value) ? value[0] : value
      }
    }
  } else if (error?.message) {
    errorMessage = error.message
  } else if (error?.toString) {
    errorMessage = error.toString()
  }
  
  console.log(`📝 Mensagem extraída:`, errorMessage)
  
  // Fallback se ainda estiver vazio
  // ✅ CORREÇÃO: Garantir que errorMessage seja string antes de chamar trim()
  if (!errorMessage || (typeof errorMessage === 'string' && errorMessage.trim() === '') || typeof errorMessage !== 'string') {
    errorMessage = 'Erro desconhecido'
    console.warn(`⚠️ Usando fallback "Erro desconhecido" para:`, { action, entity, error })
  } else {
    errorMessage = String(errorMessage).trim()
  }

  const baseMessages: Record<Action, string> = {
    criar: `Erro ao criar ${entity}`,
    atualizar: `Erro ao atualizar ${entity}`,
    salvar: `Erro ao salvar ${entity}`,
    excluir: `Erro ao excluir ${entity}`,
    carregar: `Erro ao carregar ${entity}`,
    importar: `Erro ao importar ${entity}`,
    exportar: `Erro ao exportar ${entity}`,
    conectar: `Erro ao conectar ${entity}`,
    desconectar: `Erro ao desconectar ${entity}`,
    testar: `Erro ao testar ${entity}`,
    buscar: `Erro ao buscar ${entity}`,
    iniciar: `Erro ao iniciar ${entity}`,
    pausar: `Erro ao pausar ${entity}`,
    retomar: `Erro ao retomar ${entity}`,
    cancelar: `Erro ao cancelar ${entity}`,
    duplicar: `Erro ao duplicar ${entity}`,
  }

  const baseMessage = baseMessages[action] || `Erro ao ${action} ${entity}`
  const fullMessage = errorMessage ? `❌ ${baseMessage}: ${errorMessage}` : `❌ ${baseMessage}`

  toast.error(fullMessage)
}

/**
 * Toast de loading para operações longas
 */
export function showLoadingToast(action: Action, entity: Entity): string | number {
  const messages: Record<Action, string> = {
    criar: `Criando ${entity}...`,
    atualizar: `Atualizando ${entity}...`,
    salvar: `Salvando ${entity}...`,
    excluir: `Excluindo ${entity}...`,
    carregar: `Carregando ${entity}...`,
    importar: `Importando ${entity}...`,
    exportar: `Exportando ${entity}...`,
    conectar: `Conectando ${entity}...`,
    desconectar: `Desconectando ${entity}...`,
    testar: `Testando ${entity}...`,
    buscar: `Buscando ${entity}...`,
    iniciar: `Iniciando ${entity}...`,
    pausar: `Pausando ${entity}...`,
    retomar: `Retomando ${entity}...`,
    cancelar: `Cancelando ${entity}...`,
    duplicar: `Duplicando ${entity}...`,
  }

  return toast.loading(messages[action] || `Processando ${entity}...`)
}

/**
 * Atualizar toast de loading para sucesso
 */
export function updateToastSuccess(toastId: string | number, action: Action, entity: Entity) {
  const messages: Record<Action, string> = {
    criar: `✅ ${entity} criado com sucesso!`,
    atualizar: `✅ ${entity} atualizado com sucesso!`,
    salvar: `✅ ${entity} salvo com sucesso!`,
    excluir: `✅ ${entity} excluído com sucesso!`,
    carregar: `✅ ${entity} carregado com sucesso!`,
    importar: `✅ ${entity} importado com sucesso!`,
    exportar: `✅ ${entity} exportado com sucesso!`,
    conectar: `✅ ${entity} conectado com sucesso!`,
    desconectar: `✅ ${entity} desconectado com sucesso!`,
    testar: `✅ Teste de ${entity} realizado com sucesso!`,
    buscar: `✅ ${entity} encontrado com sucesso!`,
    iniciar: `✅ ${entity} iniciado com sucesso!`,
    pausar: `✅ ${entity} pausado com sucesso!`,
    retomar: `✅ ${entity} retomado com sucesso!`,
    cancelar: `✅ ${entity} cancelado com sucesso!`,
    duplicar: `✅ ${entity} duplicado com sucesso!`,
  }

  toast.success(messages[action], { id: toastId })
}

/**
 * Atualizar toast de loading para erro
 */
export function updateToastError(toastId: string | number, action: Action, entity: Entity, error?: any) {
  // Extrair mensagem do erro (mesmo código de showErrorToast)
  let errorMessage = ''
  
  if (error?.response?.data) {
    const data = error.response.data
    
    // Tentar extrair mensagens específicas
    if (typeof data === 'string') {
      errorMessage = data
    } else if (data.detail) {
      errorMessage = Array.isArray(data.detail) ? data.detail[0] : data.detail
    } else if (data.message) {
      errorMessage = Array.isArray(data.message) ? data.message[0] : data.message
    } else if (data.error) {
      errorMessage = Array.isArray(data.error) ? data.error[0] : data.error
    } else if (data.phone) {
      errorMessage = Array.isArray(data.phone) ? data.phone[0] : data.phone
    } else if (data.email) {
      errorMessage = Array.isArray(data.email) ? data.email[0] : data.email
    } else if (data.name) {
      errorMessage = Array.isArray(data.name) ? data.name[0] : data.name
    } else if (data.non_field_errors) {
      errorMessage = Array.isArray(data.non_field_errors) ? data.non_field_errors[0] : data.non_field_errors
    } else {
      // Pegar primeiro erro encontrado
      const firstKey = Object.keys(data)[0]
      if (firstKey && data[firstKey]) {
        const value = data[firstKey]
        errorMessage = Array.isArray(value) ? value[0] : value
      }
    }
  } else if (error?.message) {
    errorMessage = error.message
  } else if (error?.toString) {
    errorMessage = error.toString()
  }
  
  // Fallback se ainda estiver vazio
  // ✅ CORREÇÃO: Garantir que errorMessage seja string antes de chamar trim()
  if (!errorMessage || (typeof errorMessage === 'string' && errorMessage.trim() === '') || typeof errorMessage !== 'string') {
    errorMessage = 'Erro desconhecido'
  } else {
    errorMessage = String(errorMessage).trim()
  }

  const baseMessages: Record<Action, string> = {
    criar: `Erro ao criar ${entity}`,
    atualizar: `Erro ao atualizar ${entity}`,
    salvar: `Erro ao salvar ${entity}`,
    excluir: `Erro ao excluir ${entity}`,
    carregar: `Erro ao carregar ${entity}`,
    importar: `Erro ao importar ${entity}`,
    exportar: `Erro ao exportar ${entity}`,
    conectar: `Erro ao conectar ${entity}`,
    desconectar: `Erro ao desconectar ${entity}`,
    testar: `Erro ao testar ${entity}`,
    buscar: `Erro ao buscar ${entity}`,
    iniciar: `Erro ao iniciar ${entity}`,
    pausar: `Erro ao pausar ${entity}`,
    retomar: `Erro ao retomar ${entity}`,
    cancelar: `Erro ao cancelar ${entity}`,
    duplicar: `Erro ao duplicar ${entity}`,
  }

  const baseMessage = baseMessages[action]
  const fullMessage = errorMessage ? `❌ ${baseMessage}: ${errorMessage}` : `❌ ${baseMessage}`

  toast.error(fullMessage, { id: toastId })
}

/**
 * Toast de informação
 */
export function showInfoToast(message: string) {
  toast.info(message)
}

/**
 * Toast de aviso
 */
export function showWarningToast(message: string) {
  toast.warning(message)
}


