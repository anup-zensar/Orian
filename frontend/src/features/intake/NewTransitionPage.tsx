import { useEffect, useMemo, useRef, useState, type ReactNode } from 'react';
import { Controller, useFieldArray, useForm, useWatch, type Control } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import { useNavigate, useSearchParams } from 'react-router';
import {
  Body1,
  Button,
  Caption1,
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
import { LoadingState } from '../../components/LoadingState';
import { ErrorState } from '../../components/ErrorState';
import { ApiError } from '../../api/client';
import type { Me, Reference, User } from '../../api/types';
import { TOASTER_ID, useApiErrorToast } from '../../hooks/useApiErrorToast';
import { useReference } from '../reference/api';
import { useProposal, type Proposal } from '../orion/api';
import { useMe, useUsers } from '../users/api';
import { useCreateTransition, useFetchServiceNow, type TransitionCreate } from './api';

const AI_TYPES = ['Agentic AI', 'Combined'];
const RETAIL = 'Retail Site Systems';

const schema = z
  .object({
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
  })
  .superRefine((v, ctx) => {
    if (AI_TYPES.includes(v.project_type)) {
      for (const k of ['audience', 'write_actions', 'sensitive_data'] as const) {
        if (!v[k]) ctx.addIssue({ code: 'custom', path: [k], message: 'Required for AI types' });
      }
    }
    if (v.portfolio === RETAIL) {
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

type FormValues = z.infer<typeof schema>;
type SimpleKey = Exclude<keyof FormValues, 'sites'>;

const useStyles = makeStyles({
  layout: {
    display: 'grid',
    gridTemplateColumns: 'minmax(0, 2fr) minmax(280px, 1fr)',
    gap: tokens.spacingHorizontalL,
    alignItems: 'start',
    '@media (max-width: 1000px)': { gridTemplateColumns: '1fr' },
  },
  grid: {
    display: 'grid',
    gridTemplateColumns: 'repeat(2, minmax(0, 1fr))',
    gap: tokens.spacingHorizontalM,
    '@media (max-width: 700px)': { gridTemplateColumns: '1fr' },
  },
  full: { gridColumn: '1 / -1' },
  row: { display: 'flex', gap: tokens.spacingHorizontalS, alignItems: 'flex-end' },
  grow: { flexGrow: 1 },
  siteRow: { display: 'flex', gap: tokens.spacingHorizontalS, alignItems: 'flex-start' },
  actions: { display: 'flex', gap: tokens.spacingHorizontalM, justifyContent: 'flex-end' },
  stack: { display: 'flex', flexDirection: 'column', gap: tokens.spacingVerticalM },
  panel: { position: 'sticky', top: tokens.spacingVerticalL },
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

function usersWithRole(users: User[], role: string): Opt[] {
  return users.filter((u) => u.role === role).map((u) => ({ value: u.id, label: u.name }));
}

function AutoScopePanel(props: { control: Control<FormValues>; reference: Reference }) {
  const s = useStyles();
  const { project_type, portfolio, region } = useWatch({ control: props.control });
  const pt = props.reference.project_types.find((p) => p.code === project_type);
  const details = props.reference.portfolio_details.find((p) => p.name === portfolio);
  const counts = props.reference.checklist_counts;
  const flavour = [project_type, portfolio, region].filter(Boolean).join(' · ');
  return (
    <SectionCard title="Auto-scope">
      <div className={s.stack}>
        <Body1 style={{ fontWeight: tokens.fontWeightSemibold }}>
          {flavour || 'Choose project type, portfolio and region'}
        </Body1>
        <Caption1>Checklists that will apply</Caption1>
        <ul className={s.list}>
          <li>Framework {counts.framework}</li>
          {pt?.checklists.includes('AI_PLAYBOOK') && (
            <li>
              AI Playbook (Tier ?) – up to {counts.ai_playbook_total}, filtered once the tier is set
            </li>
          )}
          {details && (
            <li>
              {details.name} golden set {details.golden_set_count}
            </li>
          )}
          <li>Common {counts.common}</li>
        </ul>
        {details && details.focus_areas.length > 0 && (
          <>
            <Caption1>{details.name} focus areas</Caption1>
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

  // Valid options of the select fields, to tell an Orion value that is not an option (e.g. region "UK").
  const validOptions = useMemo<Partial<Record<SimpleKey, string[]>>>(() => {
    const o = reference.intake_options;
    const byRole = (role: string) => users.filter((u) => u.role === role).map((u) => u.id);
    return {
      project_type: reference.project_types.map((p) => p.code),
      portfolio: reference.portfolios,
      region: reference.regions,
      audience: o.audience,
      write_actions: o.write_actions,
      sensitive_data: o.sensitive_data,
      target_gate: o.target_gate,
      investment_type: o.investment_type,
      delivery_method: o.delivery_method,
      or_focal_user_id: byRole('OR_FOCAL'),
      pm_user_id: byRole('PM'),
      architect_user_id: byRole('ARCHITECT'),
      olm_user_id: byRole('OLM'),
      irm_user_id: byRole('IRM'),
    };
  }, [reference, users]);
  const rejected = useMemo(() => {
    const r: Partial<Record<SimpleKey, string>> = {};
    if (!orion) return r;
    for (const k of SIMPLE_KEYS) {
      const v = orion.prefill[k];
      const valid = validOptions[k];
      if (typeof v === 'string' && v !== '' && valid && !valid.includes(v)) r[k] = v;
    }
    return r;
  }, [orion, validOptions]);

  const defaults = useMemo<FormValues>(() => {
    const pick = (role: string, id: string) =>
      users.some((u) => u.id === id && u.role === role) ? id : '';
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
  }, [users, me.user.id, me.user.role, orion, rejected]);

  const { control, handleSubmit, setValue, getValues, formState } = useForm<FormValues>({
    resolver: zodResolver(schema),
    defaultValues: defaults,
  });
  const { fields, append, remove } = useFieldArray({ control, name: 'sites' });
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
              f.name in (orion?.prefill ?? {}) &&
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
  const isEmpty = (name: string) => {
    if (name === 'sites')
      return !(allValues.sites ?? []).some((x) => x?.site_id?.trim() || x?.site_key?.trim());
    return !String((allValues as Record<string, unknown>)[name] ?? '').trim();
  };
  /** Orion decorations of one field: AI marker, "could not find" hint, "which one" chooser. */
  const decor = (name: string, baseRequired = false) => {
    if (!orion) return { required: baseRequired } as const;
    const f = orionFields.get(name);
    const marker = aiActive.has(name) && f ? <OrionMarker field={f} /> : undefined;
    const missing = orion.missing.includes(name) && isEmpty(name);
    const ambiguous = orion.ambiguous.includes(name) && isEmpty(name);
    let hint: ReactNode = undefined;
    const bad = rejected[name as SimpleKey];
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
              onClick={() =>
                setValue(name as SimpleKey, c.value, { shouldDirty: true, shouldValidate: true })
              }
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
  const projectType = useWatch({ control, name: 'project_type' });
  const portfolio = useWatch({ control, name: 'portfolio' });
  const isAi = AI_TYPES.includes(projectType);
  const isRetail = portfolio === RETAIL;
  useEffect(() => {
    if (isRetail && getValues('sites').length === 0) append({ site_id: '', site_key: '' });
  }, [isRetail, fields.length, getValues, append]);
  const canCreate = me.permissions.includes('create_transition');
  const denied = me.denied_reasons['create_transition'] ?? 'You cannot create transitions';
  const opts = reference.intake_options;
  const plain = (a: string[]): Opt[] => a.map((value) => ({ value }));

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
        const set = (k: SimpleKey, v: string | null | undefined, valid?: string[]) => {
          if (v && (!valid || valid.includes(v)))
            setValue(k, v, { shouldDirty: true, shouldValidate: true });
        };
        set('name', p.name);
        set(
          'project_type',
          p.project_type,
          reference.project_types.map((t) => t.code),
        );
        set('investment_type', p.investment_type, opts.investment_type);
        set('delivery_method', p.delivery_method, opts.delivery_method);
        set('portfolio', p.portfolio, reference.portfolios);
        set('region', p.region, reference.regions);
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

  const onSubmit = handleSubmit((v) => {
    const body: TransitionCreate = {
      name: v.name.trim(),
      servicenow_project_id: v.servicenow_project_id.trim() || null,
      project_type: v.project_type,
      portfolio: v.portfolio,
      region: v.region,
      market: v.market.trim(),
      sites:
        v.portfolio === RETAIL
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
    };
    create.mutate(body, {
      onSuccess: (t) =>
        navigate(`/transitions/${t.id}/${t.requires_tiering ? 'tiering' : 'scope'}`),
      onError: showError,
    });
  });

  const submit = (
    <Button appearance="primary" type="submit" disabled={!canCreate || create.isPending}>
      {create.isPending ? 'Creating…' : 'Create transition'}
    </Button>
  );

  return (
    <form onSubmit={onSubmit} noValidate className={s.layout}>
      <SectionCard title="Transition details">
        <div className={s.grid}>
          <div className={s.full}>
            <Field
              label={
                <>
                  Solution / transition name
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
              <MessageBar intent="warning" role="status">
                <MessageBarBody>{snMessage}</MessageBarBody>
              </MessageBar>
            </div>
          )}
          <SelectField
            control={control}
            name="project_type"
            label="Project type"
            {...decor('project_type', true)}
            options={reference.project_types.map((p) => ({ value: p.code }))}
          />
          <SelectField
            control={control}
            name="portfolio"
            label="Mobility landscape category (portfolio)"
            {...decor('portfolio', true)}
            options={plain(reference.portfolios)}
          />
          <SelectField
            control={control}
            name="region"
            label="Region"
            {...decor('region', true)}
            options={plain(reference.regions)}
          />
          <Field
            label={
              <>
                Market / country
                {decor('market').marker}
              </>
            }
            hint={hintOf(decor('market').hint)}
            required={decor('market').required}
          >
            <Input {...bind('market')} placeholder="e.g. India, Netherlands, Multi-market" />
          </Field>

          {isRetail && (
            <div className={`${s.full} ${s.stack}`}>
              <Subtitle2>
                In-scope sites (Site ID + Site key)
                {decor('sites').marker}
              </Subtitle2>
              {decor('sites').hint}
              {fields.map((f, i) => (
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
                    content={fields.length <= 1 ? 'At least one site is required' : 'Remove site'}
                    relationship="label"
                  >
                    <Button
                      icon={<Delete16Regular />}
                      aria-label="Remove site"
                      style={{ marginTop: 22 }}
                      disabledFocusable={fields.length <= 1}
                      onClick={() => {
                        if (fields.length > 1) remove(i);
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

          <SelectField
            control={control}
            name="audience"
            label="Audience"
            {...decor('audience', isAi)}
            options={plain(opts.audience)}
          />
          <SelectField
            control={control}
            name="write_actions"
            label="Write actions"
            {...decor('write_actions', isAi)}
            options={plain(opts.write_actions)}
          />
          <SelectField
            control={control}
            name="sensitive_data"
            label="Sensitive data"
            {...decor('sensitive_data', isAi)}
            options={plain(opts.sensitive_data)}
          />
          <SelectField
            control={control}
            name="target_gate"
            label="Target gate"
            {...decor('target_gate')}
            options={plain(opts.target_gate)}
          />
          <SelectField
            control={control}
            name="investment_type"
            label="Investment type"
            {...decor('investment_type')}
            options={plain(opts.investment_type)}
          />
          <SelectField
            control={control}
            name="delivery_method"
            label="Delivery method"
            {...decor('delivery_method')}
            options={plain(opts.delivery_method)}
          />
          <div className={s.full}>
            <Field
              label={
                <>
                  Description
                  {decor('description').marker}
                </>
              }
            >
              <Textarea {...bind('description')} rows={3} resize="vertical" />
            </Field>
          </div>
          <SelectField
            control={control}
            name="or_focal_user_id"
            label="OR focal"
            {...decor('or_focal_user_id', true)}
            options={usersWithRole(users, 'OR_FOCAL')}
          />
          <SelectField
            control={control}
            name="pm_user_id"
            label="PM"
            {...decor('pm_user_id')}
            options={usersWithRole(users, 'PM')}
          />
          <SelectField
            control={control}
            name="architect_user_id"
            label="Architect"
            {...decor('architect_user_id')}
            options={usersWithRole(users, 'ARCHITECT')}
          />
          <SelectField
            control={control}
            name="olm_user_id"
            label="OLM"
            {...decor('olm_user_id')}
            options={usersWithRole(users, 'OLM')}
          />
          <SelectField
            control={control}
            name="irm_user_id"
            label="IRM"
            {...decor('irm_user_id')}
            options={usersWithRole(users, 'IRM')}
          />
          <Field
            label={
              <>
                Next decision date
                {decor('next_decision_date').marker}
              </>
            }
            hint={hintOf(decor('next_decision_date').hint)}
          >
            <Input type="date" {...bind('next_decision_date')} />
          </Field>
        </div>
        <div className={s.actions}>
          <Button onClick={() => navigate('/transitions')}>Cancel</Button>
          {canCreate ? (
            submit
          ) : (
            <Tooltip content={denied} relationship="description">
              <span>{submit}</span>
            </Tooltip>
          )}
        </div>
      </SectionCard>
      <div className={s.panel}>
        <AutoScopePanel control={control} reference={reference} />
      </div>
    </form>
  );
}

/** Banner of a pre-filled intake (CR-02): the human still checks and clicks Create. */
function OrionBanner({ orion }: { orion: OrionPrefill }) {
  const [hidden, setHidden] = useState(false);
  const [showExcerpt, setShowExcerpt] = useState(false);
  if (hidden) return null;
  const labelOf = (n: string) => orion.fields.find((f) => f.name === n)?.label ?? n;
  return (
    <div style={{ marginBottom: tokens.spacingVerticalL }}>
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
