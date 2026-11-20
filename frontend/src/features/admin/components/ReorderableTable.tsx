import { useEffect, useRef, useState, type ReactNode } from 'react';
import {
  Button,
  Table,
  TableBody,
  TableCell,
  TableHeader,
  TableHeaderCell,
  TableRow,
  makeStyles,
  tokens,
} from '@fluentui/react-components';
import {
  ArrowDown16Regular,
  ArrowUp16Regular,
  LockClosed16Regular,
  ReOrderDotsVertical16Regular,
} from '@fluentui/react-icons';
import { DataTable } from '../../../components/DataTable';
import { DisabledReason } from './DisabledReason';

export interface ReorderColumn<T> {
  header: string;
  width?: number | string;
  render: (row: T, index: number) => ReactNode;
}

const useStyles = makeStyles({
  handleCell: { display: 'flex', alignItems: 'center', gap: '2px' },
  handle: { cursor: 'grab', minWidth: 0 },
  dropTarget: { boxShadow: `inset 0 2px 0 ${tokens.colorBrandStroke1}` },
});

function move<T>(rows: T[], from: number, to: number): T[] {
  const next = rows.slice();
  const [row] = next.splice(from, 1);
  next.splice(to, 0, row);
  return next;
}

/**
 * A table whose rows can be reordered by dragging the handle, with the arrow buttons, or with
 * the Up / Down arrow keys on the handle. `reorderLockedReason` turns reordering off and explains why.
 */
export function ReorderableTable<T>(props: {
  ariaLabel: string;
  rows: T[];
  rowKey: (row: T) => string;
  columns: ReorderColumn<T>[];
  onReorder: (rows: T[]) => void;
  reorderLockedReason?: string | null;
}) {
  const s = useStyles();
  const { rows, rowKey, onReorder, reorderLockedReason } = props;
  const dragFrom = useRef<number | null>(null);
  const [overIndex, setOverIndex] = useState<number | null>(null);
  const focusKey = useRef<string | null>(null);
  const locked = !!reorderLockedReason;

  // After a keyboard move, put focus back on the same row's handle.
  useEffect(() => {
    if (!focusKey.current) return;
    document.querySelector<HTMLElement>(`[data-handle="${CSS.escape(focusKey.current)}"]`)?.focus();
    focusKey.current = null;
  });

  const moveRow = (from: number, to: number) => {
    if (to < 0 || to >= rows.length || from === to) return;
    focusKey.current = rowKey(rows[from]);
    onReorder(move(rows, from, to));
  };

  return (
    <DataTable label={props.ariaLabel}>
      <Table
        aria-label={props.ariaLabel}
        size="small"
        style={{ tableLayout: 'auto', minWidth: '100%' }}
      >
        <TableHeader>
          <TableRow>
            <TableHeaderCell style={{ width: 96 }}>Order</TableHeaderCell>
            {props.columns.map((c) => (
              <TableHeaderCell key={c.header} style={{ width: c.width }}>
                {c.header}
              </TableHeaderCell>
            ))}
          </TableRow>
        </TableHeader>
        <TableBody>
          {rows.map((row, i) => (
            <TableRow
              key={rowKey(row)}
              className={overIndex === i ? s.dropTarget : undefined}
              onDragOver={(e) => {
                if (dragFrom.current === null) return;
                e.preventDefault();
                setOverIndex(i);
              }}
              onDrop={(e) => {
                e.preventDefault();
                if (dragFrom.current !== null) moveRow(dragFrom.current, i);
                dragFrom.current = null;
                setOverIndex(null);
              }}
            >
              <TableCell>
                {locked ? (
                  <DisabledReason reason={reorderLockedReason}>
                    <LockClosed16Regular aria-label="Order is fixed" />
                  </DisabledReason>
                ) : (
                  <div className={s.handleCell}>
                    <Button
                      className={s.handle}
                      size="small"
                      appearance="subtle"
                      icon={<ReOrderDotsVertical16Regular />}
                      aria-label={`Drag to reorder, or press Up or Down arrow (row ${i + 1} of ${rows.length})`}
                      data-handle={rowKey(row)}
                      draggable
                      onDragStart={(e) => {
                        dragFrom.current = i;
                        e.dataTransfer.effectAllowed = 'move';
                      }}
                      onDragEnd={() => {
                        dragFrom.current = null;
                        setOverIndex(null);
                      }}
                      onKeyDown={(e) => {
                        if (e.key === 'ArrowUp') {
                          e.preventDefault();
                          moveRow(i, i - 1);
                        } else if (e.key === 'ArrowDown') {
                          e.preventDefault();
                          moveRow(i, i + 1);
                        }
                      }}
                    />
                    <Button
                      size="small"
                      appearance="subtle"
                      icon={<ArrowUp16Regular />}
                      aria-label="Move up"
                      disabled={i === 0}
                      onClick={() => moveRow(i, i - 1)}
                    />
                    <Button
                      size="small"
                      appearance="subtle"
                      icon={<ArrowDown16Regular />}
                      aria-label="Move down"
                      disabled={i === rows.length - 1}
                      onClick={() => moveRow(i, i + 1)}
                    />
                  </div>
                )}
              </TableCell>
              {props.columns.map((c) => (
                <TableCell key={c.header}>{c.render(row, i)}</TableCell>
              ))}
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </DataTable>
  );
}
