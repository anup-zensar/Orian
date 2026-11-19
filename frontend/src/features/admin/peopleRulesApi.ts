// Hooks for the People & permissions, Rules & thresholds and Messages sections (CR-01).
// Every write refreshes the admin queries and the public reference data (labels, roles ...).
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { apiFetch } from '../../api/client';
import type {
  EvalMetricAdmin,
  EvalMetricCreate,
  MessageTemplateAdmin,
  MessageTemplatesPut,
  PermissionMatrix,
  PermissionsPut,
  RoleAdmin,
  RoleUpdate,
  TemplatePreviewInput,
  TemplatePreviewResult,
  ThresholdsAdmin,
  ThresholdsDocument,
  TieringConfig,
  UserAdmin,
  UserCreate,
  UserDeactivateInput,
  UserDeactivateResult,
  UserUpdate,
} from '../../api/types';
import { invalidateReference } from '../reference/api';

/** One write call; on success the admin queries and the reference data are refetched. */
function useAdminWrite<TIn, TOut>(
  method: 'POST' | 'PUT' | 'PATCH',
  path: (input: TIn) => string,
  body: (input: TIn) => unknown = (input) => input,
) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (input: TIn) => apiFetch<TOut>(path(input), { method, body: body(input) }),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ['admin'] });
      invalidateReference(qc);
    },
  });
}

function useAdminGet<T>(path: string, key: string) {
  return useQuery({
    queryKey: ['admin', key],
    queryFn: ({ signal }) => apiFetch<T>(path, { signal }),
  });
}

// --- people ---------------------------------------------------------------------------------

/** The users list. Fields added by CR-01 (active, assigned_transitions) are optional here. */
export const useUsersList = () => useAdminGet<UserAdmin[]>('/admin/users', 'users-list');

export const useCreateUser = () =>
  useAdminWrite<UserCreate, UserAdmin>('POST', () => '/admin/users');

export const useUpdateUser = () =>
  useAdminWrite<{ id: string; body: UserUpdate }, UserAdmin>(
    'PATCH',
    (i) => `/admin/users/${encodeURIComponent(i.id)}`,
    (i) => i.body,
  );

export const useDeactivateUser = () =>
  useAdminWrite<{ id: string; body: UserDeactivateInput }, UserDeactivateResult>(
    'POST',
    (i) => `/admin/users/${encodeURIComponent(i.id)}/deactivate`,
    (i) => i.body,
  );

export const useUpdateRole = () =>
  useAdminWrite<{ code: string; body: RoleUpdate }, RoleAdmin[]>(
    'PATCH',
    (i) => `/admin/roles/${encodeURIComponent(i.code)}`,
    (i) => i.body,
  );

export const usePermissionMatrix = () =>
  useAdminGet<PermissionMatrix>('/admin/permissions', 'permissions');

export const usePutPermissions = () =>
  useAdminWrite<PermissionsPut, PermissionMatrix>('PUT', () => '/admin/permissions');

// --- rules ----------------------------------------------------------------------------------

export const useTiering = () => useAdminGet<TieringConfig>('/admin/tiering', 'tiering');
export const usePutTiering = () =>
  useAdminWrite<Record<string, unknown>, TieringConfig>('PUT', () => '/admin/tiering');

export const useThresholds = () => useAdminGet<ThresholdsAdmin>('/admin/thresholds', 'thresholds');
export const usePutThresholds = () =>
  useAdminWrite<ThresholdsDocument, ThresholdsAdmin>(
    'PUT',
    () => '/admin/thresholds',
    (thresholds) => ({ thresholds }),
  );

export const useCreateEvalMetric = () =>
  useAdminWrite<EvalMetricCreate, EvalMetricAdmin>('POST', () => '/admin/eval-metrics');

// --- messages -------------------------------------------------------------------------------

export const useMessageTemplates = () =>
  useAdminGet<MessageTemplateAdmin[]>('/admin/message-templates', 'message-templates');

export const usePutTemplates = () =>
  useAdminWrite<MessageTemplatesPut, MessageTemplateAdmin[]>(
    'PUT',
    () => '/admin/message-templates',
  );

/** Preview writes nothing, so it is a plain mutation without any refetching. */
export function usePreviewTemplate() {
  return useMutation({
    mutationFn: (i: { key: string; body: TemplatePreviewInput }) =>
      apiFetch<TemplatePreviewResult>(
        `/admin/message-templates/${encodeURIComponent(i.key)}/preview`,
        { method: 'POST', body: i.body },
      ),
  });
}
