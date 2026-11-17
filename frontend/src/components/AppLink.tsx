import type { ReactNode } from 'react';
import { Link } from '@fluentui/react-components';
import { useNavigate } from 'react-router';

/** Fluent link that navigates inside the SPA (no full reload, no window.open) but still has a real
 * href, so middle-click and copy-link work. */
export function AppLink(props: { to: string; children: ReactNode; ariaLabel?: string }) {
  const navigate = useNavigate();
  return (
    <Link
      href={props.to}
      aria-label={props.ariaLabel}
      onClick={(e) => {
        if (e.button !== 0 || e.metaKey || e.ctrlKey || e.shiftKey) return;
        e.preventDefault();
        navigate(props.to);
      }}
    >
      {props.children}
    </Link>
  );
}
