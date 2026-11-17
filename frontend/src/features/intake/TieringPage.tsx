import { useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router';
import {
  Badge,
  Body1,
  Button,
  Caption1,
  Field,
  Input,
  MessageBar,
  MessageBarBody,
  Radio,
  RadioGroup,
  Select,
  Subtitle2,
  Textarea,
  Toast,
  ToastBody,
  ToastTitle,
  Tooltip,
  makeStyles,
  tokens,
  useToastController,
} from '@fluentui/react-components';
import { PageHeader } from '../../components/PageHeader';
import { SectionCard } from '../../components/SectionCard';
import { LoadingState } from '../../components/LoadingState';
import { ErrorState } from '../../components/ErrorState';
import { EmptyState } from '../../components/EmptyState';
import type { Me, Reference } from '../../api/types';
import { TOASTER_ID, useApiErrorToast } from '../../hooks/useApiErrorToast';
import { useReference } from '../reference/api';
import { useMe } from '../users/api';
import { useTransition, type TransitionDetail } from '../transition/api';
import {
  useAiProfile,
  useConfirmTier,
  useProposeTier,
  useSaveAiProfile,
  useTierProposal,
  type AIProfile,
  type AIProfileIn,
  type TierAssessment,
} from './api';

const useStyles = makeStyles({
  steps: { display: 'flex', gap: tokens.spacingHorizontalS, flexWrap: 'wrap' },
  stack: { display: 'flex', flexDirection: 'column', gap: tokens.spacingVerticalM },
  question: {
    display: 'flex',
    justifyContent: 'space-between',
    gap: tokens.spacingHorizontalL,
    alignItems: 'flex-start',
    flexWrap: 'wrap',
    paddingBottom: tokens.spacingVerticalS,
    borderBottom: `1px solid ${tokens.colorNeutralStroke2}`,
  },
  qText: { flex: '1 1 320px', minWidth: 0 },
  intake: {
    display: 'grid',
    gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))',
    gap: tokens.spacingHorizontalM,
  },
  two: {
    display: 'grid',
    gridTemplateColumns: 'repeat(2, minmax(0, 1fr))',
    gap: tokens.spacingHorizontalL,
    alignItems: 'start',
    '@media (max-width: 900px)': { gridTemplateColumns: '1fr' },
  },
  profile: {
    display: 'grid',
    gridTemplateColumns: 'repeat(2, minmax(0, 1fr))',
    gap: tokens.spacingHorizontalM,
    '@media (max-width: 700px)': { gridTemplateColumns: '1fr' },
  },
  actions: { display: 'flex', gap: tokens.spacingHorizontalM, flexWrap: 'wrap' },
  list: { margin: 0, paddingLeft: '20px' },
  tierNum: { fontSize: tokens.fontSizeHero800, fontWeight: tokens.fontWeightSemibold },
});

type Answers = Record<string, boolean | undefined>;

function ReadOnlyValue(props: { label: string; value: string | null | undefined }) {
  return (
    <div>
      <Caption1>{props.label}</Caption1>
      <Body1 block>{props.value || '—'}</Body1>
    </div>
  );
}

function QuestionsStep(props: {
  t: TransitionDetail;
  reference: Reference;
  answers: Answers;
  set: (a: Answers) => void;
}) {
  const s = useStyles();
  const { t, answers } = props;
  return (
    <div className={s.stack}>
      <SectionCard title="Intake answers (read-only)">
        <div className={s.intake}>
          <ReadOnlyValue label="Audience" value={t.audience} />
          <ReadOnlyValue label="Write actions" value={t.write_actions} />
          <ReadOnlyValue label="Sensitive data" value={t.sensitive_data} />
        </div>
      </SectionCard>
      <SectionCard title="Tiering questions TQ1 – TQ5">
        {props.reference.tier_questions.map((q) => (
          <div key={q.id} className={s.question}>
            <div className={s.qText}>
              <Body1 block>
                <strong>{q.id}</strong> {q.text}
              </Body1>
              <Caption1>If yes: {q.if_yes}</Caption1>
            </div>
            <RadioGroup
              layout="horizontal"
              aria-label={`${q.id} answer`}
              value={answers[q.id] === undefined ? '' : answers[q.id] ? 'yes' : 'no'}
              onChange={(_, d) => props.set({ ...answers, [q.id]: d.value === 'yes' })}
            >
              <Radio value="yes" label="Yes" />
              <Radio value="no" label="No" />
            </RadioGroup>
          </div>
        ))}
        <Caption1>Unanswered questions count as No.</Caption1>
      </SectionCard>
    </div>
  );
}

