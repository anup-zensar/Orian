import { useEffect, useMemo } from 'react';
import { Controller, useFieldArray, useForm, useWatch, type Control } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import { useNavigate } from 'react-router';
import {
  Body1,
  Button,
  Caption1,
  Field,
  Input,
  MessageBar,
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
import { PageHeader } from '../../components/PageHeader';
import { SectionCard } from '../../components/SectionCard';
import { LoadingState } from '../../components/LoadingState';
import { ErrorState } from '../../components/ErrorState';
import { ApiError } from '../../api/client';
import type { Me, Reference, User } from '../../api/types';
import { TOASTER_ID, useApiErrorToast } from '../../hooks/useApiErrorToast';
import { useReference } from '../reference/api';
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
}) {
  return (
    <Controller
      control={props.control}
      name={props.name}
      render={({ field, fieldState }) => (
        <Field
          label={props.label}
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

function IntakeForm(props: { reference: Reference; users: User[]; me: Me }) {
  const { reference, users, me } = props;
  const s = useStyles();
  const navigate = useNavigate();
  const showError = useApiErrorToast();
  const { dispatchToast } = useToastController(TOASTER_ID);
  const create = useCreateTransition();
  const fetchSn = useFetchServiceNow();

  const defaults = useMemo<FormValues>(() => {
    const pick = (role: string, id: string) =>
      users.some((u) => u.id === id && u.role === role) ? id : '';
    return {
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
  }, [users, me.user.id, me.user.role]);

  const { control, register, handleSubmit, setValue, getValues, formState } = useForm<FormValues>({
    resolver: zodResolver(schema),
    defaultValues: defaults,
  });
  const { fields, append, remove } = useFieldArray({ control, name: 'sites' });
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
              label="Solution / transition name"
              required
              validationMessage={formState.errors.name?.message}
              validationState={formState.errors.name ? 'error' : 'none'}
            >
              <Input {...register('name')} />
            </Field>
          </div>
          <div className={`${s.row} ${s.full}`}>
            <Field label="ServiceNow project ID" className={s.grow}>
              <Input
                {...register('servicenow_project_id')}
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
            required
            options={reference.project_types.map((p) => ({ value: p.code }))}
          />
          <SelectField
            control={control}
            name="portfolio"
            label="Mobility landscape category (portfolio)"
            required
            options={plain(reference.portfolios)}
          />
          <SelectField
            control={control}
            name="region"
            label="Region"
            required
            options={plain(reference.regions)}
          />
          <Field label="Market / country">
            <Input {...register('market')} placeholder="e.g. India, Netherlands, Multi-market" />
          </Field>

          {isRetail && (
            <div className={`${s.full} ${s.stack}`}>
              <Subtitle2>In-scope sites (Site ID + Site key)</Subtitle2>
              {fields.map((f, i) => (
                <div key={f.id} className={s.siteRow}>
                  <Field
                    label="Site ID"
                    required
                    className={s.grow}
                    validationMessage={formState.errors.sites?.[i]?.site_id?.message}
                    validationState={formState.errors.sites?.[i]?.site_id ? 'error' : 'none'}
                  >
                    <Input {...register(`sites.${i}.site_id`)} />
                  </Field>
                  <Field
                    label="Site key"
                    required
                    className={s.grow}
                    validationMessage={formState.errors.sites?.[i]?.site_key?.message}
                    validationState={formState.errors.sites?.[i]?.site_key ? 'error' : 'none'}
                  >
                    <Input {...register(`sites.${i}.site_key`)} />
                  </Field>
                  <Tooltip
                    content={fields.length <= 1 ? 'At least one site is required' : 'Remove site'}
                    relationship="label"
                  >
                    <Button
                      icon={<Delete16Regular />}
                      aria-label="Remove site"
                      style={{ marginTop: 22 }}
                      disabled={fields.length <= 1}
                      onClick={() => remove(i)}
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
            required={isAi}
            options={plain(opts.audience)}
          />
          <SelectField
            control={control}
            name="write_actions"
            label="Write actions"
            required={isAi}
            options={plain(opts.write_actions)}
          />
          <SelectField
            control={control}
            name="sensitive_data"
            label="Sensitive data"
            required={isAi}
            options={plain(opts.sensitive_data)}
          />
          <SelectField
            control={control}
            name="target_gate"
            label="Target gate"
            options={plain(opts.target_gate)}
          />
          <SelectField
            control={control}
            name="investment_type"
            label="Investment type"
            options={plain(opts.investment_type)}
          />
          <SelectField
            control={control}
            name="delivery_method"
            label="Delivery method"
            options={plain(opts.delivery_method)}
          />
          <div className={s.full}>
            <Field label="Description">
              <Textarea {...register('description')} rows={3} resize="vertical" />
            </Field>
          </div>
          <SelectField
            control={control}
            name="or_focal_user_id"
            label="OR focal"
            required
            options={usersWithRole(users, 'OR_FOCAL')}
          />
          <SelectField
            control={control}
            name="pm_user_id"
            label="PM"
            options={usersWithRole(users, 'PM')}
          />
          <SelectField
            control={control}
            name="architect_user_id"
            label="Architect"
            options={usersWithRole(users, 'ARCHITECT')}
          />
          <SelectField
            control={control}
            name="olm_user_id"
            label="OLM"
            options={usersWithRole(users, 'OLM')}
          />
          <SelectField
            control={control}
            name="irm_user_id"
            label="IRM"
            options={usersWithRole(users, 'IRM')}
          />
          <Field label="Next decision date">
            <Input type="date" {...register('next_decision_date')} />
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

/** New transition – FR-020 (spec 8.4): intake form with live Auto-scope preview. */
export function NewTransitionPage() {
  const ref = useReference();
  const users = useUsers();
  const me = useMe();
  const err = ref.error ?? users.error ?? me.error;
  return (
    <>
      <PageHeader
        title="New transition"
        subtitle="Start a transition. The checklists that apply are assembled from the project type and portfolio."
      />
      {err ? (
        <ErrorState error={err} />
      ) : ref.data && users.data && me.data ? (
        <IntakeForm reference={ref.data} users={users.data} me={me.data} />
      ) : (
        <LoadingState rows={8} />
      )}
    </>
  );
}
