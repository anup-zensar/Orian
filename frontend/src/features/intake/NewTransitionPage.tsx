import { useEffect, useMemo, useRef, useState, type ReactNode } from 'react';
import { Controller, useFieldArray, useForm, useWatch, type Control } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import { useNavigate, useSearchParams } from 'react-router';
import {
  Body1,
  Button,
  Caption1,
  Dialog,
  DialogActions,
  DialogBody,
  DialogContent,
  DialogSurface,
  DialogTitle,
  Field,
  Input,
  MessageBar,
  MessageBarActions,
  MessageBarBody,
  Select,
  Subtitle2,
  Textarea,
  Toast,
  ToastTitle,
  Tooltip,
  makeStyles,
  tokens,
  useToastController,
} from '@fluentui/react-components';
import { Add16Regular, Delete16Regular } from '@fluentui/react-icons';
import { AiBadge } from '../../components/AiBadge';
import { PageHeader } from '../../components/PageHeader';
import { SectionCard } from '../../components/SectionCard';
import { FormGrid } from '../../components/layout/FormGrid';
import { SplitLayout } from '../../components/layout/SplitLayout';
import { Toolbar } from '../../components/layout/Toolbar';
import { LoadingState } from '../../components/LoadingState';
import { ErrorState } from '../../components/ErrorState';
import { ApiError } from '../../api/client';
import type {
  IntakeFieldRef,
  Me,
  PortfolioRef,
  ProjectTypeRef,
  Reference,
  User,
} from '../../api/types';
import { TOASTER_ID, useApiErrorToast } from '../../hooks/useApiErrorToast';
import { useReference } from '../reference/api';
import { fieldState, optionsFrom, useIntakeFields } from '../reference/options';
import { useProposal, type Proposal } from '../orion/api';
import { useMe, useUsers } from '../users/api';
import { useCreateTransition, useFetchServiceNow, type TransitionCreate } from './api';
import { DynamicField } from './DynamicField';
import { emptyValue, fromApiValue, isEmptyValue, toApiValue, type FieldValue } from './fieldValues';

const schema = z.object({
  name: z.string().trim().min(1, 'Name is required').max(200),
  servicenow_project_id: z.string(),
  project_type: z.string().min(1, 'Project type is required'),
  portfolio: z.string().min(1, 'Portfolio is required'),
  region: z.string().min(1, 'Region is required'),
  market: z.string(),
  sites: z.array(z.object({ site_id: z.string(), site_key: z.string() })),
  audience: z.string(),
  write_actions: z.string(),
  sensitive_data: z.string(),
  target_gate: z.string(),
  investment_type: z.string(),
  delivery_method: z.string(),
  description: z.string(),
  or_focal_user_id: z.string().min(1, 'OR focal is required'),
  pm_user_id: z.string(),
  architect_user_id: z.string(),
  olm_user_id: z.string(),
  irm_user_id: z.string(),
  next_decision_date: z.string(),
  /** Values of the custom fields ("Additional details"), by field key. */
  custom: z.record(z.string(), z.custom<FieldValue>()),
});

type FormValues = z.infer<typeof schema>;
type SimpleKey = Exclude<keyof FormValues, 'sites' | 'custom'>;

/** What the form needs from the configuration to decide what is required. */
interface IntakeConfig {
  fields: IntakeFieldRef[];
  projectTypes: ProjectTypeRef[];
  portfolios: PortfolioRef[];
}

/** Keys of the fields that apply to this project type and portfolio and must be filled in. */
function requiredKeys(
  fields: IntakeFieldRef[],
  projectType: ProjectTypeRef | undefined,
  portfolio: string,
): Set<string> {
  const keys = new Set<string>();
  for (const f of fields) {
    const state = fieldState(f, projectType?.code, portfolio);
    const typeNeedsIt = projectType?.required_intake_fields?.includes(f.key) ?? false;
    if (state.applies && (state.required || typeNeedsIt)) keys.add(f.key);
  }
  return keys;
}

/** The form schema: the fixed shape above plus the rules that come from the configuration. */
function makeSchema(config: IntakeConfig) {
  return schema.superRefine((v, ctx) => {
    const projectType = config.projectTypes.find((p) => p.code === v.project_type);
    for (const key of requiredKeys(config.fields, projectType, v.portfolio)) {
      const field = config.fields.find((f) => f.key === key);
      // The five structural fields are checked by the schema above; a switch is never "empty".
      if (!field || field.structural || field.type === 'boolean') continue;
      const value = field.builtin
        ? (v as Record<string, unknown>)[key]
        : (v.custom[key] as FieldValue | undefined);
      if (!isEmptyValue(field, value as FieldValue | undefined)) continue;
      const message =
        field.required_mode === 'always'
          ? `${field.label} is required`
          : 'Required for this project type';
      ctx.addIssue({
        code: 'custom',
        path: field.builtin ? [key] : ['custom', key],
        message,
      });
    }
    if (config.portfolios.find((p) => p.name === v.portfolio)?.requires_sites) {
      if (v.sites.length === 0) {
        ctx.addIssue({ code: 'custom', path: ['sites'], message: 'Add at least one site' });
      }
      v.sites.forEach((s, i) => {
        if (!s.site_id.trim())
          ctx.addIssue({
            code: 'custom',
            path: ['sites', i, 'site_id'],
            message: 'Site ID required',
          });
        if (!s.site_key.trim())
          ctx.addIssue({
            code: 'custom',
            path: ['sites', i, 'site_key'],
            message: 'Site key required',
          });
      });
    }
  });
}

