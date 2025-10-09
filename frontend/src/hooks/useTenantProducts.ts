import { useState, useEffect } from 'react';
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
      setProducts(data);
    } catch (err: any) {
      console.error('Erro ao buscar produtos do tenant:', err);
      setError(err.response?.data?.error || 'Erro ao carregar produtos');
      // Fallback: assumir que tem todos os produtos se der erro
      setProducts([]);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchProducts();
  }, []);

  const hasProduct = (productSlug: string): boolean => {
    return billingService.hasProduct(products, productSlug);
  };

  const activeProductSlugs = products
    .filter(tp => tp.is_active)
    .map(tp => tp.product.slug);

  return {
    products,
    loading,
    error,
    hasProduct,
    activeProductSlugs,
    refetch: fetchProducts,
  };
};

