import { useState, useEffect } from 'react';
import { api } from '../lib/api';
import { useAuthStore } from '../stores/authStore';

export interface TenantLimits {
  plan: {
    name: string;
    slug: string;
    price: number;
  };
  products: {
    flow?: {
      has_access: boolean;
      current: number;
      limit: number | null;
      unlimited: boolean;
      can_create: boolean;
      message: string | null;
    };
    sense?: {
      has_access: boolean;
      current: number;
      limit: number | null;
      unlimited: boolean;
      message: string | null;
    };
    api_public?: {
      has_access: boolean;
      api_key: string | null;
      limit: number | null;
      unlimited: boolean;
      message: string | null;
    };
  };
  monthly_total: number;
  ui_access: boolean;
}

export const useTenantLimits = () => {
  const [limits, setLimits] = useState<TenantLimits | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchLimits = async () => {
    try {
      console.log('🔄 useTenantLimits - Buscando limites...');
      setLoading(true);
      setError(null);
      const response = await api.get('/tenants/tenants/limits/');
      console.log('📊 useTenantLimits - Limites recebidos:', response.data);
      console.log('📊 useTenantLimits - Flow info:', response.data?.products?.flow);
      setLimits(response.data);
    } catch (err: any) {
      console.error('Erro ao buscar limites do tenant:', err);
      setError(err.response?.data?.error || 'Erro ao carregar limites');
    } finally {
      setLoading(false);
    }
  };

  const checkInstanceLimit = async () => {
    try {
      const response = await api.post('/tenants/tenants/check_instance_limit/');
      return response.data;
    } catch (err: any) {
      console.error('Erro ao verificar limite de instâncias:', err);
      throw err;
    }
  };

  const token = useAuthStore((s) => s.token);

  useEffect(() => {
    if (!token) {
      setLoading(false);
      return;
    }
    fetchLimits();
  }, [token]);

  return {
    limits,
    loading,
    error,
    refetch: fetchLimits,
    checkInstanceLimit,
  };
};
