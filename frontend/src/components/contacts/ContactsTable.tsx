import { Edit, Trash2, Phone, Mail, MapPin } from 'lucide-react'
import { Button } from '../ui/Button'
import { Card } from '../ui/Card'

interface Tag {
  id: string
  name: string
  color: string
}

interface Contact {
  id: string
  name: string
  phone: string
  email?: string
  city?: string
  state?: string
  lifecycle_stage: string
  last_purchase_date?: string // ✅ Campo importado do CSV (data_compra)
  last_purchase_value?: number // ✅ Campo importado do CSV (Valor)
  tags: Tag[]
  custom_fields?: Record<string, any>
}

interface ContactsTableProps {
  contacts: Contact[]
  availableCustomFields: string[]
  onEdit: (contact: Contact) => void
  onDelete: (id: string) => void
}

export default function ContactsTable({ contacts, availableCustomFields, onEdit, onDelete }: ContactsTableProps) {
  // Colunas padrão sempre visíveis
  const standardColumns = ['Nome', 'Telefone', 'Email', 'Cidade/Estado', 'Última Compra', 'Tags']
  
  // Colunas customizadas (mostrar TODOS os campos disponíveis)
  const customColumns = availableCustomFields

  const lifecycleColors: Record<string, string> = {
    lead: 'bg-gray-100 text-gray-700',
    customer: 'bg-green-100 text-green-700',
    at_risk: 'bg-yellow-100 text-yellow-700',
    churned: 'bg-red-100 text-red-700'
  }

  const lifecycleLabels: Record<string, string> = {
    lead: 'Lead',
    customer: 'Cliente',
    at_risk: 'Em Risco',
    churned: 'Perdido'
  }

  if (contacts.length === 0) {
    return (
      <Card className="p-8 text-center">
        <p className="text-gray-500">Nenhum contato encontrado</p>
      </Card>
    )
  }

  return (
    <Card className="overflow-hidden">
      <div className="overflow-x-auto">
        <table className="min-w-full divide-y divide-gray-200">
          <thead className="bg-gray-50">
            <tr>
              {standardColumns.map((col) => (
                <th
                  key={col}
                  className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider"
                >
                  {col}
                </th>
              ))}
              {customColumns.map((field) => (
                <th
                  key={field}
                  className="px-6 py-3 text-left text-xs font-medium text-purple-600 uppercase tracking-wider"
                >
                  <span className="flex items-center gap-1">
                    <span className="text-purple-500">✨</span>
                    {field.charAt(0).toUpperCase() + field.slice(1)}
                  </span>
                </th>
              ))}
              <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">
                Ações
              </th>
            </tr>
          </thead>
          <tbody className="bg-white divide-y divide-gray-200">
            {contacts.map((contact) => (
              <tr key={contact.id} className="hover:bg-gray-50">
                {/* Nome */}
                <td className="px-6 py-4 whitespace-nowrap">
                  <div className="flex items-center">
                    <div>
                      <div className="text-sm font-medium text-gray-900">{contact.name}</div>
                      <div className="text-xs text-gray-500">
                        <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium ${
                          lifecycleColors[contact.lifecycle_stage] || lifecycleColors.lead
                        }`}>
                          {lifecycleLabels[contact.lifecycle_stage] || 'Lead'}
                        </span>
                      </div>
                    </div>
                  </div>
                </td>

                {/* Telefone */}
                <td className="px-6 py-4 whitespace-nowrap">
                  <div className="flex items-center text-sm text-gray-900">
                    <Phone className="h-4 w-4 mr-2 text-gray-400" />
                    {contact.phone}
                  </div>
                </td>

                {/* Email */}
                <td className="px-6 py-4 whitespace-nowrap">
                  {contact.email ? (
                    <div className="flex items-center text-sm text-gray-900">
                      <Mail className="h-4 w-4 mr-2 text-gray-400" />
                      {contact.email}
                    </div>
                  ) : (
                    <span className="text-sm text-gray-400">-</span>
                  )}
                </td>

                {/* Cidade/Estado */}
                <td className="px-6 py-4 whitespace-nowrap">
                  {(contact.city || contact.state) ? (
                    <div className="flex items-center text-sm text-gray-900">
                      <MapPin className="h-4 w-4 mr-2 text-gray-400" />
                      {[contact.city, contact.state].filter(Boolean).join(', ') || '-'}
                    </div>
                  ) : (
                    <span className="text-sm text-gray-400">-</span>
                  )}
                </td>

                {/* Última Compra */}
                <td className="px-6 py-4 whitespace-nowrap">
                  {contact.last_purchase_date || contact.last_purchase_value ? (
                    <div className="text-sm text-gray-900">
                      {contact.last_purchase_date && (
                        <div className="text-xs text-gray-500">
                          {new Date(contact.last_purchase_date).toLocaleDateString('pt-BR')}
                        </div>
                      )}
                      {contact.last_purchase_value && (
                        <div className="font-medium text-green-600">
                          R$ {Number(contact.last_purchase_value).toFixed(2).replace('.', ',')}
                        </div>
                      )}
                    </div>
                  ) : (
                    <span className="text-sm text-gray-400">-</span>
                  )}
                </td>

                {/* Tags */}
                <td className="px-6 py-4">
                  <div className="flex flex-wrap gap-1">
                    {contact.tags && contact.tags.length > 0 ? (
                      contact.tags.slice(0, 2).map((tag) => (
                        <span
                          key={tag.id}
                          className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium"
                          style={{ backgroundColor: `${tag.color}20`, color: tag.color }}
                        >
                          {tag.name}
                        </span>
                      ))
                    ) : (
                      <span className="text-sm text-gray-400">-</span>
                    )}
                    {contact.tags && contact.tags.length > 2 && (
                      <span className="text-xs text-gray-500">+{contact.tags.length - 2}</span>
                    )}
                  </div>
                </td>

                {/* Campos Customizados */}
                {customColumns.map((field) => (
                  <td key={field} className="px-6 py-4 whitespace-nowrap">
                    <div className="text-sm text-gray-900">
                      {contact.custom_fields?.[field] ? (
                        <span className="inline-flex items-center px-2 py-1 rounded bg-purple-50 text-purple-700 text-xs">
                          {String(contact.custom_fields[field])}
                        </span>
                      ) : (
                        <span className="text-gray-400">-</span>
                      )}
                    </div>
                  </td>
                ))}

                {/* Ações */}
                <td className="px-6 py-4 whitespace-nowrap text-right text-sm font-medium">
                  <div className="flex justify-end gap-2">
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => onEdit(contact)}
                      className="p-1"
                    >
                      <Edit className="h-4 w-4" />
                    </Button>
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => onDelete(contact.id)}
                      className="p-1 text-red-600 hover:bg-red-50"
                    >
                      <Trash2 className="h-4 w-4" />
                    </Button>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      
      {availableCustomFields.length > 0 && (
        <div className="px-6 py-3 bg-purple-50 border-t border-purple-200">
          <p className="text-xs text-purple-700">
            ✨ Mostrando {availableCustomFields.length} campo{availableCustomFields.length !== 1 ? 's' : ''} customizado{availableCustomFields.length !== 1 ? 's' : ''} importado{availableCustomFields.length !== 1 ? 's' : ''}
          </p>
        </div>
      )}
    </Card>
  )
}

