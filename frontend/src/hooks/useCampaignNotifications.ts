import { useEffect } from 'react'
import { showSuccessToast, showErrorToast } from '../lib/toastHelper'

interface CampaignUpdate {
  type: string
  campaign_id: string
  campaign_name: string
  status: string
  messages_sent: number
  messages_delivered: number
  messages_read: number
  messages_failed: number
  total_contacts: number
  progress_percentage: number
  last_message_sent_at?: string
  next_message_scheduled_at?: string
  next_contact_name?: string
  next_contact_phone?: string
  last_contact_name?: string
  last_contact_phone?: string
  updated_at: string
  timestamp: string
  event?: string
}

interface UseCampaignNotificationsProps {
  lastUpdate: CampaignUpdate | null
  enabled?: boolean
}

export function useCampaignNotifications({ 
  lastUpdate, 
  enabled = true 
}: UseCampaignNotificationsProps) {
  
  useEffect(() => {
    if (!enabled || !lastUpdate) return

    const { type, campaign_name, status, event } = lastUpdate

    // Determinar se deve mostrar notificação baseado no tipo de evento
    const shouldNotify = (eventType: string) => {
      const importantEvents = [
        'campaign_started',
        'campaign_paused', 
        'campaign_completed',
        'message_sent',
        'message_failed',
        'campaign_error'
      ]
      return importantEvents.includes(eventType)
    }

    if (shouldNotify(type)) {
      switch (type) {
        case 'campaign_started':
          showSuccessToast(
            `Campanha "${campaign_name}" iniciada!`,
            'A campanha começou a enviar mensagens.'
          )
          break
          
        case 'campaign_paused':
          showErrorToast(
            `Campanha "${campaign_name}" pausada`,
            'A campanha foi pausada automaticamente.'
          )
          break
          
        case 'campaign_completed':
          showSuccessToast(
            `Campanha "${campaign_name}" concluída!`,
            'Todas as mensagens foram enviadas com sucesso.'
          )
          break
          
        case 'message_sent':
          // Não mostrar toast para cada mensagem individual
          // Apenas log no console
          console.log(`✅ Mensagem enviada para ${lastUpdate.last_contact_name} (${lastUpdate.last_contact_phone})`)
          break
          
        case 'message_failed':
          showErrorToast(
            `Falha ao enviar mensagem`,
            `Campanha: ${campaign_name} - Contato: ${lastUpdate.last_contact_name}`
          )
          break
          
        case 'campaign_error':
          showErrorToast(
            `Erro na campanha "${campaign_name}"`,
            'Verifique os logs para mais detalhes.'
          )
          break
          
        default:
          // Para outros eventos, apenas log
          console.log(`📡 Evento de campanha: ${type} - ${campaign_name}`)
      }
    }
  }, [lastUpdate, enabled])
}
