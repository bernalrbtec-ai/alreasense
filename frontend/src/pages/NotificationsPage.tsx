import { useState, useEffect } from 'react'
import { Card } from '../components/ui/Card'
import { Button } from '../components/ui/Button'
import LoadingSpinner from '../components/ui/LoadingSpinner'
import { Bell, Mail, MessageSquare, Plus, Server, FileText, Eye, Trash2, Edit } from 'lucide-react'
import { api } from '../lib/api'

interface NotificationTemplate {
  id: string
  name: string
  type: 'email' | 'whatsapp'
  category: string
  subject: string
  content: string
  is_active: boolean
  tenant_name: string
}

interface WhatsAppInstance {
  id: string
  name: string
  instance_name: string
  phone_number: string
  status: string
  is_active: boolean
  is_default: boolean
}

export default function NotificationsPage() {
  const [activeTab, setActiveTab] = useState<'templates' | 'instances' | 'logs'>('templates')
  const [templates, setTemplates] = useState<NotificationTemplate[]>([])
  const [instances, setInstances] = useState<WhatsAppInstance[]>([])
  const [isLoading, setIsLoading] = useState(true)

  useEffect(() => {
    fetchData()
  }, [activeTab])

  const fetchData = async () => {
    setIsLoading(true)
    try {
      if (activeTab === 'templates') {
        const response = await api.get('/notifications/templates/')
        setTemplates(Array.isArray(response.data) ? response.data : [])
      } else if (activeTab === 'instances') {
        const response = await api.get('/notifications/whatsapp-instances/')
        setInstances(Array.isArray(response.data) ? response.data : [])
      }
    } catch (error) {
      console.error('Error fetching data:', error)
    } finally {
      setIsLoading(false)
    }
  }

  const handleCheckStatus = async (instanceId: string) => {
    try {
      await api.post(`/notifications/whatsapp-instances/${instanceId}/check_status/`)
      fetchData()
    } catch (error) {
      console.error('Error checking status:', error)
    }
  }

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <LoadingSpinner size="lg" />
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Sistema de Notificações</h1>
          <p className="text-sm text-gray-500 mt-1">
            Gerencie templates de email e WhatsApp, instâncias e histórico de envios
          </p>
        </div>
        <Button>
          <Plus className="h-4 w-4 mr-2" />
          Novo Template
        </Button>
      </div>

      {/* Tabs */}
      <div className="border-b border-gray-200">
        <nav className="-mb-px flex space-x-8">
          <button
            onClick={() => setActiveTab('templates')}
            className={`${
              activeTab === 'templates'
                ? 'border-blue-500 text-blue-600'
                : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
            } whitespace-nowrap py-4 px-1 border-b-2 font-medium text-sm flex items-center gap-2`}
          >
            <FileText className="h-4 w-4" />
            Templates
          </button>
          <button
            onClick={() => setActiveTab('instances')}
            className={`${
              activeTab === 'instances'
                ? 'border-blue-500 text-blue-600'
                : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
            } whitespace-nowrap py-4 px-1 border-b-2 font-medium text-sm flex items-center gap-2`}
          >
            <Server className="h-4 w-4" />
            Instâncias WhatsApp
          </button>
          <button
            onClick={() => setActiveTab('logs')}
            className={`${
              activeTab === 'logs'
                ? 'border-blue-500 text-blue-600'
                : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
            } whitespace-nowrap py-4 px-1 border-b-2 font-medium text-sm flex items-center gap-2`}
          >
            <Eye className="h-4 w-4" />
            Histórico
          </button>
        </nav>
      </div>

      {/* Templates Tab */}
      {activeTab === 'templates' && (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {Array.isArray(templates) && templates.map((template) => (
            <Card key={template.id} className="p-4">
              <div className="flex items-start justify-between">
                <div className="flex items-center gap-2">
                  {template.type === 'email' ? (
                    <Mail className="h-5 w-5 text-blue-500" />
                  ) : (
                    <MessageSquare className="h-5 w-5 text-green-500" />
                  )}
                  <div>
                    <h3 className="font-semibold text-gray-900">{template.name}</h3>
                    <p className="text-xs text-gray-500">{template.category}</p>
                  </div>
                </div>
                <span className={`inline-flex items-center px-2 py-1 rounded-full text-xs font-medium ${
                  template.is_active ? 'bg-green-100 text-green-800' : 'bg-gray-100 text-gray-800'
                }`}>
                  {template.is_active ? 'Ativo' : 'Inativo'}
                </span>
              </div>
              <div className="mt-3">
                <p className="text-sm text-gray-600 line-clamp-2">{template.subject || template.content}</p>
              </div>
              <div className="mt-4 flex items-center justify-between">
                <span className="text-xs text-gray-500">{template.tenant_name}</span>
                <div className="flex gap-2">
                  <Button variant="ghost" size="sm">
                    <Edit className="h-4 w-4" />
                  </Button>
                  <Button variant="ghost" size="sm">
                    <Trash2 className="h-4 w-4" />
                  </Button>
                </div>
              </div>
            </Card>
          ))}
          
          {(!Array.isArray(templates) || templates.length === 0) && (
            <div className="col-span-full text-center py-12">
              <Bell className="mx-auto h-12 w-12 text-gray-400" />
              <h3 className="mt-2 text-sm font-medium text-gray-900">Nenhum template cadastrado</h3>
              <p className="mt-1 text-sm text-gray-500">
                Comece criando um novo template de notificação
              </p>
            </div>
          )}
        </div>
      )}

      {/* Instances Tab */}
      {activeTab === 'instances' && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {Array.isArray(instances) && instances.map((instance) => (
            <Card key={instance.id} className="p-4">
              <div className="flex items-start justify-between">
                <div>
                  <h3 className="font-semibold text-gray-900">{instance.name}</h3>
                  <p className="text-sm text-gray-500">{instance.instance_name}</p>
                  {instance.phone_number && (
                    <p className="text-sm text-gray-600 mt-1">{instance.phone_number}</p>
                  )}
                </div>
                <div className="flex flex-col items-end gap-2">
                  <span className={`inline-flex items-center px-2 py-1 rounded-full text-xs font-medium ${
                    instance.status === 'active' ? 'bg-green-100 text-green-800' :
                    instance.status === 'inactive' ? 'bg-yellow-100 text-yellow-800' :
                    'bg-red-100 text-red-800'
                  }`}>
                    {instance.status}
                  </span>
                  {instance.is_default && (
                    <span className="inline-flex items-center px-2 py-1 rounded-full text-xs font-medium bg-blue-100 text-blue-800">
                      Padrão
                    </span>
                  )}
                </div>
              </div>
              <div className="mt-4 flex gap-2">
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => handleCheckStatus(instance.id)}
                >
                  Verificar Status
                </Button>
                <Button variant="ghost" size="sm">
                  <Edit className="h-4 w-4" />
                </Button>
              </div>
            </Card>
          ))}
          
          {(!Array.isArray(instances) || instances.length === 0) && (
            <div className="col-span-full text-center py-12">
              <Server className="mx-auto h-12 w-12 text-gray-400" />
              <h3 className="mt-2 text-sm font-medium text-gray-900">Nenhuma instância cadastrada</h3>
              <p className="mt-1 text-sm text-gray-500">
                Configure uma instância do WhatsApp para enviar notificações
              </p>
            </div>
          )}
        </div>
      )}

      {/* Logs Tab */}
      {activeTab === 'logs' && (
        <div className="text-center py-12">
          <Eye className="mx-auto h-12 w-12 text-gray-400" />
          <h3 className="mt-2 text-sm font-medium text-gray-900">Histórico de notificações</h3>
          <p className="mt-1 text-sm text-gray-500">
            Em desenvolvimento
          </p>
        </div>
      )}
    </div>
  )
}

