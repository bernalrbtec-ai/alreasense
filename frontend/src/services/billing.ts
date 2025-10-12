import { api } from '../lib/api';

export interface Product {
  id: string;
  slug: string;
  name: string;
  description: string;
  is_active: boolean;
  requires_ui_access: boolean;
  addon_price: string | null;
  icon?: string;
  color?: string;
}

export interface Plan {
  id: string;
  slug: string;
  name: string;
  description: string;
  price: string;
  is_active: boolean;
  sort_order: number;
  product_count: number;
}

export interface TenantProduct {
  id: string;
  product: Product;
  is_addon: boolean;
  is_active: boolean;
  activated_at: string;
}

export interface BillingInfo {
  plan: Plan | null;
  active_products: TenantProduct[];
  monthly_total: string;
  next_billing_date: string | null;
  ui_access: boolean;
}

export interface BillingSummary {
  plan: {
    name: string;
    price: number;
  };
  active_products_count: number;
  monthly_total: string;
  next_billing_date: string | null;
  recent_history: any[];
}

const billingService = {
  // Produtos
  getProducts: async (): Promise<Product[]> => {
    const response = await api.get('/billing/products/');
    return response.data;
  },

  getAvailableProducts: async (): Promise<Product[]> => {
    const response = await api.get('/billing/products/available/');
    return response.data;
  },

  // Planos
  getPlans: async (): Promise<Plan[]> => {
    const response = await api.get('/billing/plans/');
    return response.data;
  },

  selectPlan: async (planId: string): Promise<{ success: boolean; message: string }> => {
    const response = await api.post(`/billing/plans/${planId}/select/`);
    return response.data;
  },

  // Produtos do Tenant
  getTenantProducts: async (): Promise<TenantProduct[]> => {
    const response = await api.get('/billing/tenant-products/');
    // A API retorna paginado, então precisamos pegar o array 'results'
    return response.data.results || response.data;
  },

  addAddon: async (productId: string): Promise<TenantProduct> => {
    const response = await api.post('/billing/tenant-products/', { product_id: productId });
    return response.data;
  },

  deactivateAddon: async (tenantProductId: string): Promise<{ success: boolean; message: string }> => {
    const response = await api.post(`/billing/tenant-products/${tenantProductId}/deactivate/`);
    return response.data;
  },

  // Informações de Billing
  getBillingInfo: async (): Promise<BillingInfo> => {
    const response = await api.get('/billing/billing/');
    return response.data;
  },

  getBillingSummary: async (): Promise<BillingSummary> => {
    const response = await api.get('/billing/billing/summary/');
    return response.data;
  },

  // Histórico
  getHistory: async (params?: any) => {
    const response = await api.get('/billing/history/', { params });
    return response.data;
  },

  // Verificar acesso a produto
  hasProduct: (activeProducts: TenantProduct[], productSlug: string): boolean => {
    return activeProducts.some(
      tp => tp.is_active && tp.product.slug === productSlug
    );
  },
};

export default billingService;

