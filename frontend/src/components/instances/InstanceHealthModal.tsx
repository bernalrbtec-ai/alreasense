import { useEffect, useRef } from 'react'
import { X, Send, CheckCircle, Eye, AlertCircle } from 'lucide-react'
import { formatDate } from '../../lib/utils'

const INTEGRATION_META_CLOUD = 'meta_cloud'

function healthStatusLabel(score: number): string {
  if (score >= 95) return 'Excelente'
  if (score >= 80) return 'Boa'
  if (score >= 50) return 'Atenção'
  return 'Crítica'
}

export interface InstanceHealthData {
  id: string
  friendly_name: string
  integration_type?: string
  connection_state?: string
  health_score?: number | null
  msgs_sent_today?: number | null
  msgs_delivered_today?: number | null
  msgs_read_today?: number | null
  msgs_failed_today?: number | null
  consecutive_errors?: number | null
  last_success_at?: string | null
}

interface InstanceHealthModalProps {
  open: boolean
  onClose: () => void
  instance: InstanceHealthData | null
}

function healthScoreColor(score: number) {
  if (score >= 95) return 'text-emerald-600 dark:text-emerald-400'
  if (score >= 80) return 'text-green-600 dark:text-green-400'
  if (score >= 50) return 'text-amber-600 dark:text-amber-400'
  return 'text-red-600 dark:text-red-400'
}

function healthScoreBg(score: number) {
  if (score >= 95) return 'bg-emerald-500'
  if (score >= 80) return 'bg-green-500'
  if (score >= 50) return 'bg-amber-500'
  return 'bg-red-500'
}

function safeFormatDate(value: string | null | undefined): string | null {
  if (value == null || value === '') return null
  try {
    const d = new Date(value)
    if (Number.isNaN(d.getTime())) return null
    return formatDate(d)
  } catch {
    return null
  }
}

