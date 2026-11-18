/** One readable line for the checklist counts shown after launch and on the Overview (spec step 3). */
export interface CountsLike {
  framework?: number;
  ai_applicable?: number;
  ai_excluded?: number;
  golden_set_applies?: number;
  golden_set_to_confirm?: number;
  common?: number;
  total?: number;
  total_applicable?: number;
}

export function itemCountsParts(c: CountsLike, tier?: number | null): string[] {
  const parts = [`Framework ${c.framework ?? 0}`];
  if ((c.ai_applicable ?? 0) + (c.ai_excluded ?? 0) > 0)
    parts.push(
      `AI Playbook ${c.ai_applicable ?? 0} applicable / ${c.ai_excluded ?? 0} excluded${tier ? ` for Tier ${tier}` : ''}`,
    );
  const golden = (c.golden_set_applies ?? 0) + (c.golden_set_to_confirm ?? 0);
  if (golden > 0)
    parts.push(
      `Golden set ${c.golden_set_applies ?? 0}${c.golden_set_to_confirm ? ` (+${c.golden_set_to_confirm} to confirm)` : ''}`,
    );
  parts.push(`Common ${c.common ?? 0}`);
  return parts;
}

export function itemCountsText(c: CountsLike, tier?: number | null): string {
  const total = c.total ?? c.total_applicable;
  return `${itemCountsParts(c, tier).join(', ')}${total != null ? ` = ${total} applicable items` : ''}`;
}
