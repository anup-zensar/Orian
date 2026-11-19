// Hooks for the catalogue sections of Admin: checklists and items, project types, portfolios,
// form fields and dropdown lists. Every save refreshes the admin queries and the reference data,
// so the intake form and the dropdowns elsewhere show the change straight away.
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { apiFetch } from '../../api/client';
import type {
  ChecklistAdmin,
  ChecklistCreate,
  ChecklistUpdate,
  IntakeFieldAdmin,
  IntakeFieldCreate,
  IntakeFieldUpdate,
  OptionItemInput,
  OptionItemsAdmin,
  OptionListAdmin,
  OptionListCreate,
  PortfolioAdmin,
  PortfolioCreate,
  PortfolioUpdate,
  ProjectTypeAdmin,
  ProjectTypeCreate,
  ProjectTypeUpdate,
} from '../../api/types';
import type { components } from '../../api/schema';
import { invalidateReference } from '../reference/api';
import type { PlaybookItem } from './api';

export type PlaybookItemCreate = components['schemas']['PlaybookItemCreateIn'];

/** POST / PATCH / PUT / DELETE helper: refreshes every admin query and the reference data. */
function useAdminWrite<TIn, TOut = unknown>(
  method: 'POST' | 'PATCH' | 'PUT' | 'DELETE',
  path: (input: TIn) => string,
  body?: (input: TIn) => unknown,
) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (input: TIn) =>
      apiFetch<TOut>(path(input), { method, body: body ? body(input) : undefined }),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ['admin'] });
      invalidateReference(qc);
    },
  });
}

const enc = encodeURIComponent;

// --- checklists and items -----------------------------------------------------------------------

export function useChecklists() {
  return useQuery({
    queryKey: ['admin', 'checklists'],
    queryFn: ({ signal }) => apiFetch<ChecklistAdmin[]>('/admin/checklists', { signal }),
  });
}
export const useCreateChecklist = () =>
  useAdminWrite<ChecklistCreate>(
    'POST',
    () => '/admin/checklists',
    (b) => b,
  );
export const useUpdateChecklist = () =>
  useAdminWrite<{ code: string; body: ChecklistUpdate }>(
    'PATCH',
    (i) => `/admin/checklists/${enc(i.code)}`,
    (i) => i.body,
  );
export const useCreatePlaybookItem = () =>
  useAdminWrite<PlaybookItemCreate, PlaybookItem>(
    'POST',
    () => '/admin/playbook-items',
    (b) => b,
  );

// --- project types ------------------------------------------------------------------------------

export function useProjectTypesAdmin() {
  return useQuery({
    queryKey: ['admin', 'project-types'],
    queryFn: ({ signal }) => apiFetch<ProjectTypeAdmin[]>('/admin/project-types', { signal }),
  });
}
export const useCreateProjectType = () =>
  useAdminWrite<ProjectTypeCreate>(
    'POST',
    () => '/admin/project-types',
    (b) => b,
  );
export const useUpdateProjectType = () =>
  useAdminWrite<{ code: string; body: ProjectTypeUpdate }>(
    'PATCH',
    (i) => `/admin/project-types/${enc(i.code)}`,
    (i) => i.body,
  );

// --- portfolios ---------------------------------------------------------------------------------

export function usePortfoliosAdmin() {
  return useQuery({
    queryKey: ['admin', 'portfolios'],
    queryFn: ({ signal }) => apiFetch<PortfolioAdmin[]>('/admin/portfolios', { signal }),
  });
}
export const useCreatePortfolio = () =>
  useAdminWrite<PortfolioCreate>(
    'POST',
    () => '/admin/portfolios',
    (b) => b,
  );
export const useUpdatePortfolio = () =>
  useAdminWrite<{ name: string; body: PortfolioUpdate }>(
    'PATCH',
    (i) => `/admin/portfolios/${enc(i.name)}`,
    (i) => i.body,
  );

// --- form fields --------------------------------------------------------------------------------

export function useIntakeFieldsAdmin() {
  return useQuery({
    queryKey: ['admin', 'intake-fields'],
    queryFn: ({ signal }) => apiFetch<IntakeFieldAdmin[]>('/admin/intake-fields', { signal }),
  });
}
export const useCreateIntakeField = () =>
  useAdminWrite<IntakeFieldCreate>(
    'POST',
    () => '/admin/intake-fields',
    (b) => b,
  );
export const useUpdateIntakeField = () =>
  useAdminWrite<{ key: string; body: IntakeFieldUpdate }>(
    'PATCH',
    (i) => `/admin/intake-fields/${enc(i.key)}`,
    (i) => i.body,
  );

/** Saves a new field order. The list is reordered on screen first and put back if the save fails. */
export function useOrderIntakeFields() {
  const qc = useQueryClient();
  const key = ['admin', 'intake-fields'];
  return useMutation({
    mutationFn: (keys: string[]) =>
      apiFetch<unknown>('/admin/intake-fields/order', { method: 'PUT', body: { keys } }),
    onMutate: (keys: string[]) => {
      qc.setQueryData<IntakeFieldAdmin[]>(key, (old) =>
        old ? keys.flatMap((k) => old.filter((f) => f.key === k)) : old,
      );
    },
    onSettled: () => {
      void qc.invalidateQueries({ queryKey: ['admin'] });
      invalidateReference(qc);
    },
  });
}

// --- dropdown lists -----------------------------------------------------------------------------

export function useOptionListsAdmin() {
  return useQuery({
    queryKey: ['admin', 'option-lists'],
    queryFn: ({ signal }) => apiFetch<OptionListAdmin[]>('/admin/option-lists', { signal }),
  });
}
export const useCreateOptionList = () =>
  useAdminWrite<OptionListCreate>(
    'POST',
    () => '/admin/option-lists',
    (b) => b,
  );

export function useOptionItemsAdmin(listKey: string) {
  return useQuery({
    queryKey: ['admin', 'option-lists', listKey, 'items'],
    queryFn: ({ signal }) =>
      apiFetch<OptionItemsAdmin>(`/admin/option-lists/${enc(listKey)}/items`, { signal }),
    enabled: !!listKey,
  });
}
export const usePutOptionItems = () =>
  useAdminWrite<{ key: string; items: OptionItemInput[] }, OptionItemsAdmin>(
    'PUT',
    (i) => `/admin/option-lists/${enc(i.key)}/items`,
    (i) => ({ items: i.items }),
  );
