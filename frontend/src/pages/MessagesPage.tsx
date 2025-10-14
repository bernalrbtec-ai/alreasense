import { useState, useEffect } from 'react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../components/ui/Card'
import { Button } from '../components/ui/Button'
import { api } from '../lib/api'
import { formatDate, getSentimentEmoji, getSentimentColor, getEmotionEmoji } from '../lib/utils'
import { Search, Filter } from 'lucide-react'

interface Message {
  id: number
  chat_id: string
  sender: string
  text: string
  created_at: string
  sentiment: number | null
  emotion: string | null
  satisfaction: number | null
  tone: string | null
  summary: string | null
}

export default function MessagesPage() {
  const [messages, setMessages] = useState<Message[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [searchQuery, setSearchQuery] = useState('')
  const [currentPage, setCurrentPage] = useState(1)
  const [totalPages, setTotalPages] = useState(1)

  useEffect(() => {
    fetchMessages()
  }, [currentPage, searchQuery])

  const fetchMessages = async () => {
    try {
      setIsLoading(true)
      const params = new URLSearchParams({
        page: currentPage.toString(),
        ...(searchQuery && { search: searchQuery }),
      })
      
      const response = await api.get(`/messages/?${params}`)
      setMessages(response.data.results || response.data)
      
      if (response.data.count) {
        // Usar PAGE_SIZE padrão do backend (50) em vez de hardcode 20
        setTotalPages(Math.ceil(response.data.count / 50))
      }
    } catch (error) {
      console.error('Failed to fetch messages:', error)
    } finally {
      setIsLoading(false)
    }
  }

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault()
    setCurrentPage(1)
    fetchMessages()
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Mensagens</h1>
        <p className="text-gray-600">
          Visualize e analise todas as mensagens recebidas
        </p>
      </div>

      {/* Search and Filters */}
      <Card>
        <CardHeader>
          <CardTitle>Buscar Mensagens</CardTitle>
          <CardDescription>
            Encontre mensagens específicas ou use busca semântica
          </CardDescription>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleSearch} className="flex gap-4">
            <div className="flex-1">
              <div className="relative">
                <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-gray-400" />
                <input
                  type="text"
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  placeholder="Buscar mensagens..."
                  className="w-full pl-10 pr-4 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                />
              </div>
            </div>
            <Button type="submit">
              <Search className="h-4 w-4 mr-2" />
              Buscar
            </Button>
            <Button variant="outline">
              <Filter className="h-4 w-4 mr-2" />
              Filtros
            </Button>
          </form>
        </CardContent>
      </Card>

      {/* Messages List */}
      <div className="space-y-4">
        {isLoading ? (
          <div className="flex items-center justify-center h-32">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
          </div>
        ) : messages.length === 0 ? (
          <Card>
            <CardContent className="text-center py-12">
              <p className="text-gray-500">Nenhuma mensagem encontrada</p>
            </CardContent>
          </Card>
        ) : (
          Array.isArray(messages) && messages.map((message) => (
            <Card key={message.id}>
              <CardContent className="p-6">
                <div className="flex items-start justify-between">
                  <div className="flex-1">
                    <div className="flex items-center gap-2 mb-2">
                      <span className="text-sm font-medium text-gray-900">
                        {message.chat_id}
                      </span>
                      <span className="text-xs text-gray-500">
                        {formatDate(message.created_at)}
                      </span>
                    </div>
                    
                    <p className="text-gray-700 mb-3">{message.text}</p>
                    
                    {message.sentiment !== null && (
                      <div className="flex items-center gap-4 text-sm">
                        <div className="flex items-center gap-1">
                          <span>Sentimento:</span>
                          <span className={getSentimentColor(message.sentiment)}>
                            {getSentimentEmoji(message.sentiment)} {Number(message.sentiment).toFixed(2)}
                          </span>
                        </div>
                        
                        {message.emotion && (
                          <div className="flex items-center gap-1">
                            <span>Emoção:</span>
                            <span>
                              {getEmotionEmoji(message.emotion)} {message.emotion}
                            </span>
                          </div>
                        )}
                        
                        {message.satisfaction !== null && (
                          <div className="flex items-center gap-1">
                            <span>Satisfação:</span>
                            <span>{message.satisfaction}%</span>
                          </div>
                        )}
                      </div>
                    )}
                    
                    {message.summary && (
                      <div className="mt-2 p-2 bg-gray-50 rounded text-sm">
                        <strong>Resumo:</strong> {message.summary}
                      </div>
                    )}
                  </div>
                </div>
              </CardContent>
            </Card>
          ))
        )}
      </div>

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="flex items-center justify-center gap-2">
          <Button
            variant="outline"
            onClick={() => setCurrentPage(prev => Math.max(1, prev - 1))}
            disabled={currentPage === 1}
          >
            Anterior
          </Button>
          
          <span className="text-sm text-gray-600">
            Página {currentPage} de {totalPages}
          </span>
          
          <Button
            variant="outline"
            onClick={() => setCurrentPage(prev => Math.min(totalPages, prev + 1))}
            disabled={currentPage === totalPages}
          >
            Próxima
          </Button>
        </div>
      )}
    </div>
  )
}
