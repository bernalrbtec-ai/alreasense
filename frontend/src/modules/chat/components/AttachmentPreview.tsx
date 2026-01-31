/**
 * AttachmentPreview - Visualiza diferentes tipos de anexos
 * 
 * Suporta:
 * - Imagens: Preview inline + lightbox com ZOOM 🔍
 * - Vídeos: Player HTML5
 * - Áudios: Player customizado estilo WhatsApp
 * - Documentos: Ícone + download
 * - IA: Transcrição + Resumo (se addon ativo)
 */
import React, { useState, useRef, useEffect } from 'react';
import { createPortal } from 'react-dom';
import { Download, FileText, X, Play, Pause, AlertCircle, ZoomIn, ZoomOut, Maximize2 } from 'lucide-react';
import { TransformWrapper, TransformComponent } from 'react-zoom-pan-pinch';
import { showWarningToast } from '@/lib/toastHelper';
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
  transcription_language?: string | null;
  ai_summary?: string | null;
  ai_tags?: string[] | null;
  ai_metadata?: Record<string, any> | null;
  processing_status?: 'pending' | 'processing' | 'completed' | 'failed' | 'skipped';
}

interface AttachmentPreviewProps {
  attachment: Attachment;
  showAI?: boolean;  // Se tenant tem addon Flow AI
  showTranscription?: boolean;
}

