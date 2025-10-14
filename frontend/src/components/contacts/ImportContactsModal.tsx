import { useState, useRef, useEffect } from 'react'
import { X, Upload, FileText, AlertCircle, CheckCircle, Download, Loader, Info } from 'lucide-react'
import { Button } from '../ui/Button'
import { Card } from '../ui/Card'
import { api } from '../../lib/api'
import { showSuccessToast, showErrorToast, showLoadingToast, updateToastSuccess, updateToastError } from '../../lib/toastHelper'

interface ImportContactsModalProps {
  onClose: () => void
  onSuccess: () => void
}

interface PreviewData {
  status: string
  headers: string[]
  column_mapping: Record<string, string | null>
  sample_rows: any[]
  total_rows_detected: number
  validation_warnings: any[]
  delimiter: string
  has_ddd_separated: boolean
}

export default function ImportContactsModal({ onClose, onSuccess }: ImportContactsModalProps) {
  const [step, setStep] = useState(1) // 1=upload, 2=config, 3=preview, 4=processing, 5=result
  const [file, setFile] = useState<File | null>(null)
  const [previewData, setPreviewData] = useState<PreviewData | null>(null)
  const [isLoading, setIsLoading] = useState(false)
  const [tags, setTags] = useState<any[]>([])
  const [newTagName, setNewTagName] = useState('')
  const [showNewTagInput, setShowNewTagInput] = useState(false)
  const [showConsentModal, setShowConsentModal] = useState(false)
  
  const [config, setConfig] = useState({
    update_existing: false,
    all_have_consent: false,
    consent_source: '',
    consent_date: '',
    auto_tag_id: null as string | null,
  })
  
  const [importResult, setImportResult] = useState<any>(null)
  const [importId, setImportId] = useState<string | null>(null)
  const [progress, setProgress] = useState({
    current: 0,
    total: 0,
    created: 0,
    updated: 0,
    skipped: 0,
    errors: 0,
    percentage: 0
  })
  
  const fileInputRef = useRef<HTMLInputElement>(null)
  
  // Buscar tags ao montar
  useEffect(() => {
    fetchTags()
  }, [])
  
  const fetchTags = async () => {
    try {
      const response = await api.get('/contacts/tags/')
      setTags(response.data.results || response.data || [])
    } catch (error) {
      console.error('Erro ao buscar tags:', error)
    }
  }
  
  const handleCreateTag = async () => {
    if (!newTagName.trim()) return
    
    const toastId = showLoadingToast('criar', 'Tag')
    
    try {
      const response = await api.post('/contacts/tags/', {
        name: newTagName,
        color: '#3B82F6'  // Azul padrão
      })
      
      const newTag = response.data
      setTags([...tags, newTag])
      setConfig({ ...config, auto_tag_id: newTag.id })
      setNewTagName('')
      setShowNewTagInput(false)
      updateToastSuccess(toastId, 'criar', 'Tag')
    } catch (error: any) {
      updateToastError(toastId, 'criar', 'Tag', error)
    }
  }
  
  // Step 1: Upload
  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const selectedFile = e.target.files?.[0]
    if (selectedFile) {
      if (!selectedFile.name.endsWith('.csv')) {
        showErrorToast('selecionar', 'Arquivo', new Error('Arquivo deve ser .csv'))
        return
      }
      
      setFile(selectedFile)
    }
  }
  
  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault()
    const droppedFile = e.dataTransfer.files[0]
    if (droppedFile && droppedFile.name.endsWith('.csv')) {
      setFile(droppedFile)
    }
  }
  
  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault()
  }
  
  // Step 2 -> Step 3: Preview
  const handlePreview = async () => {
    if (!file) return
    
    // Validar tag selecionada
    if (!config.auto_tag_id) {
      showErrorToast('validar', 'Configuração', new Error('Selecione uma tag para identificar os contatos'))
      return
    }
    
    setIsLoading(true)
    const toastId = showLoadingToast('processar', 'Preview')
    
    try {
      const formData = new FormData()
      formData.append('file', file)
      
      const response = await api.post('/contacts/contacts/preview_csv/', formData, {
        headers: { 'Content-Type': 'multipart/form-data' }
      })
      
      setPreviewData(response.data)
      setStep(3)
      updateToastSuccess(toastId, 'processar', 'Preview')
    } catch (error: any) {
      updateToastError(toastId, 'processar', 'Preview', error)
    } finally {
      setIsLoading(false)
    }
  }
  
  // Step 3 -> Step 4/5: Import
  const handleImport = async () => {
    if (!file || !previewData) return
    
    setIsLoading(true)
    setStep(4)
    const toastId = showLoadingToast('importar', 'Contatos')
    
    try {
      const formData = new FormData()
      formData.append('file', file)
      formData.append('update_existing', config.update_existing.toString())
      formData.append('all_have_consent', config.all_have_consent.toString())
      
      if (config.all_have_consent) {
        formData.append('consent_source', config.consent_source)
        if (config.consent_date) {
          formData.append('consent_date', config.consent_date)
        }
      }
      
      if (config.auto_tag_id) {
        formData.append('auto_tag_id', config.auto_tag_id)
      }
      
      // Enviar column_mapping e delimiter do preview
      formData.append('column_mapping', JSON.stringify(previewData.column_mapping))
      formData.append('delimiter', previewData.delimiter)
      
      console.log('📤 Enviando para backend:', {
        column_mapping: previewData.column_mapping,
        delimiter: previewData.delimiter,
        update_existing: config.update_existing,
        all_have_consent: config.all_have_consent,
        auto_tag_id: config.auto_tag_id
      })
      
      const response = await api.post('/contacts/contacts/import_csv/', formData, {
        headers: { 'Content-Type': 'multipart/form-data' }
      })
      
      const result = response.data
      
      if (result.async_processing) {
        // Importação assíncrona - acompanhar progresso
        setImportId(result.import_id)
        startPolling(result.import_id)
        updateToastSuccess(toastId, 'iniciar', 'Importação')
      } else {
        // Importação síncrona - resultado imediato
        console.log('📤 Resultado da importação:', result)
        
        if (result.status === 'success' || result.status === 'completed') {
          updateToastSuccess(toastId, 'importar', 'Contatos')
          setImportResult(result)
          setStep(5)
          setIsLoading(false)
          
          // Chamar onSuccess após pequeno delay para mostrar resultado
          setTimeout(() => {
            onSuccess()
          }, 2000)
        } else {
          // Tratar diferentes tipos de erro
          let errorMessage = 'Erro desconhecido'
          
          if (result.message) {
            errorMessage = result.message
          } else if (result.error) {
            errorMessage = result.error
          } else if (result.errors_list && result.errors_list.length > 0) {
            errorMessage = result.errors_list[0].error || 'Erro na importação'
          }
          
          console.error('❌ Erro na importação:', { result, errorMessage })
          
          updateToastError(toastId, 'importar', 'Contatos', { message: errorMessage })
          setIsLoading(false)
          setStep(2) // Volta para configuração em vez de preview
          
          // Reset do arquivo e preview para permitir nova tentativa
          setFile(null)
          setPreviewData(null)
        }
      }
    } catch (error: any) {
      console.error('❌ Erro de rede/requisição na importação:', error)
      
      // Extrair mensagem de erro mais específica
      let errorMessage = 'Erro de conexão'
      
      if (error.response?.status === 400) {
        errorMessage = 'Dados inválidos no arquivo CSV'
      } else if (error.response?.status === 413) {
        errorMessage = 'Arquivo muito grande (máximo 10MB)'
      } else if (error.response?.status === 500) {
        errorMessage = 'Erro interno do servidor'
      } else if (error.code === 'NETWORK_ERROR' || !navigator.onLine) {
        errorMessage = 'Sem conexão com a internet'
      } else if (error.message) {
        errorMessage = error.message
      }
      
      updateToastError(toastId, 'importar', 'Contatos', { message: errorMessage })
      setIsLoading(false)
      setStep(2) // Volta para configuração para permitir nova tentativa
      
      // Reset do arquivo e preview para permitir nova tentativa
      setFile(null)
      setPreviewData(null)
    }
  }
  
  // Polling para acompanhar progresso
  const startPolling = (importId: string) => {
    const interval = setInterval(async () => {
      try {
        const response = await api.get(`/contacts/imports/${importId}/`)
        
        const status = response.data.status
        const total = response.data.total_rows || 0
        const processed = response.data.processed_rows || 0
        
        setProgress({
          current: processed,
          total: total,
          created: response.data.created_count || 0,
          updated: response.data.updated_count || 0,
          skipped: response.data.skipped_count || 0,
          errors: response.data.error_count || 0,
          percentage: total > 0 ? Math.round((processed / total) * 100) : 0
        })
        
        if (status === 'completed' || status === 'failed') {
          clearInterval(interval)
          setImportResult(response.data)
          setStep(5)
          setIsLoading(false)
          
          if (status === 'completed') {
            showSuccessToast('importar', 'Contatos')
          } else {
            showErrorToast('importar', 'Contatos', new Error('Importação falhou'))
          }
        }
      } catch (error) {
        console.error('Erro ao buscar progresso:', error)
        clearInterval(interval)
        setIsLoading(false)
      }
    }, 2000) // Poll a cada 2 segundos
  }
  
  const downloadTemplate = () => {
    const csvContent = 'Nome,phone,email,birth_date,city,state,notes\nMaria Silva,11999999999,maria@email.com,1990-05-15,São Paulo,SP,Cliente VIP\n'
    const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' })
    const link = document.createElement('a')
    link.href = URL.createObjectURL(blob)
    link.download = 'template_contatos.csv'
    link.click()
  }
  
  const resetAndClose = () => {
    setStep(1)
    setFile(null)
    setPreviewData(null)
    setImportResult(null)
    setProgress({ current: 0, total: 0, created: 0, updated: 0, skipped: 0, errors: 0, percentage: 0 })
    onClose()
  }
  
  return (
    <>
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
      <div className="bg-white rounded-lg shadow-xl max-w-4xl w-full max-h-[90vh] overflow-y-auto">
        {/* Header */}
          <div className="flex justify-between items-center p-4 border-b">
          <div>
              <h2 className="text-xl font-bold">Importar Contatos</h2>
            <div className="flex items-center gap-2 mt-2">
              {[1, 2, 3, 4, 5].map((s) => (
                <div
                  key={s}
                    className={`h-2 w-10 rounded ${
                    s === step ? 'bg-blue-600' : s < step ? 'bg-green-500' : 'bg-gray-200'
                  }`}
                />
              ))}
            </div>
          </div>
          <button onClick={resetAndClose} className="text-gray-400 hover:text-gray-600">
            <X className="h-6 w-6" />
          </button>
        </div>
        
        {/* Body */}
          <div className="p-4">
          {/* STEP 1: UPLOAD */}
          {step === 1 && (
              <div className="space-y-4">
              <div
                onDrop={handleDrop}
                onDragOver={handleDragOver}
                  className="border-2 border-dashed border-gray-300 rounded-lg p-8 text-center hover:border-blue-400 transition-colors cursor-pointer"
                onClick={() => fileInputRef.current?.click()}
              >
                  <Upload className="mx-auto h-10 w-10 text-gray-400 mb-3" />
                <input
                  ref={fileInputRef}
                  type="file"
                  accept=".csv"
                  onChange={handleFileSelect}
                  className="hidden"
                />
                  <p className="text-base font-medium mb-1">
                  Clique para selecionar ou arraste o arquivo aqui
                </p>
                  <p className="text-xs text-gray-500">
                  CSV, máximo 10 MB (até 50.000 contatos)
                </p>
              </div>
              
              {file && (
                  <Card className="p-3 bg-gray-50">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-3">
                        <FileText className="h-6 w-6 text-blue-600" />
                      <div>
                          <p className="font-medium text-sm">{file.name}</p>
                          <p className="text-xs text-gray-500">
                          {(file.size / 1024).toFixed(1)} KB
                        </p>
                      </div>
                    </div>
                    <button
                      onClick={(e) => {
                        e.stopPropagation()
                        setFile(null)
                      }}
                      className="text-red-500 hover:text-red-700"
                    >
                      <X className="h-5 w-5" />
                    </button>
                  </div>
                </Card>
              )}
              
                <div className="flex justify-between items-center">
                  <Button variant="outline" onClick={downloadTemplate} size="sm">
                  <Download className="h-4 w-4 mr-2" />
                  Baixar Template CSV
                </Button>
                  
                  <div className="flex gap-2">
                    <Button variant="outline" onClick={onClose} size="sm">
                  Cancelar
                </Button>
                    <Button onClick={() => setStep(2)} disabled={!file} size="sm">
                      Próximo
                </Button>
                  </div>
              </div>
            </div>
          )}
          
            {/* STEP 2: CONFIGURAÇÃO (COMPACTO) */}
          {step === 2 && (
              <div className="space-y-4">
                <h3 className="text-lg font-semibold">Configurações</h3>
              
                {/* Duplicatas */}
              <div>
                <label className="block text-sm font-medium mb-2">
                    Contatos duplicados
                </label>
                  <div className="grid grid-cols-2 gap-2">
                    <label className="flex items-center gap-2 p-2 border rounded hover:bg-gray-50 cursor-pointer text-sm">
                    <input
                      type="radio"
                      checked={!config.update_existing}
                      onChange={() => setConfig({ ...config, update_existing: false })}
                    />
                    <div>
                        <p className="font-medium">Pular</p>
                        <p className="text-xs text-gray-500">Ignorar existentes</p>
                    </div>
                  </label>
                  
                    <label className="flex items-center gap-2 p-2 border rounded hover:bg-gray-50 cursor-pointer text-sm">
                    <input
                      type="radio"
                      checked={config.update_existing}
                      onChange={() => setConfig({ ...config, update_existing: true })}
                    />
                    <div>
                        <p className="font-medium">Atualizar</p>
                        <p className="text-xs text-gray-500">Sobrescrever dados</p>
                    </div>
                  </label>
                </div>
              </div>
              
                {/* Tag - OBRIGATÓRIO */}
                <div className="border-l-4 border-blue-400 bg-blue-50 p-3 rounded">
                  <label className="block text-sm font-semibold text-blue-800 mb-2">
                    🏷️ Tag de Identificação *
                  </label>
                  
                  <select
                    value={config.auto_tag_id || ''}
                    onChange={(e) => setConfig({ ...config, auto_tag_id: e.target.value || null })}
                    className="w-full px-3 py-2 text-sm border rounded focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                    required
                  >
                    <option value="">Selecione uma tag...</option>
                    {tags.map((tag) => (
                      <option key={tag.id} value={tag.id}>
                        {tag.name}
                      </option>
                    ))}
                  </select>
                  
                  {!config.auto_tag_id && (
                    <p className="text-xs text-red-600 mt-1">* Obrigatório</p>
                  )}
                  
                  {/* Criar nova tag (inline compacto) */}
                  {!showNewTagInput ? (
                    <button
                      type="button"
                      onClick={() => setShowNewTagInput(true)}
                      className="text-xs text-blue-600 hover:text-blue-700 font-medium mt-2"
                    >
                      + Criar nova tag
                    </button>
                  ) : (
                    <div className="flex gap-2 mt-2">
                      <input
                        type="text"
                        value={newTagName}
                        onChange={(e) => setNewTagName(e.target.value)}
                        placeholder="Nome da nova tag"
                        className="flex-1 px-2 py-1 text-sm border rounded focus:ring-2 focus:ring-blue-500"
                        onKeyPress={(e) => e.key === 'Enter' && handleCreateTag()}
                      />
                      <Button type="button" size="sm" onClick={handleCreateTag}>
                        Criar
                      </Button>
                      <Button 
                        type="button" 
                        variant="outline" 
                        size="sm" 
                        onClick={() => {
                          setShowNewTagInput(false)
                          setNewTagName('')
                        }}
                      >
                        ✕
                      </Button>
                    </div>
                  )}
                </div>
                
                {/* Consentimento LGPD (Compacto) */}
                <div className="border-l-4 border-yellow-400 bg-yellow-50 p-3 rounded">
                  <div className="flex items-start justify-between gap-3">
                    <label className="flex items-start gap-2 flex-1 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={config.all_have_consent}
                    onChange={(e) => setConfig({ ...config, all_have_consent: e.target.checked })}
                    className="mt-1"
                  />
                  <div>
                    <p className="text-sm font-medium text-gray-900">
                          Contatos autorizaram receber mensagens
                    </p>
                        <p className="text-xs text-gray-600">
                          ⚠️ Necessário para enviar campanhas
                    </p>
                  </div>
                </label>
                
                    <button
                      type="button"
                      onClick={() => setShowConsentModal(true)}
                      className="text-yellow-700 hover:text-yellow-800"
                      title="Mais informações sobre LGPD"
                    >
                      <Info className="h-5 w-5" />
                    </button>
                    </div>
              </div>
              
                <div className="flex justify-end gap-2">
                  <Button variant="outline" onClick={() => setStep(1)} size="sm">
                  Voltar
                </Button>
                  <Button 
                    onClick={handlePreview} 
                    disabled={!config.auto_tag_id || isLoading}
                    size="sm"
                  >
                    {isLoading ? 'Carregando...' : 'Próximo: Preview'}
                </Button>
              </div>
            </div>
          )}
          
          {/* STEP 3: PREVIEW */}
          {step === 3 && previewData && (
              <div className="space-y-4">
                <div className="flex justify-between items-center">
                  <h3 className="text-lg font-semibold">Preview dos Dados</h3>
                  <span className="text-sm text-gray-500">
                    ~{previewData.total_rows_detected} linhas detectadas
                  </span>
              </div>
              
                {/* Mapeamento de colunas */}
                <div className="bg-gray-50 p-3 rounded text-sm">
                  <p className="font-medium mb-2">Mapeamento de Colunas</p>
                  <div className="grid grid-cols-2 gap-2 text-xs">
                    {Object.entries(previewData.column_mapping).map(([csvCol, dbField]) => (
                    <div key={csvCol} className="flex items-center gap-2">
                        <span className="text-gray-600">{csvCol}</span>
                      <span>→</span>
                        <span className="font-medium">
                          {dbField || <span className="text-gray-400">ignorado</span>}
                      </span>
                    </div>
                  ))}
                </div>
              </div>
              
                {/* Preview da tabela */}
                <div className="overflow-x-auto max-h-64 overflow-y-auto border rounded">
                  <table className="min-w-full divide-y divide-gray-200 text-xs">
                  <thead className="bg-gray-50 sticky top-0">
                    <tr>
                        {Object.keys(previewData.column_mapping).map((header) => (
                          <th key={header} className="px-3 py-2 text-left font-medium text-gray-700">
                          {header}
                        </th>
                      ))}
                    </tr>
                  </thead>
                    <tbody className="bg-white divide-y divide-gray-200">
                      {previewData.sample_rows.slice(0, 10).map((row, idx) => (
                        <tr key={idx} className="hover:bg-gray-50">
                          {Object.keys(previewData.column_mapping).map((header, colIdx) => (
                            <td key={colIdx} className="px-3 py-2 text-gray-900">
                              {row[header] || '-'}
                          </td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              
                {/* Avisos */}
                {previewData.validation_warnings && previewData.validation_warnings.length > 0 && (
                  <div className="bg-yellow-50 border border-yellow-200 rounded p-3">
                    <div className="flex items-start gap-2">
                      <AlertCircle className="h-4 w-4 text-yellow-600 mt-0.5 flex-shrink-0" />
                      <div className="text-xs">
                        <p className="font-medium text-yellow-800 mb-1">Avisos:</p>
                        <ul className="list-disc list-inside space-y-1 text-yellow-700">
                          {previewData.validation_warnings.slice(0, 5).map((warning, idx) => (
                            <li key={idx}>{warning}</li>
                          ))}
                        </ul>
                      </div>
                    </div>
                  </div>
                )}
                
                <div className="flex justify-end gap-2">
                  <Button variant="outline" onClick={() => setStep(2)} size="sm">
                  Voltar
                </Button>
                  <Button onClick={handleImport} disabled={isLoading} size="sm">
                    {isLoading ? 'Importando...' : 'Confirmar Importação'}
                </Button>
              </div>
            </div>
          )}
          
            {/* STEP 4: PROCESSANDO */}
          {step === 4 && (
            <div className="text-center py-8">
                <Loader className="h-12 w-12 animate-spin text-blue-600 mx-auto mb-4" />
                <h3 className="text-lg font-semibold mb-2">Processando Importação...</h3>
                
                {importId ? (
                  <>
                    <div className="w-full bg-gray-200 rounded-full h-3 mb-4 max-w-md mx-auto">
                      <div
                        className="bg-blue-600 h-3 rounded-full transition-all"
                    style={{ width: `${progress.percentage}%` }}
                  />
                </div>
                    <p className="text-sm text-gray-600">
                      {progress.current} de {progress.total} contatos processados ({progress.percentage}%)
                </p>
                    <div className="flex justify-center gap-4 mt-4 text-xs">
                      <span className="text-green-600">✓ Criados: {progress.created}</span>
                      <span className="text-blue-600">↻ Atualizados: {progress.updated}</span>
                      <span className="text-gray-600">⊘ Ignorados: {progress.skipped}</span>
                      <span className="text-red-600">✗ Erros: {progress.errors}</span>
              </div>
                  </>
                ) : (
                  <p className="text-sm text-gray-600">Aguarde enquanto processamos os contatos...</p>
                )}
            </div>
          )}
          
            {/* STEP 5: RESULTADO */}
          {step === 5 && importResult && (
              <div className="space-y-4">
              <div className="text-center">
                  {importResult.status === 'completed' ? (
                    <>
                      <CheckCircle className="h-12 w-12 text-green-600 mx-auto mb-3" />
                      <h3 className="text-lg font-semibold text-green-600 mb-2">
                  Importação Concluída!
                </h3>
                    </>
                  ) : (
                    <>
                      <AlertCircle className="h-12 w-12 text-red-600 mx-auto mb-3" />
                      <h3 className="text-lg font-semibold text-red-600 mb-2">
                        Importação Concluída com Erros
                      </h3>
                    </>
                  )}
              </div>
              
                {/* Estatísticas */}
                <div className="grid grid-cols-2 gap-3">
                  <Card className="p-3">
                    <p className="text-xs text-gray-500">Criados</p>
                    <p className="text-2xl font-bold text-green-600">{importResult.created_count || 0}</p>
                </Card>
                  <Card className="p-3">
                    <p className="text-xs text-gray-500">Atualizados</p>
                    <p className="text-2xl font-bold text-blue-600">{importResult.updated_count || 0}</p>
                </Card>
                  <Card className="p-3">
                    <p className="text-xs text-gray-500">Ignorados</p>
                    <p className="text-2xl font-bold text-gray-600">{importResult.skipped_count || 0}</p>
                </Card>
                  <Card className="p-3">
                    <p className="text-xs text-gray-500">Erros</p>
                    <p className="text-2xl font-bold text-red-600">{importResult.error_count || 0}</p>
                </Card>
              </div>
              
                {/* Erros detalhados */}
              {importResult.errors && importResult.errors.length > 0 && (
                  <div className="bg-red-50 border border-red-200 rounded p-3 max-h-32 overflow-y-auto">
                    <p className="text-sm font-medium text-red-800 mb-2">Erros encontrados ({importResult.errors.length}):</p>
                    <ul className="list-disc list-inside space-y-1 text-xs text-red-700">
                      {importResult.errors.slice(0, 10).map((error: string, idx: number) => (
                        <li key={idx}>{error}</li>
                      ))}
                    </ul>
                </div>
              )}
              
                <div className="flex justify-center">
                  <Button onClick={resetAndClose} size="sm">
                    Fechar
                </Button>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
      
      {/* MODAL DE CONSENTIMENTO LGPD */}
      {showConsentModal && (
        <div className="fixed inset-0 bg-black bg-opacity-60 flex items-center justify-center z-[60] p-4">
          <div className="bg-white rounded-lg shadow-xl max-w-2xl w-full max-h-[80vh] overflow-y-auto">
            <div className="p-6">
              <div className="flex justify-between items-start mb-4">
                <div className="flex items-center gap-3">
                  <AlertCircle className="h-8 w-8 text-yellow-600" />
                  <div>
                    <h3 className="text-xl font-bold">Consentimento LGPD</h3>
                    <p className="text-sm text-gray-500">Lei Geral de Proteção de Dados</p>
                  </div>
                </div>
                <button 
                  onClick={() => setShowConsentModal(false)}
                  className="text-gray-400 hover:text-gray-600"
                >
                  <X className="h-6 w-6" />
                </button>
              </div>
              
              <div className="space-y-4 text-sm">
                <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
                  <h4 className="font-semibold text-blue-900 mb-2">📋 O que é necessário?</h4>
                  <p className="text-blue-800">
                    Para enviar mensagens via WhatsApp, você precisa ter o <strong>consentimento explícito</strong> de cada contato,
                    confirmando que eles autorizaram receber comunicações da sua empresa.
                  </p>
                </div>
                
                <div className="space-y-3">
                  <h4 className="font-semibold text-gray-900">✅ Formas válidas de obter consentimento:</h4>
                  <ul className="list-disc list-inside space-y-2 text-gray-700 ml-2">
                    <li>Checkbox em formulário online (com texto claro sobre o uso)</li>
                    <li>Termo de aceite assinado fisicamente</li>
                    <li>Cadastro presencial com autorização verbal documentada</li>
                    <li>Opt-in em landing page ou evento</li>
                    <li>Aceite em aplicativo ou chatbot</li>
                  </ul>
                </div>
                
                <div className="space-y-3">
                  <h4 className="font-semibold text-gray-900">❌ NÃO é consentimento válido:</h4>
                  <ul className="list-disc list-inside space-y-2 text-gray-700 ml-2">
                    <li>Comprar listas de contatos</li>
                    <li>Adicionar números que você "encontrou"</li>
                    <li>Usar contatos de cartão de visita sem autorização</li>
                    <li>Presumir consentimento ("ele deve querer receber")</li>
                  </ul>
                </div>
                
                <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-4">
                  <h4 className="font-semibold text-yellow-900 mb-2">⚠️ Importante:</h4>
                  <ul className="list-disc list-inside space-y-1 text-yellow-800 ml-2">
                    <li>Você deve manter <strong>registros</strong> de como obteve o consentimento</li>
                    <li>Contatos podem <strong>revogar</strong> o consentimento a qualquer momento</li>
                    <li>Multas por descumprimento podem chegar a <strong>R$ 50 milhões</strong></li>
                  </ul>
                </div>
                
                <div className="bg-green-50 border border-green-200 rounded-lg p-4">
                  <h4 className="font-semibold text-green-900 mb-2">💡 Recomendação:</h4>
                  <p className="text-green-800">
                    Ao marcar o checkbox de consentimento, preencha:
                  </p>
                  <ul className="list-disc list-inside space-y-1 text-green-700 ml-2 mt-2">
                    <li><strong>Fonte:</strong> Onde obteve o consentimento (ex: "Formulário do site", "Evento X")</li>
                    <li><strong>Data:</strong> Quando o consentimento foi dado</li>
                  </ul>
                  <p className="text-green-800 mt-2">
                    Essas informações ajudam em auditorias e comprovam a conformidade com a LGPD.
                  </p>
                </div>
              </div>
              
              <div className="mt-6 flex justify-between items-center">
                <a 
                  href="https://www.gov.br/cidadania/pt-br/acesso-a-informacao/lgpd" 
                  target="_blank" 
                  rel="noopener noreferrer"
                  className="text-sm text-blue-600 hover:text-blue-700 font-medium"
                >
                  Saiba mais sobre a LGPD →
                </a>
                
                <div className="flex gap-3">
                  <Button 
                    variant="outline" 
                    onClick={() => setShowConsentModal(false)}
                    size="sm"
                  >
                    Fechar
                  </Button>
                  <Button 
                    onClick={() => {
                      setShowConsentModal(false)
                      setConfig({ ...config, all_have_consent: true })
                    }}
                    size="sm"
                  >
                    Confirmar Consentimento
                  </Button>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}
    </>
  )
}
