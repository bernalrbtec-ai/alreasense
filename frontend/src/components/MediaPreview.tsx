import { useState } from 'react'
import { X, Download, ExternalLink, FileText, Music, Video, Image as ImageIcon } from 'lucide-react'

interface MediaPreviewProps {
  fileUrl: string
  thumbnailUrl?: string
  fileType: 'image' | 'audio' | 'document' | 'video'
  filename?: string
  fileSize?: number
  onClose?: () => void
  showDownload?: boolean
  className?: string
}

export function MediaPreview({
  fileUrl,
  thumbnailUrl,
  fileType,
  filename,
  fileSize,
  onClose,
  showDownload = true,
  className = ''
}: MediaPreviewProps) {
  const [imageError, setImageError] = useState(false)

  const formatFileSize = (bytes?: number) => {
    if (!bytes) return ''
    if (bytes < 1024) return `${bytes} B`
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
  }

  const handleDownload = () => {
    window.open(fileUrl, '_blank')
  }

  const renderPreview = () => {
    switch (fileType) {
      case 'image':
        return (
          <div className="relative group">
            {!imageError ? (
              <img
                src={thumbnailUrl || fileUrl}
                alt={filename || 'Image'}
                className="max-w-full max-h-96 rounded-lg cursor-pointer"
                onClick={() => window.open(fileUrl, '_blank')}
                onError={() => setImageError(true)}
              />
            ) : (
              <div className="w-full h-48 bg-gray-100 rounded-lg flex flex-col items-center justify-center text-gray-400">
                <ImageIcon className="w-12 h-12 mb-2" />
                <p className="text-sm">Erro ao carregar imagem</p>
                {showDownload && (
                  <button
                    onClick={handleDownload}
                    className="mt-2 text-blue-500 hover:text-blue-600 text-sm flex items-center gap-1"
                  >
                    <Download className="w-4 h-4" />
                    Baixar mesmo assim
                  </button>
                )}
              </div>
            )}

            {/* Overlay com ações */}
            {!imageError && (
              <div className="absolute inset-0 bg-black bg-opacity-0 group-hover:bg-opacity-30 transition-opacity rounded-lg flex items-center justify-center gap-2 opacity-0 group-hover:opacity-100">
                <button
                  onClick={() => window.open(fileUrl, '_blank')}
                  className="p-2 bg-white rounded-full hover:bg-gray-100 transition-colors"
                  title="Abrir em nova aba"
                >
                  <ExternalLink className="w-5 h-5 text-gray-700" />
                </button>
                {showDownload && (
                  <button
                    onClick={handleDownload}
                    className="p-2 bg-white rounded-full hover:bg-gray-100 transition-colors"
                    title="Baixar"
                  >
                    <Download className="w-5 h-5 text-gray-700" />
                  </button>
                )}
              </div>
            )}
          </div>
        )

      case 'audio':
        return (
          <div className="w-full max-w-md space-y-3">
            <div className="flex items-center gap-3 p-3 bg-blue-50 rounded-lg">
              <div className="w-12 h-12 bg-blue-100 rounded-full flex items-center justify-center">
                <Music className="w-6 h-6 text-blue-600" />
              </div>
              <div className="flex-1 min-w-0">
                {filename && (
                  <p className="text-sm font-medium text-gray-900 truncate">
                    {filename}
                  </p>
                )}
                {fileSize && (
                  <p className="text-xs text-gray-500">
                    {formatFileSize(fileSize)}
                  </p>
                )}
              </div>
            </div>

            <audio
              controls
              src={fileUrl}
              className="w-full"
              preload="metadata"
            >
              Seu navegador não suporta áudio.
            </audio>

            {showDownload && (
              <button
                onClick={handleDownload}
                className="w-full px-4 py-2 border border-gray-300 rounded-lg text-gray-700 hover:bg-gray-50 transition-colors flex items-center justify-center gap-2"
              >
                <Download className="w-4 h-4" />
                Baixar áudio
              </button>
            )}
          </div>
        )

      case 'video':
        return (
          <div className="w-full max-w-2xl space-y-3">
            <video
              controls
              src={fileUrl}
              poster={thumbnailUrl}
              className="w-full rounded-lg"
              preload="metadata"
            >
              Seu navegador não suporta vídeo.
            </video>

            {showDownload && (
              <button
                onClick={handleDownload}
                className="w-full px-4 py-2 border border-gray-300 rounded-lg text-gray-700 hover:bg-gray-50 transition-colors flex items-center justify-center gap-2"
              >
                <Download className="w-4 h-4" />
                Baixar vídeo
              </button>
            )}
          </div>
        )

      case 'document':
        return (
          <div className="w-full max-w-md space-y-3">
            <div className="p-6 bg-gray-50 rounded-lg border-2 border-dashed border-gray-300">
              <div className="flex flex-col items-center text-center">
                <div className="w-16 h-16 bg-red-100 rounded-full flex items-center justify-center mb-3">
                  <FileText className="w-8 h-8 text-red-600" />
                </div>
                {filename && (
                  <p className="text-sm font-medium text-gray-900 mb-1">
                    {filename}
                  </p>
                )}
                {fileSize && (
                  <p className="text-xs text-gray-500 mb-4">
                    {formatFileSize(fileSize)}
                  </p>
                )}

                <div className="flex gap-2">
                  <button
                    onClick={() => window.open(fileUrl, '_blank')}
                    className="px-4 py-2 bg-white border border-gray-300 rounded-lg text-gray-700 hover:bg-gray-50 transition-colors flex items-center gap-2"
                  >
                    <ExternalLink className="w-4 h-4" />
                    Abrir
                  </button>
                  {showDownload && (
                    <button
                      onClick={handleDownload}
                      className="px-4 py-2 bg-blue-500 text-white rounded-lg hover:bg-blue-600 transition-colors flex items-center gap-2"
                    >
                      <Download className="w-4 h-4" />
                      Baixar
                    </button>
                  )}
                </div>
              </div>
            </div>
          </div>
        )

      default:
        return (
          <div className="text-center text-gray-500">
            Tipo de arquivo não suportado
          </div>
        )
    }
  }

  return (
    <div className={`relative ${className}`}>
      {/* Close button */}
      {onClose && (
        <button
          onClick={onClose}
          className="absolute top-2 right-2 p-1 bg-white rounded-full shadow-md hover:bg-gray-100 transition-colors z-10"
        >
          <X className="w-5 h-5 text-gray-600" />
        </button>
      )}

      {/* Preview content */}
      {renderPreview()}
    </div>
  )
}

