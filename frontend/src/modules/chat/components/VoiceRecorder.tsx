/**
 * VoiceRecorder - Gravação de áudio estilo WhatsApp Web
 * 
 * UX (Toggle Mode - Botão Único):
 * 1. Clicar UMA VEZ no microfone (cinza) → Inicia gravação
 * 2. Gravando: Microfone vira VERMELHO PULSANTE + Timer + Botão X
 * 3. Clicar NO MICROFONE VERMELHO novamente → Para e ENVIA automaticamente
 * 4. Clicar no X → Cancela gravação
 * 5. Timer em tempo real (MM:SS)
 * 6. Validação: Mínimo 1 segundo de áudio
 * 7. Feedback visual: bg-red-50 + animação pulsante
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

  // 1️⃣ CLICAR botão → Iniciar gravação (se não está gravando) OU Parar e enviar (se está gravando)
  const handleClick = async () => {
    if (isUploading) return;

    // Se já está gravando, para e envia
    if (isRecording) {
      await stopAndSend();
      return;
    }

    // Se não está gravando, inicia
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
      // Tentar OGG primeiro (compatível com WhatsApp), fallback para WEBM
      let mimeType = 'audio/ogg;codecs=opus';
      if (!MediaRecorder.isTypeSupported(mimeType)) {
        mimeType = 'audio/webm;codecs=opus';
        console.warn('⚠️ [VOICE] OGG não suportado, usando WEBM (pode não funcionar no WhatsApp)');
      }
      
      const mediaRecorder = new MediaRecorder(stream, { mimeType });
      
      console.log(`🎤 [VOICE] Formato selecionado: ${mimeType}`);
      
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

  // 2️⃣ Parar e ENVIAR automaticamente
  const stopAndSend = async () => {
    if (!isRecording || !mediaRecorderRef.current) return;

    console.log('⏹️ [VOICE] Parando gravação e enviando...');

    return new Promise<void>((resolve) => {
      const mediaRecorder = mediaRecorderRef.current!;
      
      // Listener para quando MediaRecorder finalizar
      mediaRecorder.onstop = async () => {
        console.log('✅ [VOICE] MediaRecorder finalizado');
        
        // Criar Blob do áudio (usar o mimeType do MediaRecorder)
        const mimeType = mediaRecorder.mimeType || 'audio/ogg';
        const blob = new Blob(audioChunksRef.current, { type: mimeType });
        
        console.log(`📦 [VOICE] Blob criado: ${blob.size} bytes, tipo: ${blob.type}`);
        
        // Limpar stream
        if (streamRef.current) {
          streamRef.current.getTracks().forEach(track => track.stop());
          streamRef.current = null;
        }

        // Enviar automaticamente (SEM PREVIEW)
        await sendAudioDirectly(blob);
        resolve();
      };
      
      // Parar gravação (vai disparar onstop)
      mediaRecorder.stop();
      setIsRecording(false);

      if (timerRef.current) {
        clearInterval(timerRef.current);
        timerRef.current = null;
      }
    });
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
    // Validar duração (não blob.size, pois o MediaRecorder pode ter tamanho > 0 mesmo vazio)
    if (recordingTime < 1) {
      toast.error('Áudio muito curto (mínimo 1 segundo)');
      cleanup();
      return;
    }

    // ✅ FIX: Validar tamanho de arquivo antes de iniciar upload
    const file = new File([blob], `voice-${Date.now()}.${blob.type.includes('ogg') ? 'ogg' : 'webm'}`, {
      type: blob.type
    });
    
    const { validateFileSize } = await import('../utils/messageUtils');
    const sizeValidation = validateFileSize(file, 50);
    if (!sizeValidation.valid) {
      toast.error(sizeValidation.error || 'Áudio muito grande. Máximo: 50MB');
      cleanup();
      return;
    }

    setIsUploading(true);

    try {
      // Detectar extensão baseada no mime type
      const extension = blob.type.includes('ogg') ? 'ogg' : 'webm';
      const fileToUpload = new File([blob], `voice-${Date.now()}.${extension}`, {
        type: blob.type
      });

      console.log('📤 [VOICE] Enviando áudio...', fileToUpload.size, 'bytes');

      // 1️⃣ Obter presigned URL
      const { data: presignedData } = await api.post('/chat/messages/upload-presigned-url/', {
        conversation_id: conversationId,
        filename: fileToUpload.name,
        content_type: fileToUpload.type,
        file_size: fileToUpload.size,
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
        xhr.setRequestHeader('Content-Type', fileToUpload.type);
        xhr.send(fileToUpload);
      });

      console.log('✅ [VOICE] Upload S3 completo');

      // 3️⃣ Confirmar backend
      const { data: confirmData } = await api.post('/chat/messages/confirm-upload/', {
        conversation_id: conversationId,
        attachment_id: presignedData.attachment_id,
        s3_key: presignedData.s3_key,
        filename: fileToUpload.name,
        content_type: fileToUpload.type,
        file_size: fileToUpload.size,
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
        onClick={handleClick}
        className="p-2 text-gray-600 hover:text-gray-900 hover:bg-gray-100 rounded-lg transition-colors"
        title="Clique para gravar áudio"
      >
        <Mic size={20} />
      </button>
    );
  }

  // UI: Gravando → Microfone vermelho pulsante (clica nele para enviar) + Timer + X
  if (isRecording) {
    return (
      <div className="flex items-center gap-2 px-3 py-2 bg-red-50 rounded-lg border border-red-200">
        {/* Microfone pulsante (clicável para enviar) */}
        <button
          onClick={handleClick}
          className="relative flex items-center justify-center flex-shrink-0"
          title="Clique para parar e enviar"
        >
          <div className="absolute w-8 h-8 bg-red-500 rounded-full animate-ping opacity-75"></div>
          <div className="relative w-8 h-8 bg-red-600 hover:bg-red-700 rounded-full flex items-center justify-center transition-colors cursor-pointer">
            <Mic className="text-white" size={16} />
          </div>
        </button>

        {/* Timer */}
        <span className="text-red-700 font-mono font-semibold">
          {formatTime(recordingTime)}
        </span>

        {/* Dica */}
        <span className="text-xs text-red-600 ml-2">
          Clique no microfone para enviar
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

