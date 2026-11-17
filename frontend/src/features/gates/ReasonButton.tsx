import type { ReactNode } from 'react';
import { Button, Tooltip, type ButtonProps } from '@fluentui/react-components';

/** Content of a "why is this disabled" tooltip: one line or a bullet list (spec 12, AC-08). */
export function ReasonList({ reasons }: { reasons: string[] }) {
  if (reasons.length === 1) return <span>{reasons[0]}</span>;
  return (
    <ul style={{ margin: 0, paddingLeft: 16 }}>
      {reasons.map((r, i) => (
        <li key={`${i}-${r}`}>{r}</li>
      ))}
    </ul>
  );
}

/**
 * A button that is disabled-with-reason: when `reasons` is non-empty it stays focusable (so the
 * tooltip works for mouse and keyboard) but cannot be clicked.
 */
export function ReasonButton({
  reasons,
  children,
  onClick,
  appearance,
  size,
  icon,
}: {
  reasons?: Array<string | null | undefined> | null;
  children?: ReactNode;
  onClick?: () => void;
  appearance?: ButtonProps['appearance'];
  size?: ButtonProps['size'];
  icon?: ButtonProps['icon'];
}) {
  const list = (reasons ?? []).filter((r): r is string => !!r);
  const blocked = list.length > 0;
  const button = (
    <Button
      appearance={appearance}
      size={size}
      icon={icon}
      disabledFocusable={blocked}
      onClick={() => {
        if (!blocked) onClick?.();
      }}
    >
      {children}
    </Button>
  );
  if (!blocked) return button;
  return (
    <Tooltip content={<ReasonList reasons={list} />} relationship="description">
      {button}
    </Tooltip>
  );
}
