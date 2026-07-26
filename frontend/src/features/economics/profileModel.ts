import type { CostProfile } from '../../api/contracts';

export type CostProfileTarget = 'product' | 'marketplace_default';
export type CostProfileWindowStatus = 'scheduled' | 'active' | 'ended' | 'unknown';

function belongsToTarget(
  profile: CostProfile,
  target: CostProfileTarget,
  productId: string,
): boolean {
  return target === 'product' ? profile.product_id === productId : profile.product_id === null;
}

export function latestScopedRevision(
  history: CostProfile[],
  target: CostProfileTarget,
  productId: string,
  activeFallback: CostProfile | null,
): CostProfile | null {
  return history.reduce<CostProfile | null>((latest, profile) => {
    if (!belongsToTarget(profile, target, productId)) return latest;
    if (!latest || profile.version > latest.version) return profile;
    if (profile.version < latest.version) return latest;
    return Date.parse(profile.effective_from) > Date.parse(latest.effective_from)
      ? profile
      : latest;
  }, activeFallback);
}

export function costProfileWindowStatus(
  profile: CostProfile,
  now = Date.now(),
): CostProfileWindowStatus {
  const effectiveFrom = Date.parse(profile.effective_from);
  const effectiveTo = profile.effective_to ? Date.parse(profile.effective_to) : null;
  if (Number.isNaN(effectiveFrom) || (effectiveTo !== null && Number.isNaN(effectiveTo))) {
    return 'unknown';
  }
  if (effectiveFrom > now) return 'scheduled';
  if (effectiveTo !== null && effectiveTo <= now) return 'ended';
  return 'active';
}
