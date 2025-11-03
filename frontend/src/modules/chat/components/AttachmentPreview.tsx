/**
 * AttachmentPreview - Visualiza diferentes tipos de anexos
 * 
 * Suporta:
 * - Imagens: Preview inline + lightbox
 * - Vídeos: Player HTML5
 * - Áudios: Player customizado estilo WhatsApp
 * - Documentos: Ícone + download
 * - IA: Transcrição + Resumo (se addon ativo)
 */
import React, { useState, useRef, useEffect } from 'react';
import { Download, FileText, X, Play, Pause } from 'lucide-react';
// Removed unused imports: Image, Video, Music

interface Attachment {
  id: string;
  original_filename: string;
  mime_type: string;
  file_url: string;
  size_bytes: number;
  is_image: boolean;
  is_video: boolean;
  is_audio: boolean;
  is_document: boolean;
  metadata?: Record<string, any> | null;  // ✅ Adicionar metadata
  // ✨ Campos IA (podem ser null)
  transcription?: string | null;
  ai_summary?: string | null;
  ai_tags?: string[] | null;
  processing_status?: 'pending' | 'processing' | 'completed' | 'failed' | 'skipped';
}

interface AttachmentPreviewProps {
  attachment: Attachment;
  showAI?: boolean;  // Se tenant tem addon Flow AI
}