function who(p: { name: string } | null | undefined) {
  return p ? p.name : null;
}

function StatusCard(props: { t: TransitionDetail }) {
  const tier = props.t.tier;
  if (!tier || tier.proposed_tier == null) {
    return <Body1>No tier proposed yet.</Body1>;
  }
  const confirmed = tier.status === 'Confirmed';
  return (
    <div>
      <Badge color={confirmed ? 'success' : 'warning'} appearance="filled">
        {tier.status ?? 'Proposed'}
      </Badge>{' '}
      <Body1>
        Tier {confirmed ? tier.confirmed_tier : tier.proposed_tier}
        {tier.proposed_by && <> · proposed by {who(tier.proposed_by)}</>}
        {confirmed && tier.confirmed_by_irm && (
          <> · confirmed by {who(tier.confirmed_by_irm)} (IRM)</>
        )}
      </Body1>
      {tier.change_reason && <Caption1 block>Change reason: {tier.change_reason}</Caption1>}
    </div>
  );
}

function ProposalStep(props: {
  t: TransitionDetail;
  reference: Reference;
  me: Me;
  answers: Answers;
}) {
  const s = useStyles();
  const { t, me, answers } = props;
  const showError = useApiErrorToast();
  const { dispatchToast } = useToastController(TOASTER_ID);
  const propose = useProposeTier(t.id);
  const confirm = useConfirmTier(t.id);
  const [changing, setChanging] = useState(false);
  const [newTier, setNewTier] = useState('');
  const [reason, setReason] = useState('');

  const payload = Object.fromEntries(
    props.reference.tier_questions.map((q) => [q.id, answers[q.id] ?? false]),
  );
  const proposal = useTierProposal(
    {
      audience: t.audience ?? null,
      write_actions: t.write_actions ?? null,
      sensitive_data: t.sensitive_data ?? null,
      answers: payload,
    },
    true,
  );
  const p = proposal.data;
  const tier = t.tier;
  const confirmed = tier?.status === 'Confirmed';
  const can = (perm: string) => me.permissions.includes(perm);
  const reasonFor = (perm: string) => me.denied_reasons[perm] ?? 'You are not allowed to do this';

  const toast = (title: string, a?: TierAssessment) => {
    const r = a?.reassembly;
    dispatchToast(
      <Toast>
        <ToastTitle>{title}</ToastTitle>
        {r && (
          <ToastBody>
            Checklist re-assembled: {r.added ?? 0} added, {r.excluded ?? 0} excluded,{' '}
            {r.restored ?? 0} restored
          </ToastBody>
        )}
      </Toast>,
      { intent: 'success' },
    );
  };

  const doPropose = () =>
    propose.mutate(payload, {
      onSuccess: (a) => toast(`Tier ${a.proposed_tier} proposed`, a),
      onError: showError,
    });
  const doConfirm = (tierNo: number, why?: string) =>
    confirm.mutate(
      { tier: tierNo, reason: why || null },
      {
        onSuccess: (a) => {
          toast(`Tier ${a.confirmed_tier} confirmed`, a);
          setChanging(false);
          setReason('');
        },
        onError: showError,
      },
    );

  const proposeBtn = (
    <Button
      appearance="primary"
      disabled={!can('propose_tier') || confirmed || !p || propose.isPending}
      onClick={doPropose}
    >
      {p ? `Propose tier ${p.proposed_tier}` : 'Propose tier'}
    </Button>
  );
  const proposeReason = !can('propose_tier')
    ? reasonFor('propose_tier')
    : confirmed
      ? 'Tier already confirmed – IRM must change it'
      : null;

  const storedTier = tier?.proposed_tier ?? null;
  const canConfirmNow = can('confirm_tier') && storedTier != null;
  const confirmReason = !can('confirm_tier')
    ? reasonFor('confirm_tier')
    : confirmed
      ? `Tier already confirmed by ${who(tier?.confirmed_by_irm)}`
      : storedTier == null
        ? 'No tier proposed yet – the OR focal must propose one first'
        : null;
  const changeValid = newTier !== '' && reason.trim().length > 0;

  return (
    <div className={s.two}>
      <SectionCard title="Proposed tier (live)">
        {proposal.error ? (
          <ErrorState error={proposal.error} />
        ) : !p ? (
          <LoadingState rows={3} />
        ) : (
          <div className={s.stack}>
            <div className={s.tierNum}>Tier {p.proposed_tier}</div>
            <ul className={s.list} aria-label="Rationale">
              {p.rationale.map((r) => (
                <li key={r}>{r}</li>
              ))}
            </ul>
            <Subtitle2>{p.tier.name}</Subtitle2>
            <Body1>{p.tier.definition}</Body1>
            <Caption1>Examples: {p.tier.examples}</Caption1>
            <Caption1>Builder persona: {p.tier.builder_persona}</Caption1>
            <Subtitle2>Tier dimensions</Subtitle2>
            <ul className={s.list}>
              {p.dimensions.map((d) => (
                <li key={d}>{d}</li>
              ))}
            </ul>
          </div>
        )}
      </SectionCard>
      <SectionCard title="Decision">
        <div className={s.stack}>
          <StatusCard t={t} />
          <Body1>
            The OR focal proposes the tier; IRM confirms it. Orion explains the proposal but never
            confirms it.
          </Body1>
          <div className={s.actions}>
            {proposeReason ? (
              <Tooltip content={proposeReason} relationship="description">
                <span>{proposeBtn}</span>
              </Tooltip>
            ) : (
              proposeBtn
            )}
            {(can('confirm_tier') || me.user.role === 'IRM') && (
              <>
                {confirmReason ? (
                  <Tooltip content={confirmReason} relationship="description">
                    <span>
                      <Button appearance="primary" disabled>
                        Confirm tier
                      </Button>
                    </span>
                  </Tooltip>
                ) : (
                  <Button
                    appearance="primary"
                    disabled={confirm.isPending || !storedTier}
                    onClick={() => storedTier && doConfirm(storedTier)}
                  >
                    {`Confirm tier ${storedTier}`}
                  </Button>
                )}
                {canConfirmNow ? (
                  <Button onClick={() => setChanging((v) => !v)}>Change tier</Button>
                ) : (
                  <Tooltip
                    content={confirmReason ?? 'No tier proposed yet'}
                    relationship="description"
                  >
                    <span>
                      <Button disabled>Change tier</Button>
                    </span>
                  </Tooltip>
                )}
              </>
            )}
          </div>
          {!can('confirm_tier') && (
            <Caption1>Confirm / change tier: {reasonFor('confirm_tier')}</Caption1>
          )}
          {changing && canConfirmNow && (
            <div className={s.stack}>
              <Field label="New tier" required>
                <Select value={newTier} onChange={(_, d) => setNewTier(d.value)}>
                  <option value="">Select…</option>
                  {props.reference.tiers.map((x) => (
                    <option key={x.tier} value={String(x.tier)}>
                      Tier {x.tier} – {x.name}
                    </option>
                  ))}
                </Select>
              </Field>
              <Field label="Reason for change" required>
                <Textarea value={reason} onChange={(_, d) => setReason(d.value)} rows={2} />
              </Field>
              <div>
                <Button
                  appearance="primary"
                  disabled={!changeValid || confirm.isPending}
                  onClick={() => doConfirm(Number(newTier), reason.trim())}
                >
                  Apply tier change
                </Button>
              </div>
            </div>
          )}
        </div>
      </SectionCard>
    </div>
  );
}

