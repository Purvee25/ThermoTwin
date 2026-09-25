const DRUG_LABELS: Record<string, string> = {
  beta_blocker: 'β-blocker',
  ace_inhibitor: 'ACE-i',
  arb: 'ARB',
  calcium_channel_blocker: 'CCB',
  thiazide_diuretic: 'Thiazide',
  nsaid: 'NSAID',
}

export function drugLabel(drug: string): string {
  return DRUG_LABELS[drug] ?? drug.replaceAll('_', ' ')
}
