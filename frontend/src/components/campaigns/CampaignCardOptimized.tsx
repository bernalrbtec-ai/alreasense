import React, { useState, useEffect } from 'react'
import { motion } from 'framer-motion'
import { Card, CardContent, CardHeader, CardTitle } from '../ui/Card'
import { Badge } from '../ui/badge'
import { Tooltip } from '../ui/Tooltip'
import { Button } from '../ui/Button'
import { PieChart, Pie, Cell, ResponsiveContainer } from 'recharts'
import {
  Play,
  Pause,
  Edit,
  Copy,
  FileText,
  Users,
  MessageSquare,
  Send,
  CheckCircle,
  Eye,
  X,
  Clock,
  Phone,
  RefreshCw,
  AlertCircle,
  Activity
} from 'lucide-react'

interface Campaign {
  id: string
  name: string
  description: string
  status: 'draft' | 'scheduled' | 'running' | 'paused' | 'completed' | 'cancelled'
  status_display: string
  total_contacts: number
  messages_sent: number
  messages_delivered: number
  messages_read: number
  messages_failed: number
  success_rate: number
  read_rate: number
  progress_percentage: number
  messages: any[]
  next_contact_name?: string
  next_contact_phone?: string
  next_instance_name?: string
  last_contact_name?: string
  last_contact_phone?: string
  last_instance_name?: string
  last_message_sent_at?: string
  countdown_seconds?: number
  retryInfo?: {
    is_retrying: boolean
    retry_contact_name?: string
    retry_contact_phone?: string
    retry_attempt: number
    retry_error_reason?: string
    retry_countdown: number
  }
}

interface CampaignCardOptimizedProps {
  campaign: Campaign
  onStart: (campaign: Campaign) => void
  onPause: (campaign: Campaign) => void
  onResume: (campaign: Campaign) => void
  onEdit: (campaign: Campaign) => void
  onDuplicate: (campaign: Campaign) => void
  onViewLogs: (campaign: Campaign) => void
}