export function AttachmentPreview({ attachment, showAI = false }: AttachmentPreviewProps) {
  const [lightboxOpen, setLightboxOpen] = useState(false);
  
  // 🎵 Estados do player de áudio
  const [isPlaying, setIsPlaying] = useState(false);
  const [currentTime, setCurrentTime] = useState(0);
  const [duration, setDuration] = useState(0);
  const audioRef = useRef<HTMLAudioElement>(null);
  
  // Atualizar progresso do áudio
  useEffect(() => {
    const audio = audioRef.current;
    if (!audio) return;
    
    const updateTime = () => setCurrentTime(audio.currentTime);
    const updateDuration = () => setDuration(audio.duration);
    const handleEnded = () => setIsPlaying(false);
    
    audio.addEventListener('timeupdate', updateTime);
    audio.addEventListener('loadedmetadata', updateDuration);
    audio.addEventListener('ended', handleEnded);
    
    return () => {
      audio.removeEventListener('timeupdate', updateTime);
      audio.removeEventListener('loadedmetadata', updateDuration);
      audio.removeEventListener('ended', handleEnded);
    };
  }, []);
  
  // Formatar tempo (segundos → MM:SS)
  const formatTime = (seconds: number) => {
    if (isNaN(seconds)) return '0:00';
    const mins = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    return `${mins}:${secs.toString().padStart(2, '0')}`;
  };
  
  // Toggle play/pause
  const togglePlay = () => {
    const audio = audioRef.current;
    if (!audio) return;
    
    if (isPlaying) {
      audio.pause();
    } else {
      audio.play();
    }
    setIsPlaying(!isPlaying);
  };
  
  // Seek no áudio
  const handleSeek = (e: React.MouseEvent<HTMLDivElement>) => {
    const audio = audioRef.current;
    if (!audio || !duration) return;
    
    const rect = e.currentTarget.getBoundingClientRect();
    const x = e.clientX - rect.left;
    const percentage = x / rect.width;
    audio.currentTime = percentage * duration;
  };

  // 🖼️ IMAGEM
  if (attachment.is_image) {
    // ✅ Verificar se está processando, tem erro ou se file_url é inválido
    const fileUrl = (attachment.file_url || '').trim();
    const metadata = attachment.metadata || {};
    const hasError = Boolean(metadata.error);
    // ✅ IMPORTANTE: Se file_url é válido (proxy), não mostrar como processando
    // Isso resolve race condition onde attachment foi processado mas metadata ainda tem flag
    const hasValidUrl = fileUrl && 
                       !fileUrl.includes('whatsapp.net') && 
                       !fileUrl.includes('evo.') &&
                       fileUrl.includes('/api/chat/media-proxy');
    const isProcessing = !hasValidUrl && (metadata.processing || !fileUrl || 
                         fileUrl.includes('whatsapp.net') || 
                         fileUrl.includes('evo.'));
    
    if (hasError) {
      // Mostrar erro de processamento
      return (
        <div className="attachment-preview image">
          <div className="max-w-xs rounded-lg bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 flex items-center justify-center p-4" style={{ minHeight: '150px' }}>
            <div className="text-red-600 dark:text-red-400 text-sm text-center">
              <p className="font-semibold">❌ Erro ao processar imagem</p>
              <p className="text-xs mt-1 opacity-75">{metadata.error || 'Erro desconhecido'}</p>
            </div>
          </div>
        </div>
      );
    }
    
    if (isProcessing) {
      // Skeleton/Loading enquanto processa
      return (
        <div className="attachment-preview image">
          <div className="max-w-xs rounded-lg bg-gray-200 dark:bg-gray-700 animate-pulse flex items-center justify-center" style={{ height: '200px' }}>
            <div className="text-gray-400 text-sm">Processando imagem...</div>
          </div>
        </div>
      );
    }
    
    // Imagem pronta
    return (
      <div className="attachment-preview image">
        <img
          src={fileUrl}
          alt={attachment.original_filename}
          crossOrigin="anonymous"
          className="max-w-xs rounded-lg cursor-pointer hover:opacity-90 transition"
          onClick={() => setLightboxOpen(true)}
          onError={(e) => {
            const img = e.currentTarget;
            const currentUrl = img.src;
            
            // ✅ Log detalhado do erro
            console.error('❌ [AttachmentPreview] Erro ao carregar imagem:', {
              url: fileUrl,
              currentSrc: currentUrl,
              retried: img.dataset.retried,
              naturalWidth: img.naturalWidth,
              naturalHeight: img.naturalHeight,
              complete: img.complete
            });
            
            // ✅ Não esconder imediatamente - pode ser erro temporário de rede/CORS
            // Tentar reload uma vez após 1 segundo com cache bust
            if (!img.dataset.retried) {
              img.dataset.retried = 'true';
              console.log('🔄 [AttachmentPreview] Tentando retry após 1 segundo...');
              setTimeout(() => {
                // ✅ Adicionar timestamp para bypass cache do browser
                const retryUrl = fileUrl + (fileUrl.includes('?') ? '&' : '?') + '_retry=' + Date.now();
                console.log('🔄 [AttachmentPreview] Retry URL:', retryUrl.substring(0, 100) + '...');
                img.src = retryUrl;
              }, 1000);
            } else {
              // ✅ Se já tentou uma vez, mostrar mensagem de erro ao invés de esconder
              console.warn('⚠️ [AttachmentPreview] Retry falhou, imagem não pôde ser carregada');
              // Não esconder - manter visível para debug
              img.style.opacity = '0.3';
              img.style.border = '2px solid red';
            }
          }}
        />
        
        {/* Lightbox */}
        {lightboxOpen && (
          <div 
            className="fixed inset-0 bg-black bg-opacity-90 z-50 flex items-center justify-center p-4"
            onClick={() => setLightboxOpen(false)}
          >
            <button
              className="absolute top-4 right-4 text-white hover:text-gray-300"
              onClick={() => setLightboxOpen(false)}
            >
              <X size={32} />
            </button>
            <img
              src={fileUrl}
              alt={attachment.original_filename}
              className="max-w-full max-h-full object-contain"
            />
          </div>
        )}
      </div>
    );
  }

  // 🎥 VÍDEO
  if (attachment.is_video) {
    const fileUrl = (attachment.file_url || '').trim();
    const metadata = attachment.metadata || {};
    const hasError = Boolean(metadata.error);
    // ✅ IMPORTANTE: Se file_url é válido (proxy), não mostrar como processando
    const hasValidUrl = fileUrl && 
                       !fileUrl.includes('whatsapp.net') && 
                       !fileUrl.includes('evo.') &&
                       fileUrl.includes('/api/chat/media-proxy');
    const isProcessing = !hasValidUrl && (metadata.processing || !fileUrl || 
                         fileUrl.includes('whatsapp.net') || 
                         fileUrl.includes('evo.'));
    
    if (hasError) {
      // Mostrar erro de processamento
      return (
        <div className="attachment-preview video max-w-md">
          <div className="rounded-lg bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 flex items-center justify-center p-4" style={{ minHeight: '200px' }}>
            <div className="text-red-600 dark:text-red-400 text-sm text-center">
              <p className="font-semibold">❌ Erro ao processar vídeo</p>
              <p className="text-xs mt-1 opacity-75">{metadata.error || 'Erro desconhecido'}</p>
            </div>
          </div>
        </div>
      );
    }
    
    if (isProcessing) {
      return (
        <div className="attachment-preview video">
          <div className="max-w-md rounded-lg bg-gray-200 dark:bg-gray-700 animate-pulse flex items-center justify-center" style={{ height: '300px' }}>
            <div className="text-gray-400 text-sm">Processando vídeo...</div>
          </div>
        </div>
      );
    }
    
    return (
      <div className="attachment-preview video max-w-md">
        <video
          controls
          className="w-full rounded-lg"
          preload="metadata"
          onError={() => {
            console.error('❌ [AttachmentPreview] Erro ao carregar vídeo:', {
              file_url: fileUrl.substring(0, 50),
              mime_type: attachment.mime_type
            });
          }}
        >
          <source src={fileUrl} type={attachment.mime_type} />
          Seu navegador não suporta vídeo.
        </video>
        <p className="text-xs text-gray-500 mt-1">{attachment.original_filename}</p>
      </div>
    );
  }

  // 🎵 ÁUDIO (player customizado estilo WhatsApp - responsivo)
  if (attachment.is_audio) {
    const progress = duration > 0 ? (currentTime / duration) * 100 : 0;
    
    // ✅ Detectar se áudio está disponível e é reproduzível
    // URL válida = não vazia, não é URL temporária do WhatsApp/Evolution, não é arquivo criptografado (.enc)
    const fileUrl = (attachment.file_url || '').trim();
    const metadata = attachment.metadata || {};
    const hasError = Boolean(metadata.error);
    const isEncrypted = fileUrl.includes('.enc') || 
                       attachment.original_filename?.toLowerCase().endsWith('.enc') ||
                       attachment.mime_type === 'application/octet-stream';
    
    const isAudioReady = Boolean(
      !hasError &&
      fileUrl.length > 0 &&
      !fileUrl.includes('whatsapp.net') &&  // NÃO é URL temporária do WhatsApp
      !fileUrl.includes('evo.') &&          // NÃO é URL da Evolution API
      !metadata.processing &&               // NÃO está processando
      !isEncrypted                           // NÃO é arquivo criptografado
    );
    
    // Mostrar erro se houver
    if (hasError) {
      return (
        <div className="attachment-preview audio w-full">
          <div className="flex items-center gap-3 sm:gap-4 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg p-3 sm:p-4 w-full">
            <div className="flex-shrink-0 w-10 h-10 sm:w-11 sm:h-11 rounded-full flex items-center justify-center bg-red-500">
              <span className="text-white text-xs">⚠️</span>
            </div>
            <div className="flex-1 min-w-0">
              <p className="text-red-600 dark:text-red-400 text-sm font-semibold">Erro ao processar áudio</p>
              <p className="text-red-500 dark:text-red-500 text-xs mt-1">{metadata.error || 'Erro desconhecido'}</p>
            </div>
          </div>
        </div>
      );
    }
    
    return (
      <div className="attachment-preview audio w-full">
        {/* Player estilo WhatsApp - responsivo e com largura maior */}
        <div className="flex items-center gap-3 sm:gap-4 bg-white rounded-lg p-3 sm:p-4 shadow-sm w-full">
          {/* Botão Play/Pause - levemente maior */}
          <button
            onClick={togglePlay}
            disabled={!isAudioReady}
            className={`flex-shrink-0 w-10 h-10 sm:w-11 sm:h-11 rounded-full flex items-center justify-center transition-colors ${
              isAudioReady 
                ? 'bg-green-500 hover:bg-green-600 cursor-pointer' 
                : 'bg-gray-300 cursor-not-allowed'
            }`}
            title={isAudioReady ? (isPlaying ? 'Pausar' : 'Reproduzir') : (isEncrypted ? 'Áudio criptografado - não pode ser reproduzido' : 'Baixando áudio...')}
          >
            {!isAudioReady ? (
              isEncrypted ? (
                <span className="text-white text-xs">🔒</span>
              ) : (
                <div className="w-5 h-5 border-2 border-white border-t-transparent rounded-full animate-spin" />
              )
            ) : isPlaying ? (
              <Pause className="text-white" size={20} fill="white" />
            ) : (
              <Play className="text-white ml-0.5" size={20} fill="white" />
            )}
          </button>
          
          {/* Progress Bar + Tempo */}
          <div className="flex-1 min-w-0">
            {/* Progress Bar - mais alta em mobile */}
            <div
              className="h-1.5 sm:h-1.5 bg-gray-200 rounded-full cursor-pointer mb-1.5 sm:mb-1"
              onClick={isAudioReady ? handleSeek : undefined}
            >
              <div
                className="h-full bg-green-500 rounded-full transition-all"
                style={{ width: `${progress}%` }}
              />
            </div>
            
            {/* Tempo atual / total - ajustado para mobile */}
            <div className="flex items-center justify-between text-[10px] sm:text-xs text-gray-500">
              <span>{isAudioReady ? formatTime(currentTime) : 'Baixando...'}</span>
              <span>{isAudioReady ? formatTime(duration) : '--:--'}</span>
            </div>
          </div>
        </div>
        
        {/* Áudio HTML5 (hidden - só para controle) */}
        {isAudioReady && !isEncrypted && fileUrl && (
          <audio
            ref={audioRef}
            src={fileUrl}
            preload="metadata"
            className="hidden"
            onLoadedMetadata={() => {
              if (audioRef.current) {
                setDuration(audioRef.current.duration);
              }
            }}
            onTimeUpdate={() => {
              if (audioRef.current) {
                setCurrentTime(audioRef.current.currentTime);
              }
            }}
            onEnded={() => setIsPlaying(false)}
            onError={() => {
              const error = audioRef.current?.error;
              console.error('❌ [AttachmentPreview] Erro ao carregar áudio:', {
                file_url: fileUrl.substring(0, 50),
                error_code: error?.code,
                error_message: error?.message,
                mime_type: attachment.mime_type,
                is_encrypted: isEncrypted
              });
              setIsPlaying(false);
              // Se for erro de codec não suportado, tentar marcar como não reproduzível
              if (error?.code === MediaError.MEDIA_ERR_SRC_NOT_SUPPORTED) {
                console.warn('⚠️ [AttachmentPreview] Formato de áudio não suportado pelo navegador');
              }
            }}
          />
        )}

        {/* ✨ TRANSCRIÇÃO IA (se disponível e addon ativo) */}
        {showAI && attachment.transcription && (
          <div className="mt-3 p-3 bg-white rounded border border-gray-200">
            <p className="text-xs font-semibold text-gray-700 mb-1">📝 Transcrição:</p>
            <p className="text-sm text-gray-600">{attachment.transcription}</p>
          </div>
        )}

        {/* ✨ RESUMO IA */}
        {showAI && attachment.ai_summary && (
          <div className="mt-2 p-3 bg-indigo-50 rounded border border-indigo-200">
            <p className="text-xs font-semibold text-indigo-700 mb-1">🧠 Resumo IA:</p>
            <p className="text-sm text-indigo-900">{attachment.ai_summary}</p>
          </div>
        )}

        {/* ✨ TAGS IA */}
        {showAI && attachment.ai_tags && attachment.ai_tags.length > 0 && (
          <div className="mt-2 flex flex-wrap gap-1">
            {attachment.ai_tags.map((tag, i) => (
              <span
                key={i}
                className="px-2 py-1 bg-indigo-100 text-indigo-700 text-xs rounded"
              >
                {tag}
              </span>
            ))}
          </div>
        )}
      </div>
    );
  }

  // 📄 DOCUMENTO
  return (
    <div className="attachment-preview document flex items-center gap-3 p-3 bg-gray-50 rounded-lg max-w-md">
      <FileText className="text-gray-600" size={24} />
      <div className="flex-1 min-w-0">
        <p className="text-sm font-medium truncate">{attachment.original_filename}</p>
        <p className="text-xs text-gray-500">
          {(attachment.size_bytes / 1024).toFixed(0)} KB
        </p>
      </div>
      <a
        href={attachment.file_url}
        download={attachment.original_filename}
        className="p-2 bg-white border border-gray-300 rounded hover:bg-gray-100"
      >
        <Download size={18} />
      </a>
    </div>
  );
}


