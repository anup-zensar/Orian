import { useState } from 'react';
import { Field, Input, Subtitle2, Textarea, makeStyles, tokens } from '@fluentui/react-components';
import { ErrorState } from '../../../components/ErrorState';
import { LoadingState } from '../../../components/LoadingState';
import type { TieringConfig } from '../../../api/types';
import { usePutTiering, useTiering } from '../peopleRulesApi';
import { ReasonsBar, SaveBar } from '../peopleRulesUi';
import { useDirty } from '../useDirty';
import { useSuccessToast } from '../useSavedToast';

type Question = TieringConfig['questions'][number];
type Tier = TieringConfig['tiers'][number];

const useStyles = makeStyles({
  note: { color: tokens.colorNeutralForeground3, margin: 0 },
  group: { display: 'flex', flexDirection: 'column', gap: tokens.spacingVerticalM },
  card: {
    display: 'flex',
    flexDirection: 'column',
    gap: tokens.spacingVerticalS,
    padding: tokens.spacingVerticalM,
    border: `1px solid ${tokens.colorNeutralStroke2}`,
    borderRadius: tokens.borderRadiusMedium,
  },
  pair: {
    display: 'grid',
    gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))',
    gap: tokens.spacingHorizontalM,
  },
  code: { color: tokens.colorNeutralForeground3, fontWeight: tokens.fontWeightRegular },
});

function Editor({ data }: { data: TieringConfig }) {
  const s = useStyles();
  const [questions, setQuestions] = useState<Question[]>(data.questions);
  const [tiers, setTiers] = useState<Tier[]>(data.tiers);
  const dirty = useDirty({ questions, tiers }, 'tiering');
  const save = usePutTiering();
  const ok = useSuccessToast();

  const editQuestion = (i: number, p: Partial<Question>) =>
    setQuestions((qs) => qs.map((q, j) => (j === i ? { ...q, ...p } : q)));
  const editTier = (i: number, p: Partial<Tier>) =>
    setTiers((ts) => ts.map((t, j) => (j === i ? { ...t, ...p } : t)));

  const blank = questions.some((q) => !q.text.trim()) || tiers.some((t) => !t.name.trim());

  // Send back everything we were given (the rules the server keeps stay as they are) with the
  // edited questions and tier texts; the read-only helper fields are left out.
  const submit = () =>
    save.mutate(
      { ...data, questions, tiers, sources: undefined, notice: undefined },
      { onSuccess: () => ok('Saved - applies to new transitions') },
    );

  return (
    <>
      <p className={s.note}>
        Change the wording of the tiering questions and the description of each tier. Which answers
        lead to which tier is fixed by the S&amp;T framework and is not changed here.
      </p>
      <div className={s.group}>
        <Subtitle2 as="h3">Questions</Subtitle2>
        {questions.map((q, i) => (
          <div key={q.id} className={s.card}>
            <Field label={`Question ${q.id}`}>
              <Textarea
                rows={2}
                value={q.text}
                onChange={(_, d) => editQuestion(i, { text: d.value })}
              />
            </Field>
            <Field label="Hint shown under the question">
              <Input
                aria-label={`${q.id} hint`}
                value={q.hint ?? ''}
                onChange={(_, d) => editQuestion(i, { hint: d.value })}
              />
            </Field>
          </div>
        ))}
      </div>
      <div className={s.group}>
        <Subtitle2 as="h3">Tier definitions</Subtitle2>
        {tiers.map((t, i) => (
          <div key={t.tier} className={s.card}>
            <Subtitle2 as="h4">Tier {t.tier}</Subtitle2>
            <div className={s.pair}>
              <Field label="Name" required>
                <Input
                  aria-label={`Tier ${t.tier} name`}
                  value={t.name}
                  onChange={(_, d) => editTier(i, { name: d.value })}
                />
              </Field>
              <Field label="Who builds it">
                <Input
                  aria-label={`Tier ${t.tier} builder`}
                  value={t.builder_persona ?? ''}
                  onChange={(_, d) => editTier(i, { builder_persona: d.value })}
                />
              </Field>
            </div>
            <Field label="Definition">
              <Textarea
                rows={2}
                aria-label={`Tier ${t.tier} definition`}
                value={t.definition ?? ''}
                onChange={(_, d) => editTier(i, { definition: d.value })}
              />
            </Field>
            <Field label="Examples">
              <Input
                aria-label={`Tier ${t.tier} examples`}
                value={t.examples ?? ''}
                onChange={(_, d) => editTier(i, { examples: d.value })}
              />
            </Field>
          </div>
        ))}
      </div>
      <ReasonsBar error={save.error} />
      <SaveBar
        dirty={dirty}
        saving={save.isPending}
        blockedReason={blank ? 'Questions and tier names cannot be empty' : undefined}
        onSave={submit}
        onDiscard={() => {
          setQuestions(data.questions);
          setTiers(data.tiers);
          save.reset();
        }}
      />
    </>
  );
}

export function TieringPanel() {
  const q = useTiering();
  if (q.isLoading) return <LoadingState rows={5} />;
  if (q.isError) return <ErrorState error={q.error} onRetry={() => void q.refetch()} />;
  return q.data ? <Editor key={q.dataUpdatedAt} data={q.data} /> : null;
}
