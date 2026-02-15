import { useState, useEffect, useMemo } from 'react';
import billingService, { TenantProduct } from '../services/billing';
import { useAuthStore } from '../stores/authStore';

interface UseTenantProductsReturn {
  products: TenantProduct[];
  loading: boolean;
  error: string | null;
  hasProduct: (productSlug: string) => boolean;
  activeProductSlugs: string[];
  refetch: () => Promise<void>;
}

// Constante global para evitar problemas de TDZ
const DEFAULT_ACTIVE_PRODUCT_SLUGS: string[] = [];

export const useTenantProducts = (): UseTenantProductsReturn => {
  const [products, setProducts] = useState<TenantProduct[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchProducts = async () => {
    try {
      setLoading(true);
      setError(null);
      console.log('🔍 Buscando produtos do tenant...');
      const data = await billingService.getTenantProducts();
      console.log('📦 Dados recebidos:', data);
      
      // Garantir que é um array
      if (Array.isArray(data)) {
        console.log('✅ Dados são um array, definindo produtos:', data);
        setProducts(data);
      } else {
        console.warn('⚠️ getTenantProducts não retornou um array:', data);
        setProducts([]);
      }
    } catch (err: any) {
      console.error('Erro ao buscar produtos do tenant:', err);
      
      // Se for erro 401 ou 403, não fazer nada (usuário não autenticado)
      if (err.response?.status === 401 || err.response?.status === 403) {
        setProducts([]);
        setError(null); // Não mostrar erro
      } else {
        setError(err.response?.data?.error || 'Erro ao carregar produtos');
        // Fallback: assumir que tem todos os produtos principais
        setProducts([]);
      }
    } finally {
      setLoading(false);
    }
  };

  const token = useAuthStore((s) => s.token);

  useEffect(() => {
    if (!token) {
      setProducts([]);
      setLoading(false);
      return;
    }
    fetchProducts();
  }, [token]);

  const hasProduct = (productSlug: string): boolean => {
    if (!Array.isArray(products)) return false;
    return billingService.hasProduct(products, productSlug);
  };

  // ✅ CORREÇÃO CRÍTICA: Calcular activeProductSlugs com verificação robusta
  // ✅ CORREÇÃO: Garantir que products está sempre definido antes de usar no useMemo
  const safeProducts = Array.isArray(products) ? products : [];
  
  const activeProductSlugs = useMemo((): string[] => {
    try {
      // ✅ CORREÇÃO: Usar safeProducts ao invés de products diretamente
      if (!safeProducts || safeProducts.length === 0) {
        return DEFAULT_ACTIVE_PRODUCT_SLUGS;
      }
      
      // Filtrar e mapear com verificações de segurança
      const active: string[] = [];
      for (const tp of safeProducts) {
        if (tp && tp.is_active && tp.product && tp.product.slug && typeof tp.product.slug === 'string') {
          active.push(tp.product.slug);
        }
      }
      
      return active;
    } catch (error) {
      console.error('❌ Erro ao calcular activeProductSlugs:', error);
      return DEFAULT_ACTIVE_PRODUCT_SLUGS;
    }
  }, [safeProducts]);

  // ✅ CORREÇÃO: Garantir que sempre retornamos valores válidos
  return {
    products: safeProducts,
    loading,
    error,
    hasProduct,
    activeProductSlugs: Array.isArray(activeProductSlugs) ? activeProductSlugs : DEFAULT_ACTIVE_PRODUCT_SLUGS,
    refetch: fetchProducts,
  };
};