const useStyles = makeStyles({
  full: { gridColumn: '1 / -1', minWidth: 0 },
  row: {
    display: 'flex',
    flexWrap: 'wrap',
    gap: tokens.spacingHorizontalS,
    alignItems: 'flex-end',
    minWidth: 0,
  },
  grow: { flex: '1 1 200px', minWidth: 0 },
  siteRow: {
    display: 'flex',
    flexWrap: 'wrap',
    gap: tokens.spacingHorizontalS,
    alignItems: 'flex-start',
    minWidth: 0,
  },
  stack: { display: 'flex', flexDirection: 'column', gap: tokens.spacingVerticalM, minWidth: 0 },
  list: { margin: 0, paddingLeft: '20px' },
});

interface Opt {
  value: string;
  label?: string;
}

function SelectField(props: {
  control: Control<FormValues>;
  name: SimpleKey;
  label: string;
  options: Opt[];
  required?: boolean;
  marker?: ReactNode;
  hint?: ReactNode;
}) {
  return (
    <Controller
      control={props.control}
      name={props.name}
      render={({ field, fieldState }) => (
        <Field
          label={
            <>
              {props.label}
              {props.marker}
            </>
          }
          hint={props.hint ? { children: props.hint } : undefined}
          required={props.required}
          validationMessage={fieldState.error?.message}
          validationState={fieldState.error ? 'error' : 'none'}
        >
          <Select
            value={field.value}
            onChange={(_, d) => field.onChange(d.value)}
            onBlur={field.onBlur}
          >
            <option value="">Select…</option>
            {props.options.map((o) => (
              <option key={o.value} value={o.value}>
                {o.label ?? o.value}
              </option>
            ))}
          </Select>
        </Field>
      )}
    />
  );
}

/** Checklists that count items at intake: the library sizes the reference data carries. */
function itemCountOf(reference: Reference, code: string): number | null {
  const counts = reference.checklist_counts;
  if (code === 'FRAMEWORK') return counts.framework;
  if (code === 'AI_PLAYBOOK') return counts.ai_playbook_total;
  if (code === 'COMMON') return counts.common;
  return null;
}

function AutoScopePanel(props: { control: Control<FormValues>; reference: Reference }) {
  const s = useStyles();
  const { project_type, portfolio, region } = useWatch({ control: props.control });
  const pt = props.reference.project_types.find((p) => p.code === project_type);
  const details = props.reference.portfolio_details.find((p) => p.name === portfolio);
  const flavour = [pt?.label || project_type, details?.label || portfolio, region]
    .filter(Boolean)
    .join(' · ');
  // The project type's checklists, then the portfolio golden set, then the common items.
  const lists = (pt?.checklists ?? [])
    .map((code) => props.reference.checklists.find((c) => c.code === code))
    .filter((c): c is NonNullable<typeof c> => !!c && c.active);
  return (
    <SectionCard title="Auto-scope">
      <div className={s.stack}>
        <Body1 style={{ fontWeight: tokens.fontWeightSemibold }}>
          {flavour || 'Choose project type, portfolio and region'}
        </Body1>
        <Caption1>Checklists that will apply</Caption1>
        <ul className={s.list}>
          {lists.map((c) => {
            const count = itemCountOf(props.reference, c.code);
            return (
              <li key={c.code}>
                {c.label}
                {c.tier_filtered
                  ? ` (Tier ?) – ${count != null ? `up to ${count}, ` : ''}filtered once the tier is set`
                  : count != null
                    ? ` ${count}`
                    : ''}
              </li>
            );
          })}
          {details && (
            <li>
              {details.label || details.name} golden set {details.golden_set_count}
            </li>
          )}
          <li>Common {props.reference.checklist_counts.common}</li>
        </ul>
        {details && details.focus_areas.length > 0 && (
          <>
            <Caption1>{details.label || details.name} focus areas</Caption1>
            <ul className={s.list}>
              {details.focus_areas.map((f) => (
                <li key={f}>{f}</li>
              ))}
            </ul>
          </>
        )}
      </div>
    </SectionCard>
  );
}

const SIMPLE_KEYS: SimpleKey[] = [
  'name',
  'servicenow_project_id',
  'project_type',
  'portfolio',
  'region',
  'market',
  'audience',
  'write_actions',
  'sensitive_data',
  'target_gate',
  'investment_type',
  'delivery_method',
  'description',
  'or_focal_user_id',
  'pm_user_id',
  'architect_user_id',
  'olm_user_id',
  'irm_user_id',
  'next_decision_date',
];

