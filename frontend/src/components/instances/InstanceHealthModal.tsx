import { useEffect, useRef } from 'react'
import { X } from 'lucide-react'
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
  const score = Math.min(100, Math.max(0, Number(instance.health_score ?? 100) || 0))
  const sent = Math.max(0, Number(instance.msgs_sent_today ?? 0) || 0)
  const delivered = Math.max(0, Number(instance.msgs_delivered_today ?? 0) || 0)
  const read = Math.max(0, Number(instance.msgs_read_today ?? 0) || 0)
  const failed = Math.max(0, Number(instance.msgs_failed_today ?? 0) || 0)
  const consecutiveErrors = Math.max(0, Number(instance.consecutive_errors ?? 0) || 0)
  const lastSuccessFormatted = safeFormatDate(instance.last_success_at)
  const deliveryRate = sent > 0 ? Math.round((delivered / sent) * 100) : 100
  const readRate = delivered > 0 ? Math.round((read / delivered) * 100) : 0
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
        <div className="flex items-center justify-between p-4 border-b border-gray-200 dark:border-gray-700">
          <div className="flex items-center gap-2 min-w-0">
            <h2 id="instance-health-modal-title" className="text-lg font-semibold truncate">
              Indicadores de saúde
            </h2>
            {instance.friendly_name && (
              <span className="text-sm text-gray-500 dark:text-gray-400 truncate" title={instance.friendly_name}>
                — {instance.friendly_name}
              </span>
            )}
          </div>
          {isMeta && (
            <span className="flex-shrink-0 inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium bg-indigo-100 dark:bg-indigo-900/50 text-indigo-800 dark:text-indigo-200">
              API Meta
            </span>
          )}
          <button
            ref={closeButtonRef}
            type="button"
            onClick={onClose}
            className="p-2 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-700 text-gray-500 dark:text-gray-400 flex-shrink-0 ml-2 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500 dark:focus:ring-offset-gray-800"
            aria-label="Fechar"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        <div className="p-4 space-y-4">
          {isMeta && (
            <p className="text-xs text-gray-500 dark:text-gray-400 bg-indigo-50 dark:bg-indigo-900/20 rounded-lg p-3">
              Indicadores sincronizados com a Meta: entregas e leituras são atualizados via webhook quando os destinatários recebem ou leem as mensagens.
            </p>
          )}

          {/* Health score */}
          <div>
            <div className="flex items-center justify-between text-sm mb-1.5">
              <span className="font-medium text-gray-700 dark:text-gray-300">Score de saúde</span>
              <span className="flex items-center gap-2">
                <span className={`font-semibold ${healthScoreColor(score)}`}>{score}/100</span>
                <span className={`text-xs font-medium ${healthScoreColor(score)}`}>({healthStatusLabel(score)})</span>
              </span>
            </div>
            <div className="h-2.5 w-full rounded-full bg-gray-200 dark:bg-gray-700 overflow-hidden">
              <div
                className={`h-full rounded-full transition-all ${healthScoreBg(score)}`}
                style={{ width: `${score}%` }}
              />
            </div>
          </div>

          {/* Hoje */}
          <div className="grid grid-cols-2 gap-3">
            <div className="rounded-lg border border-gray-200 dark:border-gray-600 p-3 bg-gray-50/50 dark:bg-gray-700/30">
              <div className="text-xs text-gray-500 dark:text-gray-400 uppercase tracking-wide mb-0.5">Enviadas hoje</div>
              <div className="text-xl font-semibold text-gray-900 dark:text-gray-100">{sent}</div>
            </div>
            <div className="rounded-lg border border-gray-200 dark:border-gray-600 p-3 bg-gray-50/50 dark:bg-gray-700/30">
              <div className="text-xs text-gray-500 dark:text-gray-400 uppercase tracking-wide mb-0.5">Entregues hoje</div>
              <div className="text-xl font-semibold text-gray-900 dark:text-gray-100">{delivered}</div>
              {sent > 0 && (
                <div className="text-xs text-gray-500 dark:text-gray-400 mt-0.5">{deliveryRate}% taxa de entrega</div>
              )}
            </div>
            <div className="rounded-lg border border-gray-200 dark:border-gray-600 p-3 bg-gray-50/50 dark:bg-gray-700/30">
              <div className="text-xs text-gray-500 dark:text-gray-400 uppercase tracking-wide mb-0.5">Lidas hoje</div>
              <div className="text-xl font-semibold text-gray-900 dark:text-gray-100">{read}</div>
              {delivered > 0 && (
                <div className="text-xs text-gray-500 dark:text-gray-400 mt-0.5">{readRate}% taxa de leitura</div>
              )}
            </div>
            <div className="rounded-lg border border-gray-200 dark:border-gray-600 p-3 bg-gray-50/50 dark:bg-gray-700/30">
              <div className="text-xs text-gray-500 dark:text-gray-400 uppercase tracking-wide mb-0.5">Falhas hoje</div>
              <div className={`text-xl font-semibold ${failed > 0 ? 'text-amber-600 dark:text-amber-400' : 'text-gray-900 dark:text-gray-100'}`}>
                {failed}
              </div>
            </div>
          </div>

          {/* Erros consecutivos e última entrega */}
          <div className="flex flex-wrap gap-3 text-sm">
            <div className="flex items-center gap-1.5">
              <span className="text-gray-500 dark:text-gray-400">Erros consecutivos:</span>
              <span className={consecutiveErrors > 0 ? 'font-medium text-amber-600 dark:text-amber-400' : 'text-gray-900 dark:text-gray-100'}>
                {consecutiveErrors}
              </span>
            </div>
            {lastSuccessFormatted && (
              <div className="flex items-center gap-1.5 text-gray-500 dark:text-gray-400">
                <span>Último sucesso:</span>
                <span className="text-gray-700 dark:text-gray-300">{lastSuccessFormatted}</span>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
