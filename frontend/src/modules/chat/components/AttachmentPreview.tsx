/**
 * AttachmentPreview - Visualiza diferentes tipos de anexos
 * 
 * Suporta:
 * - Imagens: Preview inline + lightbox
 * - Vídeos: Player HTML5
 * - Áudios: Player wavesurfer.js
 * - Documentos: Ícone + download
 * - IA: Transcrição + Resumo (se addon ativo)
 */
import React, { useState, useEffect, useRef } from 'react';
import { Download, FileText, Image, Video, Music, X } from 'lucide-react';
import WaveSurfer from 'wavesurfer.js';

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
  const [audioPlaying, setAudioPlaying] = useState(false);
  const waveformRef = useRef<HTMLDivElement>(null);
  const wavesurferRef = useRef<WaveSurfer | null>(null);

  const [useNativePlayer, setUseNativePlayer] = useState(false);

  // 🎵 Inicializar WaveSurfer para áudios (com fallback para player nativo)
  useEffect(() => {
    if (attachment.is_audio && waveformRef.current && !wavesurferRef.current && !useNativePlayer) {
      try {
        wavesurferRef.current = WaveSurfer.create({
          container: waveformRef.current,
          waveColor: '#4F46E5',
          progressColor: '#818CF8',
          cursorColor: '#312E81',
          barWidth: 2,
          barRadius: 3,
          cursorWidth: 1,
          height: 60,
          barGap: 2,
        });

        wavesurferRef.current.load(attachment.file_url);

        wavesurferRef.current.on('play', () => setAudioPlaying(true));
        wavesurferRef.current.on('pause', () => setAudioPlaying(false));
        wavesurferRef.current.on('finish', () => setAudioPlaying(false));
        
        // Se WaveSurfer falhar ao carregar, usa player nativo
        wavesurferRef.current.on('error', (error) => {
          console.warn('⚠️ [AUDIO] WaveSurfer error, usando player nativo:', error);
          setUseNativePlayer(true);
        });
      } catch (error) {
        console.warn('⚠️ [AUDIO] WaveSurfer init error, usando player nativo:', error);
        setUseNativePlayer(true);
      }
    }

    return () => {
      if (wavesurferRef.current) {
        wavesurferRef.current.destroy();
        wavesurferRef.current = null;
      }
    };
  }, [attachment.is_audio, attachment.file_url, useNativePlayer]);

  // 🖼️ IMAGEM
  if (attachment.is_image) {
    return (
      <div className="attachment-preview image">
        <img
          src={attachment.file_url}
          alt={attachment.original_filename}
          className="max-w-xs rounded-lg cursor-pointer hover:opacity-90 transition"
          onClick={() => setLightboxOpen(true)}
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
              src={attachment.file_url}
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
    return (
      <div className="attachment-preview video max-w-md">
        <video
          controls
          className="w-full rounded-lg"
          preload="metadata"
        >
          <source src={attachment.file_url} type={attachment.mime_type} />
          Seu navegador não suporta vídeo.
        </video>
        <p className="text-xs text-gray-500 mt-1">{attachment.original_filename}</p>
      </div>
    );
  }

  // 🎵 ÁUDIO
  if (attachment.is_audio) {
    return (
      <div className="attachment-preview audio max-w-md bg-gray-50 p-4 rounded-lg">
        <div className="flex items-center gap-3 mb-2">
          <Music className="text-indigo-600" size={20} />
          <div className="flex-1">
            <p className="text-sm font-medium">{attachment.original_filename}</p>
            <p className="text-xs text-gray-500">
              {(attachment.size_bytes / 1024 / 1024).toFixed(2)} MB
            </p>
          </div>
        </div>

        {/* Player Nativo HTML5 (fallback ou principal) */}
        {useNativePlayer ? (
          <audio
            controls
            className="w-full mb-2"
            preload="metadata"
          >
            <source src={attachment.file_url} type={attachment.mime_type} />
            Seu navegador não suporta áudio.
          </audio>
        ) : (
          <>
            {/* Waveform WaveSurfer */}
            <div ref={waveformRef} className="mb-2"></div>

            {/* Controles WaveSurfer */}
            <div className="flex items-center gap-2">
              <button
                onClick={() => {
                  if (wavesurferRef.current) {
                    wavesurferRef.current.playPause();
                  }
                }}
                className="px-4 py-2 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 text-sm"
              >
                {audioPlaying ? 'Pausar' : 'Reproduzir'}
              </button>
              <a
                href={attachment.file_url}
                download={attachment.original_filename}
                className="p-2 text-gray-600 hover:text-gray-900"
              >
                <Download size={18} />
              </a>
            </div>
          </>
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


