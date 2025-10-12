import { Phone, Mail, MapPin, Calendar, TrendingUp, Edit, Trash2, Award } from 'lucide-react'
import { Card } from '../ui/Card'
import { Button } from '../ui/Button'

interface Tag {
  id: string
  name: string
  color: string
}

interface ContactList {
  id: string
  name: string
}

interface Contact {
  id: string
  name: string
  phone: string
  email?: string
  city?: string
  state?: string
  birth_date?: string
  lifecycle_stage: string
  rfm_segment: string
  engagement_score: number
  lifetime_value: number
  days_until_birthday?: number
  tags: Tag[]
  lists: ContactList[]
  is_active: boolean
  opted_out: boolean
  created_at: string
}

interface ContactCardProps {
  contact: Contact
  onEdit: (contact: Contact) => void
  onDelete: (id: string) => void
}

export default function ContactCard({ contact, onEdit, onDelete }: ContactCardProps) {
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

  const getEngagementColor = (score: number) => {
    if (score >= 70) return 'bg-green-600'
    if (score >= 40) return 'bg-yellow-600'
    return 'bg-red-600'
  }

  return (
    <Card className="p-4 hover:shadow-lg transition-shadow">
      {/* Header */}
      <div className="flex justify-between items-start mb-3">
        <div className="flex-1">
          <h3 className="font-semibold text-lg">{contact.name}</h3>
          <p className="text-sm text-gray-500 flex items-center gap-1">
            <Phone className="h-3 w-3" />
            {contact.phone}
          </p>
        </div>
        
        <div className="flex gap-1">
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
      </div>

      {/* Lifecycle Badge */}
      <div className="mb-3">
        <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${lifecycleColors[contact.lifecycle_stage] || lifecycleColors.lead}`}>
          {lifecycleLabels[contact.lifecycle_stage] || 'Lead'}
        </span>
        
        {contact.opted_out && (
          <span className="ml-2 inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-gray-200 text-gray-700">
            Opt-out
          </span>
        )}
      </div>

      {/* Tags */}
      {contact.tags && contact.tags.length > 0 && (
        <div className="flex flex-wrap gap-1 mb-3">
          {contact.tags.map(tag => (
            <span
              key={tag.id}
              className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium"
              style={{ backgroundColor: `${tag.color}20`, color: tag.color }}
            >
              {tag.name}
            </span>
          ))}
        </div>
      )}

      {/* Info */}
      <div className="space-y-2 text-sm text-gray-600">
        {contact.email && (
          <div className="flex items-center gap-2">
            <Mail className="h-4 w-4 flex-shrink-0" />
            <span className="truncate">{contact.email}</span>
          </div>
        )}
        
        {(contact.city || contact.state) && (
          <div className="flex items-center gap-2">
            <MapPin className="h-4 w-4 flex-shrink-0" />
            {contact.city && contact.city}
            {contact.city && contact.state && ', '}
            {contact.state && contact.state}
          </div>
        )}
        
        {contact.days_until_birthday !== null && contact.days_until_birthday !== undefined && contact.days_until_birthday <= 7 && (
          <div className="flex items-center gap-2 text-blue-600">
            <Calendar className="h-4 w-4 flex-shrink-0" />
            Aniversário em {contact.days_until_birthday} dias! 🎂
          </div>
        )}
        
        {contact.lifetime_value > 0 && (
          <div className="flex items-center gap-2">
            <TrendingUp className="h-4 w-4 flex-shrink-0" />
            LTV: R$ {Number(contact.lifetime_value).toFixed(2)}
          </div>
        )}

        {/* RFM Segment */}
        {contact.rfm_segment && contact.rfm_segment !== 'lost' && (
          <div className="flex items-center gap-2 text-purple-600">
            <Award className="h-4 w-4 flex-shrink-0" />
            {contact.rfm_segment === 'champions' && 'Campeão'}
            {contact.rfm_segment === 'loyal' && 'Fiel'}
            {contact.rfm_segment === 'at_risk' && 'Em Risco'}
            {contact.rfm_segment === 'hibernating' && 'Hibernando'}
          </div>
        )}
      </div>

      {/* Engagement Score */}
      <div className="mt-3 pt-3 border-t">
        <div className="flex justify-between items-center text-xs">
          <span className="text-gray-500">Engajamento</span>
          <span className="font-semibold">{contact.engagement_score}/100</span>
        </div>
        <div className="w-full bg-gray-200 rounded-full h-2 mt-1">
          <div 
            className={`h-2 rounded-full transition-all ${getEngagementColor(contact.engagement_score)}`}
            style={{ width: `${contact.engagement_score}%` }}
          />
        </div>
      </div>
    </Card>
  )
}


