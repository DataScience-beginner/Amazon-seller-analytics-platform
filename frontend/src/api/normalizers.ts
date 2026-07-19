import type {
  DashboardApiResponse,
  DashboardResponse,
  ImportBatch,
  ImportDetailApiResponse,
  ImportListApiResponse,
  ImportListResponse,
  ProductDetail,
  ProductDetailApiResponse,
  ProductListApiResponse,
  ProductListResponse,
  ProductListItemResponse,
  ProductSnapshotResponse,
  ProductSummary,
  Recommendation,
  RecommendationEvidenceResponse,
  RecommendationResponse,
  Score,
  Snapshot,
} from './contracts';

export function normalizeImportDetail(response: ImportDetailApiResponse): ImportBatch {
  return {
    id: response.id,
    organisation_id: response.organisation_id,
    marketplace_id: response.marketplace_id,
    original_filename: response.original_filename,
    checksum_sha256: response.checksum,
    status: response.status,
    duplicate: response.duplicate,
    uploaded_at: response.uploaded_at,
    completed_at: response.completed_at,
    row_count: response.summary?.total,
    column_count: response.mapping.columns.length,
    selected_sheet: response.workbook.sheet_name ?? undefined,
    header_row: response.workbook.header_row_number ?? undefined,
    mapping: {
      registry_id: response.mapping.registry_id,
      registry_version: response.mapping.registry_version,
      columns: response.mapping.columns,
      missing: response.mapping.missing_required,
      required: response.mapping.missing_required,
      optional: response.mapping.missing_optional,
      requires_confirmation: response.mapping.requires_confirmation,
    },
    preview_rows: response.preview_rows.map((row) => ({
      'Source row': row.row_number,
      ...row.values,
    })),
    summary: response.summary ?? undefined,
    error_message: response.failure?.message ?? null,
  };
}

export function normalizeImportList(response: ImportListApiResponse): ImportListResponse {
  return {
    items: response.items.map((item) => ({
      id: item.id,
      original_filename: item.original_filename,
      status: item.status,
      uploaded_at: item.uploaded_at,
      completed_at: item.completed_at,
      row_count: item.summary?.total,
      summary: item.summary ?? undefined,
    })),
  };
}

function score(response: {
  name: string;
  value: number;
  formula_version?: string | null;
  reason_codes?: string[];
  inputs?: Record<string, unknown>;
}): Score {
  return {
    name: response.name,
    value: response.value,
    formula_version: response.formula_version ?? undefined,
    reason_codes: response.reason_codes,
    inputs: response.inputs,
  };
}

function evidenceByPolarity(
  evidence: RecommendationEvidenceResponse[],
  polarity: 'positive' | 'negative',
): string[] {
  return evidence
    .filter((item) => item.polarity === polarity)
    .map((item) => item.statement)
    .filter(Boolean);
}

function recommendation(response: RecommendationResponse | null): Recommendation | undefined {
  if (!response) return undefined;
  return {
    strategy: response.strategy,
    confidence: response.confidence,
    formula_version: response.rules_version,
    reason_codes: response.evidence.map((item) => item.reason_code),
    positive_signals: evidenceByPolarity(response.evidence, 'positive'),
    warnings: evidenceByPolarity(response.evidence, 'negative'),
  };
}

function snapshot(response: ProductSnapshotResponse): Snapshot {
  return {
    id: response.id,
    snapshot_at: response.snapshot_at,
    metrics: response.metrics,
    scores: response.scores.map(score),
    recommendation: recommendation(response.recommendation),
  };
}

export function normalizeProductSummary(item: ProductListItemResponse): ProductSummary {
  const scores: Score[] = [];
  if (item.overall_opportunity_score !== null) {
    scores.push(
      score({
        name: 'overall_opportunity',
        value: item.overall_opportunity_score,
        formula_version: item.score_formula_version,
      }),
    );
  }
  if (item.data_confidence_score !== null) {
    scores.push(
      score({
        name: 'data_confidence',
        value: item.data_confidence_score,
        formula_version: item.score_formula_version,
        reason_codes: item.data_quality_codes,
      }),
    );
  }
  return {
    id: item.product_id,
    asin: item.asin,
    title: item.title ?? 'Untitled product',
    brand: item.brand,
    category: item.category,
    image_url: item.image_url,
    amazon_url: item.amazon_url,
    strategy: item.strategy ?? undefined,
    recommendation: item.strategy
      ? {
          strategy: item.strategy,
          confidence: item.recommendation_confidence ?? undefined,
          formula_version: item.strategy_rules_version ?? undefined,
          missing_data: item.data_quality_codes,
        }
      : undefined,
    scores,
    offer_count: item.offer_count,
    buy_box_price:
      item.buy_box_price !== null
        ? { amount: item.buy_box_price, currency_code: item.currency_code }
        : null,
    latest_snapshot_at: item.latest_snapshot_at,
  };
}