const CampaignCardOptimized: React.FC<CampaignCardOptimizedProps> = ({
  campaign,
  onStart,
  onPause,
  onResume,
  onEdit,
  onDuplicate,
  onViewLogs
}) => {
  const [isHovered, setIsHovered] = useState(false)
  const [countdown, setCountdown] = useState(campaign.countdown_seconds || 0)

  // Countdown em tempo real
  useEffect(() => {
    if (countdown <= 0) return

    const timer = setInterval(() => {
      setCountdown(prev => {
        if (prev <= 1) {
          return 0
        }
        return prev - 1
      })
    }, 1000)

    return () => clearInterval(timer)
  }, [countdown])

  // Atualizar countdown quando campaign.countdown_seconds mudar
  useEffect(() => {
    setCountdown(campaign.countdown_seconds || 0)
  }, [campaign.countdown_seconds])

  // Status configuration
  const getStatusConfig = (status: string) => {
    switch (status) {
      case 'running':
        return {
          icon: <Activity className="h-3 w-3" />,
          color: 'bg-green-100 text-green-800 border-green-200',
          bgColor: 'bg-green-50',
          pulse: true
        }
      case 'paused':
        return {
          icon: <Pause className="h-3 w-3" />,
          color: 'bg-yellow-100 text-yellow-800 border-yellow-200',
          bgColor: 'bg-yellow-50',
          pulse: false
        }
      case 'completed':
        return {
          icon: <CheckCircle className="h-3 w-3" />,
          color: 'bg-purple-100 text-purple-800 border-purple-200',
          bgColor: 'bg-purple-50',
          pulse: false
        }
      case 'draft':
        return {
          icon: <Edit className="h-3 w-3" />,
          color: 'bg-gray-100 text-gray-800 border-gray-200',
          bgColor: 'bg-gray-50',
          pulse: false
        }
      case 'scheduled':
        return {
          icon: <Clock className="h-3 w-3" />,
          color: 'bg-blue-100 text-blue-800 border-blue-200',
          bgColor: 'bg-blue-50',
          pulse: false
        }
      case 'cancelled':
        return {
          icon: <X className="h-3 w-3" />,
          color: 'bg-red-100 text-red-800 border-red-200',
          bgColor: 'bg-red-50',
          pulse: false
        }
      default:
        return {
          icon: <Activity className="h-3 w-3" />,
          color: 'bg-gray-100 text-gray-800 border-gray-200',
          bgColor: 'bg-gray-50',
          pulse: false
        }
    }
  }

  const statusConfig = getStatusConfig(campaign.status)

  // Dados para o gráfico circular
  const getPieData = () => {
    const sent = campaign.messages_sent
    const delivered = campaign.messages_delivered
    const read = campaign.messages_read
    const failed = campaign.messages_failed
    const pending = campaign.total_contacts - sent

    return [
      { name: 'Enviadas', value: sent, color: '#3B82F6' },
      { name: 'Entregues', value: delivered, color: '#10B981' },
      { name: 'Lidas', value: read, color: '#F59E0B' },
      { name: 'Falhas', value: failed, color: '#EF4444' },
      { name: 'Pendentes', value: Math.max(0, pending), color: '#E5E7EB' }
    ].filter(item => item.value > 0)
  }

  // Format countdown
  const formatCountdown = (seconds: number) => {
    if (seconds <= 0) return null

    const hours = Math.floor(seconds / 3600)
    const minutes = Math.floor((seconds % 3600) / 60)
    const secs = seconds % 60

    if (hours > 0) {
      return `${hours}h ${minutes}m`
    } else if (minutes > 0) {
      return `${minutes}m ${secs}s`
    } else {
      return `${secs}s`
    }
  }

  const pieData = getPieData()
  const totalSent = campaign.messages_sent
  const sentPercentage = campaign.total_contacts > 0 ? Math.round((totalSent / campaign.total_contacts) * 100) : 0

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3 }}
      onHoverStart={() => setIsHovered(true)}
      onHoverEnd={() => setIsHovered(false)}
    >
      <Card className={`relative overflow-hidden transition-all duration-300 hover:shadow-lg hover:shadow-blue-500/10 ${statusConfig.bgColor}`}>
        {/* Status indicator line */}
        <div className={`absolute top-0 left-0 right-0 h-1 ${
          campaign.status === 'running' ? 'bg-green-500' :
          campaign.status === 'paused' ? 'bg-yellow-500' :
          campaign.status === 'completed' ? 'bg-purple-500' :
          campaign.status === 'draft' ? 'bg-gray-500' :
          campaign.status === 'scheduled' ? 'bg-blue-500' :
          'bg-red-500'
        }`} />

        <CardHeader className="pb-4">
          <div className="flex items-start justify-between">
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-3 mb-2">
                <CardTitle className="text-lg font-semibold text-gray-900 truncate">
                  {campaign.name}
                </CardTitle>
                <Badge 
                  variant="outline" 
                  className={`${statusConfig.color} border ${statusConfig.pulse ? 'animate-pulse' : ''}`}
                >
                  {statusConfig.icon}
                  <span className="ml-1">{campaign.status_display}</span>
                </Badge>
              </div>
              
              {/* Métricas básicas */}
              <div className="flex items-center gap-4 text-sm text-gray-600">
                <div className="flex items-center gap-1">
                  <Users className="h-4 w-4" />
                  <span>{campaign.total_contacts} contatos</span>
                </div>
                <div className="flex items-center gap-1">
                  <MessageSquare className="h-4 w-4" />
                  <span>{campaign.messages.length} mensagens</span>
                </div>
              </div>
            </div>
            
            {/* Action buttons */}
            <div className="flex items-center gap-1 ml-4">
              {campaign.status === 'draft' && (
                <Tooltip content="Iniciar campanha">
                  <Button
                    size="sm"
                    onClick={() => onStart(campaign)}
                    className="h-8 w-8 p-0 hover:bg-green-100 hover:text-green-700"
                  >
                    <Play className="h-4 w-4" />
                  </Button>
                </Tooltip>
              )}
              
              {campaign.status === 'running' && (
                <Tooltip content="Pausar campanha">
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={() => onPause(campaign)}
                    className="h-8 w-8 p-0 hover:bg-yellow-100 hover:text-yellow-700"
                  >
                    <Pause className="h-4 w-4" />
                  </Button>
                </Tooltip>
              )}
              
              {campaign.status === 'paused' && (
                <Tooltip content="Retomar campanha">
                  <Button
                    size="sm"
                    onClick={() => onResume(campaign)}
                    className="h-8 w-8 p-0 hover:bg-green-100 hover:text-green-700"
                  >
                    <Play className="h-4 w-4" />
                  </Button>
                </Tooltip>
              )}
              
              {campaign.status !== 'running' && (
                <Tooltip content="Editar campanha">
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={() => onEdit(campaign)}
                    className="h-8 w-8 p-0 hover:bg-blue-100 hover:text-blue-700"
                  >
                    <Edit className="h-4 w-4" />
                  </Button>
                </Tooltip>
              )}
              
              <Tooltip content="Duplicar campanha">
                <Button
                  size="sm"
                  variant="outline"
                  onClick={() => onDuplicate(campaign)}
                  className="h-8 w-8 p-0 hover:bg-purple-100 hover:text-purple-700"
                >
                  <Copy className="h-4 w-4" />
                </Button>
              </Tooltip>
              
              {campaign.status !== 'draft' && (
                <Tooltip content="Ver logs">
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={() => onViewLogs(campaign)}
                    className="h-8 w-8 p-0 hover:bg-gray-100 hover:text-gray-700"
                  >
                    <FileText className="h-4 w-4" />
                  </Button>
                </Tooltip>
              )}
            </div>
          </div>
        </CardHeader>

        <CardContent className="space-y-6">
          {/* Gráfico Circular de Progresso */}
          <div className="flex justify-center">
            <div className="relative w-48 h-48">
              <ResponsiveContainer width="100%" height="100%">
                <PieChart>
                  <Pie
                    data={pieData}
                    cx="50%"
                    cy="50%"
                    innerRadius={60}
                    outerRadius={80}
                    paddingAngle={2}
                    dataKey="value"
                  >
                    {pieData.map((entry, index) => (
                      <Cell key={`cell-${index}`} fill={entry.color} />
                    ))}
                  </Pie>
                </PieChart>
              </ResponsiveContainer>
              
              {/* Centro do gráfico com percentual */}
              <div className="absolute inset-0 flex flex-col items-center justify-center">
                <div className="text-2xl font-bold text-gray-900">{sentPercentage}%</div>
                <div className="text-sm text-gray-600">Enviadas</div>
              </div>
            </div>
          </div>

          {/* Métricas detalhadas */}
          <div className="grid grid-cols-4 gap-3">
            <div className="text-center">
              <div className="flex items-center justify-center gap-1 mb-1">
                <Send className="h-4 w-4 text-blue-600" />
              </div>
              <div className="text-lg font-bold text-blue-900">{campaign.messages_sent}</div>
              <div className="text-xs text-blue-700">Enviadas</div>
            </div>
            <div className="text-center">
              <div className="flex items-center justify-center gap-1 mb-1">
                <CheckCircle className="h-4 w-4 text-green-600" />
              </div>
              <div className="text-lg font-bold text-green-900">{campaign.messages_delivered}</div>
              <div className="text-xs text-green-700">Entregues</div>
            </div>
            <div className="text-center">
              <div className="flex items-center justify-center gap-1 mb-1">
                <Eye className="h-4 w-4 text-yellow-600" />
              </div>
              <div className="text-lg font-bold text-yellow-900">{campaign.messages_read}</div>
              <div className="text-xs text-yellow-700">Lidas</div>
            </div>
            <div className="text-center">
              <div className="flex items-center justify-center gap-1 mb-1">
                <X className="h-4 w-4 text-red-600" />
              </div>
              <div className="text-lg font-bold text-red-900">{campaign.messages_failed}</div>
              <div className="text-xs text-red-700">Falhas</div>
            </div>
          </div>

          {/* Countdown ou retry info */}
          {campaign.status === 'running' && (
            <div className="space-y-3">
              {campaign.retryInfo?.is_retrying ? (
                <div className="bg-orange-50 border border-orange-200 rounded-lg p-3">
                  <div className="flex items-center gap-2 mb-2">
                    <RefreshCw className="h-4 w-4 text-orange-600 animate-spin" />
                    <span className="text-sm font-medium text-orange-800">
                      Tentativa {campaign.retryInfo.retry_attempt}/3
                    </span>
                  </div>
                  <div className="text-sm text-gray-700 mb-1">
                    <strong>Contato:</strong> {campaign.retryInfo.retry_contact_name} ({campaign.retryInfo.retry_contact_phone})
                  </div>
                  {campaign.retryInfo.retry_error_reason && (
                    <div className="text-sm text-red-600 mb-1">
                      <strong>Erro:</strong> {campaign.retryInfo.retry_error_reason}
                    </div>
                  )}
                  <div className="text-sm text-blue-600">
                    <strong>Próximo retry em:</strong> {campaign.retryInfo.retry_countdown}s
                  </div>
                </div>
              ) : countdown > 0 ? (
                <div className="bg-blue-50 border border-blue-200 rounded-lg p-3">
                  <div className="flex items-center gap-2">
                    <Clock className="h-4 w-4 text-blue-600" />
                    <span className="text-sm text-blue-800">
                      Próximo disparo em: <strong>{formatCountdown(countdown)}</strong>
                    </span>
                  </div>
                </div>
              ) : null}
            </div>
          )}

          {/* Footer info */}
          <div className="pt-4 border-t border-gray-200">
            <div className="space-y-2 text-sm">
              {campaign.next_contact_name && (
                <div className="flex items-center gap-2 text-gray-600">
                  <Users className="h-4 w-4 text-blue-500" />
                  <span><strong>Próximo:</strong> {campaign.next_contact_name} ({campaign.next_contact_phone})</span>
                </div>
              )}
              {campaign.next_instance_name && (
                <div className="flex items-center gap-2 text-gray-600">
                  <Phone className="h-4 w-4 text-green-500" />
                  <span><strong>Via:</strong> {campaign.next_instance_name}</span>
                </div>
              )}
            </div>
          </div>
        </CardContent>
      </Card>
    </motion.div>
  )
}

export default CampaignCardOptimized
