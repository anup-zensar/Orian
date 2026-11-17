import type { ReactNode } from 'react';
import {
  MessageBar,
  MessageBarBody,
  Tab,
  TabList,
  makeStyles,
  tokens,
} from '@fluentui/react-components';
import { Navigate, useNavigate, useParams } from 'react-router';
import { PageHeader } from '../../components/PageHeader';
import { useReference } from '../reference/api';
import { ADMIN_NOTICE } from './api';
import { ChainsSection } from './ChainsSection';
import { DemoSection } from './DemoSection';
import { EvalSection } from './EvalSection';
import { FlavourSection } from './FlavourSection';
import { GoldenSetSection } from './GoldenSetSection';
import { PlaybookSection } from './PlaybookSection';
import { RemindersSection } from './RemindersSection';
import { UsersSection } from './UsersSection';

interface SectionDef {
  key: string;
  label: string;
  render: () => ReactNode;
  demoOnly?: boolean;
}

const SECTIONS: SectionDef[] = [
  { key: 'playbook', label: 'Playbook library', render: () => <PlaybookSection /> },
  { key: 'flavour', label: 'Flavour rules', render: () => <FlavourSection /> },
  { key: 'golden-sets', label: 'Portfolio golden sets', render: () => <GoldenSetSection /> },
  { key: 'eval-targets', label: 'Eval metric targets', render: () => <EvalSection /> },
  { key: 'approval-chains', label: 'Approval chains', render: () => <ChainsSection /> },
  { key: 'reminders', label: 'Reminder rules', render: () => <RemindersSection /> },
  { key: 'users', label: 'Users', render: () => <UsersSection /> },
  { key: 'demo', label: 'Demo controls', render: () => <DemoSection />, demoOnly: true },
];

const useStyles = makeStyles({
  layout: {
    display: 'flex',
    gap: tokens.spacingHorizontalXL,
    alignItems: 'flex-start',
    flexWrap: 'wrap',
  },
  nav: { minWidth: '210px' },
  content: {
    flexGrow: 1,
    flexBasis: '480px',
    minWidth: 0,
    display: 'flex',
    flexDirection: 'column',
    gap: tokens.spacingVerticalL,
  },
});

/** Admin (FR-100, spec 8.16): playbook configuration and demo controls. ADMIN only. */
export function AdminPage() {
  const s = useStyles();
  const navigate = useNavigate();
  const section = useParams()['*']?.split('/')[0] ?? '';
  const ref = useReference();
  const demoMode = ref.data?.app.demo_mode === true;
  const visible = SECTIONS.filter((x) => !x.demoOnly || demoMode);
  const current = visible.find((x) => x.key === section);

  // Unknown section: go to the first. The demo tab waits for /reference before it is judged.
  if (!current && !(section === 'demo' && ref.isLoading)) {
    return <Navigate to={`/admin/${visible[0].key}`} replace />;
  }

  return (
    <div>
      <PageHeader title="Admin" subtitle="Playbook configuration and demo controls" />
      <div className={s.layout}>
        <TabList
          className={s.nav}
          vertical
          selectedValue={section}
          onTabSelect={(_, d) => navigate(`/admin/${String(d.value)}`)}
        >
          {visible.map((x) => (
            <Tab key={x.key} value={x.key}>
              {x.label}
            </Tab>
          ))}
        </TabList>
        <div className={s.content}>
          {section !== 'demo' && section !== 'users' && (
            <MessageBar intent="info">
              <MessageBarBody>{ADMIN_NOTICE}</MessageBarBody>
            </MessageBar>
          )}
          {current?.render()}
        </div>
      </div>
    </div>
  );
}