// Componente simplificado para thumbnails pequenos
interface MediaThumbnailProps {
  fileUrl: string
  thumbnailUrl?: string
  fileType: 'image' | 'audio' | 'document' | 'video'
  onClick?: () => void
  className?: string
}

export function MediaThumbnail({
  fileUrl,
  thumbnailUrl,
  fileType,
  onClick,
  className = ''
}: MediaThumbnailProps) {
  const [imageError, setImageError] = useState(false)

  const getIcon = () => {
    switch (fileType) {
      case 'audio':
        return <Music className="w-6 h-6" />
      case 'video':
        return <Video className="w-6 h-6" />
      case 'document':
        return <FileText className="w-6 h-6" />
      default:
        return <ImageIcon className="w-6 h-6" />
    }
  }

  const getIconColor = () => {
    switch (fileType) {
      case 'audio':
        return 'bg-blue-100 text-blue-600'
      case 'video':
        return 'bg-purple-100 text-purple-600'
      case 'document':
        return 'bg-red-100 text-red-600'
      default:
        return 'bg-gray-100 text-gray-600'
    }
  }

  if (fileType === 'image' && !imageError) {
    return (
      <div
        className={`relative w-16 h-16 rounded-lg overflow-hidden cursor-pointer hover:opacity-80 transition-opacity ${className}`}
        onClick={onClick}
      >
        <img
          src={thumbnailUrl || fileUrl}
          alt="Thumbnail"
          className="w-full h-full object-cover"
          onError={() => setImageError(true)}
        />
      </div>
    )
  }

  return (
    <div
      className={`w-16 h-16 rounded-lg flex items-center justify-center cursor-pointer hover:opacity-80 transition-opacity ${getIconColor()} ${className}`}
      onClick={onClick}
    >
      {getIcon()}
    </div>
  )
}