export function normalizeProductList(response: ProductListApiResponse): ProductListResponse {
  const items = response.items.map(normalizeProductSummary);
  return {
    items,
    total: response.pagination.total_items,
    page: response.pagination.page,
    page_size: response.pagination.page_size,
    total_pages: response.pagination.total_pages,
  };
}

function numericKpi(response: DashboardApiResponse, id: string): number | undefined {
  const raw = response.kpis.find((item) => item.id === id)?.value;
  if (raw === null || raw === undefined || raw === '') return undefined;
  const value = Number(raw);
  return Number.isFinite(value) ? value : undefined;
}

export function normalizeDashboard(response: DashboardApiResponse): DashboardResponse {
  return {
    kpis: {
      tracked_products: response.tracked_product_count,
      data_quality_alerts: response.data_quality_alerts.reduce(
        (total, alert) => total + alert.count,
        0,
      ),
      average_opportunity_score: numericKpi(response, 'average_opportunity_score'),
      classified_products: numericKpi(response, 'classified_products'),
      low_confidence_products: numericKpi(response, 'low_confidence_products'),
    },
    latest_import: response.latest_import
      ? {
          id: response.latest_import.id,
          filename: response.latest_import.original_filename,
          status: response.latest_import.status,
          uploaded_at: response.latest_import.uploaded_at,
          completed_at: response.latest_import.completed_at,
        }
      : null,
    strategy_distribution: response.strategy_distribution,
    data_quality_alerts: response.data_quality_alerts.map((alert) => ({
      code: alert.id,
      severity: alert.severity === 'error' ? 'critical' : 'warning',
      count: alert.count,
      message: `${alert.title}: ${alert.description}`,
    })),
    top_opportunities: response.top_opportunities.map(normalizeProductSummary),
    top_risks: response.top_risks.map((risk) => {
      const product = normalizeProductSummary(risk.product);
      if (product.recommendation) product.recommendation.reason_codes = risk.reason_codes;
      return product;
    }),
    definitions: Object.fromEntries(response.kpis.map((item) => [item.id, item.definition])),
  };
}

export function normalizeProductDetail(response: ProductDetailApiResponse): ProductDetail {
  const latest = response.latest_snapshot;
  const currentRecommendation = recommendation(latest?.recommendation ?? null);
  if (currentRecommendation) {
    currentRecommendation.missing_data = response.notices.map((notice) => notice.message);
  }
  const offerCount = latest?.metrics.total_offer_count ?? latest?.metrics.new_offer_count;
  const currencyCode = latest?.metrics.currency_code;
  const price = latest?.metrics.buy_box_price;

  return {
    id: response.product.product_id,
    asin: response.product.asin,
    title: response.product.title ?? 'Untitled product',
    brand: response.product.brand,
    category: response.product.subcategory ?? response.product.category,
    image_url: response.product.image_url,
    amazon_url: response.product.amazon_url,
    latest_snapshot_at: latest?.snapshot_at ?? null,
    strategy: currentRecommendation?.strategy,
    recommendation: currentRecommendation,
    scores: latest?.scores.map(score) ?? [],
    offer_count: typeof offerCount === 'number' ? offerCount : Number(offerCount) || null,
    buy_box_price:
      price !== undefined && price !== null
        ? {
            amount: typeof price === 'string' || typeof price === 'number' ? price : String(price),
            currency_code: typeof currencyCode === 'string' ? currencyCode : null,
          }
        : null,
    latest_metrics: latest?.metrics ?? {},
    snapshots: response.snapshot_history.map(snapshot),
  };
}
