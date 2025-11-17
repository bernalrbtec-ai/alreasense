import { useState, useEffect } from 'react'
import { api } from '../lib/api'

export interface MessageVariable {
  variable: string
  display_name: string
  description: string
  category: 'padrão' | 'sistema' | 'customizado'
  example_value?: string
}

interface UseMessageVariablesReturn {
  variables: MessageVariable[]
  loading: boolean
  error: string | null
  refetch: (contactId?: string) => Promise<void>
}

export const useMessageVariables = (contactId?: string): UseMessageVariablesReturn => {
  const [variables, setVariables] = useState<MessageVariable[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const fetchVariables = async (cid?: string) => {
    try {
      setLoading(true)
      setError(null)
      
      const url = cid 
        ? `/campaigns/variables/?contact_id=${cid}`
        : '/campaigns/variables/'
      
      console.log('📋 [VARIABLES] Buscando variáveis:', url)
      const response = await api.get(url)
      const variables = response.data.variables || []
      console.log('📋 [VARIABLES] Variáveis recebidas:', variables.length, 'total')
      console.log('📋 [VARIABLES] Variáveis customizadas:', variables.filter((v: MessageVariable) => v.category === 'customizado').length)
      console.log('📋 [VARIABLES] Lista completa:', variables.map((v: MessageVariable) => ({ variable: v.variable, category: v.category })))
      
      setVariables(variables)
    } catch (err: any) {
      console.error('❌ [VARIABLES] Erro ao buscar variáveis:', err)
      setError(err.response?.data?.error || 'Erro ao carregar variáveis')
      // Fallback para variáveis padrão se API falhar
      setVariables([
        {
          variable: '{{nome}}',
          display_name: 'Nome Completo',
          description: 'Nome completo do contato',
          category: 'padrão'
        },
        {
          variable: '{{primeiro_nome}}',
          display_name: 'Primeiro Nome',
          description: 'Primeiro nome do contato',
          category: 'padrão'
        },
        {
          variable: '{{saudacao}}',
          display_name: 'Saudação',
          description: 'Bom dia/Boa tarde/Boa noite (automático)',
          category: 'sistema'
        },
        {
          variable: '{{dia_semana}}',
          display_name: 'Dia da Semana',
          description: 'Dia da semana atual',
          category: 'sistema'
        }
      ])
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchVariables(contactId)
  }, [contactId])

  return {
    variables,
    loading,
    error,
    refetch: fetchVariables
  }
}

/**
 * Função helper para renderizar preview de mensagem com variáveis
 * Simula substituição de variáveis para preview no frontend
 */
export const renderMessagePreview = (
  template: string,
  mockData: {
    nome?: string
    primeiro_nome?: string
    email?: string
    cidade?: string
    estado?: string
    clinica?: string
    valor?: string
    [key: string]: any
  } = {}
): string => {
  const defaults = {
    nome: mockData.nome || 'Maria Silva',
    primeiro_nome: mockData.primeiro_nome || 'Maria',
    email: mockData.email || 'maria@email.com',
    cidade: mockData.cidade || 'São Paulo',
    estado: mockData.estado || 'SP',
    quem_indicou: mockData.quem_indicou || 'João Santos',
    primeiro_nome_indicador: mockData.primeiro_nome_indicador || 'João',
    valor_compra: mockData.valor_compra || 'R$ 1.500,00',
    data_compra: mockData.data_compra || '25/03/2024',
    ...mockData
  }

  let rendered = template

  // Variáveis padrão
  Object.entries(defaults).forEach(([key, value]) => {
    if (value) {
      rendered = rendered.replace(new RegExp(`\\{\\{${key}\\}\\}`, 'g'), String(value))
    }
  })

  // Variáveis do sistema
  const hour = new Date().getHours()
  const saudacao = hour < 12 ? 'Bom dia' : hour < 18 ? 'Boa tarde' : 'Boa noite'
  rendered = rendered.replace(/\{\{saudacao\}\}/g, saudacao)

  const dias = ['Segunda-feira', 'Terça-feira', 'Quarta-feira', 'Quinta-feira', 'Sexta-feira', 'Sábado', 'Domingo']
  const diaSemana = dias[new Date().getDay()]
  rendered = rendered.replace(/\{\{dia_semana\}\}/g, diaSemana)

  return rendered
}

