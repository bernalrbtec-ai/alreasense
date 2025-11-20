import { useState } from 'react'
import { X, Search } from 'lucide-react'
import { Button } from '../ui/Button'

interface TaskSearchModalProps {
  isOpen: boolean
  onClose: () => void
  onApplyFilters: (filters: {
    status: string
    department: string
    assigned_to: string
    my_tasks: boolean
    created_by_me: boolean
    overdue: boolean
    search: string
  }) => void
  departments: Array<{ id: string; name: string }>
  users: Array<{ id: string; email: string; first_name?: string; last_name?: string }>
  currentFilters: {
    status: string
    department: string
    assigned_to: string
    my_tasks: boolean
    created_by_me: boolean
    overdue: boolean
  }
}

export default function TaskSearchModal({
  isOpen,
  onClose,
  onApplyFilters,
  departments,
  users,
  currentFilters
}: TaskSearchModalProps) {
  const [filters, setFilters] = useState({
    ...currentFilters,
    search: ''
  })

  if (!isOpen) return null

  const handleApply = () => {
    onApplyFilters(filters)
    onClose()
  }

  const handleReset = () => {
    const resetFilters = {
      status: '',
      department: '',
      assigned_to: '',
      my_tasks: false,
      created_by_me: false,
      overdue: false,
      search: ''
    }
    setFilters(resetFilters)
    onApplyFilters(resetFilters)
    onClose()
  }

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
      <div className="bg-white rounded-lg shadow-xl max-w-2xl w-full max-h-[90vh] overflow-y-auto">
        {/* Header */}
        <div className="flex items-center justify-between p-4 border-b sticky top-0 bg-white z-10">
          <h2 className="text-xl font-bold flex items-center gap-2">
            <Search className="h-5 w-5" />
            Pesquisar e Filtrar Tarefas
          </h2>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600">
            <X className="h-6 w-6" />
          </button>
        </div>

        {/* Form */}
        <div className="p-6 space-y-4">
          {/* Busca por texto */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Buscar
            </label>
            <input
              type="text"
              value={filters.search}
              onChange={(e) => setFilters({ ...filters, search: e.target.value })}
              className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
              placeholder="Buscar por título ou descrição..."
            />
          </div>

          {/* Status */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Status
            </label>
            <select
              value={filters.status}
              onChange={(e) => setFilters({ ...filters, status: e.target.value })}
              className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
            >
              <option value="">Todos</option>
              <option value="pending">Pendente</option>
              <option value="in_progress">Em Andamento</option>
              <option value="completed">Concluída</option>
              <option value="cancelled">Cancelada</option>
            </select>
          </div>

          {/* Departamento e Atribuída Para */}
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Departamento
              </label>
              <select
                value={filters.department}
                onChange={(e) => setFilters({ ...filters, department: e.target.value })}
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
              >
                <option value="">Todos</option>
                {departments.map(dept => (
                  <option key={dept.id} value={dept.id}>{dept.name}</option>
                ))}
              </select>
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Atribuída Para
              </label>
              <select
                value={filters.assigned_to}
                onChange={(e) => setFilters({ ...filters, assigned_to: e.target.value })}
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
              >
                <option value="">Todos</option>
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

          {/* Checkboxes */}
          <div className="space-y-2">
            <label className="flex items-center gap-2 text-sm">
              <input
                type="checkbox"
                checked={filters.my_tasks}
                onChange={(e) => setFilters({ ...filters, my_tasks: e.target.checked })}
                className="rounded border-gray-300"
              />
              <span>Minhas tarefas atribuídas</span>
            </label>
            <label className="flex items-center gap-2 text-sm">
              <input
                type="checkbox"
                checked={filters.created_by_me}
                onChange={(e) => setFilters({ ...filters, created_by_me: e.target.checked })}
                className="rounded border-gray-300"
              />
              <span>Tarefas que criei</span>
            </label>
            <label className="flex items-center gap-2 text-sm">
              <input
                type="checkbox"
                checked={filters.overdue}
                onChange={(e) => setFilters({ ...filters, overdue: e.target.checked })}
                className="rounded border-gray-300"
              />
              <span>Atrasadas</span>
            </label>
          </div>

          {/* Botões */}
          <div className="flex justify-end gap-2 pt-4 border-t">
            <Button type="button" variant="outline" onClick={handleReset}>
              Limpar Filtros
            </Button>
            <Button type="button" variant="outline" onClick={onClose}>
              Cancelar
            </Button>
            <Button type="button" onClick={handleApply}>
              Aplicar Filtros
            </Button>
          </div>
        </div>
      </div>
    </div>
  )
}

