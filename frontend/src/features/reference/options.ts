// Option sourcing (CR-01 design 7.1): every dropdown, filter chip and label reads the reference data
// through these hooks, never from a literal array. Adding a project type, region, severity ... in
// Admin therefore needs no code change. Unknown values still render (the value itself, neutral colour).
import { useCallback, useMemo } from 'react';
import type {
  IntakeFieldRef,
  OptionRef,
  PortfolioRef,
  ProjectTypeRef,
  Reference,
  RoleRef,
} from '../../api/types';
import { useReference } from './api';

/** Fluent `Badge` colour tokens an option can carry in `meta.color`. */
export type BadgeColor =
  'brand' | 'danger' | 'important' | 'informative' | 'severe' | 'subtle' | 'success' | 'warning';

const BADGE_COLORS: readonly string[] = [
  'brand',
  'danger',
  'important',
  'informative',
  'severe',
  'subtle',
  'success',
  'warning',
];

/** Shown for a colour nobody defined (unknown value, or a list without a colour meta). */
export const NEUTRAL_COLOR: BadgeColor = 'subtle';

export const INACTIVE_SUFFIX = ' (inactive)';

export interface OptionView {
  value: string;
  /** Display text; an inactive value kept for the current record ends with "(inactive)". */
  label: string;
  description: string;
  meta: Record<string, unknown>;
  active: boolean;
}

export interface UseOptionsConfig {
  /** The record's current value(s): offered even when inactive, labelled "(inactive)". */
  include?: string | readonly string[] | null;
}

function includeSet(include: UseOptionsConfig['include']): Set<string> {
  if (include == null) return new Set();
  return new Set(typeof include === 'string' ? [include] : include);
}

function toView(o: OptionRef, inactiveNote: boolean): OptionView {
  const label = o.label || o.value;
  return {
    value: o.value,
    label: inactiveNote ? `${label}${INACTIVE_SUFFIX}` : label,
    description: o.description ?? '',
    meta: (o.meta ?? {}) as Record<string, unknown>,
    active: o.active ?? true,
  };
}

/** Pure form of `useOptions` (tests, non-hook code): the options of list `key`. */
export function optionsFrom(
  reference: Reference | undefined,
  key: string,
  config: UseOptionsConfig = {},
): OptionView[] {
  const items = reference?.lists?.[key] ?? [];
  const keep = includeSet(config.include);
  return items
    .filter((o) => o.active !== false || keep.has(o.value))
    .map((o) => toView(o, o.active === false));
}

/** Display label of `value` in list `key` (the value itself when unknown, '' when empty). */
export function optionLabelFrom(
  reference: Reference | undefined,
  key: string,
  value: string | null | undefined,
): string {
  if (value == null || value === '') return '';
  const found = reference?.lists?.[key]?.find((o) => o.value === value);
  return found ? found.label || found.value : value;
}

/** `meta.color` of an option as a Fluent Badge colour; neutral for anything unknown. */
export function colorForOption(
  reference: Reference | undefined,
  key: string,
  value: string | null | undefined,
): BadgeColor {
  const color = reference?.lists?.[key]?.find((o) => o.value === value)?.meta?.color;
  return typeof color === 'string' && BADGE_COLORS.includes(color)
    ? (color as BadgeColor)
    : NEUTRAL_COLOR;
}

/** Active options of list `key` (plus the record's current value when inactive). [] while loading. */
export function useOptions(key: string, config: UseOptionsConfig = {}): OptionView[] {
  const { data } = useReference();
  const { include } = config;
  const includeKey = typeof include === 'string' ? include : (include ?? []).join('|');
  return useMemo(
    () => optionsFrom(data, key, { include: includeKey ? includeKey.split('|') : null }),
    [data, key, includeKey],
  );
}

/** `(list, value) => label`; unknown values show themselves. */
export function useOptionLabel(): (list: string, value: string | null | undefined) => string {
  const { data } = useReference();
  return useCallback((list, value) => optionLabelFrom(data, list, value), [data]);
}

/** `(list, value) => Badge colour token`; neutral for unknown values. */
export function useOptionColor(): (list: string, value: string | null | undefined) => BadgeColor {
  const { data } = useReference();
  return useCallback((list, value) => colorForOption(data, list, value), [data]);
}

// --- project types ------------------------------------------------------------------------------

export interface ProjectTypeView extends ProjectTypeRef {
  /** Display text (never empty). */
  label: string;
}

/** Active project types in Admin order (+ `include` when inactive). Flags drive tabs and steps. */
export function useProjectTypes(config: { include?: string | null } = {}): ProjectTypeView[] {
  const { data } = useReference();
  const { include } = config;
  return useMemo(
    () =>
      (data?.project_types ?? [])
        .filter((p) => p.active !== false || p.code === include)
        .map((p) => {
          const label = p.label || p.code;
          return { ...p, label: p.active === false ? `${label}${INACTIVE_SUFFIX}` : label };
        }),
    [data, include],
  );
}

