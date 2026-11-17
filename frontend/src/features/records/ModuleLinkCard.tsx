import { Badge, Body1, MessageBar, MessageBarBody } from '@fluentui/react-components';
import { AppLink } from '../../components/AppLink';
import { EmptyState } from '../../components/EmptyState';
import { ErrorState } from '../../components/ErrorState';
import { LoadingState } from '../../components/LoadingState';
import { PageHeader } from '../../components/PageHeader';
import { SectionCard } from '../../components/SectionCard';
import { useItems } from './api';
import { useRecordStyles } from './hooks';

/**
 * Link card for a module that arrives later (OCET M6, support model M7): explains what the module
 * will show and lists the current status of the linked checklist items.
 */
export function ModuleLinkCard(props: {
  transitionId: string;
  title: string;
  description: string;
  bullets: string[];
  itemIds: string[];
  milestone: string;
}) {
  const s = useRecordStyles();
  const items = useItems(props.transitionId, { all_gates: 'true', applicability: 'all' });
  const linked = (items.data?.items ?? []).filter((i) => props.itemIds.includes(i.item_id));

  return (
    <div className={s.stack}>
      <PageHeader title={props.title} subtitle={props.description} />
      <MessageBar intent="info">
        <MessageBarBody>Module arrives in {props.milestone}.</MessageBarBody>
      </MessageBar>
      <SectionCard title="What this module shows">
        <ul style={{ margin: 0, paddingLeft: 20 }}>
          {props.bullets.map((b) => (
            <li key={b}>
              <Body1>{b}</Body1>
            </li>
          ))}
        </ul>
      </SectionCard>
      <SectionCard title="Linked checklist items">
        {items.isPending ? (
          <LoadingState rows={2} />
        ) : items.isError ? (
          <ErrorState error={items.error} />
        ) : linked.length === 0 ? (
          <EmptyState message="The linked items are not part of this transition's scope." />
        ) : (
          <div className={s.stack}>
            {linked.map((i) => (
              <div key={i.item_id} className={s.row}>
                <AppLink
                  to={`/transitions/${encodeURIComponent(props.transitionId)}/assessment?item=${encodeURIComponent(i.item_id)}`}
                >
                  {i.item_id}
                </AppLink>
                <span>{i.title}</span>
                <Badge appearance="tint">{i.status}</Badge>
                {i.applicability !== 'Applies' && (
                  <Badge appearance="outline">{i.applicability}</Badge>
                )}
              </div>
            ))}
          </div>
        )}
      </SectionCard>
    </div>
  );
}
