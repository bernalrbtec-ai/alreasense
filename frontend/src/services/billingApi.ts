/**
 * Service para Billing API
 * Gerencia envio de cobranças via WhatsApp
 */
import { api } from '../lib/api'

export interface BillingContact {
  nome: string
  telefone: string
  valor?: string
  data_vencimento?: string
  valor_total?: string
  codigo_pix?: string
  link_pagamento?: string
  titulo?: string
  mensagem?: string
  metadata?: Record<string, any>
}

export interface SendBillingRequest {
  template_type: 'overdue' | 'upcoming' | 'notification'
  contacts: BillingContact[]
  external_id?: string
  instance_id?: string
}

export interface SendBillingResponse {
  success: boolean
  message: string
  campaign_id?: string
  queue_id?: string
  total_contacts?: number
  errors?: Array<Record<string, any>>
}

export interface QueueStatus {
  id: string
  billing_campaign: string
  campaign_name: string
  status: string
  total_contacts: number
  processed_contacts: number
  sent_contacts: number
  failed_contacts: number
  progress_percentage: number
  processing_by?: string
  last_heartbeat?: string
  scheduled_for?: string
  started_at?: string
  completed_at?: string
  created_at: string
  updated_at: string
}

export interface CampaignContact {
  contact_id: string
  phone: string
  name: string
  status: string
  sent_at?: string
  error_message?: string
}

export interface CampaignContactsResponse {
  success: boolean
  campaign_id: string
  total: number
  page: number
  page_size: number
  contacts: CampaignContact[]
}

export interface BillingAPIKey {
  id: string
  tenant: string
  name: string
  key_masked: string
  key_set: boolean
  is_active: boolean
  expires_at?: string
  allowed_ips: string[]
  allowed_template_types?: string[]
  total_requests: number
  last_used_at?: string
  last_used_ip?: string
  created_at: string
  updated_at: string
}

export interface BillingTemplate {
  id: string
  tenant: string
  name: string
  template_type: 'overdue' | 'upcoming' | 'notification'
  description?: string
  priority: number
  allow_retry: boolean
  max_retries: number
  rotation_strategy: string
  required_fields: string[]
  optional_fields: string[]
  json_schema?: Record<string, any>
  media_type: string
  is_active: boolean
  total_uses: number
  variations?: BillingTemplateVariation[]
  created_at: string
  updated_at: string
}

export interface BillingTemplateVariation {
  id: string
  template: string
  name: string
  template_text: string
  order: number
  is_active: boolean
  times_used: number
  created_at: string
  updated_at: string
}

const billingApiService = {
  /**
   * Envia cobrança atrasada
   */
  sendOverdue: async (data: SendBillingRequest): Promise<SendBillingResponse> => {
    const response = await api.post('/billing/v1/billing/send/overdue', data, {
      headers: {
        'X-Billing-API-Key': localStorage.getItem('billing_api_key') || ''
      }
    })
    return response.data
  },

  /**
   * Envia cobrança a vencer
   */
  sendUpcoming: async (data: SendBillingRequest): Promise<SendBillingResponse> => {
    const response = await api.post('/billing/v1/billing/send/upcoming', data, {
      headers: {
        'X-Billing-API-Key': localStorage.getItem('billing_api_key') || ''
      }
    })
    return response.data
  },

  /**
   * Envia notificação
   */
  sendNotification: async (data: SendBillingRequest): Promise<SendBillingResponse> => {
    const response = await api.post('/billing/v1/billing/send/notification', data, {
      headers: {
        'X-Billing-API-Key': localStorage.getItem('billing_api_key') || ''
      }
    })
    return response.data
  },

  /**
   * Consulta status da fila
   */
  getQueueStatus: async (queueId: string): Promise<{ success: boolean; queue: QueueStatus }> => {
    const response = await api.get(`/billing/v1/billing/queue/${queueId}/status`, {
      headers: {
        'X-Billing-API-Key': localStorage.getItem('billing_api_key') || ''
      }
    })
    return response.data
  },

  /**
   * Lista contatos de uma campanha
   */
  getCampaignContacts: async (
    campaignId: string,
    params?: { status?: string; page?: number; page_size?: number }
  ): Promise<CampaignContactsResponse> => {
    const response = await api.get(`/billing/v1/billing/campaign/${campaignId}/contacts`, {
      params,
      headers: {
        'X-Billing-API-Key': localStorage.getItem('billing_api_key') || ''
      }
    })
    return response.data
  },

  /**
   * Lista API Keys (admin)
   */
  getAPIKeys: async (): Promise<BillingAPIKey[]> => {
    const response = await api.get('/billing/v1/billing/api-keys/')
    return response.data.results || response.data
  },

  /**
   * Cria API Key (admin)
   */
  createAPIKey: async (data: { name: string; expires_at?: string; allowed_ips?: string[] }): Promise<BillingAPIKey> => {
    const response = await api.post('/billing/v1/billing/api-keys/', data)
    return response.data
  },

  /**
   * Deleta API Key (admin)
   */
  deleteAPIKey: async (keyId: string): Promise<void> => {
    await api.delete(`/billing/v1/billing/api-keys/${keyId}/`)
  },

  /**
   * Lista Templates (admin)
   */
  getTemplates: async (tenantId?: string): Promise<BillingTemplate[]> => {
    const params = tenantId ? { tenant_id: tenantId } : {}
    const response = await api.get('/billing/v1/billing/templates/', { params })
    return response.data.results || response.data
  },

  /**
   * Cria Template (admin)
   */
  createTemplate: async (data: Partial<BillingTemplate>): Promise<BillingTemplate> => {
    const response = await api.post('/billing/v1/billing/templates/', data)
    return response.data
  },

  /**
   * Atualiza Template (admin)
   */
  updateTemplate: async (templateId: string, data: Partial<BillingTemplate>): Promise<BillingTemplate> => {
    const response = await api.patch(`/billing/v1/billing/templates/${templateId}/`, data)
    return response.data
  },

  /**
   * Deleta Template (admin)
   */
  deleteTemplate: async (templateId: string): Promise<void> => {
    await api.delete(`/billing/v1/billing/templates/${templateId}/`)
  },
}

export default billingApiService

