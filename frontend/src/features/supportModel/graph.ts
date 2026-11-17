import type { Landscape, LandscapeComponent } from './api';

export const APP_NODE_ID = 'app';
export type Direction = 'bidirectional' | 'inbound' | 'outbound' | 'child_of';

export const DIRECTIONS: { value: Direction; label: string }[] = [
  { value: 'bidirectional', label: 'Both ways' },
  { value: 'inbound', label: 'Inbound (into target)' },
  { value: 'outbound', label: 'Outbound (from target)' },
  { value: 'child_of', label: 'Child of target' },
];

export function directionOf(c: LandscapeComponent): Direction {
  if (c.relation.startsWith('child_of')) return 'child_of';
  if (c.relation === 'inbound' || c.relation === 'outbound') return c.relation;
  return 'bidirectional';
}

/** Name of the node this component's edge points to (central app unless a target/parent is set). */
export function targetNameOf(c: LandscapeComponent, centralApp: string): string {
  if (c.relation.startsWith('child_of:')) return c.relation.slice('child_of:'.length);
  return c.target ?? centralApp;
}

/** Rebuild relation/target for a component given a direction and target node name. */
export function withEdge(
  c: LandscapeComponent,
  direction: Direction,
  targetName: string,
  centralApp: string,
): LandscapeComponent {
  if (direction === 'child_of') {
    return { ...c, relation: `child_of:${targetName}`, target: null };
  }
  return { ...c, relation: direction, target: targetName === centralApp ? null : targetName };
}

export function nextComponentId(components: LandscapeComponent[]): string {
  let max = 0;
  for (const c of components) {
    const n = Number(/^c(\d+)$/.exec(c.id)?.[1] ?? 0);
    if (n > max) max = n;
  }
  return `c${max + 1}`;
}

export interface Pos {
  x: number;
  y: number;
}

/** Radial layout: central app at the origin, components on a ring, child_of nodes on an outer ring
 * near their parent. */
export function radialLayout(landscape: Landscape): Record<string, Pos> {
  const out: Record<string, Pos> = { [APP_NODE_ID]: { x: 0, y: 0 } };
  const comps = landscape.components;
  const names = new Set(comps.map((c) => c.name));
  const isChild = (c: LandscapeComponent) =>
    c.relation.startsWith('child_of:') && names.has(targetNameOf(c, landscape.central_app));
  const roots = comps.filter((c) => !isChild(c));
  // Ellipse (wider than tall) so the layout fits a landscape canvas at a readable zoom.
  const rx = Math.max(300, roots.length * 48);
  const ry = Math.round(rx * 0.5);
  const angleOf = new Map<string, number>();
  roots.forEach((c, i) => {
    const a = (2 * Math.PI * i) / Math.max(roots.length, 1) - Math.PI / 2;
    angleOf.set(c.name, a);
    out[c.id] = { x: Math.cos(a) * rx, y: Math.sin(a) * ry };
  });
  const kidsOf = new Map<string, LandscapeComponent[]>();
  for (const c of comps.filter(isChild)) {
    const p = targetNameOf(c, landscape.central_app);
    kidsOf.set(p, [...(kidsOf.get(p) ?? []), c]);
  }
  for (const [parent, kids] of kidsOf) {
    const base = angleOf.get(parent) ?? 0;
    kids.forEach((c, i) => {
      const a = base + (i - (kids.length - 1) / 2) * 0.35;
      out[c.id] = { x: Math.cos(a) * (rx + 220), y: Math.sin(a) * (ry + 130) };
    });
  }
  return out;
}