const SOURCE_LABEL: Record<string, string> = {
  servicenow: 'ServiceNow',
  text: 'Your text',
  document: 'Document',
  context: 'You (default)',
  inferred: 'Inferred',
};

/** What Orion found for one intake field (payload.fields of a create_transition proposal). */
interface OrionField {
  name: string;
  label: string;
  state: string;
  source?: string | null;
  confidence?: number;
  evidence?: string | null;
  note?: string | null;
  candidates?: { value: string; label: string }[];
}

interface OrionPrefill {
  prefill: Record<string, unknown>;
  fields: OrionField[];
  missing: string[];
  ambiguous: string[];
  excerpt: string;
  warnings: string[];
}

function readPrefill(proposal: Proposal): OrionPrefill {
  const p = proposal.payload;
  const arr = (v: unknown): unknown[] => (Array.isArray(v) ? v : []);
  return {
    prefill:
      p.prefill && typeof p.prefill === 'object' ? (p.prefill as Record<string, unknown>) : {},
    fields: arr(p.fields) as OrionField[],
    missing: arr(p.missing_fields).map(String),
    ambiguous: arr(p.ambiguous_fields).map(String),
    excerpt: typeof p.source_excerpt === 'string' ? p.source_excerpt : '',
    warnings: arr(p.warnings).map(String),
  };
}

/** Marker shown next to a field Orion filled; editing the field removes it. */
function OrionMarker({ field }: { field: OrionField }) {
  const src = field.source ? (SOURCE_LABEL[field.source] ?? field.source) : 'Orion';
  const tip = `Filled by Orion. Source: ${src}${field.evidence ? ` - "${field.evidence}"` : ''}`;
  return (
    <Tooltip content={tip} relationship="description">
      <span style={{ marginLeft: 6, display: 'inline-flex', verticalAlign: 'middle' }} tabIndex={0}>
        <AiBadge />
      </span>
    </Tooltip>
  );
}

const hintOf = (h: ReactNode) => (h ? { children: h } : undefined);

/** The choices of a select / multiselect / user field; null for a free-text field. */
function choicesFor(field: IntakeFieldRef, reference: Reference, users: User[]): Opt[] | null {
  const list = field.option_list ?? '';
  if (field.type === 'user') {
    return users.filter((u) => u.role === list).map((u) => ({ value: u.id, label: u.name }));
  }
  if (field.type !== 'select' && field.type !== 'multiselect') return null;
  if (list === 'project_types') {
    return reference.project_types
      .filter((p) => p.active)
      .map((p) => ({ value: p.code, label: p.label || p.code }));
  }
  if (list === 'portfolios') {
    return reference.portfolio_details
      .filter((p) => p.active)
      .map((p) => ({ value: p.name, label: p.label || p.name }));
  }
  return optionsFrom(reference, list).map((o) => ({ value: o.value, label: o.label }));
}

/** An Orion value for one field (custom fields may sit under `custom_fields` or directly). */
function prefillOf(orion: OrionPrefill, key: string): unknown {
  const custom = orion.prefill['custom_fields'];
  if (custom && typeof custom === 'object' && key in custom) {
    return (custom as Record<string, unknown>)[key];
  }
  return orion.prefill[key];
}

