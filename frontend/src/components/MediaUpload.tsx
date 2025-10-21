import { useState, useRef } from 'react'
import { Upload, X, Image, File, Music, Video, Loader2 } from 'lucide-react'
import { toast } from 'sonner'
import { api } from '@/lib/api'

interface MediaUploadProps {
  onUploadComplete: (fileUrl: string, thumbnailUrl?: string, fileType?: string) => void
  onCancel?: () => void
  accept?: string
  maxSize?: number // em MB
  showPreview?: boolean
}

export function MediaUpload({
  onUploadComplete,
  onCancel,
  accept = 'image/*,audio/*,video/*,.pdf,.doc,.docx,.xls,.xlsx',
  maxSize = 25, // 25MB
  showPreview = true
}: MediaUploadProps) {
  const [file, setFile] = useState<File | null>(null)
  const [preview, setPreview] = useState<string | null>(null)
  const [uploading, setUploading] = useState(false)
  const [progress, setProgress] = useState(0)
  const fileInputRef = useRef<HTMLInputElement>(null)

  const getFileIcon = (type: string) => {
    if (type.startsWith('image/')) return <Image className="w-8 h-8" />
    if (type.startsWith('audio/')) return <Music className="w-8 h-8" />
    if (type.startsWith('video/')) return <Video className="w-8 h-8" />
    return <File className="w-8 h-8" />
  }

  const formatFileSize = (bytes: number) => {
    if (bytes < 1024) return `${bytes} B`
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
  }

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const selectedFile = e.target.files?.[0]
    if (!selectedFile) return

    // Validar tamanho
    const maxBytes = maxSize * 1024 * 1024
    if (selectedFile.size > maxBytes) {
      toast.error('Arquivo muito grande', {
        description: `Tamanho máximo: ${maxSize}MB`
      })
      return
    }

    setFile(selectedFile)

    // Preview para imagens
    if (selectedFile.type.startsWith('image/') && showPreview) {
      const reader = new FileReader()
      reader.onload = (e) => {
        setPreview(e.target?.result as string)
      }
      reader.readAsDataURL(selectedFile)
    }
  }

  const handleUpload = async () => {
    if (!file) return

    setUploading(true)
    setProgress(0)

    try {
      // Criar FormData
      const formData = new FormData()
      formData.append('file', file)

      // Simular progresso (pode ser substituído por XMLHttpRequest para progresso real)
      const progressInterval = setInterval(() => {
        setProgress((prev) => {
          if (prev >= 90) {
            clearInterval(progressInterval)
            return 90
          }
          return prev + 10
        })
      }, 200)

      // Upload
      const response = await api.post('/chat/upload-media/', formData, {
        headers: {
          'Content-Type': 'multipart/form-data'
        }
      })

      clearInterval(progressInterval)
      setProgress(100)

      if (response.data.success) {
        toast.success('Upload concluído!', {
          description: `${file.name} enviado com sucesso`
        })

        onUploadComplete(
          response.data.file_url,
          response.data.thumbnail_url,
          response.data.file_type
        )

        // Reset
        setFile(null)
        setPreview(null)
        setProgress(0)
      } else {
        throw new Error(response.data.error || 'Erro no upload')
      }
    } catch (error: any) {
      console.error('❌ [UPLOAD] Erro:', error)
      toast.error('Erro no upload', {
        description: error.response?.data?.error || error.message || 'Tente novamente'
      })
    } finally {
      setUploading(false)
    }
  }

  const handleCancel = () => {
    setFile(null)
    setPreview(null)
    setProgress(0)
    setUploading(false)
    if (fileInputRef.current) {
      fileInputRef.current.value = ''
    }
    onCancel?.()
  }

  return (
    <div className="bg-white rounded-lg shadow-lg p-4 space-y-4">
      {/* File Input */}
      {!file && (
        <div>
          <label
            htmlFor="file-upload"
            className="flex flex-col items-center justify-center w-full h-32 border-2 border-dashed border-gray-300 rounded-lg cursor-pointer hover:border-blue-500 hover:bg-gray-50 transition-colors"
          >
            <Upload className="w-8 h-8 text-gray-400 mb-2" />
            <p className="text-sm text-gray-600">
              Clique para selecionar ou arraste o arquivo
            </p>
            <p className="text-xs text-gray-400 mt-1">
              Máx: {maxSize}MB
            </p>
          </label>
          <input
            id="file-upload"
            ref={fileInputRef}
            type="file"
            className="hidden"
            accept={accept}
            onChange={handleFileSelect}
            disabled={uploading}
          />
        </div>
      )}

      {/* File Preview */}
      {file && (
        <div className="space-y-3">
          {/* Preview/Icon */}
          <div className="flex items-center gap-3 p-3 bg-gray-50 rounded-lg">
            {preview ? (
              <img
                src={preview}
                alt="Preview"
                className="w-16 h-16 object-cover rounded"
              />
            ) : (
              <div className="w-16 h-16 flex items-center justify-center bg-gray-200 rounded text-gray-500">
                {getFileIcon(file.type)}
              </div>
            )}

            <div className="flex-1 min-w-0">
              <p className="text-sm font-medium text-gray-900 truncate">
                {file.name}
              </p>
              <p className="text-xs text-gray-500">
                {formatFileSize(file.size)}
              </p>
            </div>

            {!uploading && (
              <button
                onClick={handleCancel}
                className="p-1 hover:bg-gray-200 rounded transition-colors"
              >
                <X className="w-5 h-5 text-gray-500" />
              </button>
            )}
          </div>

          {/* Progress Bar */}
          {uploading && (
            <div className="space-y-2">
              <div className="w-full bg-gray-200 rounded-full h-2">
                <div
                  className="bg-blue-500 h-2 rounded-full transition-all duration-300"
                  style={{ width: `${progress}%` }}
                />
              </div>
              <p className="text-xs text-gray-500 text-center">
                {progress < 100 ? `Enviando... ${progress}%` : 'Processando...'}
              </p>
            </div>
          )}

          {/* Actions */}
          {!uploading && (
            <div className="flex gap-2">
              <button
                onClick={handleCancel}
                className="flex-1 px-4 py-2 border border-gray-300 rounded-lg text-gray-700 hover:bg-gray-50 transition-colors"
              >
                Cancelar
              </button>
              <button
                onClick={handleUpload}
                className="flex-1 px-4 py-2 bg-blue-500 text-white rounded-lg hover:bg-blue-600 transition-colors flex items-center justify-center gap-2"
              >
                <Upload className="w-4 h-4" />
                Enviar
              </button>
            </div>
          )}

          {uploading && (
            <div className="flex items-center justify-center gap-2 py-2">
              <Loader2 className="w-5 h-5 animate-spin text-blue-500" />
              <span className="text-sm text-gray-600">Enviando arquivo...</span>
            </div>
          )}
        </div>
      )}
    </div>
  )
}