export function InstanceHealthModal({ open, onClose, instance }: InstanceHealthModalProps) {
  if (!open) return null
  if (!instance) return null

  const isMeta = instance.integration_type === INTEGRATION_META_CLOUD
  const connectionState = (instance.connection_state || '').toLowerCase()
  const score = Math.min(100, Math.max(0, Number(instance.health_score ?? 100) || 0))
  const sent = Math.max(0, Number(instance.msgs_sent_today ?? 0) || 0)
  const delivered = Math.max(0, Number(instance.msgs_delivered_today ?? 0) || 0)
  const read = Math.max(0, Number(instance.msgs_read_today ?? 0) || 0)
  const failed = Math.max(0, Number(instance.msgs_failed_today ?? 0) || 0)
  const consecutiveErrors = Math.max(0, Number(instance.consecutive_errors ?? 0) || 0)
  const lastSuccessFormatted = safeFormatDate(instance.last_success_at)
  const deliveryRate = sent > 0 ? Math.round((delivered / sent) * 100) : 100
  const readRate = delivered > 0 ? Math.round((read / delivered) * 100) : 0

  const connectionLabel = connectionState === 'open' ? 'Conectado' : connectionState === 'connecting' ? 'Conectando' : 'Desconectado'
  const connectionColor = connectionState === 'open' ? 'bg-emerald-500' : connectionState === 'connecting' ? 'bg-amber-500' : 'bg-red-500'
  const closeButtonRef = useRef<HTMLButtonElement>(null)
  const onCloseRef = useRef(onClose)
  onCloseRef.current = onClose

  useEffect(() => {
    if (!open) return
    closeButtonRef.current?.focus()
  }, [open])

  useEffect(() => {
    if (!open) return
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onCloseRef.current()
    }
    window.addEventListener('keydown', onKeyDown)
    return () => window.removeEventListener('keydown', onKeyDown)
  }, [open])

  return (
    <div
      className="fixed inset-0 bg-black/50 dark:bg-black/60 flex items-center justify-center z-50 p-4"
      onClick={onClose}
      role="dialog"
      aria-modal="true"
      aria-labelledby="instance-health-modal-title"
    >
      <div
        className="bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100 rounded-xl shadow-xl w-full max-w-md overflow-hidden"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between gap-3 p-4 border-b border-gray-200 dark:border-gray-700">
          <div className="flex items-center gap-2 min-w-0 flex-1">
            <span
              className={`flex-shrink-0 w-3 h-3 rounded-full ${isMeta ? (score >= 80 ? 'bg-emerald-500' : score >= 50 ? 'bg-amber-500' : 'bg-red-500') : connectionColor}`}
              title={isMeta ? `Saúde ${score}%` : connectionLabel}
            />
            <div className="min-w-0">
              <h2 id="instance-health-modal-title" className="text-lg font-semibold truncate">
                Indicadores de saúde
              </h2>
              {instance.friendly_name && (
                <p className="text-sm text-gray-500 dark:text-gray-400 truncate" title={instance.friendly_name}>
                  {instance.friendly_name}
                </p>
              )}
            </div>
          </div>
          {isMeta && (
            <span className="flex-shrink-0 inline-flex items-center px-2.5 py-1 rounded-full text-xs font-medium bg-indigo-100 dark:bg-indigo-900/50 text-indigo-800 dark:text-indigo-200 border border-indigo-200 dark:border-indigo-800">
              API Meta
            </span>
          )}
          <button
            ref={closeButtonRef}
            type="button"
            onClick={onClose}
            className="p-2 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-700 text-gray-500 dark:text-gray-400 flex-shrink-0 ml-2 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-ring dark:focus:ring-offset-gray-800"
            aria-label="Fechar"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        <div className="p-4 space-y-4">
          {isMeta ? (
            <>
              <div className="rounded-lg border border-indigo-200 dark:border-indigo-800 bg-indigo-50/80 dark:bg-indigo-900/20 p-3">
                <p className="text-xs text-indigo-800 dark:text-indigo-200 leading-relaxed">
                  <strong>Sincronizado com a Meta.</strong> Entregas e leituras são atualizados em tempo real via webhook quando os destinatários recebem ou leem as mensagens.
                </p>
              </div>

              {/* Health score */}
              <div className="rounded-lg bg-gray-50 dark:bg-gray-700/30 p-3 border border-gray-200 dark:border-gray-600">
                <div className="flex items-center justify-between text-sm mb-2">
                  <span className="font-medium text-gray-700 dark:text-gray-300">Score de saúde</span>
                  <span className="flex items-center gap-2">
                    <span className={`text-lg font-bold tabular-nums ${healthScoreColor(score)}`}>{score}/100</span>
                    <span className={`text-xs font-medium ${healthScoreColor(score)}`}>({healthStatusLabel(score)})</span>
                  </span>
                </div>
                <div className="h-3 w-full rounded-full bg-gray-200 dark:bg-gray-600 overflow-hidden">
                  <div
                    className={`h-full rounded-full transition-all duration-300 ${healthScoreBg(score)}`}
                    style={{ width: `${score}%` }}
                  />
                </div>
              </div>

              {/* Métricas hoje - apenas API Meta */}
              <div className="grid grid-cols-2 gap-3">
                <div className="rounded-lg border border-gray-200 dark:border-gray-600 p-3 bg-gray-50/50 dark:bg-gray-700/30 flex gap-2">
                  <Send className="h-5 w-5 text-gray-400 dark:text-gray-500 flex-shrink-0 mt-0.5" />
                  <div className="min-w-0">
                    <div className="text-xs text-gray-500 dark:text-gray-400 uppercase tracking-wide">Enviadas hoje</div>
                    <div className="text-xl font-semibold text-gray-900 dark:text-gray-100 tabular-nums">{sent}</div>
                  </div>
                </div>
                <div className="rounded-lg border border-gray-200 dark:border-gray-600 p-3 bg-gray-50/50 dark:bg-gray-700/30 flex gap-2">
                  <CheckCircle className="h-5 w-5 text-gray-400 dark:text-gray-500 flex-shrink-0 mt-0.5" />
                  <div className="min-w-0">
                    <div className="text-xs text-gray-500 dark:text-gray-400 uppercase tracking-wide">Entregues hoje</div>
                    <div className="text-xl font-semibold text-gray-900 dark:text-gray-100 tabular-nums">{delivered}</div>
                    {sent > 0 && (
                      <div className="text-xs text-gray-500 dark:text-gray-400 mt-0.5">{deliveryRate}% taxa</div>
                    )}
                  </div>
                </div>
                <div className="rounded-lg border border-gray-200 dark:border-gray-600 p-3 bg-gray-50/50 dark:bg-gray-700/30 flex gap-2">
                  <Eye className="h-5 w-5 text-gray-400 dark:text-gray-500 flex-shrink-0 mt-0.5" />
                  <div className="min-w-0">
                    <div className="text-xs text-gray-500 dark:text-gray-400 uppercase tracking-wide">Lidas hoje</div>
                    <div className="text-xl font-semibold text-gray-900 dark:text-gray-100 tabular-nums">{read}</div>
                    {delivered > 0 && (
                      <div className="text-xs text-gray-500 dark:text-gray-400 mt-0.5">{readRate}% taxa</div>
                    )}
                  </div>
                </div>
                <div className="rounded-lg border border-gray-200 dark:border-gray-600 p-3 bg-gray-50/50 dark:bg-gray-700/30 flex gap-2">
                  <AlertCircle className={`h-5 w-5 flex-shrink-0 mt-0.5 ${failed > 0 ? 'text-amber-500' : 'text-gray-400 dark:text-gray-500'}`} />
                  <div className="min-w-0">
                    <div className="text-xs text-gray-500 dark:text-gray-400 uppercase tracking-wide">Falhas hoje</div>
                    <div className={`text-xl font-semibold tabular-nums ${failed > 0 ? 'text-amber-600 dark:text-amber-400' : 'text-gray-900 dark:text-gray-100'}`}>
                      {failed}
                    </div>
                  </div>
                </div>
              </div>

              {/* Erros consecutivos e última entrega */}
              <div className="pt-2 border-t border-gray-200 dark:border-gray-600 flex flex-wrap gap-4 text-sm">
                <div className="flex items-center gap-1.5">
                  <span className="text-gray-500 dark:text-gray-400">Erros consecutivos:</span>
                  <span className={`font-semibold tabular-nums ${consecutiveErrors > 0 ? 'text-amber-600 dark:text-amber-400' : 'text-gray-900 dark:text-gray-100'}`}>
                    {consecutiveErrors}
                  </span>
                </div>
                {lastSuccessFormatted && (
                  <div className="flex items-center gap-1.5 text-gray-500 dark:text-gray-400">
                    <span>Último sucesso:</span>
                    <span className="text-gray-700 dark:text-gray-300 font-medium">{lastSuccessFormatted}</span>
                  </div>
                )}
              </div>
            </>
          ) : (
            /* Evolution: só status de conexão — contadores não existem na API */
            <div className="space-y-4">
              <div className="rounded-lg border border-amber-200 dark:border-amber-800 bg-amber-50/50 dark:bg-amber-900/20 p-4">
                <p className="text-sm text-amber-900 dark:text-amber-100 leading-relaxed">
                  Para instâncias <strong>Evolution</strong> a API não fornece contagem de mensagens (enviadas/entregues/lidas). 
                  O que temos é apenas o <strong>status de conexão</strong>, exibido no card da instância.
                </p>
                <p className="text-xs text-amber-700 dark:text-amber-200 mt-2">
                  Indicadores detalhados (score, enviadas, entregues, leituras) estão disponíveis apenas para instâncias <strong>API Meta</strong>, sincronizados via webhook.
                </p>
              </div>
              <div className="rounded-lg bg-gray-50 dark:bg-gray-700/30 p-3 border border-gray-200 dark:border-gray-600">
                <div className="flex items-center gap-2">
                  <span className={`w-3 h-3 rounded-full flex-shrink-0 ${connectionColor}`} />
                  <span className="font-medium text-gray-900 dark:text-gray-100">Status atual</span>
                  <span className={`ml-auto font-semibold ${
                    connectionState === 'open' ? 'text-emerald-600 dark:text-emerald-400' :
                    connectionState === 'connecting' ? 'text-amber-600 dark:text-amber-400' : 'text-red-600 dark:text-red-400'
                  }`}>
                    {connectionLabel}
                  </span>
                </div>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
