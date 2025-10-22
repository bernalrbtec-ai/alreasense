/**
 * VoiceRecorder - Gravação de áudio estilo WhatsApp Web
 * 
 * UX:
 * 1. Apertar botão → Inicia gravação
 * 2. Ícone muda (Mic → Square pulsante vermelho)
 * 3. Soltar botão → Para e ENVIA automaticamente (sem preview)
 * 4. Clicar X → Cancela gravação
 * 5. Timer em tempo real
 * 6. Feedback visual (animação pulsante)
 */
import React, { useState, useRef, useEffect } from 'react';
import { Mic, X } from 'lucide-react';
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
  const [isUploading, setIsUploading] = useState(false);
  const [recordingTime, setRecordingTime] = useState(0);
  
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const audioChunksRef = useRef<Blob[]>([]);
  const timerRef = useRef<NodeJS.Timeout | null>(null);
  const streamRef = useRef<MediaStream | null>(null);

  // Limpar ao desmontar
  useEffect(() => {
    return () => {
      cleanup();
    };
  }, []);

  // Formatar tempo (MM:SS)
  const formatTime = (seconds: number) => {
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
  };

  // Limpar recursos
  const cleanup = () => {
    if (timerRef.current) {
      clearInterval(timerRef.current);
      timerRef.current = null;
    }
    if (streamRef.current) {
      streamRef.current.getTracks().forEach(track => track.stop());
      streamRef.current = null;
    }
    if (mediaRecorderRef.current) {
      mediaRecorderRef.current = null;
    }
    audioChunksRef.current = [];
  };

  // 1️⃣ APERTAR botão → Iniciar gravação
  const handleMouseDown = async () => {
    if (isRecording || isUploading) return;

    try {
      console.log('🎤 [VOICE] Solicitando permissão do microfone...');
      
      // Solicitar permissão
      const stream = await navigator.mediaDevices.getUserMedia({ 
        audio: {
          echoCancellation: true,
          noiseSuppression: true,
          autoGainControl: true
        } 
      });
      streamRef.current = stream;

      // Criar MediaRecorder
      const mediaRecorder = new MediaRecorder(stream, {
        mimeType: 'audio/webm;codecs=opus'
      });
      
      mediaRecorderRef.current = mediaRecorder;
      audioChunksRef.current = [];

      // Coletar chunks
      mediaRecorder.ondataavailable = (event) => {
        if (event.data.size > 0) {
          audioChunksRef.current.push(event.data);
        }
      };

      // Iniciar gravação
      mediaRecorder.start();
      setIsRecording(true);
      setRecordingTime(0);

      // Timer
      timerRef.current = setInterval(() => {
        setRecordingTime(prev => prev + 1);
      }, 1000);

      console.log('🎤 [VOICE] Gravação iniciada!');
    } catch (error: any) {
      console.error('❌ [VOICE] Erro ao iniciar:', error);
      
      if (error.name === 'NotAllowedError') {
        toast.error('Permissão de microfone negada');
      } else {
        toast.error('Erro ao acessar microfone');
      }
      
      onRecordingError?.(error.message);
    }
  };

  // 2️⃣ SOLTAR botão → Parar e ENVIAR automaticamente
  const handleMouseUp = async () => {
    if (!isRecording || !mediaRecorderRef.current) return;

    console.log('✋ [VOICE] Soltou botão - parando gravação...');

    // Parar gravação
    mediaRecorderRef.current.stop();
    setIsRecording(false);

    if (timerRef.current) {
      clearInterval(timerRef.current);
      timerRef.current = null;
    }

    // Criar Blob do áudio
    const blob = new Blob(audioChunksRef.current, { type: 'audio/webm' });
    
    // Limpar stream
    if (streamRef.current) {
      streamRef.current.getTracks().forEach(track => track.stop());
      streamRef.current = null;
    }

    // Enviar automaticamente (SEM PREVIEW)
    await sendAudioDirectly(blob);
  };

  // 3️⃣ CANCELAR (X button)
  const handleCancel = () => {
    console.log('❌ [VOICE] Cancelando gravação...');
    
    if (mediaRecorderRef.current && isRecording) {
      mediaRecorderRef.current.stop();
    }
    
    cleanup();
    setIsRecording(false);
    setRecordingTime(0);
    
    toast.info('Gravação cancelada');
  };

  // Enviar áudio direto (sem preview)
  const sendAudioDirectly = async (blob: Blob) => {
    if (blob.size === 0) {
      toast.error('Áudio muito curto');
      cleanup();
      return;
    }

    setIsUploading(true);

    try {
      const file = new File([blob], `voice-${Date.now()}.webm`, {
        type: 'audio/webm'
      });

      console.log('📤 [VOICE] Enviando áudio...', file.size, 'bytes');

      // 1️⃣ Obter presigned URL
      const { data: presignedData } = await api.post('/chat/messages/upload-presigned-url/', {
        conversation_id: conversationId,
        filename: file.name,
        content_type: file.type,
        file_size: file.size,
      });

      console.log('✅ [VOICE] Presigned URL obtida');

      // 2️⃣ Upload S3
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
          reject(new Error('Erro de rede'));
        });

        xhr.open('PUT', presignedData.upload_url);
        xhr.setRequestHeader('Content-Type', file.type);
        xhr.send(file);
      });

      console.log('✅ [VOICE] Upload S3 completo');

      // 3️⃣ Confirmar backend
      const { data: confirmData } = await api.post('/chat/messages/confirm-upload/', {
        conversation_id: conversationId,
        attachment_id: presignedData.attachment_id,
        s3_key: presignedData.s3_key,
        filename: file.name,
        content_type: file.type,
        file_size: file.size,
      });

      console.log('✅ [VOICE] Áudio enviado com sucesso!');
      onRecordingComplete?.(confirmData.attachment);

    } catch (error: any) {
      console.error('❌ [VOICE] Erro ao enviar:', error);
      const errorMsg = error.response?.data?.error || error.message || 'Erro ao enviar áudio';
      toast.error(errorMsg);
      onRecordingError?.(errorMsg);
    } finally {
      cleanup();
      setIsUploading(false);
      setRecordingTime(0);
    }
  };

  // UI: Não gravando → Botão simples de Microfone
  if (!isRecording && !isUploading) {
    return (
      <button
        onMouseDown={handleMouseDown}
        onMouseUp={handleMouseUp}
        onMouseLeave={handleMouseUp} // Se sair com mouse pressionado, para também
        className="p-2 text-gray-600 hover:text-gray-900 hover:bg-gray-100 rounded-lg transition-colors"
        title="Segurar para gravar áudio"
      >
        <Mic size={20} />
      </button>
    );
  }

  // UI: Gravando → Timer + Botão X (cancelar)
  if (isRecording) {
    return (
      <div className="flex items-center gap-2 px-3 py-2 bg-red-50 rounded-lg border border-red-200">
        {/* Ícone pulsante */}
        <div className="relative flex items-center justify-center">
          <div className="absolute w-8 h-8 bg-red-500 rounded-full animate-ping opacity-75"></div>
          <div className="relative w-8 h-8 bg-red-600 rounded-full flex items-center justify-center">
            <Mic className="text-white" size={16} />
          </div>
        </div>

        {/* Timer */}
        <span className="text-red-700 font-mono font-semibold">
          {formatTime(recordingTime)}
        </span>

        {/* Dica */}
        <span className="text-xs text-red-600 ml-2">
          Solte para enviar
        </span>

        {/* Botão Cancelar */}
        <button
          onClick={handleCancel}
          className="ml-auto p-1.5 hover:bg-red-100 rounded-full transition-colors"
          title="Cancelar gravação"
        >
          <X size={18} className="text-red-700" />
        </button>
      </div>
    );
  }

  // UI: Enviando → Loader
  if (isUploading) {
    return (
      <div className="flex items-center gap-2 px-3 py-2 bg-gray-100 rounded-lg">
        <div className="w-4 h-4 border-2 border-gray-400 border-t-transparent rounded-full animate-spin"></div>
        <span className="text-sm text-gray-600">Enviando...</span>
      </div>
    );
  }

  return null;
}

