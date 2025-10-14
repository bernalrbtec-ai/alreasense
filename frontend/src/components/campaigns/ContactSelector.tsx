import { useState, useEffect } from 'react'
import { Users, Tag as TagIcon, List, UserCheck } from 'lucide-react'
import { Card } from '../ui/Card'
import { Badge } from '../ui/badge'
import { api } from '../../lib/api'

interface Tag {
  id: string
  name: string
  color: string
  contact_count: number
}

interface ContactList {
  id: string
  name: string
  contact_count: number
}

interface ContactSelectorProps {
  value: {
    type: 'all' | 'tags' | 'lists' | 'manual'
    tag_ids?: string[]
    list_ids?: string[]
    contact_ids?: string[]
  }
  onChange: (value: any) => void
}

export default function ContactSelector({ value, onChange }: ContactSelectorProps) {
  const [tags, setTags] = useState<Tag[]>([])
  const [lists, setLists] = useState<ContactList[]>([])
  const [selectedTags, setSelectedTags] = useState<string[]>(value.tag_ids || [])
  const [selectedLists, setSelectedLists] = useState<string[]>(value.list_ids || [])
  const [estimatedCount, setEstimatedCount] = useState(0)
  
  useEffect(() => {
    fetchTags()
    fetchLists()
  }, [])
  
  useEffect(() => {
    // Atualizar valor quando seleção mudar
    if (value.type === 'tags') {
      onChange({ ...value, tag_ids: selectedTags })
      calculateEstimatedCount()
    } else if (value.type === 'lists') {
      onChange({ ...value, list_ids: selectedLists })
      calculateEstimatedCount()
    }
  }, [selectedTags, selectedLists, value.type])
  
  const fetchTags = async () => {
    try {
      const response = await api.get('/contacts/tags/')
      setTags(response.data.results || response.data)
    } catch (error) {
      console.error('Error fetching tags:', error)
    }
  }
  
  const fetchLists = async () => {
    try {
      const response = await api.get('/contacts/lists/')
      setLists(response.data.results || response.data)
    } catch (error) {
      console.error('Error fetching lists:', error)
    }
  }
  
  const calculateEstimatedCount = async () => {
    try {
      let params = new URLSearchParams()
      
      if (value.type === 'tags' && selectedTags.length > 0) {
        params.append('tags', selectedTags.join(','))
      } else if (value.type === 'lists' && selectedLists.length > 0) {
        params.append('lists', selectedLists.join(','))
      }
      
      params.append('opted_out', 'false')
      params.append('is_active', 'true')
      
      const response = await api.get(`/contacts/contacts/?${params}`)
      setEstimatedCount(response.data.count || response.data.results?.length || 0)
    } catch (error) {
      console.error('Error calculating count:', error)
      setEstimatedCount(0)
    }
  }
  
  const handleTypeChange = (type: 'all' | 'tags' | 'lists' | 'manual') => {
    onChange({ type, tag_ids: [], list_ids: [], contact_ids: [] })
    setSelectedTags([])
    setSelectedLists([])
    setEstimatedCount(0)
    
    if (type === 'all') {
      // Buscar total de contatos usando stats endpoint
      api.get('/contacts/contacts/stats/?opted_out=false&is_active=true')
        .then(res => setEstimatedCount(res.data.active || 0))
        .catch(() => {
          // Fallback para endpoint antigo
          api.get('/contacts/contacts/?opted_out=false&is_active=true')
            .then(res => setEstimatedCount(res.data.count || res.data.results?.length || 0))
        })
    }
  }
  
  const toggleTag = (tagId: string) => {
    setSelectedTags(prev => 
      prev.includes(tagId) 
        ? prev.filter(id => id !== tagId)
        : [...prev, tagId]
    )
  }
  
  const toggleList = (listId: string) => {
    setSelectedLists(prev => 
      prev.includes(listId) 
        ? prev.filter(id => id !== listId)
        : [...prev, listId]
    )
  }
  
  return (
    <div className="space-y-4">
      <div>
        <label className="block text-sm font-medium mb-3">
          Quem vai receber esta campanha?
        </label>
        
        <div className="space-y-2">
          {/* Todos */}
          <label className="flex items-start gap-3 p-4 border rounded-lg hover:bg-gray-50 cursor-pointer">
            <input
              type="radio"
              checked={value.type === 'all'}
              onChange={() => handleTypeChange('all')}
              className="mt-1"
            />
            <div className="flex-1">
              <div className="flex items-center gap-2">
                <Users className="h-5 w-5 text-gray-600" />
                <p className="font-medium">Todos os contatos ativos</p>
              </div>
              <p className="text-sm text-gray-500 mt-1">
                Todos os contatos (exceto opted-out)
              </p>
            </div>
          </label>
          
          {/* Por Tags */}
          <label className="flex items-start gap-3 p-4 border rounded-lg hover:bg-gray-50 cursor-pointer">
            <input
              type="radio"
              checked={value.type === 'tags'}
              onChange={() => handleTypeChange('tags')}
              className="mt-1"
            />
            <div className="flex-1">
              <div className="flex items-center gap-2">
                <TagIcon className="h-5 w-5 text-gray-600" />
                <p className="font-medium">Por tags</p>
              </div>
              <p className="text-sm text-gray-500 mt-1">
                Selecione uma ou mais tags
              </p>
              
              {value.type === 'tags' && (
                <div className="mt-3 flex flex-wrap gap-2">
                  {tags.map(tag => (
                    <button
                      key={tag.id}
                      type="button"
                      onClick={(e) => {
                        e.stopPropagation()
                        toggleTag(tag.id)
                      }}
                      className={`px-3 py-1 rounded-full text-sm font-medium transition-colors ${
                        selectedTags.includes(tag.id)
                          ? 'bg-blue-600 text-white'
                          : 'bg-gray-200 text-gray-700 hover:bg-gray-300'
                      }`}
                    >
                      {tag.name} ({tag.contact_count})
                    </button>
                  ))}
                  {tags.length === 0 && (
                    <p className="text-sm text-gray-500">
                      Nenhuma tag criada ainda
                    </p>
                  )}
                </div>
              )}
            </div>
          </label>
          
          {/* Por Listas */}
          <label className="flex items-start gap-3 p-4 border rounded-lg hover:bg-gray-50 cursor-pointer">
            <input
              type="radio"
              checked={value.type === 'lists'}
              onChange={() => handleTypeChange('lists')}
              className="mt-1"
            />
            <div className="flex-1">
              <div className="flex items-center gap-2">
                <List className="h-5 w-5 text-gray-600" />
                <p className="font-medium">Por listas</p>
              </div>
              <p className="text-sm text-gray-500 mt-1">
                Selecione uma ou mais listas de contatos
              </p>
              
              {value.type === 'lists' && (
                <div className="mt-3 space-y-2">
                  {lists.map(list => (
                    <label
                      key={list.id}
                      className="flex items-center gap-3 p-2 bg-white rounded border hover:border-blue-400 cursor-pointer"
                      onClick={(e) => e.stopPropagation()}
                    >
                      <input
                        type="checkbox"
                        checked={selectedLists.includes(list.id)}
                        onChange={() => toggleList(list.id)}
                      />
                      <span className="font-medium text-sm">{list.name}</span>
                      <span className="text-xs text-gray-500">
                        ({list.contact_count} contatos)
                      </span>
                    </label>
                  ))}
                  {lists.length === 0 && (
                    <p className="text-sm text-gray-500">
                      Nenhuma lista criada ainda
                    </p>
                  )}
                </div>
              )}
            </div>
          </label>
          
          {/* Manual */}
          <label className="flex items-start gap-3 p-4 border rounded-lg hover:bg-gray-50 cursor-pointer">
            <input
              type="radio"
              checked={value.type === 'manual'}
              onChange={() => handleTypeChange('manual')}
              className="mt-1"
            />
            <div className="flex-1">
              <div className="flex items-center gap-2">
                <UserCheck className="h-5 w-5 text-gray-600" />
                <p className="font-medium">Seleção manual</p>
              </div>
              <p className="text-sm text-gray-500 mt-1">
                Escolher contatos individualmente
              </p>
              
              {value.type === 'manual' && (
                <div className="mt-3">
                  <p className="text-sm text-blue-600">
                    🚧 Em breve: Seletor de contatos individual
                  </p>
                </div>
              )}
            </div>
          </label>
        </div>
      </div>
      
      {/* Contador */}
      <Card className="p-4 bg-blue-50 border-blue-200">
        <div className="flex items-center justify-between">
          <div>
            <p className="text-sm text-gray-600">Contatos que receberão a campanha:</p>
            <p className="text-2xl font-bold text-blue-600 mt-1">
              {estimatedCount}
            </p>
          </div>
          <Users className="h-10 w-10 text-blue-400" />
        </div>
        
        {value.type !== 'all' && estimatedCount === 0 && (
          <p className="text-sm text-yellow-600 mt-2">
            ⚠️ Nenhum contato selecionado ainda
          </p>
        )}
        
        <p className="text-xs text-gray-500 mt-2">
          * Excluindo automaticamente contatos opted-out
        </p>
      </Card>
    </div>
  )
}





