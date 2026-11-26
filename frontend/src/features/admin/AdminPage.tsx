import { useEffect, useState, type ReactNode } from 'react';
import {
  Field,
  Select,
  Tab,
  TabList,
  makeStyles,
  mergeClasses,
  tokens,
} from '@fluentui/react-components';
import { Navigate, useNavigate, useParams } from 'react-router';
import { cardRadius, cardShadow } from '../../theme/orionTheme';
import { PageHeader } from '../../components/PageHeader';
import { useReference } from '../reference/api';
import { ChecklistsSection } from './checklists/ChecklistsSection';
import { DemoSection } from './DemoSection';
import { FormsSection } from './forms/FormsSection';
import { MessagesSection } from './messages/MessagesSection';
import { PeopleSection } from './people/PeopleSection';
import { PortfoliosSection } from './portfolios/PortfoliosSection';
import { ProjectTypesSection } from './projectTypes/ProjectTypesSection';
import { RulesSection } from './rules/RulesSection';

interface SectionDef {
  key: string;
  label: string;
  render: () => ReactNode;
  demoOnly?: boolean;
}

/** The eight admin sections, in the order of the left menu. Each has one URL: /admin/<key>. */
const SECTIONS: SectionDef[] = [
  { key: 'checklists', label: 'Checklists & items', render: () => <ChecklistsSection /> },
  { key: 'project-types', label: 'Project types', render: () => <ProjectTypesSection /> },
  { key: 'portfolios', label: 'Portfolios', render: () => <PortfoliosSection /> },
  { key: 'forms', label: 'Forms & dropdowns', render: () => <FormsSection /> },
  { key: 'people', label: 'People & permissions', render: () => <PeopleSection /> },
  { key: 'rules', label: 'Rules & thresholds', render: () => <RulesSection /> },
  { key: 'messages', label: 'Messages', render: () => <MessagesSection /> },
  { key: 'demo', label: 'Demo controls', render: () => <DemoSection />, demoOnly: true },
];

/** Old section URLs (bookmarks, earlier links) and the section that replaced them. */
const OLD_LINKS: Record<string, string> = {
  playbook: 'checklists',
  flavour: 'project-types',
  'golden-sets': 'portfolios',
  'eval-targets': 'rules',
  'approval-chains': 'rules',
  reminders: 'rules',
  users: 'people',
};

/** On narrow windows the left menu becomes a dropdown so the tables get the full width. */
const NARROW = '(max-width: 1399px)';
function useNarrow(): boolean {
  const [narrow, setNarrow] = useState(() => window.matchMedia(NARROW).matches);
  useEffect(() => {
    const query = window.matchMedia(NARROW);
    const update = () => setNarrow(query.matches);
    query.addEventListener('change', update);
    return () => query.removeEventListener('change', update);
  }, []);
  return narrow;
}

const useStyles = makeStyles({
  layout: {
    display: 'flex',
    gap: tokens.spacingHorizontalXL,
    alignItems: 'flex-start',
    flexWrap: 'wrap',
  },
  nav: {
    minWidth: '190px',
    padding: tokens.spacingVerticalS,
    backgroundColor: tokens.colorNeutralBackground1,
    border: `1px solid ${tokens.colorNeutralStroke2}`,
    borderRadius: cardRadius,
    boxShadow: cardShadow,
  },
  tab: {
    justifyContent: 'flex-start',
    width: '100%',
    '& .fui-Tab__content': { width: '100%', textAlign: 'left' },
  },
  picker: {
    width: '100%',
    maxWidth: '360px',
    padding: tokens.spacingHorizontalM,
    backgroundColor: tokens.colorNeutralBackground1,
    border: `1px solid ${tokens.colorNeutralStroke2}`,
    borderRadius: cardRadius,
    boxShadow: cardShadow,
  },
  content: {
    flexGrow: 1,
    flexBasis: '480px',
    minWidth: 0,
    display: 'flex',
    flexDirection: 'column',
    gap: tokens.spacingVerticalL,
  },
  contentBelowPicker: { flexBasis: '100%' },
});

/** Admin (FR-100, spec 8.16): configuration of everything a non-developer may change. ADMIN only. */
export function AdminPage() {
  const s = useStyles();
  const narrow = useNarrow();
  const navigate = useNavigate();
  const section = useParams()['*']?.split('/')[0] ?? '';
  const ref = useReference();
  const demoMode = ref.data?.app.demo_mode === true;
  const visible = SECTIONS.filter((x) => !x.demoOnly || demoMode);
  const current = visible.find((x) => x.key === section);

  // Old links go to the section that replaced them; anything else goes to the first section.
  // The demo section waits for /reference before it is judged.
  if (!current && !(section === 'demo' && ref.isLoading)) {
    return <Navigate to={`/admin/${OLD_LINKS[section] ?? visible[0].key}`} replace />;
  }

  return (
    <div>
      <PageHeader title="Admin" subtitle="Configure Orion without changing code" />
      <div className={s.layout}>
        {narrow ? (
          <Field label="Section" className={s.picker}>
            <Select value={section} onChange={(_, d) => navigate(`/admin/${d.value}`)}>
              {visible.map((x) => (
                <option key={x.key} value={x.key}>
                  {x.label}
                </option>
              ))}
            </Select>
          </Field>
        ) : (
          <TabList
            className={s.nav}
            vertical
            selectedValue={section}
            onTabSelect={(_, d) => navigate(`/admin/${String(d.value)}`)}
          >
            {visible.map((x) => (
              <Tab key={x.key} value={x.key} className={s.tab}>
                {x.label}
              </Tab>
            ))}
          </TabList>
        )}
        <div className={mergeClasses(s.content, narrow && s.contentBelowPicker)}>
          {current?.render()}
        </div>
      </div>
    </div>
  );
}
