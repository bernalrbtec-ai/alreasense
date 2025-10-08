import { useState, useEffect } from 'react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../components/ui/Card'
import { Button } from '../components/ui/Button'
import { api } from '../lib/api'
import { formatDate } from '../lib/utils'
import { FlaskConical, Play, BarChart3, Plus } from 'lucide-react'

interface PromptTemplate {
  id: number
  version: string
  body: string
  description: string
  is_active: boolean
  created_at: string
  created_by: string
}

interface ExperimentRun {
  id: number
  run_id: string
  name: string
  description: string
  prompt_version: string
  status: string
  total_messages: number
  processed_messages: number
  progress_percentage: number
  created_at: string
}

export default function ExperimentsPage() {
  const [prompts, setPrompts] = useState<PromptTemplate[]>([])
  const [experiments, setExperiments] = useState<ExperimentRun[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [activeTab, setActiveTab] = useState<'prompts' | 'experiments'>('prompts')

  useEffect(() => {
    fetchData()
  }, [])

  const fetchData = async () => {
    try {
      setIsLoading(true)
      const [promptsResponse, experimentsResponse] = await Promise.all([
        api.get('/experiments/prompts/'),
        api.get('/experiments/runs/')
      ])
      
      setPrompts(promptsResponse.data)
      setExperiments(experimentsResponse.data)
    } catch (error) {
      console.error('Failed to fetch data:', error)
    } finally {
      setIsLoading(false)
    }
  }

  const startExperiment = async (promptVersion: string) => {
    try {
      const response = await api.post('/experiments/replay/', {
        prompt_version: promptVersion,
        start_date: new Date(Date.now() - 7 * 24 * 60 * 60 * 1000).toISOString(), // 7 days ago
        end_date: new Date().toISOString(),
        name: `Teste ${promptVersion}`,
        description: 'Teste automático do prompt'
      })
      
      // Refresh experiments list
      fetchData()
    } catch (error) {
      console.error('Failed to start experiment:', error)
    }
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Experimentos</h1>
        <p className="text-gray-600">
          Gerencie prompts e execute experimentos de IA
        </p>
      </div>

      {/* Tabs */}
      <div className="border-b border-gray-200">
        <nav className="-mb-px flex space-x-8">
          <button
            onClick={() => setActiveTab('prompts')}
            className={`py-2 px-1 border-b-2 font-medium text-sm ${
              activeTab === 'prompts'
                ? 'border-blue-500 text-blue-600'
                : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
            }`}
          >
            <FlaskConical className="h-4 w-4 inline mr-2" />
            Prompts
          </button>
          <button
            onClick={() => setActiveTab('experiments')}
            className={`py-2 px-1 border-b-2 font-medium text-sm ${
              activeTab === 'experiments'
                ? 'border-blue-500 text-blue-600'
                : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
            }`}
          >
            <BarChart3 className="h-4 w-4 inline mr-2" />
            Experimentos
          </button>
        </nav>
      </div>

      {/* Prompts Tab */}
      {activeTab === 'prompts' && (
        <div className="space-y-6">
          <div className="flex items-center justify-between">
            <h2 className="text-lg font-semibold">Templates de Prompt</h2>
            <Button>
              <Plus className="h-4 w-4 mr-2" />
              Novo Prompt
            </Button>
          </div>

          {isLoading ? (
            <div className="flex items-center justify-center h-32">
              <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
            </div>
          ) : prompts.length === 0 ? (
            <Card>
              <CardContent className="text-center py-12">
                <FlaskConical className="h-12 w-12 text-gray-400 mx-auto mb-4" />
                <p className="text-gray-500 mb-4">Nenhum prompt configurado</p>
                <Button>
                  <Plus className="h-4 w-4 mr-2" />
                  Criar Primeiro Prompt
                </Button>
              </CardContent>
            </Card>
          ) : (
            <div className="grid gap-4">
              {Array.isArray(prompts) && prompts.map((prompt) => (
                <Card key={prompt.id}>
                  <CardHeader>
                    <div className="flex items-center justify-between">
                      <div>
                        <CardTitle className="flex items-center gap-2">
                          {prompt.version}
                          {prompt.is_active && (
                            <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-green-100 text-green-800">
                              Ativo
                            </span>
                          )}
                        </CardTitle>
                        <CardDescription>
                          Criado por {prompt.created_by} em {formatDate(prompt.created_at)}
                        </CardDescription>
                      </div>
                      <div className="flex gap-2">
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() => startExperiment(prompt.version)}
                        >
                          <Play className="h-4 w-4 mr-2" />
                          Testar
                        </Button>
                        <Button variant="outline" size="sm">
                          Editar
                        </Button>
                      </div>
                    </div>
                  </CardHeader>
                  <CardContent>
                    <p className="text-sm text-gray-600 mb-2">{prompt.description}</p>
                    <div className="bg-gray-50 p-3 rounded text-sm font-mono">
                      {prompt.body.substring(0, 200)}
                      {prompt.body.length > 200 && '...'}
                    </div>
                  </CardContent>
                </Card>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Experiments Tab */}
      {activeTab === 'experiments' && (
        <div className="space-y-6">
          <h2 className="text-lg font-semibold">Execuções de Experimentos</h2>

          {isLoading ? (
            <div className="flex items-center justify-center h-32">
              <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
            </div>
          ) : experiments.length === 0 ? (
            <Card>
              <CardContent className="text-center py-12">
                <BarChart3 className="h-12 w-12 text-gray-400 mx-auto mb-4" />
                <p className="text-gray-500">Nenhum experimento executado ainda</p>
              </CardContent>
            </Card>
          ) : (
            <div className="grid gap-4">
              {Array.isArray(experiments) && experiments.map((experiment) => (
                <Card key={experiment.id}>
                  <CardHeader>
                    <div className="flex items-center justify-between">
                      <div>
                        <CardTitle>{experiment.name}</CardTitle>
                        <CardDescription>
                          {experiment.description} • {formatDate(experiment.created_at)}
                        </CardDescription>
                      </div>
                      <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${
                        experiment.status === 'running' ? 'bg-blue-100 text-blue-800' :
                        experiment.status === 'completed' ? 'bg-green-100 text-green-800' :
                        experiment.status === 'failed' ? 'bg-red-100 text-red-800' :
                        'bg-gray-100 text-gray-800'
                      }`}>
                        {experiment.status}
                      </span>
                    </div>
                  </CardHeader>
                  <CardContent>
                    <div className="space-y-2">
                      <div className="flex justify-between text-sm">
                        <span>Prompt: {experiment.prompt_version}</span>
                        <span>Progresso: {experiment.processed_messages}/{experiment.total_messages}</span>
                      </div>
                      <div className="w-full bg-gray-200 rounded-full h-2">
                        <div 
                          className="bg-blue-600 h-2 rounded-full transition-all duration-300"
                          style={{ width: `${experiment.progress_percentage}%` }}
                        ></div>
                      </div>
                    </div>
                  </CardContent>
                </Card>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  )
}
