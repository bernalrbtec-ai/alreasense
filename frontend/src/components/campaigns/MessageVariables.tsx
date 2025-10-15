import React, { useState } from 'react'
import { Info, Copy, Check, MoreVertical, Hand, Mail, Users, Calendar, Clock, Sun } from 'lucide-react'
import { Button } from '../ui/Button'

interface MessageVariablesProps {
  className?: string
}

const AVAILABLE_VARIABLES = [
  {
    variable: '{{nome}}',
    displayName: 'Nome Completo',
    description: 'Nome completo do contato',
    example: 'João Silva',
    icon: Users
  },
  {
    variable: '{{primeiro_nome}}',
    displayName: 'Primeiro Nome',
    description: 'Primeiro nome do contato',
    example: 'João',
    icon: Hand
  },
  {
    variable: '{{saudacao}}',
    displayName: 'Saudação',
    description: 'Saudação baseada no horário atual',
    example: 'Bom dia',
    icon: Sun
  },
  {
    variable: '{{dia_semana}}',
    displayName: 'Dia da Semana',
    description: 'Dia da semana atual',
    example: 'Segunda-feira',
    icon: Calendar
  },
  {
    variable: '{{quem_indicou}}',
    displayName: 'Quem Indicou',
    description: 'Nome de quem indicou o contato',
    example: 'Maria Santos',
    icon: Users
  },
  {
    variable: '{{primeiro_nome_indicador}}',
    displayName: 'Primeiro Nome Indicador',
    description: 'Primeiro nome de quem indicou',
    example: 'Maria',
    icon: Hand
  }
]

export function MessageVariables({ className = '' }: MessageVariablesProps) {
  const [isVisible, setIsVisible] = useState(false)
  const [copiedVariable, setCopiedVariable] = useState<string | null>(null)

  const copyToClipboard = (variable: string) => {
    navigator.clipboard.writeText(variable)
    setCopiedVariable(variable)
    setTimeout(() => setCopiedVariable(null), 2000)
  }

  const insertVariable = (variable: string) => {
    // Esta função seria passada como prop do componente pai para inserir no textarea
    const event = new CustomEvent('insertVariable', { detail: variable })
    window.dispatchEvent(event)
  }

  return (
    <div className={`relative ${className}`}>
      {/* Botão de toggle */}
      <Button
        onClick={() => setIsVisible(!isVisible)}
        variant="outline"
        size="sm"
        className="flex items-center gap-2"
      >
        <Info className="w-4 h-4" />
        Variáveis Disponíveis
      </Button>

      {/* Painel de variáveis */}
      {isVisible && (
        <div className="absolute top-full left-0 mt-2 w-96 bg-white border border-gray-200 rounded-lg shadow-xl z-50">
          <div className="p-4 border-b border-gray-200">
            <h3 className="font-semibold text-sm">📝 Variáveis Disponíveis</h3>
            <p className="text-xs text-gray-600 mt-1">
              (Clique para adicionar ao campo acima)
            </p>
          </div>
          
          <div className="max-h-80 overflow-y-auto p-2">
            {AVAILABLE_VARIABLES.map((item) => {
              const IconComponent = item.icon
              return (
                <div 
                  key={item.variable} 
                  className="flex items-center gap-3 p-3 mb-2 bg-gray-50 rounded-lg cursor-pointer hover:bg-gray-100 transition-colors"
                  onClick={() => insertVariable(item.variable)}
                >
                  {/* Ícone */}
                  <div className="flex-shrink-0 w-8 h-8 bg-blue-100 rounded-full flex items-center justify-center">
                    <IconComponent className="w-4 h-4 text-blue-600" />
                  </div>
                  
                  {/* Conteúdo */}
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center justify-between">
                      <h4 className="text-sm font-medium text-gray-900 truncate">
                        {item.displayName}
                      </h4>
                      <div className="flex items-center gap-1">
                        <Button
                          onClick={(e) => {
                            e.stopPropagation()
                            copyToClipboard(item.variable)
                          }}
                          size="sm"
                          variant="ghost"
                          className="p-1 h-6 w-6"
                          title="Copiar variável"
                        >
                          {copiedVariable === item.variable ? (
                            <Check className="w-3 h-3 text-green-600" />
                          ) : (
                            <Copy className="w-3 h-3" />
                          )}
                        </Button>
                        <Button
                          onClick={(e) => {
                            e.stopPropagation()
                            insertVariable(item.variable)
                          }}
                          size="sm"
                          variant="ghost"
                          className="p-1 h-6 w-6"
                          title="Inserir na mensagem"
                        >
                          <MoreVertical className="w-3 h-3" />
                        </Button>
                      </div>
                    </div>
                    <code className="text-xs text-blue-600 font-mono bg-blue-50 px-1 py-0.5 rounded">
                      {item.variable}
                    </code>
                    <p className="text-xs text-gray-600 mt-1">{item.description}</p>
                    <p className="text-xs text-gray-500 italic">Ex: {item.example}</p>
                  </div>
                </div>
              )
            })}
          </div>
          
          <div className="p-3 bg-blue-50 border-t border-blue-200">
            <p className="text-xs text-blue-700">
              💡 <strong>Dica:</strong> Clique em qualquer variável para inserir automaticamente na mensagem. As variáveis serão substituídas pelos dados reais do contato.
            </p>
          </div>
        </div>
      )}
    </div>
  )
}
