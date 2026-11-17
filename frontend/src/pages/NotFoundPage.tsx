import { Link } from 'react-router';
import { EmptyState } from '../components/EmptyState';
import { PageHeader } from '../components/PageHeader';

export function NotFoundPage() {
  return (
    <>
      <PageHeader title="Page not found" />
      <EmptyState
        message="This page does not exist."
        action={<Link to="/">Go to the dashboard</Link>}
      />
    </>
  );
}