export function AttachmentPreview({ attachment, showAI = false, showTranscription = false }: AttachmentPreviewProps) {
  const [lightboxOpen, setLightboxOpen] = useState(false);
  const [isTranscriptionCollapsed, setIsTranscriptionCollapsed] = useState(false);
  
  // 🎵 Estados do player de áudio
  const [isPlaying, setIsPlaying] = useState(false);
  const [currentTime, setCurrentTime] = useState(0);
  const [duration, setDuration] = useState(0);
  const audioRef = useRef<HTMLAudioElement>(null);
  
  // ✅ Fechar lightbox com ESC e prevenir scroll do body
  useEffect(() => {
    if (!lightboxOpen) return;
    
    // Prevenir scroll do body quando modal está aberto
    document.body.style.overflow = 'hidden';
    
    const handleEscape = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        setLightboxOpen(false);
      }
    };
    
    window.addEventListener('keydown', handleEscape);
    
    return () => {
      document.body.style.overflow = '';
      window.removeEventListener('keydown', handleEscape);
    };
  }, [lightboxOpen]);
  
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
          // ✅ REMOVIDO: crossOrigin="anonymous" - pode estar causando problema de CORS preflight
          // Se a imagem não carregar, o servidor já está configurado para aceitar qualquer origem
          className="max-w-xs rounded-lg cursor-pointer hover:opacity-90 transition-all hover:shadow-lg"
          onClick={() => setLightboxOpen(true)}
          title="Clique para ampliar"
          onLoad={(e) => {
            const img = e.currentTarget;
            const blobUrl = (img as any).__blobUrl;
            
            // ✅ Limpar blob URL se foi usado
            if (blobUrl) {
              console.log('✅ [AttachmentPreview] Imagem carregada via blob URL, limpando...');
              URL.revokeObjectURL(blobUrl);
              delete (img as any).__blobUrl;
            }
            
            console.log('✅ [AttachmentPreview] Imagem carregada com sucesso:', {
              url: fileUrl, // ✅ URL COMPLETA - sem truncar
              naturalWidth: img.naturalWidth,
              naturalHeight: img.naturalHeight,
              viaBlob: !!blobUrl
            });
          }}
          onError={async (e) => {
            const img = e.currentTarget;
            const currentUrl = img.src;
            const error = (img as any).error;
            
            // ✅ Tentar fazer fetch direto para ver o que está vindo do servidor
            try {
              const response = await fetch(currentUrl, { method: 'GET', mode: 'cors' });
              const blob = await response.blob();
              const blobUrl = URL.createObjectURL(blob);
              
              // ✅ Expandir objeto para garantir que todos os detalhes sejam visíveis
              const fetchDetails = {
                status: response.status,
                statusText: response.statusText,
                contentType: response.headers.get('content-type'),
                contentLength: response.headers.get('content-length'),
                blobSize: blob.size,
                blobType: blob.type,
                blobUrl: blobUrl,
                allHeaders: Object.fromEntries(response.headers.entries())
              };
              
              // ✅ Log individual de cada propriedade para garantir visibilidade
              console.log('🔍 [AttachmentPreview] Fetch direto da URL:');
              console.log('   Status:', response.status, response.statusText);
              console.log('   Content-Type:', response.headers.get('content-type'));
              console.log('   Content-Length:', response.headers.get('content-length'));
              console.log('   Blob Size:', blob.size, 'bytes');
              console.log('   Blob Type:', blob.type);
              console.log('   Todos os headers:', fetchDetails.allHeaders);
              console.log('   Detalhes completos:', fetchDetails);
              
              // ✅ CRUCIAL: Usar blob URL diretamente na imagem principal
              // Se fetch retornou 200 OK com blob válido, usar o blob URL
              if (response.status === 200 && blob.size > 0 && blob.type.startsWith('image/')) {
                console.log('✅ [AttachmentPreview] Usando blob URL diretamente:', {
                  blobSize: blob.size,
                  blobType: blob.type,
                  blobUrl: blobUrl.substring(0, 50) + '...'
                });
                
                // ✅ Armazenar blob URL para limpar depois
                (img as any).__blobUrl = blobUrl;
                
                // ✅ Usar blob URL diretamente (manter handlers originais)
                img.src = blobUrl;
                
                // ✅ Não substituir handlers - deixar os originais funcionarem
                // O onLoad original vai limpar o blob URL
              } else {
                console.warn('⚠️ [AttachmentPreview] Blob inválido, não usando blob URL:', {
                  status: response.status,
                  blobSize: blob.size,
                  blobType: blob.type
                });
                URL.revokeObjectURL(blobUrl);
              }
              
            } catch (fetchError) {
              console.error('❌ [AttachmentPreview] Erro ao fazer fetch direto:', fetchError);
            }
            
            // ✅ Log MUITO detalhado do erro para debug - URL COMPLETA
            console.error('❌ [AttachmentPreview] Erro ao carregar imagem:', {
              fileUrl: fileUrl, // ✅ URL COMPLETA - sem truncar
              currentSrc: currentUrl, // ✅ URL COMPLETA - sem truncar
              retried: img.dataset.retried,
              naturalWidth: img.naturalWidth,
              naturalHeight: img.naturalHeight,
              complete: img.complete,
              error: error ? {
                code: error.code,
                message: error.message,
                type: error.type
              } : 'N/A',
              // Verificar se é problema de CORS/Mixed Content
              isSameOrigin: new URL(fileUrl, window.location.href).origin === window.location.origin,
              protocol: new URL(fileUrl, window.location.href).protocol,
              pageProtocol: window.location.protocol
            });
            
            // ✅ Tentar carregar sem crossOrigin primeiro (se não foi tentado)
            if (!img.dataset.retried) {
              img.dataset.retried = 'true';
              console.log('🔄 [AttachmentPreview] Tentando retry após 1 segundo...');
              setTimeout(() => {
                // ✅ Adicionar timestamp para bypass cache do browser
                const retryUrl = fileUrl + (fileUrl.includes('?') ? '&' : '?') + '_retry=' + Date.now();
                console.log('🔄 [AttachmentPreview] Retry URL:', retryUrl); // ✅ URL COMPLETA
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
        
        {/* Lightbox - Fullscreen com ZOOM usando Portal */}
        {lightboxOpen && typeof document !== 'undefined' && createPortal(
          <div 
            className="fixed inset-0 bg-black bg-opacity-95 z-[9999] flex items-center justify-center animate-fade-in"
            style={{
              backdropFilter: 'blur(4px)',
              width: '100vw',
              height: '100vh',
              padding: 0,
              margin: 0,
              position: 'fixed',
              top: 0,
              left: 0,
              right: 0,
              bottom: 0,
            }}
          >
            <TransformWrapper
              initialScale={1}
              minScale={0.5}
              maxScale={5}
              doubleClick={{ mode: "toggle", step: 0.5 }}
              wheel={{ step: 0.1 }}
              panning={{ disabled: false }}
              centerOnInit={true}
              limitToBounds={false}
            >
              {({ zoomIn, zoomOut, resetTransform, instance }) => (
                <>
                  {/* Botão Fechar */}
                  <button
                    className="absolute top-4 right-4 z-[10000] p-3 bg-black/60 hover:bg-black/80 rounded-full text-white transition-all hover:scale-110 shadow-lg"
                    onClick={(e) => {
                      e.stopPropagation();
                      setLightboxOpen(false);
                    }}
                    title="Fechar (ESC)"
                    aria-label="Fechar modal"
                  >
                    <X size={24} />
                  </button>

                  {/* Botão Download */}
                  <button
                    className="absolute top-4 right-20 z-[10000] p-3 bg-black/60 hover:bg-black/80 rounded-full text-white transition-all hover:scale-110 shadow-lg"
                    onClick={async (e) => {
                      e.stopPropagation();
                      
                      // ✅ Verificar se arquivo existe antes de baixar
                      try {
                        let response = await fetch(fileUrl, { method: 'HEAD' }).catch(() => null);
                        
                        if (!response || !response.ok) {
                          response = await fetch(fileUrl, { 
                            method: 'GET',
                            headers: { 'Range': 'bytes=0-0' }
                          }).catch(() => null);
                        }
                        
                        if (!response || !response.ok) {
                          try {
                            const errorResponse = await fetch(fileUrl, { method: 'GET' });
                            const contentType = errorResponse.headers.get('content-type');
                            if (contentType?.includes('application/json')) {
                              const errorData = await errorResponse.json();
                              if (errorData.error === 'Arquivo indisponível') {
                                showWarningToast('Anexo indisponível', errorData.message || 'O arquivo não está mais disponível no servidor');
                                return;
                              }
                            }
                          } catch {
                            // Ignorar erro ao tentar ler JSON
                          }
                          showWarningToast('Anexo indisponível', 'Não foi possível acessar o arquivo');
                          return;
                        }
                        
                        // Arquivo existe, fazer download
                        const link = document.createElement('a');
                        link.href = fileUrl;
                        link.download = attachment.original_filename || 'image.jpg';
                        link.target = '_blank';
                        link.rel = 'noopener noreferrer';
                        document.body.appendChild(link);
                        link.click();
                        document.body.removeChild(link);
                      } catch (error) {
                        console.error('Erro ao verificar/download arquivo:', error);
                        showWarningToast('Anexo indisponível', 'Não foi possível acessar o arquivo');
                      }
                    }}
                    title="Baixar imagem"
                    aria-label="Baixar imagem"
                  >
                    <Download size={24} />
                  </button>

                  {/* 🔍 CONTROLES DE ZOOM - Canto inferior direito */}
                  <div className="absolute bottom-6 right-6 z-[10000] flex flex-col gap-2">
                    {/* Zoom In */}
                    <button
                      className="p-3 bg-black/60 hover:bg-black/80 rounded-full text-white transition-all hover:scale-110 shadow-lg"
                      onClick={() => {
                        zoomIn();
                      }}
                      title="Aumentar zoom (scroll up)"
                      aria-label="Aumentar zoom"
                    >
                      <ZoomIn size={20} />
                    </button>

                    {/* Zoom Out */}
                    <button
                      className="p-3 bg-black/60 hover:bg-black/80 rounded-full text-white transition-all hover:scale-110 shadow-lg"
                      onClick={() => {
                        zoomOut();
                      }}
                      title="Diminuir zoom (scroll down)"
                      aria-label="Diminuir zoom"
                    >
                      <ZoomOut size={20} />
                    </button>

                    {/* Reset Zoom */}
                    <button
                      className="p-3 bg-black/60 hover:bg-black/80 rounded-full text-white transition-all hover:scale-110 shadow-lg"
                      onClick={() => {
                        resetTransform();
                      }}
                      title="Resetar zoom (double-click)"
                      aria-label="Resetar zoom"
                    >
                      <Maximize2 size={20} />
                    </button>
                  </div>

                  {/* 📊 INDICADOR DE ZOOM - Canto inferior esquerdo */}
                  {instance.transformState.scale !== 1 && (
                    <div className="absolute bottom-6 left-6 z-[10000] px-4 py-2 bg-black/60 rounded-full text-white text-sm font-medium shadow-lg">
                      {(instance.transformState.scale * 100).toFixed(0)}%
                    </div>
                  )}

                  {/* 💡 DICA DE USO - Aparece brevemente */}
                  {instance.transformState.scale === 1 && (
                    <div className="absolute bottom-6 left-1/2 transform -translate-x-1/2 z-[10000] px-4 py-2 bg-black/60 rounded-full text-white text-xs opacity-70 animate-pulse">
                      🖱️ Scroll para zoom • 🖐️ Arraste para mover • 👆 Double-click para resetar
                    </div>
                  )}

                  {/* 🖼️ Imagem com Zoom/Pan */}
                  <TransformComponent
                    wrapperStyle={{
                      width: '100vw',
                      height: '100vh',
                      cursor: instance.transformState.scale > 1 ? 'grab' : 'default',
                    }}
                    contentStyle={{
                      width: '100%',
                      height: '100%',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                    }}
                  >
                    <img
                      src={fileUrl}
                      alt={attachment.original_filename}
                      className="object-contain select-none"
                      onError={(e) => {
                        console.error('❌ [AttachmentPreview] Erro ao carregar imagem no lightbox:', {
                          fileUrl: fileUrl.substring(0, 100),
                          filename: attachment.original_filename
                        });
                      }}
                      draggable={false}
                      style={{
                        userSelect: 'none',
                        WebkitUserSelect: 'none',
                        maxWidth: '90vw',
                        maxHeight: '90vh',
                        width: 'auto',
                        height: 'auto',
                        display: 'block',
                      }}
                    />
                  </TransformComponent>
                </>
              )}
            </TransformWrapper>
          </div>,
          document.body
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

        {/* ✨ TRANSCRIÇÃO IA (mostrar quando habilitado no tenant) */}
        {(showTranscription || showAI) && (attachment.transcription || attachment.ai_metadata?.transcription?.status === 'processing') && (
          <div className="mt-3 p-3 bg-white rounded border border-gray-200">
            <div className="flex items-center justify-between mb-1">
              <button
                type="button"
                onClick={() => setIsTranscriptionCollapsed((prev) => !prev)}
                className="text-xs font-semibold text-gray-700 hover:text-gray-900"
                title="Minimizar/expandir transcrição"
              >
                📝 Transcrição:
              </button>
              {attachment.transcription_language && (
                <span className="text-xs text-gray-500">
                  {attachment.transcription_language.toUpperCase()}
                </span>
              )}
            </div>
            {!isTranscriptionCollapsed && (
              <p className="text-sm text-gray-600">
                {attachment.transcription || 'Transcrevendo...'}
              </p>
            )}
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
            {attachment.ai_tags.map((tag, tagIndex) => (
              <span
                key={tagIndex}
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

  // 📄 DOCUMENTO (estilo WhatsApp - vertical com ícone grande)
  // ✅ MELHORIA: Usar nome original ou fallback melhor
  const filename = attachment.original_filename || attachment.mime_type?.split('/')[1] || 'document';
  const fileExt = filename.toLowerCase().split('.').pop() || '';
  const metadata = attachment.metadata || {};
  const fileUrl = (attachment.file_url || '').trim();
  // ✅ CORREÇÃO: Verificar se URL é válida (proxy) antes de considerar como processando
  // Se file_url é válido (proxy), não mostrar como processando
  const hasValidUrl = fileUrl && 
                     !fileUrl.includes('whatsapp.net') && 
                     !fileUrl.includes('evo.') &&
                     fileUrl.includes('/api/chat/media-proxy');
  const isProcessing = !hasValidUrl && (!!metadata.processing || !fileUrl || 
                       fileUrl.includes('whatsapp.net') || 
                       fileUrl.includes('evo.'));
  const hasError = Boolean(metadata.error);
  const isPDF = attachment.mime_type === 'application/pdf' || fileExt === 'pdf';
  const isWord = fileExt === 'doc' || fileExt === 'docx' || 
                 attachment.mime_type?.includes('word');
  const isExcel = fileExt === 'xls' || fileExt === 'xlsx' || 
                  attachment.mime_type?.includes('spreadsheet');
  const isPowerPoint = fileExt === 'ppt' || fileExt === 'pptx' || 
                       attachment.mime_type?.includes('presentation');
  
  // Cores e estilos baseados no tipo de arquivo (estilo WhatsApp)
  const getDocumentStyle = () => {
    if (isPDF) {
      return {
        bgColor: 'bg-red-50',
        iconColor: 'text-red-600',
        iconBg: 'bg-red-100',
        borderColor: 'border-red-200'
      };
    } else if (isWord) {
      return {
        bgColor: 'bg-blue-50',
        iconColor: 'text-blue-600',
        iconBg: 'bg-blue-100',
        borderColor: 'border-blue-200'
      };
    } else if (isExcel) {
      return {
        bgColor: 'bg-green-50',
        iconColor: 'text-green-600',
        iconBg: 'bg-green-100',
        borderColor: 'border-green-200'
      };
    } else if (isPowerPoint) {
      return {
        bgColor: 'bg-orange-50',
        iconColor: 'text-orange-600',
        iconBg: 'bg-orange-100',
        borderColor: 'border-orange-200'
      };
    } else {
      return {
        bgColor: 'bg-gray-50',
        iconColor: 'text-gray-600',
        iconBg: 'bg-gray-100',
        borderColor: 'border-gray-200'
      };
    }
  };

  const docStyle = getDocumentStyle();
  
  if (hasError) {
    return (
      <div className="attachment-preview document max-w-xs rounded-lg border border-red-200 bg-red-50 p-4">
        <div className="flex items-center gap-3 text-red-600">
          <AlertCircle size={24} />
          <div>
            <p className="text-sm font-semibold">Erro ao processar arquivo</p>
            <p className="text-xs opacity-80">{metadata.error || 'Não foi possível concluir o processamento do arquivo.'}</p>
          </div>
        </div>
      </div>
    );
  }
  
  if (isProcessing) {
    return (
      <div className="attachment-preview document max-w-xs rounded-lg border border-gray-200 bg-gray-50 p-4">
        <div className="flex flex-col items-center gap-3 text-gray-500">
          <div className="w-12 h-12 rounded-full border-4 border-gray-200 border-t-gray-400 animate-spin" />
          {/* ✅ MELHORIA: Mostrar nome do arquivo mesmo durante processamento */}
          {filename && filename !== 'document' && (
            <p className="text-sm font-medium text-gray-700 text-center max-w-full truncate px-2" title={filename}>
              {filename}
            </p>
          )}
          <p className="text-sm font-medium">Processando arquivo...</p>
          <p className="text-xs text-center opacity-70">Você será notificado automaticamente assim que o download estiver disponível.</p>
        </div>
      </div>
    );
  }
  
  // Formatar tamanho do arquivo
  const formatFileSize = (bytes: number) => {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  };

  const handleDocumentClick = async (e: React.MouseEvent) => {
    e.preventDefault();
    e.stopPropagation();
    
    if (hasError) {
      showWarningToast('Arquivo indisponível', metadata.error || 'Erro ao processar o arquivo.');
      return;
    }
    
    if (isProcessing) {
      showWarningToast('Processando arquivo', 'Ainda estamos preparando este arquivo. Tente novamente em alguns segundos.');
      return;
    }
    
    // ✅ NOVO: Verificar se arquivo existe antes de abrir/baixar
    try {
      // Tentar HEAD primeiro (mais rápido), se falhar, tentar GET com range
      let response = await fetch(fileUrl, { method: 'HEAD' }).catch(() => null);
      
      // Se HEAD não funcionar, tentar GET com range (primeiros bytes)
      if (!response || !response.ok) {
        response = await fetch(fileUrl, { 
          method: 'GET',
          headers: { 'Range': 'bytes=0-0' } // Apenas primeiro byte
        }).catch(() => null);
      }
      
      if (!response || !response.ok) {
        // Tentar verificar se é resposta JSON de erro
        try {
          const errorResponse = await fetch(fileUrl, { method: 'GET' });
          const contentType = errorResponse.headers.get('content-type');
          if (contentType?.includes('application/json')) {
            const errorData = await errorResponse.json();
            if (errorData.error === 'Arquivo indisponível') {
              showWarningToast('Anexo indisponível', errorData.message || 'O arquivo não está mais disponível no servidor');
              return;
            }
          }
        } catch {
          // Ignorar erro ao tentar ler JSON
        }
        showWarningToast('Anexo indisponível', 'Não foi possível acessar o arquivo');
        return;
      }
      
      // Arquivo existe, proceder com abertura/download
      if (isPDF) {
        // ✅ PDF: Abrir em nova aba para não quebrar autenticação
        const newWindow = window.open(fileUrl, '_blank', 'noopener,noreferrer');
        if (!newWindow) {
          // Se popup foi bloqueado, tentar download direto
          const link = document.createElement('a');
          link.href = fileUrl;
          link.download = filename;
          link.target = '_blank';
          link.rel = 'noopener noreferrer';
          document.body.appendChild(link);
          link.click();
          document.body.removeChild(link);
        }
      } else if (isWord || isExcel || isPowerPoint) {
        // ✅ Word, Excel, PowerPoint: Download direto (abre no aplicativo padrão)
        const link = document.createElement('a');
        link.href = fileUrl;
        link.download = filename;
        link.target = '_blank';
        link.rel = 'noopener noreferrer';
        // Forçar download para abrir no aplicativo padrão
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
      } else {
        // Outros documentos: Tentar abrir em nova aba, fallback para download
        const newWindow = window.open(fileUrl, '_blank', 'noopener,noreferrer');
        if (!newWindow) {
          // Se popup foi bloqueado, tentar download direto
          const link = document.createElement('a');
          link.href = fileUrl;
          link.download = filename;
          link.target = '_blank';
          link.rel = 'noopener noreferrer';
          document.body.appendChild(link);
          link.click();
          document.body.removeChild(link);
        }
      }
    } catch (error) {
      console.error('Erro ao verificar/acessar arquivo:', error);
      showWarningToast('Anexo indisponível', 'Não foi possível acessar o arquivo');
    }
  };

  const handleDocumentDownload = async (e: React.MouseEvent) => {
    e.preventDefault();
    e.stopPropagation();
    
    if (hasError) {
      showWarningToast('Arquivo indisponível', metadata.error || 'Erro ao processar o arquivo.');
      return;
    }
    
    if (isProcessing) {
      showWarningToast('Processando arquivo', 'Ainda estamos preparando este arquivo. Tente novamente em alguns segundos.');
      return;
    }
    
    // ✅ MELHORIA: Usar fetch + blob para garantir download correto (especialmente para Excel)
    try {
      console.log('📥 [AttachmentPreview] Iniciando download:', {
        file_url: fileUrl,
        filename: attachment.original_filename,
        mime_type: attachment.mime_type
      });
      
      // 1. Verificar se arquivo existe (HEAD request)
      let headResponse = await fetch(fileUrl, { method: 'HEAD' }).catch(() => null);
      
      if (!headResponse || !headResponse.ok) {
        // Se HEAD falhar, tentar GET com range (primeiros bytes)
        headResponse = await fetch(fileUrl, { 
          method: 'GET',
          headers: { 'Range': 'bytes=0-0' }
        }).catch(() => null);
      }
      
      if (!headResponse || !headResponse.ok) {
        // Verificar se é resposta JSON de erro
        try {
          const errorResponse = await fetch(fileUrl, { method: 'GET' });
          const contentType = errorResponse.headers.get('content-type');
          if (contentType?.includes('application/json')) {
            const errorData = await errorResponse.json();
            if (errorData.error === 'Arquivo indisponível') {
              showWarningToast('Anexo indisponível', errorData.message || 'O arquivo não está mais disponível no servidor');
              return;
            }
          }
        } catch {
          // Ignorar erro ao tentar ler JSON
        }
        showWarningToast('Anexo indisponível', 'Não foi possível acessar o arquivo');
        return;
      }
      
      // 2. Baixar arquivo completo via fetch
      const response = await fetch(fileUrl);
      
      if (!response.ok) {
        showWarningToast('Erro ao baixar', `Erro HTTP ${response.status}`);
        return;
      }
      
      // 3. Converter para blob
      const blob = await response.blob();
      
      console.log('✅ [AttachmentPreview] Arquivo baixado:', {
        size: blob.size,
        type: blob.type,
        filename: attachment.original_filename
      });
      
      // 4. Criar URL do blob e fazer download
      const blobUrl = URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = blobUrl;
      link.download = attachment.original_filename || 'arquivo';
      link.target = '_blank';
      link.rel = 'noopener noreferrer';
      
      // ✅ IMPORTANTE: Adicionar ao DOM antes de clicar (alguns browsers requerem)
      document.body.appendChild(link);
      link.click();
      
      // ✅ Limpar: remover link e revogar blob URL
      document.body.removeChild(link);
      setTimeout(() => URL.revokeObjectURL(blobUrl), 100);
      
      console.log('✅ [AttachmentPreview] Download concluído');
    } catch (error) {
      console.error('❌ [AttachmentPreview] Erro ao baixar arquivo:', error);
      showWarningToast('Erro ao baixar', 'Não foi possível baixar o arquivo. Tente novamente.');
    }
  };

  return (
    <div 
      className={`attachment-preview document ${docStyle.bgColor} rounded-lg border ${docStyle.borderColor} max-w-xs cursor-pointer hover:shadow-md transition-shadow`}
      onClick={handleDocumentClick}
    >
      {/* Container vertical estilo WhatsApp */}
      <div className="flex flex-col items-center p-4">
        {/* Ícone grande centralizado */}
        <div className={`w-16 h-16 ${docStyle.iconBg} rounded-lg flex items-center justify-center mb-3`}>
          <FileText className={docStyle.iconColor} size={40} />
        </div>
        
        {/* Nome do arquivo */}
        <p className="text-xs font-medium text-gray-700 mb-1 text-center max-w-full truncate px-2" title={filename}>
          {filename}
        </p>
        
        {/* Tamanho do arquivo */}
        <p className="text-xs text-gray-500 mb-3">
          {attachment.size_bytes > 0 
            ? formatFileSize(attachment.size_bytes) 
            : (hasValidUrl 
                ? formatFileSize(0) // URL válida mas tamanho ainda não disponível
                : 'Processando...')}
        </p>
        
        {/* Botões de ação */}
        <div className="flex gap-2 mt-2">
          {isPDF && (
            <button
              onClick={(e) => {
                e.stopPropagation();
                handleDocumentClick(e);
              }}
              className="px-3 py-1.5 bg-white border border-gray-300 rounded text-xs text-gray-700 hover:bg-gray-50 transition-colors flex items-center gap-1"
              title="Abrir PDF"
            >
              <FileText size={14} />
              Abrir
            </button>
          )}
          <button
            onClick={(e) => {
              e.stopPropagation();
              handleDocumentDownload(e);
            }}
            className="px-3 py-1.5 bg-white border border-gray-300 rounded text-xs text-gray-700 hover:bg-gray-50 transition-colors flex items-center gap-1"
            title="Baixar arquivo"
          >
            <Download size={14} />
            Baixar
          </button>
        </div>
      </div>
    </div>
  );
}


