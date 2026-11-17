// Friendly aliases over the generated schema (src/api/schema.d.ts, never hand-edited).
import type { components } from './schema';

type S = components['schemas'];

export type User = S['UserOut'];
export type Me = S['MeOut'];
export type Reference = S['ReferenceOut'];

// M2: register, control tower, dashboard, Orion insights (FR-010..012).
export type TransitionSummary = S['TransitionSummaryOut'];
export type TransitionFilters = S['TransitionFilters'];
export type KpiTile = S['KpiTileOut'];
export type LensValues = S['LensValues'];
export type ControlTower = S['ControlTowerOut'];
export type Heatmap = S['HeatmapOut'];
export type HeatmapCell = S['HeatmapCellOut'];
export type GateRef = S['GateRefOut'];
export type RegionReadiness = S['RegionReadinessOut'];
export type Escalation = S['EscalationOut'];
export type CalendarEntry = S['CalendarEntryOut'];
export type OperatingRhythmRow = S['OperatingRhythmRowOut'];
export type Dashboard = S['DashboardOut'];
export type WorkItem = S['WorkItemOut'];
export type PortfolioTile = S['PortfolioTileOut'];
export type AuditEvent = S['AuditEventOut'];
export type Insights = S['InsightsOut'];
export type Insight = S['InsightOut'];
