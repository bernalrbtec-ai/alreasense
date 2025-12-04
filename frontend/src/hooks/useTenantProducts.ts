import { useState, useEffect, useMemo } from 'react';
import billingService, { TenantProduct } from '../services/billing';

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

  useEffect(() => {
    // Só buscar se houver token de autenticação
    const authStorage = localStorage.getItem('auth-storage');
    if (!authStorage) {
      console.log('⚠️ Sem auth-storage, não buscando produtos');
      setProducts([]);
      setLoading(false);
      return;
    }
    
    try {
      const auth = JSON.parse(authStorage);
      const token = auth?.state?.token;
      const user = auth?.state?.user;
      
      if (!token || !user) {
        console.log('⚠️ Token ou user não encontrado no storage');
        setProducts([]);
        setLoading(false);
        return;
      }
      
      console.log('✅ Token encontrado, buscando produtos...');
      fetchProducts();
    } catch (e) {
      console.warn('❌ Erro ao parsear auth-storage:', e);
      setProducts([]);
      setLoading(false);
    }
  }, []);

  const hasProduct = (productSlug: string): boolean => {
    if (!Array.isArray(products)) return false;
    return billingService.hasProduct(products, productSlug);
  };

  // Calcular activeProductSlugs com verificação robusta
  const activeProductSlugs = useMemo((): string[] => {
    try {
      console.log('🔄 Calculando activeProductSlugs...');
      console.log('   Products:', products);
      
      // Verificar se products existe e é array
      if (!products || !Array.isArray(products) || products.length === 0) {
        console.log('   ❌ Products não é array válido, retornando []');
        return DEFAULT_ACTIVE_PRODUCT_SLUGS;
      }
      
      // Filtrar e mapear com verificações de segurança
      const active: string[] = [];
      for (const tp of products) {
        if (tp && tp.is_active && tp.product && tp.product.slug && typeof tp.product.slug === 'string') {
          active.push(tp.product.slug);
        }
      }
      
      console.log('   ✅ Produtos ativos:', active);
      return active;
    } catch (error) {
      console.error('❌ Erro ao calcular activeProductSlugs:', error);
      return DEFAULT_ACTIVE_PRODUCT_SLUGS;
    }
  }, [products]);

  return {
    products: Array.isArray(products) ? products : [],
    loading,
    error,
    hasProduct,
    activeProductSlugs: Array.isArray(activeProductSlugs) ? activeProductSlugs : [],
    refetch: fetchProducts,
  };
};

