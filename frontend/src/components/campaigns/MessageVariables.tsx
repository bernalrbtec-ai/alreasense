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
  const [copiedVariable, setCopiedVariable] = useState<string | null>(null)

  const copyToClipboard = (variable: string) => {
    navigator.clipboard.writeText(variable)
    setCopiedVariable(variable)
    setTimeout(() => setCopiedVariable(null), 2000)
  }

  const insertVariable = (variable: string) => {
    const event = new CustomEvent('insertVariable', { detail: variable })
    window.dispatchEvent(event)
  }

  return (
    <div className={`${className}`}>
      <div className="mb-3">
        <h4 className="text-sm font-medium text-gray-700 mb-2">📝 Variáveis Disponíveis</h4>
        <p className="text-xs text-gray-500 mb-3">
          Clique em qualquer variável para inserir na mensagem ou arraste para o campo de texto
        </p>
      </div>
      
      <div className="grid grid-cols-2 gap-2">
        {AVAILABLE_VARIABLES.map((item) => {
          const IconComponent = item.icon
          return (
            <div 
              key={item.variable} 
              className="group relative p-3 bg-gradient-to-br from-blue-50 to-indigo-50 border border-blue-200 rounded-lg cursor-pointer hover:from-blue-100 hover:to-indigo-100 hover:border-blue-300 transition-all duration-200 hover:shadow-md"
              onClick={() => insertVariable(item.variable)}
              draggable
              onDragStart={(e) => {
                e.dataTransfer.setData('text/plain', item.variable)
                e.dataTransfer.effectAllowed = 'copy'
                
                // Adicionar feedback visual
                const element = e.target as HTMLElement
                element.style.opacity = '0.5'
                
                // Criar um elemento de preview personalizado
                const dragImage = document.createElement('div')
                dragImage.textContent = item.variable
                dragImage.style.cssText = `
                  background: #3b82f6;
                  color: white;
                  padding: 8px 12px;
                  border-radius: 6px;
                  font-family: monospace;
                  font-size: 12px;
                  position: absolute;
                  top: -1000px;
                `
                document.body.appendChild(dragImage)
                e.dataTransfer.setDragImage(dragImage, 0, 0)
                
                // Limpar após um tempo
                setTimeout(() => {
                  document.body.removeChild(dragImage)
                }, 0)
              }}
              onDragEnd={(e) => {
                // Restaurar opacidade
                const element = e.target as HTMLElement
                element.style.opacity = '1'
              }}
            >
              {/* Ícone */}
              <div className="flex items-center gap-2 mb-2">
                <div className="flex-shrink-0 w-6 h-6 bg-blue-100 rounded-full flex items-center justify-center group-hover:bg-blue-200 transition-colors">
                  <IconComponent className="w-3 h-3 text-blue-600" />
                </div>
                <h4 className="text-xs font-medium text-gray-900 truncate">
                  {item.displayName}
                </h4>
              </div>
              
              {/* Variável */}
              <code className="text-xs text-blue-600 font-mono bg-white px-2 py-1 rounded border block mb-1">
                {item.variable}
              </code>
              
              {/* Exemplo */}
              <p className="text-xs text-gray-500 italic">
                Ex: {item.example}
              </p>
              
              {/* Botão de copiar */}
              <button
                onClick={(e) => {
                  e.stopPropagation()
                  copyToClipboard(item.variable)
                }}
                className="absolute top-2 right-2 p-1 opacity-0 group-hover:opacity-100 transition-opacity"
                title="Copiar variável"
              >
                {copiedVariable === item.variable ? (
                  <Check className="w-3 h-3 text-green-600" />
                ) : (
                  <Copy className="w-3 h-3 text-gray-400 hover:text-gray-600" />
                )}
              </button>
              
              {/* Indicador de arrastar */}
              <div className="absolute bottom-1 right-1 opacity-0 group-hover:opacity-100 transition-opacity">
                <div className="w-2 h-2 bg-blue-300 rounded-full"></div>
              </div>
            </div>
          )
        })}
      </div>
      
      <div className="mt-3 p-2 bg-green-50 border border-green-200 rounded-lg">
        <p className="text-xs text-green-700">
          💡 <strong>Dica:</strong> Clique para inserir ou arraste para o campo de texto. As variáveis serão substituídas pelos dados reais do contato.
        </p>
      </div>
    </div>
  )
}
