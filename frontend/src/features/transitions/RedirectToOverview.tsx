import { Navigate, useLocation, useParams } from 'react-router';

/** /transitions/:id -> /transitions/:id/overview, keeping ?query and #hash (A-31, deep links). */
export function RedirectToOverview() {
  const { id = '' } = useParams();
  const { search, hash } = useLocation();
  return (
    <Navigate
      to={{ pathname: `/transitions/${encodeURIComponent(id)}/overview`, search, hash }}
      replace
    />
  );
}
