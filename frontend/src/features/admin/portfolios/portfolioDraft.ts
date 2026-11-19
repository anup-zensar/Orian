import type { PortfolioAdmin } from '../../../api/types';

/** What the admin edits for a portfolio. Focus areas are one per line, synonyms comma separated. */
export interface PortfolioDraft {
  label: string;
  description: string;
  focus_areas: string;
  requires_sites: boolean;
  sites_label: string;
  synonyms: string;
}

export const EMPTY_PORTFOLIO: PortfolioDraft = {
  label: '',
  description: '',
  focus_areas: '',
  requires_sites: false,
  sites_label: '',
  synonyms: '',
};

export const draftFromPortfolio = (p: PortfolioAdmin): PortfolioDraft => ({
  label: p.label,
  description: p.description,
  focus_areas: p.focus_areas.join('\n'),
  requires_sites: p.requires_sites,
  sites_label: p.sites_label,
  synonyms: p.synonyms.join(', '),
});

const splitLines = (text: string) =>
  text
    .split('\n')
    .map((x) => x.trim())
    .filter(Boolean);
const splitCommas = (text: string) =>
  text
    .split(',')
    .map((x) => x.trim())
    .filter(Boolean);

/** The request body fields shared by create and update. */
export const draftToBody = (d: PortfolioDraft) => ({
  label: d.label.trim(),
  description: d.description,
  focus_areas: splitLines(d.focus_areas),
  requires_sites: d.requires_sites,
  sites_label: d.requires_sites ? d.sites_label.trim() : '',
  synonyms: splitCommas(d.synonyms),
});
