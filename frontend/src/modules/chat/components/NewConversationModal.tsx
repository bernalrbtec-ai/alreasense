import { useState, useEffect, useCallback, useMemo, useRef } from 'react';
import { X, Search, User, Phone, Loader2, Tag as TagIcon } from 'lucide-react';
import { api } from '@/lib/api';
import { rawInputToE164, isValidE164 } from '@/lib/phoneDDD';
import { parseE164ToCountryAndNational, buildE164International } from '@/lib/countryCodes';
import { PhoneInputWithDDD } from '@/components/PhoneInputWithDDD';
import { useChatStore } from '../store/chatStore';
import { useAuthStore } from '@/stores/authStore';
import { usePermissions } from '@/hooks/usePermissions';
import { useTheme } from '@/hooks/useTheme';
import { showErrorToast } from '@/lib/toastHelper';
import { TagSelectModal } from './TagSelectModal';

interface Contact {
  id: string;
  name: string;
  phone: string;
  tags?: Array<{ id: string; name: string; color: string }>;
}

interface WhatsAppInstance {
  id: string;
  friendly_name: string;
  instance_name: string;
  is_active: boolean;
  is_default?: boolean;
}

interface NewConversationModalProps {
  isOpen: boolean;
  onClose: () => void;
}

export function NewConversationModal({ isOpen, onClose }: NewConversationModalProps) {
  const { setActiveConversation, addConversation, activeDepartment, departments } = useChatStore();
  const { user } = useAuthStore();
  const { can_access_all_departments, departmentIds } = usePermissions();
  const { theme } = useTheme();
  const isDark = theme === 'dark';
  const [searchQuery, setSearchQuery] = useState('');
  const [contacts, setContacts] = useState<Contact[]>([]);
  const [isSearching, setIsSearching] = useState(false);
  const [isCreating, setIsCreating] = useState(false);
  const [phoneInput, setPhoneInput] = useState('');
  const [isValidPhone, setIsValidPhone] = useState(false);
  const [instances, setInstances] = useState<WhatsAppInstance[]>([]);
  const [selectedInstanceId, setSelectedInstanceId] = useState<string | null>(null);
  const [selectedDepartmentId, setSelectedDepartmentId] = useState<string | null>(null);
  const [selectedTagIds, setSelectedTagIds] = useState<string[]>([]);
  const [selectedTagsInfo, setSelectedTagsInfo] = useState<Array<{ id: string; name: string; color: string }>>([]);
  const [isTagSelectModalOpen, setIsTagSelectModalOpen] = useState(false);
  const searchAbortRef = useRef<AbortController | null>(null);

  // Departamentos reais do usuário (exclui inbox e my_conversations)
  const userDepartments = useMemo(() => {
    const list = Array.isArray(departments) ? departments : [];
    const real = list.filter(
      (d: { id: string }) => d.id !== 'inbox' && d.id !== 'my_conversations'
    );
    if (can_access_all_departments) return real;
    if (!departmentIds?.length) return [];
    return real.filter((d: { id: string }) => departmentIds.includes(d.id));
  }, [departments, can_access_all_departments, departmentIds]);

  // ✅ MULTI-INSTÂNCIA: Buscar instâncias quando modal abre; preselection = user default ou is_default ou primeira
  useEffect(() => {
    if (!isOpen) return;
    const fetchInstances = async () => {
      try {
        const response = await api.get('/notifications/whatsapp-instances/', {
          params: { page_size: 50 }
        });
        const results = response.data.results ?? response.data ?? [];
        const list = Array.isArray(results) ? results.filter((i: any) => i.is_active !== false) : [];
        setInstances(list);
        if (list.length === 1) {
          setSelectedInstanceId(list[0].id);
        } else if (list.length > 1) {
          const userDefaultId = user?.default_whatsapp_instance_id ?? user?.default_whatsapp_instance?.id;
          const inList = userDefaultId && list.some((i: WhatsAppInstance) => i.id === userDefaultId);
          const defaultInstance = list.find((i: WhatsAppInstance) => i.is_default === true);
          const pick = inList ? userDefaultId : (defaultInstance?.id ?? list[0]?.id ?? null);
          setSelectedInstanceId(pick);
        } else {
          setSelectedInstanceId(null);
        }
      } catch {
        setInstances([]);
        setSelectedInstanceId(null);
      }
    };
    fetchInstances();
  }, [isOpen, user?.default_whatsapp_instance_id, user?.default_whatsapp_instance?.id]);

  // Inicializar selectedDepartmentId quando modal abre: activeDepartment na lista ou primeiro
  useEffect(() => {
    if (!isOpen || userDepartments.length === 0) return;
    if (userDepartments.length === 1) {
      setSelectedDepartmentId(userDepartments[0].id);
      return;
    }
    const activeInList = activeDepartment && activeDepartment.id !== 'inbox' && activeDepartment.id !== 'my_conversations' &&
      userDepartments.some((d: { id: string }) => d.id === activeDepartment.id);
    setSelectedDepartmentId(activeInList ? activeDepartment!.id : userDepartments[0].id);
  }, [isOpen, userDepartments, activeDepartment]);

  // department_id a enviar no POST /start/: 0 depts = undefined; 1 = esse id; 2+ = selectedDepartmentId (se ainda estiver na lista)
  const departmentIdForStart = useMemo(() => {
    if (userDepartments.length === 0) return undefined;
    if (userDepartments.length === 1) return userDepartments[0].id;
    const valid = selectedDepartmentId && userDepartments.some((d: { id: string }) => d.id === selectedDepartmentId);
    return valid ? selectedDepartmentId : (userDepartments[0]?.id ?? undefined);
  }, [userDepartments, selectedDepartmentId]);

  // Detectar se query é telefone ou nome
  const isPhoneQuery = useCallback((query: string): boolean => {
    // Remove espaços, parênteses, hífens e outros caracteres
    const clean = query.replace(/[\s\(\)\-\+]/g, '');
    // Se tem mais de 5 dígitos, provavelmente é telefone
    return /^\d{6,}$/.test(clean);
  }, []);

  // Normalizar telefone para E.164 (preserva internacional)
  const normalizePhone = useCallback((phone: string): string => {
    const digits = (phone || '').replace(/\D/g, '');
    if (!digits.length) return '';
    if (phone.trim().startsWith('+')) return '+' + digits;
    const { dial, national } = parseE164ToCountryAndNational('+' + digits);
    if (dial && national.length >= 6 && digits.startsWith(dial)) return '+' + digits;
    return '+55' + digits;
  }, []);

  const isGroupIdentifier = useCallback((value: string): boolean => {
    if (!value) return false;
    const lower = value.toLowerCase();
    if (lower.includes('@g.us') || lower.includes('@broadcast') || lower.includes('@lid')) {
      return true;
    }
    const digits = value.replace(/\D/g, '');
    // E.164 permite até 15 dígitos; IDs de grupo costumam ser maiores
    return digits.length > 15;
  }, []);

  const normalizeGroupId = useCallback((value: string): string => {
    if (!value) return value;
    const lower = value.toLowerCase();
    if (lower.includes('@g.us') || lower.includes('@broadcast')) {
      return value;
    }
    const digits = value.replace(/\D/g, '');
    return digits ? `${digits}@g.us` : value;
  }, []);

  // Validar telefone (Brasil ou internacional E.164)
  const validatePhone = useCallback((phone: string): boolean => {
    const normalized = normalizePhone(phone);
    return isValidE164(normalized);
  }, [normalizePhone]);

  // Telefone efetivo ao iniciar por número. Hooks devem vir antes de qualquer return (regra do React).
  const getEffectivePhone = useCallback((input: string): string => {
    const s = input != null && typeof input === 'string' ? input : String(input ?? '');
    if (!s.trim()) return '';
    const digits = s.replace(/\D/g, '');
    if (digits.length >= 12 && digits.startsWith('55')) return '+' + digits;
    if (digits.length >= 10) {
      const { dial, national } = parseE164ToCountryAndNational('+' + digits);
      if (dial && national.length >= 6) return buildE164International(dial, national);
    }
    return rawInputToE164(s, '17');
  }, []);

  // Buscar contatos (nome/telefone e/ou tags)
  useEffect(() => {
    if (!isOpen) {
      setSearchQuery('');
      setContacts([]);
      setPhoneInput('');
      setIsValidPhone(false);
      setSelectedTagIds([]);
      setSelectedTagsInfo([]);
      setIsTagSelectModalOpen(false);
      return;
    }

    const hasSearch = searchQuery.trim().length >= 2;
    const hasTags = selectedTagIds.length > 0;
    const delayMs = hasSearch ? 300 : 0;

    const searchContacts = async () => {
      if (!hasSearch && !hasTags) {
        setContacts([]);
        return;
      }

      searchAbortRef.current?.abort();
      searchAbortRef.current = new AbortController();
      const signal = searchAbortRef.current.signal;
      setIsSearching(true);
      try {
        const params: Record<string, string> = {};
        if (hasSearch) {
          params.search = searchQuery.trim();
          params.page_size = '10';
        } else {
          params.page_size = '20';
        }
        if (hasTags) {
          const tagIds = selectedTagIds.filter((id) => id != null && String(id).trim());
          if (tagIds.length > 0) params.tags = tagIds.join(',');
        }
        const response = await api.get('/contacts/contacts/', { params, signal });
        const results = (response?.data?.results ?? response?.data) ?? [];
        setContacts(Array.isArray(results) ? results : []);
      } catch (error) {
        const isAbort = (error as { name?: string })?.name === 'CanceledError' || (error as { name?: string })?.name === 'AbortError';
        if (!isAbort) console.error('Erro ao buscar contatos:', error);
        if (!signal.aborted) setContacts([]);
      } finally {
        setIsSearching(false);
      }
    };

    const timeoutId = setTimeout(searchContacts, delayMs);
    return () => {
      clearTimeout(timeoutId);
      searchAbortRef.current?.abort();
    };
  }, [searchQuery, isOpen, selectedTagIds]);

  // Validar telefone quando mudar
  useEffect(() => {
    if (phoneInput && isPhoneQuery(phoneInput)) {
      const valid = validatePhone(phoneInput);
      setIsValidPhone(valid);
    } else {
      setIsValidPhone(false);
    }
  }, [phoneInput, isPhoneQuery, validatePhone]);

  // Iniciar conversa com contato
  const handleStartConversation = async (contact: Contact) => {
    try {
      setIsCreating(true);
      const isGroup = isGroupIdentifier(contact.phone);
      const normalizedPhone = isGroup ? normalizeGroupId(contact.phone) : normalizePhone(contact.phone);
      
      // Verificar se conversa já existe (filtrar pela instância selecionada para abrir/enviar pela correta)
      const listParams: Record<string, string> = { search: normalizedPhone };
      if (selectedInstanceId) listParams.instance = selectedInstanceId;
      const response = await api.get('/chat/conversations/', {
        params: listParams
      });
      
      const conversations = response.data.results || response.data || [];
      let conversation = conversations.find((conv: any) => {
        if (isGroup) {
          const convRaw = conv.contact_phone || '';
          const convDigits = convRaw.replace(/\D/g, '');
          const contactDigits = normalizedPhone.replace(/\D/g, '');
          return convRaw === normalizedPhone || (convDigits && convDigits === contactDigits);
        }
        
        const convPhone = conv.contact_phone?.replace(/[^\d]/g, '') || '';
        const contactPhone = contact.phone.replace(/[^\d]/g, '') || '';
        return convPhone === contactPhone || 
               convPhone === `55${contactPhone}` ||
               convPhone === `+55${contactPhone}`;
      });

      // Garantir que a conversa existente entre no store (ex.: conversa criada pelo webhook Meta)
      if (conversation) {
        addConversation(conversation);
      }
      
      // Se não encontrou, criar nova conversa
      if (!conversation) {
        const createResponse = await api.post('/chat/conversations/start/', {
          contact_phone: normalizedPhone,
          contact_name: contact.name,
          ...(departmentIdForStart && { department: departmentIdForStart }),
          ...(selectedInstanceId && { instance_id: selectedInstanceId })
        });
        conversation = createResponse.data.conversation || createResponse.data;

        try {
          const convDepartmentId = typeof conversation.department === 'string'
            ? conversation.department
            : conversation.department?.id || null;
          const { setActiveDepartment } = useChatStore.getState();
          if (convDepartmentId && activeDepartment?.id !== convDepartmentId) {
            const { departments } = useChatStore.getState();
            const matchingDept = departments.find(d => d.id === convDepartmentId);
            if (matchingDept) {
              setActiveDepartment(matchingDept);
            } else {
              console.warn(`⚠️ [NEW CONVERSATION] Departamento ${convDepartmentId} não encontrado no store`);
            }
          } else if (!convDepartmentId && activeDepartment?.id !== 'inbox') {
            setActiveDepartment({ id: 'inbox', name: 'Inbox', color: '#ea580c' } as any);
          }
          addConversation(conversation);
        } catch (e) {
          console.error('Erro ao aplicar conversa (department/store):', e);
          addConversation(conversation);
        }
      }

      try {
        setActiveConversation(conversation);
        onClose();
      } catch (e) {
        console.error('Erro ao selecionar conversa:', e);
      }
    } catch (error: any) {
      const convFromError = error?.response?.data?.conversation ?? (error?.response?.data?.id ? error.response.data : null);
      if (convFromError?.id) {
        addConversation(convFromError);
        setActiveConversation(convFromError);
        onClose();
        return;
      }
      console.error('Erro ao iniciar conversa:', error);
      showErrorToast('iniciar', 'Conversa', error);
    } finally {
      setIsCreating(false);
    }
  };

  // Iniciar conversa com telefone direto (E.164; Brasil ou internacional)
  const handleStartConversationWithPhone = async () => {
    const effectivePhone = getEffectivePhone(phoneInput);
    if (!effectivePhone || !validatePhone(effectivePhone)) return;

    try {
      setIsCreating(true);
      const normalizedPhone = effectivePhone;
      
      // Verificar se conversa já existe (filtrar pela instância selecionada)
      const listParams: Record<string, string> = { search: normalizedPhone };
      if (selectedInstanceId) listParams.instance = selectedInstanceId;
      const response = await api.get('/chat/conversations/', {
        params: listParams
      });
      
      const conversations = response.data.results || response.data || [];
      let conversation = conversations.find((conv: any) => {
        const convPhone = conv.contact_phone?.replace(/[^\d]/g, '') || '';
        const searchPhone = normalizedPhone.replace(/[^\d]/g, '') || '';
        return convPhone === searchPhone || 
               convPhone === `55${searchPhone}` ||
               convPhone === `+55${searchPhone}`;
      });

      // Garantir que a conversa existente entre no store (ex.: conversa criada pelo webhook Meta)
      if (conversation) {
        addConversation(conversation);
      }
      
      // Se não encontrou, criar nova conversa
      if (!conversation) {
        const createResponse = await api.post('/chat/conversations/start/', {
          contact_phone: normalizedPhone,
          contact_name: normalizedPhone,
          ...(departmentIdForStart && { department: departmentIdForStart }),
          ...(selectedInstanceId && { instance_id: selectedInstanceId })
        });
        conversation = createResponse.data.conversation || createResponse.data;

        try {
          const convDepartmentId = typeof conversation.department === 'string'
            ? conversation.department
            : conversation.department?.id || null;
          const { setActiveDepartment } = useChatStore.getState();
          if (convDepartmentId && activeDepartment?.id !== convDepartmentId) {
            const { departments } = useChatStore.getState();
            const matchingDept = departments.find(d => d.id === convDepartmentId);
            if (matchingDept) {
              setActiveDepartment(matchingDept);
            } else {
              console.warn(`⚠️ [NEW CONVERSATION] Departamento ${convDepartmentId} não encontrado no store`);
            }
          } else if (!convDepartmentId && activeDepartment?.id !== 'inbox') {
            setActiveDepartment({ id: 'inbox', name: 'Inbox', color: '#ea580c' } as any);
          }
          addConversation(conversation);
        } catch (e) {
          console.error('Erro ao aplicar conversa (department/store):', e);
          addConversation(conversation);
        }
      }

      try {
        setActiveConversation(conversation);
        onClose();
      } catch (e) {
        console.error('Erro ao selecionar conversa:', e);
      }
    } catch (error: any) {
      const convFromError = error?.response?.data?.conversation ?? (error?.response?.data?.id ? error.response.data : null);
      if (convFromError?.id) {
        addConversation(convFromError);
        setActiveConversation(convFromError);
        onClose();
        return;
      }
      console.error('Erro ao iniciar conversa:', error);
      showErrorToast('iniciar', 'Conversa', error);
    } finally {
      setIsCreating(false);
    }
  };

  // Formatar telefone para exibição
  const formatPhone = (phone: string): string => {
    let clean = phone.replace(/[^\d]/g, '');
    
    if (clean.startsWith('55') && clean.length >= 12) {
      clean = clean.substring(2);
    }
    
    if (clean.length === 11) {
      return `(${clean.substring(0, 2)}) ${clean.substring(2, 7)}-${clean.substring(7)}`;
    } else if (clean.length === 10) {
      return `(${clean.substring(0, 2)}) ${clean.substring(2, 6)}-${clean.substring(6)}`;
    }
    
    return phone;
  };

  const isPhone = isPhoneQuery(searchQuery);
  const showPhoneOption = isPhone && contacts.length === 0;
  const effectivePhone = showPhoneOption ? getEffectivePhone(phoneInput) : '';
  const effectivePhoneValid = !!effectivePhone && validatePhone(effectivePhone);

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 bg-black/50 dark:bg-black/60 flex items-center justify-center z-50 p-4 animate-fade-in">
      <div className="bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100 rounded-xl shadow-xl max-w-3xl w-full max-h-[90vh] flex flex-col animate-scale-in">
        {/* Header */}
        <div className="flex items-center justify-between p-6 border-b border-gray-200 dark:border-gray-600">
          <h2 className="text-xl font-bold text-gray-900 dark:text-gray-100">Nova Conversa</h2>
          <button
            onClick={onClose}
            className="text-gray-400 hover:text-gray-600 dark:text-gray-400 dark:hover:text-gray-300 transition-colors"
          >
            <X className="h-6 w-6" />
          </button>
        </div>

        {/* ✅ MULTI-INSTÂNCIA: Seletor de instância (só quando > 1) */}
        {instances.length > 1 && (
          <div className="px-4 pt-4 pb-2 border-b border-gray-200 dark:border-gray-600">
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">Enviar por</label>
            <select
              value={selectedInstanceId ?? ''}
              onChange={(e) => setSelectedInstanceId(e.target.value || null)}
              className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 rounded-lg focus:outline-none focus:ring-2 focus:ring-green-500 focus:ring-offset-2 dark:ring-offset-gray-800 text-sm"
            >
              {instances.map((inst) => (
                <option key={inst.id} value={inst.id}>
                  {inst.friendly_name || inst.instance_name || inst.id}
                </option>
              ))}
            </select>
          </div>
        )}

        {/* Departamento (só quando usuário tem 2+ departamentos) */}
        {userDepartments.length > 1 && (
          <div className="px-4 pt-4 pb-2 border-b border-gray-200 dark:border-gray-600">
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">Iniciar no departamento</label>
            <select
              value={selectedDepartmentId ?? ''}
              onChange={(e) => setSelectedDepartmentId(e.target.value || null)}
              className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 rounded-lg focus:outline-none focus:ring-2 focus:ring-green-500 focus:ring-offset-2 dark:ring-offset-gray-800 text-sm"
            >
              {userDepartments.map((d: { id: string; name: string }) => (
                <option key={d.id} value={d.id}>{d.name}</option>
              ))}
            </select>
          </div>
        )}

        {/* Search Input */}
        <div className="p-6 border-b border-gray-200 dark:border-gray-600 space-y-2">
          <div className="flex gap-2">
            <div className="relative flex-1">
              <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 h-5 w-5 text-gray-400 dark:text-gray-400" />
              <input
                type="text"
                placeholder="Buscar por nome ou telefone..."
                value={searchQuery}
                onChange={(e) => {
                  setSearchQuery(e.target.value);
                  if (isPhoneQuery(e.target.value)) {
                    setPhoneInput(e.target.value);
                  }
                }}
                className="w-full pl-10 pr-4 py-2 border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 placeholder:text-gray-500 dark:placeholder-gray-400 rounded-lg focus:outline-none focus:ring-2 focus:ring-green-500 focus:ring-offset-2 dark:ring-offset-gray-800"
                autoFocus
              />
              {isSearching && (
                <Loader2 className="absolute right-3 top-1/2 transform -translate-y-1/2 h-5 w-5 text-gray-400 dark:text-gray-400 animate-spin" />
              )}
            </div>
            <button
              type="button"
              onClick={() => setIsTagSelectModalOpen(true)}
              className="flex-shrink-0 flex items-center gap-1.5 px-3 py-2 border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-700 dark:text-gray-200 rounded-lg hover:bg-gray-50 dark:hover:bg-gray-600 transition-colors text-sm font-medium active:scale-95"
              title="Filtrar por tag"
            >
              <TagIcon className="h-4 w-4" />
              <span className="hidden sm:inline">Tag</span>
            </button>
          </div>
          {selectedTagsInfo.length > 0 && (
            <div className="flex flex-wrap gap-1.5">
              {selectedTagsInfo.map((tag) => {
                const color = tag.color || '#6b7280';
                return (
                <span
                  key={tag.id}
                  className="inline-flex items-center gap-0.5 pl-2 pr-1 py-1 rounded-full text-xs font-medium border transition-opacity duration-150"
                  style={
                    isDark
                      ? { backgroundColor: 'rgb(55 65 81)', color: 'rgb(229 231 235)', borderColor: 'rgb(75 85 99)' }
                      : { backgroundColor: `${color}20`, color, borderColor: `${color}40` }
                  }
                >
                  {tag.name}
                  <button
                    type="button"
                    onClick={() => {
                      setSelectedTagIds((prev) => prev.filter((id) => id !== tag.id));
                      setSelectedTagsInfo((prev) => prev.filter((t) => t.id !== tag.id));
                    }}
                    className="min-w-[28px] min-h-[28px] flex items-center justify-center rounded-full hover:bg-black/10 dark:hover:bg-white/10 transition-colors active:scale-90"
                    aria-label={`Remover tag ${tag.name}`}
                  >
                    <X className="h-3.5 w-3.5" />
                  </button>
                </span>
                );
              })}
            </div>
          )}
        </div>

        {/* Results */}
        <div className="flex-1 overflow-y-auto p-6">
          {searchQuery.length < 2 && selectedTagIds.length === 0 ? (
            <div className="text-center py-8">
              <Search className="h-12 w-12 mx-auto mb-4 text-gray-300 dark:text-gray-500" />
              <p className="text-gray-500 dark:text-gray-400">Digite um nome ou telefone para buscar</p>
              <p className="text-gray-400 dark:text-gray-500 text-sm mt-1">ou use &quot;Tag&quot; para filtrar por tags</p>
            </div>
          ) : contacts.length > 0 ? (
            <div className="space-y-2">
              {contacts.map((contact) => (
                <button
                  key={contact.id}
                  onClick={() => handleStartConversation(contact)}
                  disabled={isCreating}
                  className="w-full flex items-center gap-3 p-3 hover:bg-gray-50 dark:hover:bg-gray-700 rounded-lg transition-colors text-left disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  <div className="flex-shrink-0 w-10 h-10 rounded-full bg-gray-200 dark:bg-gray-600 flex items-center justify-center">
                    <User className="h-5 w-5 text-gray-600 dark:text-gray-400" />
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="font-medium text-gray-900 dark:text-gray-100 truncate">{contact.name}</div>
                    <div className="text-sm text-gray-500 dark:text-gray-300 flex items-center gap-1">
                      <Phone className="h-3 w-3 text-gray-500 dark:text-gray-400" />
                      <span>{formatPhone(contact.phone)}</span>
                    </div>
                    {contact.tags && contact.tags.length > 0 && (
                      <div className="flex flex-wrap gap-1 mt-1">
                        {contact.tags.slice(0, 2).map((tag) => (
                          <span
                            key={tag.id}
                            className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium border"
                            style={isDark
                              ? { backgroundColor: 'rgb(55 65 81)', color: 'rgb(229 231 235)', border: '1px solid rgb(75 85 99)' }
                              : { backgroundColor: `${tag.color}20`, color: tag.color, border: `1px solid ${tag.color}40` }
                            }
                          >
                            {tag.name}
                          </span>
                        ))}
                        {contact.tags.length > 2 && (
                          <span className="text-xs text-gray-500 dark:text-gray-400">+{contact.tags.length - 2}</span>
                        )}
                      </div>
                    )}
                  </div>
                </button>
              ))}
            </div>
          ) : showPhoneOption ? (
            <div className="py-6 px-4">
              <div className="mb-4 text-center">
                <Phone className="h-10 w-10 mx-auto mb-3 text-gray-300 dark:text-gray-500" />
                <p className="text-gray-600 dark:text-gray-400 mb-1">Nenhum contato encontrado</p>
                <p className="text-sm text-gray-500 dark:text-gray-400 mb-4">Informe o DDD e o número para iniciar a conversa</p>
              </div>
              <div className="max-w-sm mx-auto mb-4">
                <PhoneInputWithDDD
                  value={effectivePhone}
                  onChange={(e164) => setPhoneInput(e164)}
                  defaultDdd="17"
                  placeholder="99999-9999"
                />
              </div>
              <div className="text-center">
                <button
                  onClick={handleStartConversationWithPhone}
                  disabled={isCreating || !effectivePhoneValid}
                  className="px-6 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2 mx-auto"
                >
                {isCreating ? (
                  <>
                    <Loader2 className="h-4 w-4 animate-spin" />
                    <span>Criando...</span>
                  </>
                ) : (
                  <>
                    <Phone className="h-4 w-4" />
                    <span>Iniciar Conversa</span>
                  </>
                )}
                </button>
              </div>
            </div>
          ) : isSearching ? (
            <div className="text-center py-8">
              <Loader2 className="h-8 w-8 mx-auto mb-4 text-gray-400 dark:text-gray-300 animate-spin" />
              <p className="text-gray-500 dark:text-gray-400">Buscando...</p>
            </div>
          ) : (
            <div className="text-center py-8">
              <p className="text-gray-500 dark:text-gray-400">
                {selectedTagIds.length > 0 && searchQuery.trim().length < 2
                  ? 'Nenhum contato com as tags selecionadas'
                  : 'Nenhum resultado encontrado'}
              </p>
              {isPhone && !isValidPhone && (
                <p className="text-sm text-red-500 dark:text-red-400 mt-2">Telefone inválido</p>
              )}
            </div>
          )}
        </div>

        <TagSelectModal
          isOpen={isTagSelectModalOpen}
          onClose={() => setIsTagSelectModalOpen(false)}
          selectedIds={selectedTagIds}
          onApply={(ids, tagsInfo) => {
            setSelectedTagIds(ids);
            setSelectedTagsInfo(tagsInfo);
            setIsTagSelectModalOpen(false);
          }}
        />
      </div>
    </div>
  );
}