const PROFILE_FIELDS: { key: keyof AIProfileIn; label: string; area?: boolean }[] = [
  { key: 'infrastructure_solution', label: 'Infrastructure solution' },
  { key: 'agentic_framework', label: 'Agentic development framework' },
  { key: 'number_of_users', label: 'Number of users' },
  { key: 'models_used', label: 'Models used' },
  { key: 'data_sources', label: 'Data sources' },
  { key: 'hosting', label: 'Hosting' },
  { key: 'agentic_workflows', label: 'Agentic workflows', area: true },
  { key: 'write_actions_detail', label: 'Write actions detail', area: true },
];

function ProfileForm(props: { transitionId: string; initial: AIProfile; me: Me }) {
  const s = useStyles();
  const [v, setV] = useState<AIProfileIn>({ ...props.initial });
  const save = useSaveAiProfile(props.transitionId);
  const showError = useApiErrorToast();
  const { dispatchToast } = useToastController(TOASTER_ID);
  const allowed = props.me.permissions.includes('edit_ai_profile');
  const why = props.me.denied_reasons['edit_ai_profile'] ?? 'You cannot edit the AI profile';
  const btn = (
    <Button
      appearance="primary"
      disabled={!allowed || save.isPending}
      onClick={() =>
        save.mutate(v, {
          onSuccess: () =>
            dispatchToast(
              <Toast>
                <ToastTitle>AI profile saved</ToastTitle>
              </Toast>,
              { intent: 'success' },
            ),
          onError: showError,
        })
      }
    >
      Save AI profile
    </Button>
  );
  return (
    <SectionCard title="AI profile questionnaire">
      <div className={s.profile}>
        {PROFILE_FIELDS.map((f) => (
          <Field key={f.key} label={f.label} style={f.area ? { gridColumn: '1 / -1' } : undefined}>
            {f.area ? (
              <Textarea
                rows={2}
                disabled={!allowed}
                value={String(v[f.key] ?? '')}
                onChange={(_, d) => setV({ ...v, [f.key]: d.value })}
              />
            ) : (
              <Input
                disabled={!allowed}
                value={String(v[f.key] ?? '')}
                onChange={(_, d) => setV({ ...v, [f.key]: d.value })}
              />
            )}
          </Field>
        ))}
        <Field label="Multi-agent orchestration">
          <RadioGroup
            layout="horizontal"
            disabled={!allowed}
            value={v.multi_agent_orchestration ? 'yes' : 'no'}
            onChange={(_, d) => setV({ ...v, multi_agent_orchestration: d.value === 'yes' })}
          >
            <Radio value="yes" label="Yes" />
            <Radio value="no" label="No" />
          </RadioGroup>
        </Field>
      </div>
      <div>
        {allowed ? (
          btn
        ) : (
          <Tooltip content={why} relationship="description">
            <span>{btn}</span>
          </Tooltip>
        )}
      </div>
    </SectionCard>
  );
}