function IntakeForm(props: {
  reference: Reference;
  users: User[];
  me: Me;
  orion: OrionPrefill | null;
}) {
  const { reference, users, me, orion } = props;
  const s = useStyles();
  const navigate = useNavigate();
  const showError = useApiErrorToast();
  const { dispatchToast } = useToastController(TOASTER_ID);
  const create = useCreateTransition();
  const fetchSn = useFetchServiceNow();

  // The configured form: built-in fields (label, help, visibility) and the custom fields.
  // A field an Admin hid stays on the form when a project type (or the field itself) requires it,
  // otherwise nobody could create that kind of transition.
  const allFields = useIntakeFields({ includeHidden: true });
  const fields = useMemo(
    () =>
      allFields.filter(
        (f) =>
          f.visible !== false ||
          f.required_mode === 'always' ||
          reference.project_types.some((t) => t.required_intake_fields?.includes(f.key)),
      ),
    [allFields, reference.project_types],
  );
  const fieldOf = (key: string) => fields.find((f) => f.key === key);
  const customFields = useMemo(() => fields.filter((f) => !f.builtin), [fields]);
  const config = useMemo<IntakeConfig>(
    () => ({
      fields,
      projectTypes: reference.project_types,
      portfolios: reference.portfolio_details,
    }),
    [fields, reference],
  );
  const formSchema = useMemo(() => makeSchema(config), [config]);
  const label = (key: string, fallback: string) => fieldOf(key)?.label ?? fallback;
  const choices = (key: string): Opt[] => {
    const f = fieldOf(key);
    return (f && choicesFor(f, reference, users)) || [];
  };

  // Orion values that are not an option (e.g. region "UK"), so the person is asked to choose.
  const rejected = useMemo(() => {
    const r: Record<string, string> = {};
    if (!orion) return r;
    for (const f of fields) {
      const v = prefillOf(orion, f.key);
      const valid = choicesFor(f, reference, users)?.map((o) => o.value);
      if (typeof v === 'string' && v !== '' && valid && !valid.includes(v)) r[f.key] = v;
    }
    return r;
  }, [orion, fields, reference, users]);

  const defaults = useMemo<FormValues>(() => {
    const pick = (role: string, id: string) =>
      users.some((u) => u.id === id && u.role === role) ? id : '';
    const custom: Record<string, FieldValue> = {};
    for (const f of customFields) {
      const fromOrion = orion ? prefillOf(orion, f.key) : undefined;
      custom[f.key] =
        fromOrion != null && !(f.key in rejected) ? fromApiValue(f, fromOrion) : emptyValue(f);
    }
    const base: FormValues = {
      name: '',
      servicenow_project_id: '',
      project_type: '',
      portfolio: '',
      region: '',
      market: '',
      sites: [],
      audience: '',
      write_actions: '',
      sensitive_data: '',
      target_gate: '',
      investment_type: '',
      delivery_method: '',
      description: '',
      or_focal_user_id: me.user.role === 'OR_FOCAL' ? me.user.id : '',
      pm_user_id: pick('PM', 'U10'),
      architect_user_id: pick('ARCHITECT', 'U11'),
      olm_user_id: pick('OLM', 'U12'),
      irm_user_id: pick('IRM', 'U14'),
      next_decision_date: '',
      custom,
    };
    if (!orion) return base;
    // Orion only fills what it found; unknown keys are ignored, nothing is submitted for the user.
    const merged: FormValues = { ...base };
    for (const k of SIMPLE_KEYS) {
      const v = orion.prefill[k];
      if (typeof v === 'string' && v !== '' && !(k in rejected)) merged[k] = v;
    }
    const sites = orion.prefill['sites'];
    if (Array.isArray(sites)) {
      merged.sites = sites
        .filter((x): x is Record<string, unknown> => !!x && typeof x === 'object')
        .map((x) => ({ site_id: String(x.site_id ?? ''), site_key: String(x.site_key ?? '') }));
    }
    return merged;
  }, [users, me.user.id, me.user.role, orion, rejected, customFields]);

  const { control, handleSubmit, setValue, getValues, formState } = useForm<FormValues>({
    resolver: zodResolver(formSchema),
    defaultValues: defaults,
  });
  const { fields: siteRows, append, remove } = useFieldArray({ control, name: 'sites' });
  const allValues = useWatch({ control });
  const orionFields = useMemo(() => {
    const m = new Map<string, OrionField>();
    for (const f of orion?.fields ?? []) m.set(f.name, f);
    return m;
  }, [orion]);
  // Fields Orion filled (found or inferred); typing in one removes its marker.
  const [aiActive, setAiActive] = useState<Set<string>>(
    () =>
      new Set(
        (orion?.fields ?? [])
          .filter(
            (f) =>
              (f.state === 'found' || f.state === 'inferred') &&
              prefillOf(orion as OrionPrefill, f.name) !== undefined &&
              !(f.name in rejected),
          )
          .map((f) => f.name),
      ),
  );
  const clearAi = (name: string) =>
    setAiActive((prev) => {
      if (!prev.has(name)) return prev;
      const next = new Set(prev);
      next.delete(name);
      return next;
    });
  // Text inputs are controlled (Fluent inputs keep their own value, so uncontrolled register() would
  // lose pre-filled values on re-render). Typing removes the Orion marker of that field.
  const bind = (name: SimpleKey) => ({
    name,
    value: String((allValues as Record<string, unknown>)[name] ?? ''),
    onChange: (_: unknown, d: { value: string }) => {
      clearAi(name);
      setValue(name, d.value, { shouldDirty: true, shouldValidate: formState.isSubmitted });
    },
  });
  const bindSite = (i: number, key: 'site_id' | 'site_key') => ({
    value: allValues.sites?.[i]?.[key] ?? '',
    onChange: (_: unknown, d: { value: string }) => {
      clearAi('sites');
      setValue(`sites.${i}.${key}`, d.value, {
        shouldDirty: true,
        shouldValidate: formState.isSubmitted,
      });
    },
  });

  const projectType = useWatch({ control, name: 'project_type' });
  const portfolio = useWatch({ control, name: 'portfolio' });
  const region = useWatch({ control, name: 'region' });
  const projectTypeCfg = reference.project_types.find((p) => p.code === projectType);
  const portfolioCfg = reference.portfolio_details.find((p) => p.name === portfolio);
  const requiresSites = !!portfolioCfg?.requires_sites;
  const required = useMemo(
    () => requiredKeys(fields, projectTypeCfg, portfolio ?? ''),
    [fields, projectTypeCfg, portfolio],
  );
  /** Is the field on the form for this project type and portfolio? (Hidden fields are not listed.) */
  const shown = (key: string) => {
    const f = fieldOf(key);
    return !!f && fieldState(f, projectType, portfolio).applies;
  };
  const shownCustom = customFields.filter((f) => shown(f.key));

  const isEmpty = (name: string) => {
    if (name === 'sites')
      return !(allValues.sites ?? []).some((x) => x?.site_id?.trim() || x?.site_key?.trim());
    const f = fieldOf(name);
    if (f && !f.builtin) return isEmptyValue(f, allValues.custom?.[name] as FieldValue | undefined);
    return !String((allValues as Record<string, unknown>)[name] ?? '').trim();
  };
  const setField = (name: string, value: string) => {
    const f = fieldOf(name);
    if (f && !f.builtin) {
      setValue(`custom.${name}`, value, { shouldDirty: true, shouldValidate: true });
    } else {
      setValue(name as SimpleKey, value, { shouldDirty: true, shouldValidate: true });
    }
  };
  /** Orion decorations of one field (AI marker, "could not find" hint, "which one" chooser), the
   * configured help text and the required star. */
  const decor = (name: string) => {
    const baseRequired = required.has(name);
    const help = fieldOf(name)?.help || undefined;
    if (!orion) return { required: baseRequired, hint: help as ReactNode } as const;
    const f = orionFields.get(name);
    const marker = aiActive.has(name) && f ? <OrionMarker field={f} /> : undefined;
    const missing = orion.missing.includes(name) && isEmpty(name);
    const ambiguous = orion.ambiguous.includes(name) && isEmpty(name);
    let hint: ReactNode = help;
    const bad = rejected[name];
    if (bad && isEmpty(name)) {
      hint = (
        <span style={{ color: tokens.colorPaletteMarigoldForeground2 }}>
          Orion read &quot;{bad}&quot;, which is not an available option - please choose
        </span>
      );
    } else if (ambiguous && f?.candidates?.length) {
      hint = (
        <span style={{ color: tokens.colorPaletteMarigoldForeground2 }}>
          Which one?{' '}
          {f.candidates.map((c) => (
            <Button
              key={c.value}
              size="small"
              appearance="outline"
              style={{ marginRight: 4 }}
              onClick={() => setField(name, c.value)}
            >
              {c.label}
            </Button>
          ))}
        </span>
      );
    } else if (missing || ambiguous) {
      hint = (
        <span style={{ color: tokens.colorPaletteMarigoldForeground2 }}>
          Orion could not find this - please enter
        </span>
      );
    }
    return { marker, hint, required: baseRequired || orion.missing.includes(name) } as const;
  };
  useEffect(() => {
    if (requiresSites && getValues('sites').length === 0) append({ site_id: '', site_key: '' });
  }, [requiresSites, siteRows.length, getValues, append]);
  const canCreate = me.permissions.includes('create_transition');
  const denied = me.denied_reasons['create_transition'] ?? 'You cannot create transitions';

  // Market: a dropdown when the chosen region lists its markets, otherwise free text.
  const regionMarkets = useMemo(() => {
    const markets = reference.lists?.['regions']?.find((o) => o.value === region)?.meta?.markets;
    return Array.isArray(markets) ? markets.map(String) : [];
  }, [reference, region]);
  const market = String(allValues.market ?? '');
  const marketChoices =
    market && !regionMarkets.includes(market) ? [...regionMarkets, market] : regionMarkets;

  const snMessage = fetchSn.error
    ? fetchSn.error instanceof ApiError && fetchSn.error.status === 404
      ? 'Not found in ServiceNow (mock) – enter manually'
      : fetchSn.error instanceof ApiError
        ? fetchSn.error.detail
        : 'ServiceNow lookup failed'
    : null;

  const doFetch = () => {
    const id = getValues('servicenow_project_id').trim();
    if (!id) return;
    fetchSn.mutate(id, {
      onSuccess: (p) => {
        const set = (k: SimpleKey, v: string | null | undefined, validFor?: string) => {
          const valid = validFor ? choices(validFor).map((o) => o.value) : null;
          if (v && (!valid || valid.includes(v)))
            setValue(k, v, { shouldDirty: true, shouldValidate: true });
        };
        set('name', p.name);
        set('project_type', p.project_type, 'project_type');
        set('investment_type', p.investment_type, 'investment_type');
        set('delivery_method', p.delivery_method, 'delivery_method');
        set('portfolio', p.portfolio, 'portfolio');
        set('region', p.region, 'region');
        set('market', p.market);
        set('description', p.description);
        const pm = p.pm_user_id;
        if (pm && users.some((u) => u.id === pm && u.role === 'PM'))
          setValue('pm_user_id', pm, { shouldDirty: true });
        dispatchToast(
          <Toast>
            <ToastTitle>Pre-filled from ServiceNow (mock)</ToastTitle>
          </Toast>,
          { intent: 'success' },
        );
      },
    });
  };

  // A-80: the first attempt is sent without confirm_duplicate; a 409 opens the duplicate dialog.
  const [duplicate, setDuplicate] = useState<{ reasons: string[]; body: TransitionCreate } | null>(
    null,
  );
  const send = (body: TransitionCreate) =>
    create.mutate(body, {
      onSuccess: (t) => {
        setDuplicate(null);
        navigate(`/transitions/${t.id}/${t.requires_tiering ? 'tiering' : 'scope'}`);
      },
      onError: (e) => {
        if (!body.confirm_duplicate && e instanceof ApiError && e.status === 409 && e.reasons[0]) {
          setDuplicate({ reasons: e.reasons, body });
        } else {
          setDuplicate(null);
          showError(e);
        }
      },
    });

  const onSubmit = handleSubmit((v) => {
    // Only the custom fields that apply to this project type and portfolio, and only filled ones.
    const customValues: Record<string, unknown> = {};
    for (const f of shownCustom) {
      const value = toApiValue(f, v.custom[f.key]);
      if (value !== null) customValues[f.key] = value;
    }
    const body: TransitionCreate = {
      confirm_duplicate: false,
      name: v.name.trim(),
      servicenow_project_id: v.servicenow_project_id.trim() || null,
      project_type: v.project_type,
      portfolio: v.portfolio,
      region: v.region,
      market: v.market.trim(),
      sites: requiresSites
        ? v.sites.map((x) => ({ site_id: x.site_id.trim(), site_key: x.site_key.trim() }))
        : [],
      audience: v.audience || null,
      write_actions: v.write_actions || null,
      sensitive_data: v.sensitive_data || null,
      target_gate: v.target_gate || null,
      investment_type: v.investment_type || null,
      delivery_method: v.delivery_method || null,
      description: v.description,
      or_focal_user_id: v.or_focal_user_id,
      pm_user_id: v.pm_user_id || null,
      architect_user_id: v.architect_user_id || null,
      olm_user_id: v.olm_user_id || null,
      irm_user_id: v.irm_user_id || null,
      next_decision_date: v.next_decision_date || null,
      custom_fields: customValues,
    };
    send(body);
  });

  const submit = (
    <Button appearance="primary" type="submit" disabled={!canCreate || create.isPending}>
      {create.isPending ? 'Creating…' : 'Create transition'}
    </Button>
  );

  /** A dropdown of a built-in field, drawn only when the field is on the form. */
  const select = (name: SimpleKey) =>
    shown(name) && (
      <SelectField
        control={control}
        name={name}
        label={label(name, name)}
        {...decor(name)}
        options={choices(name)}
      />
    );

  return (
    <form onSubmit={onSubmit} noValidate>
      {duplicate && (
        <DuplicateDialog
          reasons={duplicate.reasons}
          busy={create.isPending}
          onOpen={(id) => navigate(`/transitions/${id}`)}
          onCreateAnyway={() => send({ ...duplicate.body, confirm_duplicate: true })}
          onClose={() => setDuplicate(null)}
        />
      )}
      <SplitLayout
        main={
          <div className={s.stack}>
            <SectionCard title="Transition details">
              <FormGrid>
                <div className={s.full}>
                  <Field
                    label={
                      <>
                        {label('name', 'Solution / transition name')}
                        {decor('name').marker}
                      </>
                    }
                    hint={hintOf(decor('name').hint)}
                    required
                    validationMessage={formState.errors.name?.message}
                    validationState={formState.errors.name ? 'error' : 'none'}
                  >
                    <Input {...bind('name')} />
                  </Field>
                </div>
                <div className={`${s.row} ${s.full}`}>
                  <Field label="ServiceNow project ID" className={s.grow}>
                    <Input
                      {...bind('servicenow_project_id')}
                      placeholder="e.g. PRJ0052210"
                      onKeyDown={(e) => {
                        if (e.key === 'Enter') {
                          e.preventDefault();
                          if (!fetchSn.isPending) doFetch();
                        }
                      }}
                    />
                  </Field>
                  <Button onClick={doFetch} disabled={fetchSn.isPending}>
                    {fetchSn.isPending ? 'Fetching…' : 'Fetch from ServiceNow'}
                  </Button>
                </div>
                {snMessage && (
                  <div className={s.full}>
                    <MessageBar intent="warning" layout="multiline" role="status">
                      <MessageBarBody>{snMessage}</MessageBarBody>
                    </MessageBar>
                  </div>
                )}
                {select('project_type')}
                {select('portfolio')}
                {select('region')}
                {shown('market') && (
                  <Field
                    label={
                      <>
                        {label('market', 'Market / country')}
                        {decor('market').marker}
                      </>
                    }
                    hint={hintOf(decor('market').hint)}
                    required={decor('market').required}
                  >
                    {regionMarkets.length > 0 ? (
                      <Select
                        value={market}
                        onChange={(_, d) => {
                          clearAi('market');
                          setValue('market', d.value, { shouldDirty: true });
                        }}
                      >
                        <option value="">Select…</option>
                        {marketChoices.map((m) => (
                          <option key={m} value={m}>
                            {m}
                          </option>
                        ))}
                      </Select>
                    ) : (
                      <Input {...bind('market')} />
                    )}
                  </Field>
                )}

                {requiresSites && (
                  <div className={`${s.full} ${s.stack}`}>
                    <Subtitle2>
                      {portfolioCfg?.sites_label || 'In-scope sites (Site ID + Site key)'}
                      {decor('sites').marker}
                    </Subtitle2>
                    {decor('sites').hint}
                    {siteRows.map((f, i) => (
                      <div key={f.id} className={s.siteRow}>
                        <Field
                          label="Site ID"
                          required
                          className={s.grow}
                          validationMessage={formState.errors.sites?.[i]?.site_id?.message}
                          validationState={formState.errors.sites?.[i]?.site_id ? 'error' : 'none'}
                        >
                          <Input {...bindSite(i, 'site_id')} />
                        </Field>
                        <Field
                          label="Site key"
                          required
                          className={s.grow}
                          validationMessage={formState.errors.sites?.[i]?.site_key?.message}
                          validationState={formState.errors.sites?.[i]?.site_key ? 'error' : 'none'}
                        >
                          <Input {...bindSite(i, 'site_key')} />
                        </Field>
                        <Tooltip
                          content={
                            siteRows.length <= 1 ? 'At least one site is required' : 'Remove site'
                          }
                          relationship="label"
                        >
                          <Button
                            icon={<Delete16Regular />}
                            aria-label="Remove site"
                            style={{ marginTop: 22 }}
                            disabledFocusable={siteRows.length <= 1}
                            onClick={() => {
                              if (siteRows.length > 1) remove(i);
                            }}
                          />
                        </Tooltip>
                      </div>
                    ))}
                    {formState.errors.sites?.message && (
                      <Caption1 style={{ color: tokens.colorPaletteRedForeground1 }}>
                        {formState.errors.sites.message}
                      </Caption1>
                    )}
                    <div>
                      <Button
                        icon={<Add16Regular />}
                        onClick={() => append({ site_id: '', site_key: '' })}
                      >
                        Add site
                      </Button>
                    </div>
                  </div>
                )}

                {select('audience')}
                {select('write_actions')}
                {select('sensitive_data')}
                {select('target_gate')}
                {select('investment_type')}
                {select('delivery_method')}
                {shown('description') && (
                  <div className={s.full}>
                    <Field
                      label={
                        <>
                          {label('description', 'Description')}
                          {decor('description').marker}
                        </>
                      }
                      hint={hintOf(decor('description').hint)}
                      required={decor('description').required}
                    >
                      <Textarea {...bind('description')} rows={3} resize="vertical" />
                    </Field>
                  </div>
                )}
                {select('or_focal_user_id')}
                {select('pm_user_id')}
                {select('architect_user_id')}
                {select('olm_user_id')}
                {select('irm_user_id')}
                {shown('next_decision_date') && (
                  <Field
                    label={
                      <>
                        {label('next_decision_date', 'Next decision date')}
                        {decor('next_decision_date').marker}
                      </>
                    }
                    hint={hintOf(decor('next_decision_date').hint)}
                    required={decor('next_decision_date').required}
                  >
                    <Input type="date" {...bind('next_decision_date')} />
                  </Field>
                )}
              </FormGrid>
            </SectionCard>
            {shownCustom.length > 0 && (
              <SectionCard title="Additional details">
                <FormGrid>
                  {shownCustom.map((f) => {
                    const info = decor(f.key);
                    return (
                      <div
                        key={f.key}
                        className={
                          f.type === 'textarea' || f.type === 'multiselect' ? s.full : undefined
                        }
                      >
                        <DynamicField
                          field={f}
                          users={users}
                          value={allValues.custom?.[f.key] as FieldValue | undefined}
                          onChange={(value) => {
                            clearAi(f.key);
                            setValue(`custom.${f.key}`, value, {
                              shouldDirty: true,
                              shouldValidate: formState.isSubmitted,
                            });
                          }}
                          required={info.required}
                          marker={'marker' in info ? info.marker : undefined}
                          hint={info.hint}
                          error={formState.errors.custom?.[f.key]?.message}
                        />
                      </div>
                    );
                  })}
                </FormGrid>
              </SectionCard>
            )}
            <Toolbar align="end">
              <Button onClick={() => navigate('/transitions')}>Cancel</Button>
              {canCreate ? (
                submit
              ) : (
                <Tooltip content={denied} relationship="description">
                  <span>{submit}</span>
                </Tooltip>
              )}
            </Toolbar>
          </div>
        }
        aside={<AutoScopePanel control={control} reference={reference} />}
      />
    </form>
  );
}

