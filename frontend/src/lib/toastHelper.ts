/**
 * Helper centralizado para toasts padronizados em todo o projeto
 * 
 * Uso:
 * - showSuccessToast('criar', 'Cliente')
 * - showErrorToast('atualizar', 'Produto', error)
 */

import { toast } from 'sonner'
import { ApiErrorHandler } from './apiErrorHandler'

type Action = 'criar' | 'atualizar' | 'excluir' | 'salvar' | 'carregar' | 'importar' | 'exportar' | 'conectar' | 'desconectar' | 'testar' | 'buscar' | 'iniciar' | 'pausar' | 'retomar' | 'cancelar' | 'duplicar' | 'validar'
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
    validar: `✅ ${entity} validado com sucesso!`,
  }

  toast.success(messages[action] || `✅ ${action} realizado com sucesso!`)
}

const baseMessagesForError: Record<Action, string> = {
  criar: 'Erro ao criar',
  atualizar: 'Erro ao atualizar',
  salvar: 'Erro ao salvar',
  excluir: 'Erro ao excluir',
  carregar: 'Erro ao carregar',
  importar: 'Erro ao importar',
  exportar: 'Erro ao exportar',
  conectar: 'Erro ao conectar',
  desconectar: 'Erro ao desconectar',
  testar: 'Erro ao testar',
  buscar: 'Erro ao buscar',
  iniciar: 'Erro ao iniciar',
  pausar: 'Erro ao pausar',
  retomar: 'Erro ao retomar',
  cancelar: 'Erro ao cancelar',
  duplicar: 'Erro ao duplicar',
  validar: 'Erro ao validar',
}

/**
 * Toast de erro padronizado com extração de mensagem do erro.
 * Suporta: showErrorToast(msg), showErrorToast(action, entity), showErrorToast(action, entity, error).
 */
export function showErrorToast(action: Action, entity?: Entity, error?: any) {
  // Chamada com uma única string (mensagem simples): showErrorToast('Erro ao carregar...')
  if (arguments.length === 1 && typeof action === 'string') {
    toast.error(`❌ ${action}`)
    return
  }
  // Chamada com (action, mensagem): showErrorToast('Erro ao buscar Templates', error.response?.data?.message)
  if (arguments.length === 2 && typeof entity === 'string' && entity) {
    const baseMsg = (baseMessagesForError as Record<string, string>)[action as string] ?? action
    toast.error(`❌ ${baseMsg}: ${entity}`)
    return
  }
  let errorMessage =
    error != null && (error?.response != null || error?.message != null || typeof error === 'string')
      ? typeof error === 'string'
        ? error
        : ApiErrorHandler.extractMessage(error)
      : ''
  const baseMessage = (baseMessagesForError[action as Action] ?? `Erro ao ${action}`) + (entity ? ` ${entity}` : '')
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
  // Chamada com (toastId, action, mensagem) quando action não é um Action padrão: updateToastError(toastId, 'Erro ao criar Template', msg)
  if (arguments.length === 3 && typeof entity === 'string' && entity !== undefined && !(action in baseMessagesForError)) {
    toast.error(`❌ ${action}: ${entity}`, { id: toastId })
    return
  }
  const errorMessage =
    error != null && (error?.response != null || error?.message != null || typeof error === 'string')
      ? typeof error === 'string'
        ? error
        : ApiErrorHandler.extractMessage(error)
      : ''
  const baseMessage = (baseMessagesForError[action as Action] ?? action) + (entity ? ` ${entity}` : '')
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


