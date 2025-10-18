# 📋 Sistema de Permissões e Roles

## 🎯 Roles Disponíveis

### 1. Administrador (`admin`)
**Acesso:** Total ao tenant

**Pode:**
- ✅ Ver todas as métricas do tenant
- ✅ Acessar todos os chats
- ✅ Gerenciar usuários
- ✅ Gerenciar departamentos
- ✅ Configurar campanhas
- ✅ Ver todos os contatos
- ✅ Exportar dados
- ✅ Configurações globais

**Não pode:**
- ❌ Acessar outros tenants (apenas superuser)

---

### 2. Gerente (`gerente`)
**Acesso:** Departamentos específicos

**Pode:**
- ✅ Ver métricas dos seus departamentos
- ✅ Acessar chat dos seus departamentos
- ✅ Ver contatos dos seus departamentos
- ✅ Ver campanhas dos seus departamentos

**Não pode:**
- ❌ Gerenciar usuários
- ❌ Gerenciar departamentos
- ❌ Ver métricas de outros departamentos
- ❌ Acessar configurações globais
- ❌ Exportar dados completos

---

### 3. Agente (`agente`)
**Acesso:** Apenas chat

**Pode:**
- ✅ Acessar chat dos seus departamentos
- ✅ Ver conversas atribuídas a ele
- ✅ Responder mensagens

**Não pode:**
- ❌ Ver métricas
- ❌ Ver campanhas
- ❌ Ver todos os contatos
- ❌ Gerenciar nada
- ❌ Acessar relatórios

---

## 🔧 Backend - Como Usar

### 1. Permissions

```python
from apps.authn.permissions import IsAdmin, IsGerenteOrAdmin, CanAccessChat

class MyViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated, IsGerenteOrAdmin]
```

**Permissions disponíveis:**
- `IsAdmin` - Apenas admin
- `IsGerenteOrAdmin` - Admin ou gerente
- `CanAccessDepartment` - Verifica acesso ao departamento
- `CanViewMetrics` - Verifica se pode ver métricas
- `CanAccessChat` - Verifica se pode acessar chat

---

### 2. Mixins

```python
from apps.authn.mixins import DepartmentFilterMixin

class ChatViewSet(DepartmentFilterMixin, viewsets.ModelViewSet):
    department_field = 'department'  # Campo FK para department
    
    # Admin vê tudo
    # Gerente/Agente vêem apenas dos seus departamentos
```

**Mixins disponíveis:**
- `DepartmentFilterMixin` - Para models com FK department
- `MultiDepartmentFilterMixin` - Para models com M2M departments
- `MetricsPermissionMixin` - Para views de métricas

---

### 3. Verificar Permissões no Code

```python
# No modelo User
user.is_admin  # True/False
user.is_gerente  # True/False
user.is_agente  # True/False

user.can_access_all_departments()  # Admin retorna True
user.can_view_department_metrics(department)  # Verifica se pode ver métricas
user.can_access_chat(department)  # Verifica se pode acessar chat

# Pegar departamentos do usuário
user.departments.all()
```

---

## 🎨 Frontend - Como Usar

### 1. Hook usePermissions

```tsx
import { usePermissions } from '../hooks/usePermissions'

function MyComponent() {
  const perms = usePermissions()
  
  // Verificar role
  if (perms.isAdmin) {
    // Admin only
  }
  
  if (perms.isGerente) {
    // Gerente only
  }
  
  // Verificar permissões
  if (perms.can_manage_users) {
    // Pode gerenciar usuários
  }
  
  // Verificar acesso a departamento específico
  if (perms.canAccessDepartment('dept-uuid-123')) {
    // Tem acesso
  }
  
  // Saber se precisa filtrar por departamento
  if (perms.needsDepartmentFilter) {
    // Filtrar dados por perms.departmentIds
  }
  
  return <div>...</div>
}
```

**Permissões disponíveis:**
- `can_access_all_departments`
- `can_view_metrics`
- `can_access_chat`
- `can_manage_users`
- `can_manage_departments`
- `can_manage_campaigns`
- `can_view_all_contacts`

**Helpers:**
- `canAccessDashboard` - Admin ou Gerente
- `canAccessSettings` - Apenas Admin
- `canViewReports` - Admin ou Gerente
- `canExportData` - Apenas Admin

---

### 2. Componente PermissionGuard