/** A-80: an active transition already exists for this ServiceNow project. */
function DuplicateDialog(props: {
  reasons: string[];
  busy: boolean;
  onOpen: (id: string) => void;
  onCreateAnyway: () => void;
  onClose: () => void;
}) {
  const existingId = /TR-\d+/.exec(props.reasons[0] ?? '')?.[0] ?? null;
  return (
    <Dialog open onOpenChange={(_, d) => !d.open && props.onClose()}>
      <DialogSurface style={{ maxWidth: 600 }}>
        <DialogBody>
          <DialogTitle>A transition already exists for this ServiceNow project</DialogTitle>
          <DialogContent>
            {props.reasons.map((r) => (
              <Body1 key={r} block>
                {r}
              </Body1>
            ))}
          </DialogContent>
          <DialogActions>
            {existingId && (
              <Button
                appearance="primary"
                style={{ whiteSpace: 'nowrap' }}
                onClick={() => props.onOpen(existingId)}
              >
                Open {existingId}
              </Button>
            )}
            <Button
              style={{ whiteSpace: 'nowrap' }}
              disabled={props.busy}
              onClick={props.onCreateAnyway}
            >
              Create anyway
            </Button>
            <Button appearance="subtle" onClick={props.onClose}>
              Cancel
            </Button>
          </DialogActions>
        </DialogBody>
      </DialogSurface>
    </Dialog>
  );
}

