import React, { useState } from 'react'
import { Info, Copy, Check } from 'lucide-react'
import { Button } from '../ui/Button'

interface MessageVariablesProps {
  className?: string
}

const AVAILABLE_VARIABLES = [
  {
    variable: '{{nome}}',
    description: 'Nome completo do contato',
    example: 'João Silva'
  },
  {
    variable: '{{primeiro_nome}}',
    description: 'Primeiro nome do contato',
    example: 'João'
  },
  {
    variable: '{{saudacao}}',
    description: 'Saudação baseada no horário atual',
    example: 'Bom dia'
  },
  {
    variable: '{{dia_semana}}',
    description: 'Dia da semana atual',
    example: 'Segunda-feira'
  },
  {
    variable: '{{quem_indicou}}',
    description: 'Nome de quem indicou o contato',
    example: 'Maria Santos'
  },
  {
    variable: '{{primeiro_nome_indicador}}',
    description: 'Primeiro nome de quem indicou',
    example: 'Maria'
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
        <div className="absolute top-full left-0 mt-2 w-80 bg-white border border-gray-200 rounded-lg shadow-xl z-50">
          <div className="p-3 border-b border-gray-200">
            <h3 className="font-semibold text-sm">Variáveis de Template</h3>
            <p className="text-xs text-gray-600 mt-1">
              Use essas variáveis nas suas mensagens para personalizar o conteúdo
            </p>
          </div>
          
          <div className="max-h-64 overflow-y-auto">
            {AVAILABLE_VARIABLES.map((item) => (
              <div key={item.variable} className="p-3 border-b border-gray-100 last:border-b-0">
                <div className="flex items-center justify-between mb-1">
                  <code className="bg-gray-100 px-2 py-1 rounded text-sm font-mono">
                    {item.variable}
                  </code>
                  <div className="flex gap-1">
                    <Button
                      onClick={() => copyToClipboard(item.variable)}
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
                      onClick={() => insertVariable(item.variable)}
                      size="sm"
                      variant="ghost"
                      className="p-1 h-6 w-6 text-xs"
                      title="Inserir na mensagem"
                    >
                      +
                    </Button>
                  </div>
                </div>
                <p className="text-xs text-gray-600 mb-1">{item.description}</p>
                <p className="text-xs text-gray-500 italic">Ex: {item.example}</p>
              </div>
            ))}
          </div>
          
          <div className="p-3 bg-gray-50 border-t border-gray-200">
            <p className="text-xs text-gray-600">
              💡 <strong>Dica:</strong> As variáveis serão substituídas automaticamente pelos dados do contato quando a mensagem for enviada.
            </p>
          </div>
        </div>
      )}
    </div>
  )
}
