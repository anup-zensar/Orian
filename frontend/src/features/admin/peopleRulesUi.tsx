// Small building blocks shared by the People, Rules and Messages sections.
import { useCallback, useState, type ReactNode } from 'react';
import {
  Button,
  MessageBar,
  MessageBarBody,
  Tooltip,
  makeStyles,
  tokens,
} from '@fluentui/react-components';
import { ApiError } from '../../api/client';
import { DirtyContext } from './useDirty';
import { useLeaveGuard } from '../ocet/useLeaveGuard';

const useStyles = makeStyles({
  intro: { color: tokens.colorNeutralForeground2, maxWidth: '900px', margin: 0 },
  bar: {
    position: 'sticky',
    bottom: 0,
    zIndex: 2,
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'flex-end',
    gap: tokens.spacingHorizontalM,
    flexWrap: 'wrap',
    padding: tokens.spacingVerticalS,
    border: `1px solid ${tokens.colorNeutralStroke2}`,
    borderRadius: tokens.borderRadiusMedium,
    backgroundColor: tokens.colorNeutralBackground3,
    boxShadow: tokens.shadow8,
  },
  barText: { marginRight: 'auto', fontWeight: tokens.fontWeightSemibold },
  reasons: { margin: 0, paddingLeft: '18px' },
});

/** The one plain sentence every section starts with: what you can change and what it affects. */
export function Intro({ children }: { children: ReactNode }) {
  const s = useStyles();
  return <p className={s.intro}>{children}</p>;
}

type ReportDirty = (id: string, dirty: boolean) => void;

/** Wrap a section: leaving the page (or reloading) while any editor inside is dirty asks first. */
export function DirtyGuard({ children }: { children: ReactNode }) {
  const [dirtyIds, setDirtyIds] = useState<string[]>([]);
  const report = useCallback<ReportDirty>((id, dirty) => {
    setDirtyIds((cur) => {
      const has = cur.includes(id);
      if (dirty === has) return cur;
      return dirty ? [...cur, id] : cur.filter((x) => x !== id);
    });
  }, []);
  const dialog = useLeaveGuard(dirtyIds.length > 0);
  return (
    <DirtyContext.Provider value={report}>
      {children}
      {dialog}
    </DirtyContext.Provider>
  );
}

/** Inline list of the reasons the server gave for refusing a save. */
export function ReasonsBar({ error }: { error: unknown }) {
  const s = useStyles();
  if (!(error instanceof ApiError)) return null;
  return (
    <MessageBar layout="multiline" intent="error">
      <MessageBarBody>
        {error.detail}
        {error.reasons.length > 0 && (
          <ul className={s.reasons}>
            {error.reasons.map((r) => (
              <li key={r}>{r}</li>
            ))}
          </ul>
        )}
      </MessageBarBody>
    </MessageBar>
  );
}

/** "Unsaved changes" bar with Discard and Save. Shown only while there is something to save. */
export function SaveBar(props: {
  dirty: boolean;
  saving: boolean;
  onSave: () => void;
  onDiscard: () => void;
  /** Why Save is disabled (shown as a tooltip); empty when the edit is valid. */
  blockedReason?: string;
}) {
  const s = useStyles();
  if (!props.dirty) return null;
  const blocked = Boolean(props.blockedReason);
  return (
    <div className={s.bar} role="status">
      <span className={s.barText}>You have unsaved changes</span>
      <Button onClick={props.onDiscard} disabled={props.saving}>
        Discard changes
      </Button>
      <Tooltip content={props.blockedReason ?? 'Save'} relationship="description">
        <Button
          appearance="primary"
          onClick={props.onSave}
          disabled={props.saving}
          disabledFocusable={blocked}
        >
          {props.saving ? 'Saving...' : 'Save'}
        </Button>
      </Tooltip>
    </div>
  );
}
