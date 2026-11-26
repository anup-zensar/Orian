import { useState } from 'react';
import { Badge, Button, makeStyles, tokens } from '@fluentui/react-components';
import { LockClosed16Regular } from '@fluentui/react-icons';
import { ErrorState } from '../../../components/ErrorState';
import { LoadingState } from '../../../components/LoadingState';
import { SectionCard } from '../../../components/SectionCard';
import type { IntakeFieldAdmin } from '../../../api/types';
import { useReference } from '../../reference/api';
import { useIntakeFieldsAdmin, useOrderIntakeFields } from '../catalogApi';
import { DisabledReason } from '../components/DisabledReason';
import { ReorderableTable } from '../components/ReorderableTable';
import { UsedByBadge } from '../components/UsedByBadge';
import { FieldDialog } from './FieldDialog';
import { typeText } from './fieldTypes';

const useStyles = makeStyles({
  small: { color: tokens.colorNeutralForeground3 },
  label: { display: 'flex', alignItems: 'center', gap: tokens.spacingHorizontalXS },
});

/** The form fields in the order they appear, with Add custom field and an Edit button per field. */
export function FormFieldsPanel() {
  const s = useStyles();
  const q = useIntakeFieldsAdmin();
  const order = useOrderIntakeFields();
  const { data: ref } = useReference();
  const [dialog, setDialog] = useState<IntakeFieldAdmin | 'new' | null>(null);
  const typeLabel = (code: string) =>
    ref?.project_types.find((p) => p.code === code)?.label || code;

  const requiredText = (f: IntakeFieldAdmin) => {
    if (f.required_mode === 'always') return 'Required';
    if (f.required_mode === 'by_project_type' && f.required_for_project_types.length)
      return `Required for ${f.required_for_project_types.map(typeLabel).join(', ')}`;
    return 'Optional';
  };

  return (
    <SectionCard
      title="Form fields"
      actions={
        <Button appearance="primary" onClick={() => setDialog('new')}>
          Add custom field
        </Button>
      }
    >
      <p className={s.small} style={{ margin: 0 }}>
        Drag a field, or use the arrows, to change the order. Custom fields appear in the intake
        form under &quot;Additional details&quot;.
      </p>
      {q.isLoading ? (
        <LoadingState rows={6} />
      ) : q.isError ? (
        <ErrorState error={q.error} onRetry={() => void q.refetch()} />
      ) : (
        <>
          {order.isError && <ErrorState error={order.error} />}
          <ReorderableTable
            ariaLabel="Form fields"
            rows={q.data ?? []}
            rowKey={(f) => f.key}
            onReorder={(rows) => order.mutate(rows.map((f) => f.key))}
            columns={[
              {
                header: 'Field',
                render: (f) => (
                  <div>
                    <div className={s.label} title={`Code: ${f.key}`}>
                      {f.label}
                      {f.structural && (
                        <DisabledReason reason="The app needs this field: it can be renamed but not hidden or made optional.">
                          <LockClosed16Regular aria-label="Locked field" />
                        </DisabledReason>
                      )}
                    </div>
                  </div>
                ),
              },
              { header: 'Type', render: (f) => typeText(f.type) },
              { header: 'Required', render: requiredText },
              {
                header: 'Shown in',
                render: (f) =>
                  [
                    f.show_on_overview && 'Overview',
                    f.show_in_list && 'List column',
                    f.filterable && 'Filter',
                  ]
                    .filter(Boolean)
                    .join(', ') || '-',
              },
              {
                header: 'Status',
                render: (f) =>
                  !f.active ? (
                    <Badge appearance="tint" color="subtle">
                      Retired
                    </Badge>
                  ) : !f.visible ? (
                    <Badge appearance="tint" color="warning">
                      Hidden
                    </Badge>
                  ) : (
                    <Badge appearance="tint" color="success">
                      Shown
                    </Badge>
                  ),
              },
              {
                header: 'Answers',
                render: (f) =>
                  f.builtin ? '-' : <UsedByBadge count={f.used_by} noun="transitions" />,
              },
              {
                header: '',
                render: (f) => (
                  <Button size="small" onClick={() => setDialog(f)}>
                    Edit
                  </Button>
                ),
              },
            ]}
          />
        </>
      )}
      {dialog && (
        <FieldDialog
          key={dialog === 'new' ? 'new' : dialog.key}
          field={dialog === 'new' ? undefined : dialog}
          onClose={() => setDialog(null)}
        />
      )}
    </SectionCard>
  );
}