/** Banner of a pre-filled intake (CR-02): the human still checks and clicks Create. */
function OrionBanner({ orion }: { orion: OrionPrefill }) {
  const [hidden, setHidden] = useState(false);
  const [showExcerpt, setShowExcerpt] = useState(false);
  const labelOf = (n: string) => orion.fields.find((f) => f.name === n)?.label ?? n;
  return (
    <div style={{ marginBottom: tokens.spacingVerticalL }}>
      {!hidden && (
        <MessageBar intent="info" role="status">
          <MessageBarBody>
            <AiBadge /> Pre-filled by Orion from your description - check and create
            {orion.missing.length > 0 && (
              <div>
                <Caption1>
                  Orion could not find: {orion.missing.map(labelOf).join(', ')}. Please enter them.
                </Caption1>
              </div>
            )}
            {showExcerpt && orion.excerpt && (
              <pre style={{ whiteSpace: 'pre-wrap', margin: '8px 0 0', fontSize: 12 }}>
                {orion.excerpt}
              </pre>
            )}
          </MessageBarBody>
          <MessageBarActions>
            {orion.excerpt && (
              <Button size="small" onClick={() => setShowExcerpt((v) => !v)}>
                {showExcerpt ? 'Hide source excerpt' : 'View source excerpt'}
              </Button>
            )}
            <Button size="small" onClick={() => setHidden(true)}>
              Dismiss
            </Button>
          </MessageBarActions>
        </MessageBar>
      )}
      {orion.warnings.length > 0 && (
        <MessageBar
          intent="warning"
          layout="multiline"
          role="status"
          style={{ marginTop: tokens.spacingVerticalS }}
        >
          <MessageBarBody>
            {orion.warnings.map((w) => (
              <div key={w}>{w}</div>
            ))}
          </MessageBarBody>
        </MessageBar>
      )}
    </div>
  );
}

