import type { ReactNode } from 'react';
import {
  Accordion,
  AccordionHeader,
  AccordionItem,
  AccordionPanel,
  makeStyles,
  tokens,
} from '@fluentui/react-components';
import { DirtyGuard, Intro } from '../peopleRulesUi';
import { ChainsPanel } from './ChainsPanel';
import { EvalPanel } from './EvalPanel';
import { RemindersPanel } from './RemindersPanel';
import { ThresholdsPanel } from './ThresholdsPanel';
import { TieringPanel } from './TieringPanel';

interface PanelDef {
  key: string;
  title: string;
  render: () => ReactNode;
}

const PANELS: PanelDef[] = [
  { key: 'tiering', title: 'Tiering', render: () => <TieringPanel /> },
  { key: 'rag', title: 'RAG thresholds', render: () => <ThresholdsPanel /> },
  { key: 'reminders', title: 'Reminder rules', render: () => <RemindersPanel /> },
  { key: 'chains', title: 'Approval chains', render: () => <ChainsPanel /> },
  { key: 'eval', title: 'Eval metric targets', render: () => <EvalPanel /> },
];

const useStyles = makeStyles({
  page: { display: 'flex', flexDirection: 'column', gap: tokens.spacingVerticalL },
  accordion: {
    border: `1px solid ${tokens.colorNeutralStroke2}`,
    borderRadius: tokens.borderRadiusMedium,
    backgroundColor: tokens.colorNeutralBackground1,
  },
  body: {
    display: 'flex',
    flexDirection: 'column',
    gap: tokens.spacingVerticalM,
    padding: `${tokens.spacingVerticalS} ${tokens.spacingHorizontalM} ${tokens.spacingVerticalL}`,
    minWidth: 0,
  },
});

/** Admin section 6: the numbers, wording and chains the workflow rules read. One page, five panels. */
export function RulesSection() {
  const s = useStyles();
  return (
    <DirtyGuard>
      <div className={s.page}>
        <Intro>
          Change the tiering questions, the Red / Amber / Green numbers, reminder timings, approval
          chains and evaluation targets. Thresholds apply immediately; chains and targets apply to
          new transitions. The rules themselves stay in the framework and are not changed here.
        </Intro>
        <Accordion className={s.accordion} multiple collapsible>
          {PANELS.map((p) => (
            <AccordionItem key={p.key} value={p.key}>
              <AccordionHeader size="large">{p.title}</AccordionHeader>
              <AccordionPanel>
                <div className={s.body}>{p.render()}</div>
              </AccordionPanel>
            </AccordionItem>
          ))}
        </Accordion>
      </div>
    </DirtyGuard>
  );
}