```tsx
import { PermissionGuard } from '../components/PermissionGuard'

// Por role
<PermissionGuard require="admin">
  <AdminOnlyContent />
</PermissionGuard>

<PermissionGuard require="admin_or_gerente">
  <MetricsDashboard />
</PermissionGuard>

// Por permissão específica
<PermissionGuard permission="can_manage_users">
  <UserManagement />
</PermissionGuard>

// Esconder completamente se não tiver acesso
<PermissionGuard require="admin" hideContent>
  <SettingsButton />
</PermissionGuard>

// Fallback customizado
<PermissionGuard 
  require="admin"
  fallback={<p>Você precisa ser admin</p>}
>
  <AdminPanel />
</PermissionGuard>
```

---

### 3. Hook Imperativo

```tsx
import { usePermissionCheck } from '../components/PermissionGuard'

function MyComponent() {
  const { checkPermission, checkRole } = usePermissionCheck()
  
  const handleAction = () => {
    if (!checkPermission('can_manage_campaigns')) {
      toast.error('Você não tem permissão')
      return
    }
    
    // Fazer ação
  }
  
  return <button onClick={handleAction}>Ação</button>
}
```

---

## 📊 Exemplos de Uso

### Dashboard - Admin vs Gerente

```tsx
function DashboardPage() {
  const perms = usePermissions()
  
  // Admin vê todas as métricas
  // Gerente vê apenas dos seus departamentos
  const params = perms.needsDepartmentFilter 
    ? { department_ids: perms.departmentIds.join(',') }
    : {}
  
  const { data } = useQuery(['metrics', params], () =>
    api.get('/metrics/', { params })
  )
  
  return (
    <div>
      {perms.canAccessDashboard ? (
        <MetricsDisplay data={data} />
      ) : (
        <NoAccessMessage />
      )}
    </div>
  )
}
```

---

### Menu Lateral - Mostrar/Ocultar Itens

```tsx
function Sidebar() {
  const perms = usePermissions()
  
  return (
    <nav>
      {/* Todos vêem */}
      <MenuItem href="/chat" icon={MessageSquare}>
        Chat
      </MenuItem>
      
      {/* Apenas Admin e Gerente */}
      {perms.canViewReports && (
        <MenuItem href="/reports" icon={BarChart}>
          Relatórios
        </MenuItem>
      )}
      
      {/* Apenas Admin */}
      {perms.canAccessSettings && (
        <MenuItem href="/settings" icon={Settings}>
          Configurações
        </MenuItem>
      )}
    </nav>
  )
}
```

---

### Filtrar Lista de Contatos

```tsx
function ContactsPage() {
  const perms = usePermissions()
  
  const fetchContacts = async () => {
    const params: any = {}
    
    // Se não é admin, filtrar por departamentos
    if (perms.needsDepartmentFilter) {
      params.department_ids = perms.departmentIds.join(',')
    }
    
    const response = await api.get('/contacts/', { params })
    return response.data
  }
  
  // ...
}
```

---

## 🔒 Segurança

### Backend (Obrigatório)
**SEMPRE** validar permissões no backend, mesmo se o frontend esconder algo.

```python
# ✅ CORRETO
class ContactViewSet(DepartmentFilterMixin, viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated, IsGerenteOrAdmin]
    department_field = 'department'

# ❌ ERRADO
class ContactViewSet(viewsets.ModelViewSet):
    # Sem permissão, qualquer autenticado pode acessar
```

### Frontend (UX)
O frontend usa permissões para:
- Esconder botões/menus que o usuário não pode usar
- Prevenir chamadas desnecessárias
- Melhorar UX mostrando mensagens claras

**Mas não é segurança!** Um usuário técnico pode manipular o frontend.

---

## 🧪 Testar Permissões

```bash
# Criar usuários de teste
python manage.py shell

from apps.authn.models import User, Department
from apps.tenancy.models import Tenant

tenant = Tenant.objects.first()
dept_vendas = Department.objects.create(tenant=tenant, name="Vendas")
dept_suporte = Department.objects.create(tenant=tenant, name="Suporte")

# Admin
admin = User.objects.create_user(
    username='admin@test.com',
    email='admin@test.com',
    password='senha123',
    tenant=tenant,
    role='admin'
)

# Gerente de Vendas
gerente = User.objects.create_user(
    username='gerente@test.com',
    email='gerente@test.com',
    password='senha123',
    tenant=tenant,
    role='gerente'
)
gerente.departments.add(dept_vendas)

# Agente de Suporte
agente = User.objects.create_user(
    username='agente@test.com',
    email='agente@test.com',
    password='senha123',
    tenant=tenant,
    role='agente'
)
agente.departments.add(dept_suporte)
```

Agora faça login com cada usuário e teste as permissões!

---

## 📚 Recursos Adicionais

- Código: `backend/apps/authn/permissions.py`
- Código: `backend/apps/authn/mixins.py`
- Código: `frontend/src/hooks/usePermissions.ts`
- Código: `frontend/src/components/PermissionGuard.tsx`