/** New transition - FR-020 (spec 8.4): intake form with live Auto-scope preview. With
 * ?proposal=<id> (CR-02) the form is pre-filled from an Orion create_transition proposal. */
export function NewTransitionPage() {
  const ref = useReference();
  const users = useUsers();
  const me = useMe();
  const [params] = useSearchParams();
  const proposalId = params.get('proposal');
  const proposal = useProposal(proposalId);
  const { dispatchToast } = useToastController(TOASTER_ID);
  const warned = useRef<string | null>(null);

  const proposalUsable =
    proposal.data && proposal.data.kind === 'create_transition' ? proposal.data : null;
  const proposalFailed = !!proposalId && (proposal.isError || (!!proposal.data && !proposalUsable));
  useEffect(() => {
    if (!proposalFailed || warned.current === proposalId) return;
    warned.current = proposalId;
    dispatchToast(
      <Toast>
        <ToastTitle>Orion proposal not available - starting with an empty form</ToastTitle>
      </Toast>,
      { intent: 'warning' },
    );
  }, [proposalFailed, proposalId, dispatchToast]);

  const orion = useMemo(
    () => (proposalUsable ? readPrefill(proposalUsable) : null),
    [proposalUsable],
  );
  const err = ref.error ?? users.error ?? me.error;
  const waiting = !!proposalId && proposal.isLoading;
  return (
    <>
      <PageHeader
        title="New transition"
        subtitle="Start a transition. The checklists that apply are assembled from the project type and portfolio."
      />
      {err ? (
        <ErrorState error={err} />
      ) : ref.data && users.data && me.data && !waiting ? (
        <>
          {orion && <OrionBanner orion={orion} />}
          <IntakeForm
            key={proposalUsable?.id ?? 'blank'}
            reference={ref.data}
            users={users.data}
            me={me.data}
            orion={orion}
          />
        </>
      ) : (
        <LoadingState rows={8} />
      )}
    </>
  );
}
