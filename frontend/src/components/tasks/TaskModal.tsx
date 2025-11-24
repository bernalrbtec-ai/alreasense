import { useState, useEffect } from 'react'
import { X, User } from 'lucide-react'
import { Button } from '../ui/Button'
import { api } from '../../lib/api'
import { showSuccessToast, showErrorToast, showWarningToast } from '../../lib/toastHelper'

interface Task {
  id: string
  title: string
  description?: string
  status: string
  priority: string
  due_date?: string
  assigned_to?: string
  department: string
  related_contacts: Array<{ id: string; name: string }>
}

interface Department {
  id: string
  name: string
}

interface User {
  id: string
  email: string
  first_name?: string
  last_name?: string
}

interface Contact {
  id: string
  name: string
  phone: string
}

interface TaskModalProps {
  isOpen: boolean
  onClose: () => void
  onSuccess: () => void
  task?: Task | null
  initialDepartmentId?: string
  initialContactId?: string
  initialDate?: Date
  departments: Department[]
  users: User[]
}

export default function TaskModal({
  isOpen,
  onClose,
  onSuccess,
  task,
  initialDepartmentId,
  initialContactId,
  initialDate,
  departments,
  users
}: TaskModalProps) {
  const [formData, setFormData] = useState({
    title: '',
    description: '',
    status: 'pending',
    priority: 'medium',
    department: initialDepartmentId || '',
    assigned_to: '',
    due_date: '',
    due_time: '',
    has_due_date: false,
    related_contact_ids: [] as string[],
    notify_contacts: false  // ✅ NOVO: Opção para notificar contatos relacionados
  })
  
  const [contacts, setContacts] = useState<Contact[]>([])
  const [searchContact, setSearchContact] = useState('')
  const [isLoading, setIsLoading] = useState(false)
  const [loadingContacts, setLoadingContacts] = useState(false)

  useEffect(() => {
    if (isOpen) {
      if (task) {
        // Editar tarefa existente
        const dueDate = task.due_date ? new Date(task.due_date) : null
        setFormData({
          title: task.title || '',
          description: task.description || '',
          status: task.status || 'pending',
          priority: task.priority || 'medium',
          department: task.department || '',
          assigned_to: task.assigned_to || '',
          due_date: dueDate ? formatDateForInput(dueDate) : '',
          due_time: dueDate ? formatTimeForInput(dueDate) : '',
          has_due_date: !!task.due_date,
          related_contact_ids: task.related_contacts?.map(c => c.id) || [],
          notify_contacts: (task as any).metadata?.notify_contacts || false  // ✅ NOVO: Carregar preferência de notificação
        })
      } else {
        // Nova tarefa
        // Garantir que initialDate é um Date válido
        let prefillDate: Date | null = null
        if (initialDate instanceof Date && !isNaN(initialDate.getTime())) {
          prefillDate = initialDate
        } else if (task) {
          const taskDueDate = (task as Task).due_date
          if (taskDueDate) {
            const taskDate = new Date(taskDueDate)
            if (!isNaN(taskDate.getTime())) {
              prefillDate = taskDate
            }
          }
        }
        
        setFormData({
          title: '',
          description: '',
          status: 'pending',
          priority: 'medium',
          department: initialDepartmentId || '',
          assigned_to: '',
          due_date: prefillDate ? formatDateForInput(prefillDate) : '',
          due_time: prefillDate ? formatTimeForInput(prefillDate) : '',
          has_due_date: !!prefillDate,
          related_contact_ids: initialContactId ? [initialContactId] : [],
          notify_contacts: false  // ✅ NOVO: Padrão é não notificar
        })
      }
      if (initialContactId) {
        fetchContact(initialContactId)
      }
    }
  }, [isOpen, task, initialDepartmentId, initialContactId])

  const formatDateForInput = (date: Date) => {
    if (!(date instanceof Date) || isNaN(date.getTime())) {
      return ''
    }
    return date.toISOString().split('T')[0]
  }

  const formatTimeForInput = (date: Date) => {
    const hours = date.getHours().toString().padStart(2, '0')
    const minutes = date.getMinutes().toString().padStart(2, '0')
    return `${hours}:${minutes}`
  }

  const fetchContact = async (contactId: string) => {
    try {
      const response = await api.get(`/contacts/contacts/${contactId}/`)
      const contact = response.data
      setContacts([contact])
    } catch (error) {
      console.error('Erro ao buscar contato:', error)
    }
  }

  const searchContacts = async (query: string) => {
    if (!query || query.length < 2) {
      setContacts([])
      return
    }

    try {
      setLoadingContacts(true)
      const response = await api.get('/contacts/contacts/', {
        params: { search: query, page_size: 10 }
      })
      const results = response.data.results || response.data
      setContacts(Array.isArray(results) ? results : [])
    } catch (error) {
      console.error('Erro ao buscar contatos:', error)
      setContacts([])
    } finally {
      setLoadingContacts(false)
    }
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    
    if (!formData.title.trim()) {
      showWarningToast('Título é obrigatório')
      return
    }

    if (!formData.department) {
      showWarningToast('Departamento é obrigatório')
      return
    }

    try {
      setIsLoading(true)
      
      // Preparar dados
      const payload: any = {
        title: formData.title,
        description: formData.description,
        status: formData.status,
        priority: formData.priority,
        department: formData.department,
        related_contact_ids: formData.related_contact_ids,
        metadata: {
          notify_contacts: formData.notify_contacts  // ✅ NOVO: Salvar preferência de notificação
        }
      }

      if (formData.assigned_to) {
        payload.assigned_to = formData.assigned_to
      }

      // Se tem data agendada, combinar data + hora
      if (formData.has_due_date && formData.due_date) {
        const dateTime = formData.due_time
          ? `${formData.due_date}T${formData.due_time}:00`
          : `${formData.due_date}T00:00:00`
        const scheduledDate = new Date(dateTime)
        const now = new Date()
        
        // Validar se não é no passado
        if (scheduledDate < now) {
          showWarningToast('Não é possível agendar tarefas no passado. A data/hora deve ser a partir de agora.')
          return
        }
        
        payload.due_date = scheduledDate.toISOString()
      }

      if (task) {
        // Atualizar
        await api.patch(`/contacts/tasks/${task.id}/`, payload)
        showSuccessToast('atualizar', 'Tarefa')
      } else {
        // Criar
        await api.post('/contacts/tasks/', payload)
        showSuccessToast('criar', 'Tarefa')
      }

      onSuccess()
    } catch (error: any) {
      console.error('Erro ao salvar tarefa:', error)
      showErrorToast(task ? 'atualizar' : 'criar', 'Tarefa', error)
    } finally {
      setIsLoading(false)
    }
  }

  const addContact = (contact: Contact) => {
    if (!formData.related_contact_ids.includes(contact.id)) {
      setFormData({
        ...formData,
        related_contact_ids: [...formData.related_contact_ids, contact.id]
      })
    }
    setSearchContact('')
    setContacts([])
  }

  const removeContact = (contactId: string) => {
    setFormData({
      ...formData,
      related_contact_ids: formData.related_contact_ids.filter(id => id !== contactId)
    })
  }

  if (!isOpen) return null

  const selectedContacts = contacts.filter(c => formData.related_contact_ids.includes(c.id))

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
      <div className="bg-white rounded-lg shadow-xl max-w-2xl w-full max-h-[90vh] overflow-y-auto">
        {/* Header */}
        <div className="flex items-center justify-between p-4 border-b sticky top-0 bg-white z-10">
          <h2 className="text-xl font-bold">
            {task ? 'Editar Tarefa' : 'Nova Tarefa'}
          </h2>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600">
            <X className="h-6 w-6" />
          </button>
        </div>

        {/* Form */}
        <form onSubmit={handleSubmit} className="p-6 space-y-4">
          {/* Título */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Título *
            </label>
            <input
              type="text"
              value={formData.title}
              onChange={(e) => setFormData({ ...formData, title: e.target.value })}
              className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
              placeholder="Ex: Ligar cliente sobre proposta"
              required
            />
          </div>

          {/* Descrição */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Descrição
            </label>
            <textarea
              value={formData.description}
              onChange={(e) => setFormData({ ...formData, description: e.target.value })}
              rows={3}
              className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
              placeholder="Detalhes da tarefa..."
            />
          </div>

          {/* Departamento e Status */}
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Departamento *
              </label>
              <select
                value={formData.department}
                onChange={(e) => setFormData({ ...formData, department: e.target.value })}
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                required
              >
                <option value="">Selecione...</option>
                {departments.map(dept => (
                  <option key={dept.id} value={dept.id}>{dept.name}</option>
                ))}
              </select>
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Status
              </label>
              <select
                value={formData.status}
                onChange={(e) => setFormData({ ...formData, status: e.target.value })}
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
              >
                <option value="pending">Pendente</option>
                <option value="in_progress">Em Andamento</option>
                <option value="completed">Concluída</option>
                <option value="cancelled">Cancelada</option>
              </select>
            </div>
          </div>

          {/* Prioridade e Atribuída Para */}
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Prioridade
              </label>
              <select
                value={formData.priority}
                onChange={(e) => setFormData({ ...formData, priority: e.target.value })}
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
              >
                <option value="low">Baixa</option>
                <option value="medium">Média</option>
                <option value="high">Alta</option>
                <option value="urgent">Urgente</option>
              </select>
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Atribuída Para
              </label>
              <select
                value={formData.assigned_to}
                onChange={(e) => setFormData({ ...formData, assigned_to: e.target.value })}
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
              >
                <option value="">Ninguém (tarefa geral)</option>
                {users.map(user => (
                  <option key={user.id} value={user.id}>
                    {user.first_name && user.last_name
                      ? `${user.first_name} ${user.last_name}`
                      : user.email}
                  </option>
                ))}
              </select>
            </div>
          </div>

          {/* Data/Hora Agendada */}
          <div>
            <label className="flex items-center gap-2 text-sm font-medium text-gray-700 mb-1">
              <input
                type="checkbox"
                checked={formData.has_due_date}
                onChange={(e) => {
                  const checked = e.target.checked
                  if (checked) {
                    // ✅ CORREÇÃO: Quando marca o checkbox, preencher automaticamente data e hora
                    const now = new Date()
                    const defaultDate = formatDateForInput(now)
                    
                    // ✅ CORREÇÃO: Preencher hora com +20 minutos da hora atual
                    const defaultTimeDate = new Date(now.getTime() + 20 * 60 * 1000) // +20 minutos
                    const defaultTime = formatTimeForInput(defaultTimeDate)
                    
                    setFormData({ 
                      ...formData, 
                      has_due_date: checked,
                      due_date: formData.due_date || defaultDate,
                      due_time: formData.due_time || defaultTime
                    })
                  } else {
                    setFormData({ ...formData, has_due_date: checked })
                  }
                }}
                className="rounded border-gray-300"
              />
              <span>Agendar para data/hora específica</span>
            </label>
            {formData.has_due_date && (
              <div className="grid grid-cols-2 gap-4 mt-2">
                <div>
                  <label className="block text-xs text-gray-600 mb-1">Data</label>
                  <input
                    type="date"
                    value={formData.due_date}
                    min={new Date().toISOString().split('T')[0]}
                    onChange={(e) => {
                      const selectedDate = e.target.value
                      const today = new Date().toISOString().split('T')[0]
                      
                      // Se selecionou hoje, validar hora também
                      if (selectedDate === today && formData.due_time) {
                        const now = new Date()
                        const [hours, minutes] = formData.due_time.split(':')
                        const selectedDateTime = new Date()
                        selectedDateTime.setHours(parseInt(hours), parseInt(minutes), 0, 0)
                        
                        if (selectedDateTime < now) {
                          // Se hora selecionada já passou hoje, ajustar para próxima hora
                          const nextHour = new Date(now)
                          nextHour.setHours(nextHour.getHours() + 1, 0, 0, 0)
                          setFormData({
                            ...formData,
                            due_date: selectedDate,
                            due_time: `${nextHour.getHours().toString().padStart(2, '0')}:${nextHour.getMinutes().toString().padStart(2, '0')}`
                          })
                          return
                        }
                      }
                      
                      setFormData({ ...formData, due_date: selectedDate })
                    }}
                    className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                  />
                </div>
                <div>
                  <label className="block text-xs text-gray-600 mb-1">
                    Hora
                    {formData.due_date === new Date().toISOString().split('T')[0] && (() => {
                      // ✅ NOVO: Mostrar hora mínima permitida
                      const now = new Date()
                      const marginMinutes = 5
                      const minAllowedTime = new Date(now.getTime() + marginMinutes * 60 * 1000)
                      const minHour = minAllowedTime.getHours().toString().padStart(2, '0')
                      const minMinute = minAllowedTime.getMinutes().toString().padStart(2, '0')
                      return ` (mín: ${minHour}:${minMinute})`
                    })()}
                  </label>
                  <input
                    type="time"
                    value={formData.due_time}
                    min={formData.due_date === new Date().toISOString().split('T')[0] 
                      ? (() => {
                          // ✅ CORREÇÃO: Calcular hora mínima considerando hora:minuto atual + margem de 5 minutos
                          // Isso permite selecionar a hora atual mesmo que já tenha passado alguns segundos
                          const now = new Date()
                          const marginMinutes = 5
                          const minAllowedTime = new Date(now.getTime() + marginMinutes * 60 * 1000)
                          const minHour = minAllowedTime.getHours().toString().padStart(2, '0')
                          const minMinute = minAllowedTime.getMinutes().toString().padStart(2, '0')
                          return `${minHour}:${minMinute}`
                        })()
                      : undefined}
                    onChange={(e) => {
                      const selectedTime = e.target.value
                      const today = new Date().toISOString().split('T')[0]
                      
                      // ✅ CORREÇÃO: Validar considerando hora:minuto, não apenas hora
                      if (formData.due_date === today) {
                        const now = new Date()
                        const [hours, minutes] = selectedTime.split(':')
                        const selectedDateTime = new Date()
                        selectedDateTime.setHours(parseInt(hours), parseInt(minutes), 0, 0)
                        
                        // ✅ CORREÇÃO: Permitir hora atual + alguns minutos de margem (5 minutos)
                        // Isso permite selecionar a hora atual mesmo que já tenha passado alguns segundos
                        const marginMinutes = 5
                        const minAllowedTime = new Date(now.getTime() + marginMinutes * 60 * 1000)
                        
                        if (selectedDateTime < minAllowedTime) {
                          const minTimeStr = `${minAllowedTime.getHours().toString().padStart(2, '0')}:${minAllowedTime.getMinutes().toString().padStart(2, '0')}`
                          showWarningToast(`Não é possível agendar no passado. Selecione uma hora a partir de ${minTimeStr}.`)
                          return
                        }
                      }
                      
                      setFormData({ ...formData, due_time: selectedTime })
                    }}
                    className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                  />
                </div>
              </div>
            )}
          </div>

          {/* Contatos Relacionados */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Contatos Relacionados (opcional)
            </label>
            
            {/* Buscar contato */}
            <div className="mb-2">
              <input
                type="text"
                value={searchContact}
                onChange={(e) => {
                  setSearchContact(e.target.value)
                  searchContacts(e.target.value)
                }}
                placeholder="Buscar contato..."
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
              {loadingContacts && (
                <div className="text-xs text-gray-500 mt-1">Buscando...</div>
              )}
              {searchContact && contacts.length > 0 && (
                <div className="mt-1 border border-gray-200 rounded-md max-h-40 overflow-y-auto">
                  {contacts
                    .filter(c => !formData.related_contact_ids.includes(c.id))
                    .map(contact => (
                      <button
                        key={contact.id}
                        type="button"
                        onClick={() => addContact(contact)}
                        className="w-full text-left px-3 py-2 hover:bg-gray-50 border-b border-gray-100 last:border-b-0"
                      >
                        <div className="font-medium">{contact.name}</div>
                        <div className="text-xs text-gray-500">{contact.phone}</div>
                      </button>
                    ))}
                </div>
              )}
            </div>

            {/* Contatos selecionados */}
            {formData.related_contact_ids.length > 0 && (
              <div className="flex flex-wrap gap-2">
                {selectedContacts.map(contact => (
                  <span
                    key={contact.id}
                    className="inline-flex items-center gap-1 px-2 py-1 bg-blue-100 text-blue-700 rounded text-sm"
                  >
                    {contact.name}
                    <button
                      type="button"
                      onClick={() => removeContact(contact.id)}
                      className="text-blue-700 hover:text-blue-900"
                    >
                      <X className="h-3 w-3" />
                    </button>
                  </span>
                ))}
              </div>
            )}
          </div>

          {/* Botões */}
          <div className="flex justify-end gap-2 pt-4 border-t">
            <Button type="button" variant="outline" onClick={onClose}>
              Cancelar
            </Button>
            <Button type="submit" disabled={isLoading}>
              {isLoading ? 'Salvando...' : task ? 'Atualizar' : 'Criar'}
            </Button>
          </div>
        </form>
      </div>
    </div>
  )
}

