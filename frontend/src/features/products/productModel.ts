import type { ProductSummary, Recommendation, Score } from '../../api/contracts';

const flatScoreFields: Record<string, keyof ProductSummary> = {
  demand: 'demand_score',
  competition: 'competition_score',
  price_stability: 'price_stability_score',
  data_confidence: 'confidence_score',
  overall_opportunity: 'overall_score',
};

export function productScore(product: ProductSummary, name: string): Score | undefined {
  const score = product.scores?.find((item) => item.name === name);
  if (score) return score;
  const field = flatScoreFields[name];
  const value = field ? product[field] : undefined;
  return typeof value === 'number' ? { name, value } : undefined;
}

export function productStrategy(product: ProductSummary): string | undefined {
  return product.recommendation?.strategy ?? product.strategy;
}

export function productRecommendation(product: ProductSummary): Recommendation | undefined {
  return product.recommendation;
}

export function allProductScores(product: ProductSummary): Score[] {
  if (product.scores && product.scores.length > 0) return product.scores;
  return ['demand', 'competition', 'price_stability', 'data_confidence', 'overall_opportunity']
    .map((name) => productScore(product, name))
    .filter((score): score is Score => Boolean(score));
}
