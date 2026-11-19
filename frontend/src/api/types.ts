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

// CR-01 no-code configuration (GET /reference additions, features/reference/options.ts).
export type ProjectTypeRef = Reference['project_types'][number];
export type PortfolioRef = Reference['portfolio_details'][number];
export type RoleRef = Reference['roles'][number];
export type OptionRef = S['OptionOut'];
export type IntakeFieldRef = S['IntakeFieldRefOut'];
export type ChecklistRef = S['ChecklistRefOut'];

// CR-01 admin API (/admin/...): response and request bodies of routers/config_admin.py.
export type ProjectTypeAdmin = S['ProjectTypeAdminOut'];
export type ProjectTypeCreate = S['ProjectTypeCreateIn'];
export type ProjectTypeUpdate = S['ProjectTypeUpdateIn'];
export type ProjectTypePreview = S['ProjectTypePreviewOut'];
export type ChecklistAdmin = S['ChecklistAdminOut'];
export type ChecklistCreate = S['ChecklistCreateIn'];
export type ChecklistUpdate = S['ChecklistUpdateIn'];
export type PlaybookItemCreate = S['PlaybookItemCreateIn'];
export type PortfolioAdmin = S['PortfolioAdminOut'];
export type PortfolioCreate = S['PortfolioCreateIn'];
export type PortfolioUpdate = S['PortfolioUpdateIn'];
export type OptionListAdmin = S['OptionListAdminOut'];
export type OptionListCreate = S['OptionListCreateIn'];
export type OptionListUpdate = S['OptionListUpdateIn'];
export type OptionItemAdmin = S['OptionItemOut'];
export type OptionItemInput = S['OptionItemIn'];
export type OptionItemsAdmin = S['OptionItemsOut'];
export type IntakeFieldAdmin = S['IntakeFieldAdminOut'];
export type IntakeFieldCreate = S['IntakeFieldCreateIn'];
export type IntakeFieldUpdate = S['IntakeFieldUpdateIn'];
export type RoleAdmin = S['RoleAdminOut'];
export type RoleUpdate = S['RoleUpdateIn'];
export type UserAdmin = S['UserAdminOut'];
export type UserCreate = S['UserCreateIn'];
export type UserUpdate = S['UserUpdateIn'];
export type UserDeactivateInput = S['UserDeactivateIn'];
export type UserDeactivateResult = S['UserDeactivateOut'];
export type PermissionMatrix = S['PermissionMatrixOut'];
export type PermissionRow = S['PermissionRowOut'];
export type PermissionsPut = S['PermissionsPutIn'];
export type TieringConfig = S['TieringConfigOut'];
export type TieringConfigInput = S['TieringConfigIn'];
export type EvalMetricAdmin = S['EvalMetricAdminOut'];
export type EvalMetricCreate = S['EvalMetricCreateIn'];
export type EvalMetricUpdate = S['EvalMetricUpdateIn'];
export type ThresholdsAdmin = S['ThresholdsOut'];
export type ThresholdsDocument = S['ThresholdsDoc'];
export type MessageTemplateAdmin = S['MessageTemplateAdminOut'];
export type MessageTemplatesPut = S['MessageTemplatesPutIn'];
export type TemplatePreviewInput = S['TemplatePreviewIn'];
export type TemplatePreviewResult = S['TemplatePreviewOut'];
export type ConfigUsage = S['UsageOut'];
