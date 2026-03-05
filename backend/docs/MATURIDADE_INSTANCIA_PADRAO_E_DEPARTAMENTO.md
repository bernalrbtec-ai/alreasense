# Maturidade: Instância padrão por usuário + Departamento na nova conversa

Documento de revisão para liberação em produção. Alterações: instância padrão em Meu Perfil e no modal de nova conversa; departamento automático (1 depto) ou seletor (2+ deptos) no modal.

---

## 1. Resumo da revisão

| Área | Status | Observação |
|------|--------|------------|
| Backend authn (modelo, serializer, view) | Revisado | Campo opcional, serializer mascara inativo/outro tenant, PATCH só altera se chave presente, validação tenant + is_active + tenant_id |
| Backend chat (validação department em start) | Revisado | 403 só quando department enviado e usuário sem acesso; Inbox inalterado |
| Frontend ProfilePage | Revisado | Seção só com 2+ instâncias, payload só envia id válido na lista, select value seguro |
| Frontend NewConversationModal | Revisado | departments defensivo (Array.isArray), departmentIdForStart valida selected na lista, preselection com fallbacks |
| Edge cases e melhorias aplicadas | Revisado | Ver seção 2 |

---

## 2. Edge cases cobertos na implementação

- **PATCH sem a chave:** backend não altera o campo.
- **Valor null / string "null" / string vazia:** tratados como “limpar” no update_profile.
- **UUID inválido ou instância de outro tenant / inativa:** 400 sem save; serializer retorna null se instância inativa ou outro tenant.
- **user.tenant_id ausente:** 400 antes de consultar instância.
- **GET /auth/me/ com instância inativa:** serializer retorna default_whatsapp_instance_id = null (e objeto null).
- **ProfilePage:** envia default_whatsapp_instance_id só se estiver na lista de instâncias atuais; select value só mostra id se existir em instances.
- **Modal:** departments indefinido → Array.isArray fallback; selectedDepartmentId fora da lista → fallback para primeiro depto; 0 deptos → não envia department (Inbox).
- **Conversation start com department:** validação de permissão (can_access_all_departments ou departments.filter(id=...)); 403 com mensagem clara.

---

## 3. Pré-requisito obrigatório para produção

- **Script SQL já executado** no banco de produção (ou executar antes do deploy do código):
  - Arquivo: `backend/scripts/sql_add_user_default_whatsapp_instance.sql`
  - Comando: `ALTER TABLE authn_user ADD COLUMN IF NOT EXISTS default_whatsapp_instance_id UUID NULL REFERENCES notifications_whatsapp_instance(id) ON DELETE SET NULL;`
- Se o código for deployado **sem** a coluna, GET /auth/me/, login e PATCH /auth/profile/ podem falhar ao acessar o campo.

---

## 4. Checklist pré-deploy (produção)

- [ ] Backup do banco ou janela de rollback definida.
- [ ] Script SQL já executado no banco de produção (coluna `authn_user.default_whatsapp_instance_id` existe).
- [ ] Deploy do backend (authn + chat) feito após o SQL.
- [ ] Em staging/homologação já validado: login, GET /auth/me/, PATCH perfil com/sem instância padrão, nova conversa (1 e 2+ instâncias; 0, 1 e 2+ departamentos).
- [ ] Deploy do frontend após (ou junto) do backend.

---

## 5. Testes manuais recomendados antes de liberar

1. **Login e me:** após login, GET /auth/me/ retorna user com `default_whatsapp_instance_id` (null ou UUID) sem erro.
2. **Meu Perfil (2+ instâncias):** exibir seção “Instância padrão”, escolher uma e salvar; recarregar e ver valor persistido; escolher “Nenhuma” e salvar.
3. **Nova conversa:** abrir modal com 2 instâncias; verificar preselection da instância padrão do user; criar conversa e confirmar que não quebra.
4. **Nova conversa – departamentos:** agente com 1 departamento → conversa criada nesse departamento; agente com 2+ → select “Iniciar no departamento” visível e conversa no departamento escolhido; agente sem departamento → conversa no Inbox.
5. **Rollback conhecido:** comando para remover coluna (se necessário): `ALTER TABLE authn_user DROP COLUMN IF EXISTS default_whatsapp_instance_id;`

---

## 6. Rollback

- **Só código:** reverter deploy backend e/ou frontend; banco pode manter a coluna (backend antigo ignora o campo).
- **Remover coluna:** executar `ALTER TABLE authn_user DROP COLUMN IF EXISTS default_whatsapp_instance_id;` após reverter o código que usa o campo.

---

## 7. Conclusão

Com o SQL já aplicado e o checklist acima cumprido, as alterações estão **prontas para produção**: compatibilidade retroativa preservada, edge cases tratados e rollback simples. Recomenda-se validar em staging antes de produção.