/** One project type by code (active or not), e.g. `useProjectType(t.project_type)?.has_ai_profile`. */
export function useProjectType(code: string | null | undefined): ProjectTypeView | undefined {
  const { data } = useReference();
  return useMemo(() => {
    const found = data?.project_types?.find((p) => p.code === code);
    return found ? { ...found, label: found.label || found.code } : undefined;
  }, [data, code]);
}

// --- portfolios ---------------------------------------------------------------------------------

export interface PortfolioView extends PortfolioRef {
  label: string;
}

/** Active portfolios in Admin order (+ `include` when inactive). `requires_sites` drives site rows. */
export function usePortfolios(config: { include?: string | null } = {}): PortfolioView[] {
  const { data } = useReference();
  const { include } = config;
  return useMemo(
    () =>
      (data?.portfolio_details ?? [])
        .filter((p) => p.active !== false || p.name === include)
        .map((p) => {
          const label = p.label || p.name;
          return { ...p, label: p.active === false ? `${label}${INACTIVE_SUFFIX}` : label };
        }),
    [data, include],
  );
}

// --- roles --------------------------------------------------------------------------------------

export interface RoleView extends RoleRef {
  label: string;
  short_label: string;
}

export interface UseRolesConfig {
  /** Only roles holding a person on every transition (OR focal, PM ... and custom slot roles). */
  slotOnly?: boolean;
  /** Only roles that may be an approval step role. */
  approveOnly?: boolean;
  /** A role to keep even when inactive. */
  include?: string | null;
}

/** Active roles in Admin order. */
export function useRoles(config: UseRolesConfig = {}): RoleView[] {
  const { data } = useReference();
  const { slotOnly, approveOnly, include } = config;
  return useMemo(
    () =>
      (data?.roles ?? [])
        .filter((r) => r.active !== false || r.code === include)
        .filter((r) => !slotOnly || r.has_transition_slot)
        .filter((r) => !approveOnly || r.can_approve)
        .map((r) => ({
          ...r,
          label: r.label || r.code,
          short_label: r.short_label || r.label || r.code,
        })),
    [data, slotOnly, approveOnly, include],
  );
}

/** `(roleCode, kind?) => label`: 'long' "OR focal (S&T)", 'short' "OR focal", 'phrase' for sentences. */
export function useRoleLabel(): (
  code: string | null | undefined,
  kind?: 'long' | 'short' | 'phrase',
) => string {
  const { data } = useReference();
  return useCallback(
    (code, kind = 'long') => {
      if (!code) return '';
      const r = data?.roles?.find((x) => x.code === code);
      if (!r) return code === 'CISO_BISO' ? 'CISO/BISO' : code;
      if (kind === 'short') return r.short_label || r.label || code;
      if (kind === 'phrase') return r.phrase_label || r.label || code;
      return r.label || code;
    },
    [data],
  );
}

// --- gates --------------------------------------------------------------------------------------

/** `(gateCode, kind?) => text`: 'label' = full name, 'short' = "AtD". Falls back to the code. */
export function useGateLabel(): (
  code: string | null | undefined,
  kind?: 'label' | 'short',
) => string {
  const { data } = useReference();
  return useCallback(
    (code, kind = 'label') => {
      if (!code) return '';
      const g = data?.gate_labels?.[code];
      return (kind === 'short' ? g?.short : g?.label) || code;
    },
    [data],
  );
}

// --- intake fields ------------------------------------------------------------------------------

export interface UseIntakeFieldsConfig {
  /** 'intake' (default) or 'ai_profile'. */
  form?: 'intake' | 'ai_profile';
  /** Keep hidden (visible = false) fields too (admin preview, "Retired fields"). */
  includeHidden?: boolean;
  /** Keep inactive fields too (read-only display of stored values). */
  includeInactive?: boolean;
}

/** Form fields in Admin order. The intake form is rendered from this list (design 7.1). */
export function useIntakeFields(config: UseIntakeFieldsConfig = {}): IntakeFieldRef[] {
  const { data } = useReference();
  const { form = 'intake', includeHidden, includeInactive } = config;
  return useMemo(
    () =>
      (data?.intake_fields ?? [])
        .filter((f) => f.form === form)
        .filter((f) => includeInactive || f.active !== false)
        .filter((f) => includeHidden || f.visible !== false)
        .map((f) => ({ ...f, label: f.label || f.key })),
    [data, form, includeHidden, includeInactive],
  );
}

/** Whether `field` applies to this project type and portfolio ([] = all) and whether it is required. */
export function fieldState(
  field: IntakeFieldRef,
  projectType: string | null | undefined,
  portfolio: string | null | undefined,
): { applies: boolean; required: boolean } {
  const types = field.applies_to_project_types ?? [];
  const portfolios = field.applies_to_portfolios ?? [];
  const applies =
    (types.length === 0 || (!!projectType && types.includes(projectType))) &&
    (portfolios.length === 0 || (!!portfolio && portfolios.includes(portfolio)));
  const required =
    field.required_mode === 'always' ||
    (field.required_mode === 'by_project_type' &&
      !!projectType &&
      (field.required_for_project_types ?? []).includes(projectType));
  return { applies, required: applies && required };
}