function ProfileStep(props: { t: TransitionDetail; me: Me }) {
  const q = useAiProfile(props.t.id, true);
  if (q.error) return <ErrorState error={q.error} />;
  if (!q.data) return <LoadingState rows={5} />;
  return <ProfileForm transitionId={props.t.id} initial={q.data} me={props.me} />;
}

const STEP_TITLES = ['1. Questions', '2. Proposed tier', '3. AI profile'];

/** AI tiering wizard – FR-021 (spec 8.5, BR-011). */
export function TieringPage() {
  const { id } = useParams();
  const s = useStyles();
  const navigate = useNavigate();
  const tq = useTransition(id);
  const ref = useReference();
  const me = useMe();
  const [step, setStep] = useState(0);
  const [edited, setAnswers] = useState<Answers | null>(null);

  const err = tq.error ?? ref.error ?? me.error;
  const t = tq.data;
  const answers: Answers = edited ?? (t?.tier?.answers as Answers | undefined) ?? {};
  return (
    <>
      <PageHeader
        title="AI tiering"
        subtitle={t ? `${t.id} · ${t.name} · ${t.flavour_label}` : undefined}
        actions={
          <Button appearance="primary" onClick={() => navigate(`/transitions/${id}/scope`)}>
            Continue to scope
          </Button>
        }
      />
      {err ? (
        <ErrorState error={err} />
      ) : !t || !ref.data || !me.data ? (
        <LoadingState rows={6} />
      ) : !t.requires_tiering ? (
        <EmptyState
          message="Tiering applies to AI project types only."
          action={<Link to={`/transitions/${t.id}/scope`}>Go to scope</Link>}
        />
      ) : (
        <div className={s.stack}>
          <div className={s.steps} role="tablist" aria-label="Tiering steps">
            {STEP_TITLES.map((title, i) => (
              <Button
                key={title}
                role="tab"
                aria-selected={step === i}
                appearance={step === i ? 'primary' : 'secondary'}
                onClick={() => setStep(i)}
              >
                {title}
              </Button>
            ))}
          </div>
          {t.tier?.status === 'Proposed' && (
            <MessageBar intent="info">
              <MessageBarBody>
                Tier {t.tier.proposed_tier} proposed – waiting for IRM confirmation.
              </MessageBarBody>
            </MessageBar>
          )}
          {step === 0 && (
            <QuestionsStep t={t} reference={ref.data} answers={answers} set={setAnswers} />
          )}
          {step === 1 && <ProposalStep t={t} reference={ref.data} me={me.data} answers={answers} />}
          {step === 2 && <ProfileStep t={t} me={me.data} />}
          <div className={s.actions}>
            <Button disabled={step === 0} onClick={() => setStep(step - 1)}>
              Back
            </Button>
            {step < 2 ? (
              <Button appearance="primary" onClick={() => setStep(step + 1)}>
                Next
              </Button>
            ) : (
              <Button appearance="primary" onClick={() => navigate(`/transitions/${t.id}/scope`)}>
                Continue to scope
              </Button>
            )}
          </div>
        </div>
      )}
    </>
  );
}
