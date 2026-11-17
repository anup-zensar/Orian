import type { OcetLine, OcetLineIn } from './api';

/** One row of the editable grid. `key` is a stable React key (line id or a client counter). */
export interface EditLine {
  key: string;
  id: number | null;
  line_key: string | null;
  category: string;
  description: string;
  vendor: string;
  pricing_basis: string;
  base_amount: number | null;
  growth_pct: number;
  year_overrides: Record<string, number>;
  override_reason: string;
  input_owner_role: string;
  input_owner_user_id: string | null;
  input_status: 'Provided' | 'Requested' | 'Missing';
  input_requested_at: string | null;
  requested_days: number;
}

export function fromServer(l: OcetLine): EditLine {
  return {
    key: `L${l.id}`,
    id: l.id,
    line_key: l.line_key,
    category: l.category,
    description: l.description,
    vendor: l.vendor,
    pricing_basis: l.pricing_basis,
    base_amount: l.base_amount,
    growth_pct: l.growth_pct,
    year_overrides: { ...l.year_overrides },
    override_reason: l.override_reason ?? '',
    input_owner_role: l.input_owner_role,
    input_owner_user_id: l.input_owner?.id ?? null,
    input_status: l.input_status,
    input_requested_at: l.input_requested_at,
    requested_days: l.requested_days,
  };
}

let counter = 0;
export function newLine(category: string, pricingBasis: string, growth: number): EditLine {
  counter += 1;
  return {
    key: `N${counter}`,
    id: null,
    line_key: null,
    category,
    description: '',
    vendor: '',
    pricing_basis: pricingBasis,
    base_amount: null,
    growth_pct: growth,
    year_overrides: {},
    override_reason: '',
    input_owner_role: 'PM',
    input_owner_user_id: null,
    input_status: 'Missing',
    input_requested_at: null,
    requested_days: 0,
  };
}

/** Client-side preview of BR-070: amount[y] = amount[y-1] * (1 + g_y/100); missing base -> 0. */
export function project(line: EditLine, years: number[]): number[] {
  if (line.base_amount === null) return years.map(() => 0);
  const out: number[] = [];
  let prev = line.base_amount;
  years.forEach((y, i) => {
    if (i > 0) {
      const g = line.year_overrides[String(y)] ?? line.growth_pct;
      prev = prev * (1 + g / 100);
    }
    out.push(prev);
  });
  return out;
}

export function toInput(l: EditLine): OcetLineIn {
  const hasOverrides = Object.keys(l.year_overrides).length > 0;
  let status = l.input_status;
  if (l.base_amount !== null) status = 'Provided';
  else if (status === 'Provided') status = 'Missing';
  return {
    id: l.id,
    line_key: l.line_key,
    category: l.category,
    description: l.description,
    vendor: l.vendor,
    pricing_basis: l.pricing_basis,
    base_amount: l.base_amount,
    growth_pct: l.growth_pct,
    year_overrides: l.year_overrides,
    override_reason: hasOverrides ? l.override_reason : null,
    input_owner_role: l.input_owner_role,
    input_owner_user_id: l.input_owner_user_id,
    input_status: status,
  };
}
