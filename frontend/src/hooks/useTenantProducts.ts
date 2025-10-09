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

export const useTenantProducts = (): UseTenantProductsReturn => {
  const [products, setProducts] = useState<TenantProduct[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchProducts = async () => {
    try {
      setLoading(true);
      setError(null);
      const data = await billingService.getTenantProducts();
      
      // Garantir que é um array
      if (Array.isArray(data)) {
        setProducts(data);
      } else {
        console.warn('getTenantProducts não retornou um array:', data);
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
    if (authStorage) {
      try {
        const auth = JSON.parse(authStorage);
        if (auth?.state?.token) {
          fetchProducts();
          return;
        }
      } catch (e) {
        console.warn('Erro ao parsear auth-storage:', e);
      }
    }
    
    // Se não houver token, setar como não loading e array vazio
    setProducts([]);
    setLoading(false);
  }, []);

  const hasProduct = (productSlug: string): boolean => {
    if (!Array.isArray(products)) return false;
    return billingService.hasProduct(products, productSlug);
  };

  const activeProductSlugs = useMemo(() => {
    if (!Array.isArray(products)) return [];
    return products
      .filter(tp => tp.is_active)
      .map(tp => tp.product.slug);
  }, [products]);

  return {
    products,
    loading,
    error,
    hasProduct,
    activeProductSlugs,
    refetch: fetchProducts,
  };
};

