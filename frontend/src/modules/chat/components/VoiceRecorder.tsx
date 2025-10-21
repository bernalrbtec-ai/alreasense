/**
 * VoiceRecorder - Gravação de áudio estilo WhatsApp Web
 * 
 * Funcionalidades:
 * - Gravar áudio pelo microfone
 * - Timer de gravação
 * - Preview antes de enviar
 * - Upload automático para S3
 * - Visualização de waveform durante gravação
 */
import React, { useState, useRef, useEffect } from 'react';
import { Mic, Square, Trash2, Send, Loader2 } from 'lucide-react';
import { api } from '@/lib/api';
import { toast } from 'sonner';

interface VoiceRecorderProps {
  conversationId: string;
  onRecordingComplete?: (attachment: any) => void;
  onRecordingError?: (error: string) => void;
}

export function VoiceRecorder({
  conversationId,
  onRecordingComplete,
  onRecordingError,
}: VoiceRecorderProps) {
  const [isRecording, setIsRecording] = useState(false);
  const [isPreviewing, setIsPreviewing] = useState(false);
  const [isUploading, setIsUploading] = useState(false);
  const [recordingTime, setRecordingTime] = useState(0);
  const [audioBlob, setAudioBlob] = useState<Blob | null>(null);
  const [audioUrl, setAudioUrl] = useState<string | null>(null);
  
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const audioChunksRef = useRef<Blob[]>([]);
  const timerRef = useRef<NodeJS.Timeout | null>(null);
  const streamRef = useRef<MediaStream | null>(null);

  // Limpar ao desmontar
  useEffect(() => {
    return () => {
      stopRecording();
      if (audioUrl) {
        URL.revokeObjectURL(audioUrl);
      }
      if (streamRef.current) {
        streamRef.current.getTracks().forEach(track => track.stop());
      }
    };
  }, [audioUrl]);

  // Formatar tempo (MM:SS)
  const formatTime = (seconds: number) => {
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
  };

  // Iniciar gravação
  const startRecording = async () => {
    try {
      // Solicitar permissão do microfone
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      streamRef.current = stream;

      // Criar MediaRecorder
      const mediaRecorder = new MediaRecorder(stream, {
        mimeType: 'audio/webm;codecs=opus'
      });
      
      mediaRecorderRef.current = mediaRecorder;
      audioChunksRef.current = [];

      // Coletar chunks de áudio
      mediaRecorder.ondataavailable = (event) => {
        if (event.data.size > 0) {
          audioChunksRef.current.push(event.data);
        }
      };

      // Quando parar a gravação
      mediaRecorder.onstop = () => {
        const blob = new Blob(audioChunksRef.current, { type: 'audio/webm' });
        setAudioBlob(blob);
        setAudioUrl(URL.createObjectURL(blob));
        setIsPreviewing(true);
        
        // Parar stream
        if (streamRef.current) {
          streamRef.current.getTracks().forEach(track => track.stop());
          streamRef.current = null;
        }
      };

      // Iniciar gravação
      mediaRecorder.start();
      setIsRecording(true);
      setRecordingTime(0);

      // Iniciar timer
      timerRef.current = setInterval(() => {
        setRecordingTime(prev => prev + 1);
      }, 1000);

      console.log('🎤 [VOICE] Gravação iniciada');
    } catch (error: any) {
      console.error('❌ [VOICE] Erro ao iniciar gravação:', error);
      
      if (error.name === 'NotAllowedError') {
        toast.error('Permissão de microfone negada');
      } else {
        toast.error('Erro ao acessar microfone');
      }
      
      onRecordingError?.(error.message);
    }
  };

  // Parar gravação
  const stopRecording = () => {
    if (mediaRecorderRef.current && isRecording) {
      mediaRecorderRef.current.stop();
      setIsRecording(false);
      
      if (timerRef.current) {
        clearInterval(timerRef.current);
        timerRef.current = null;
      }
      
      console.log('⏹️ [VOICE] Gravação parada');
    }
  };

  // Cancelar gravação
  const cancelRecording = () => {
    if (isRecording) {
      stopRecording();
    }
    
    if (audioUrl) {
      URL.revokeObjectURL(audioUrl);
    }
    
    setAudioBlob(null);
    setAudioUrl(null);
    setIsPreviewing(false);
    setRecordingTime(0);
    audioChunksRef.current = [];
    
    console.log('🗑️ [VOICE] Gravação cancelada');
  };

  // Enviar áudio
  const sendAudio = async () => {
    if (!audioBlob) return;

    setIsUploading(true);

    try {
      // Converter Blob para File
      const file = new File([audioBlob], `voice-${Date.now()}.webm`, {
        type: 'audio/webm'
      });

      console.log('📤 [VOICE] Enviando áudio gravado...');

      // 1️⃣ Obter presigned URL
      const { data: presignedData } = await api.post('/chat/messages/upload-presigned-url/', {
        conversation_id: conversationId,
        filename: file.name,
        content_type: file.type,
        file_size: file.size,
      });

      console.log('✅ [VOICE] Presigned URL obtida:', presignedData.attachment_id);

      // 2️⃣ Upload para S3
      const xhr = new XMLHttpRequest();
      
      await new Promise<void>((resolve, reject) => {
        xhr.addEventListener('load', () => {
          if (xhr.status >= 200 && xhr.status < 300) {
            resolve();
          } else {
            reject(new Error(`Upload falhou: ${xhr.status}`));
          }
        });

        xhr.addEventListener('error', () => {
          reject(new Error('Erro de rede ao fazer upload'));
        });

        xhr.open('PUT', presignedData.upload_url);
        xhr.setRequestHeader('Content-Type', file.type);
        xhr.send(file);
      });

      console.log('✅ [VOICE] Áudio enviado para S3');

      // 3️⃣ Confirmar no backend
      const { data: confirmData } = await api.post('/chat/messages/confirm-upload/', {
        conversation_id: conversationId,
        attachment_id: presignedData.attachment_id,
        s3_key: presignedData.s3_key,
        filename: file.name,
        content_type: file.type,
        file_size: file.size,
      });

      console.log('✅ [VOICE] Upload confirmado:', confirmData);

      toast.success('Áudio enviado com sucesso!');
      onRecordingComplete?.(confirmData.attachment);

      // Limpar
      cancelRecording();
    } catch (error: any) {
      console.error('❌ [VOICE] Erro ao enviar:', error);
      const errorMsg = error.response?.data?.error || error.message || 'Erro ao enviar áudio';
      toast.error(errorMsg);
      onRecordingError?.(errorMsg);
    } finally {
      setIsUploading(false);
    }
  };

  // UI: Botão normal (não gravando)
  if (!isRecording && !isPreviewing) {
    return (
      <button
        onClick={startRecording}
        className="p-2 text-gray-600 hover:text-gray-900 hover:bg-gray-100 rounded-lg transition"
        title="Gravar áudio"
        disabled={isUploading}
      >
        <Mic size={20} />
      </button>
    );
  }

  // UI: Gravando
  if (isRecording) {
    return (
      <div className="fixed inset-0 bg-black bg-opacity-50 z-50 flex items-center justify-center p-4">
        <div className="bg-white rounded-lg p-6 max-w-md w-full">
          <div className="text-center">
            {/* Ícone pulsante */}
            <div className="relative inline-flex mb-4">
              <div className="absolute inset-0 bg-red-500 rounded-full animate-ping opacity-75"></div>
              <div className="relative bg-red-600 p-6 rounded-full">
                <Mic className="text-white" size={32} />
              </div>
            </div>

            {/* Timer */}
            <h3 className="text-2xl font-bold mb-2">{formatTime(recordingTime)}</h3>
            <p className="text-sm text-gray-600 mb-6">Gravando áudio...</p>

            {/* Botões */}
            <div className="flex gap-3 justify-center">
              <button
                onClick={cancelRecording}
                className="flex-1 px-6 py-3 border border-gray-300 rounded-lg hover:bg-gray-50 flex items-center justify-center gap-2"
              >
                <Trash2 size={18} />
                Cancelar
              </button>
              <button
                onClick={stopRecording}
                className="flex-1 px-6 py-3 bg-red-600 text-white rounded-lg hover:bg-red-700 flex items-center justify-center gap-2"
              >
                <Square size={18} />
                Parar
              </button>
            </div>
          </div>
        </div>
      </div>
    );
  }

  // UI: Preview (após gravar)
  if (isPreviewing && audioUrl) {
    return (
      <div className="fixed inset-0 bg-black bg-opacity-50 z-50 flex items-center justify-center p-4">
        <div className="bg-white rounded-lg p-6 max-w-md w-full">
          <div className="text-center">
            <h3 className="text-lg font-semibold mb-4">Preview do Áudio</h3>

            {/* Player */}
            <div className="mb-6">
              <audio controls className="w-full" src={audioUrl}>
                Seu navegador não suporta áudio.
              </audio>
            </div>

            {/* Info */}
            <p className="text-sm text-gray-600 mb-6">
              Duração: {formatTime(recordingTime)}
            </p>

            {/* Botões */}
            {isUploading ? (
              <div className="flex items-center justify-center gap-2 py-3">
                <Loader2 className="animate-spin text-indigo-600" size={20} />
                <span className="text-sm">Enviando...</span>
              </div>
            ) : (
              <div className="flex gap-3">
                <button
                  onClick={cancelRecording}
                  className="flex-1 px-6 py-3 border border-gray-300 rounded-lg hover:bg-gray-50 flex items-center justify-center gap-2"
                >
                  <Trash2 size={18} />
                  Descartar
                </button>
                <button
                  onClick={sendAudio}
                  className="flex-1 px-6 py-3 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 flex items-center justify-center gap-2"
                >
                  <Send size={18} />
                  Enviar
                </button>
              </div>
            )}
          </div>
        </div>
      </div>
    );
  }

  return null;
}

