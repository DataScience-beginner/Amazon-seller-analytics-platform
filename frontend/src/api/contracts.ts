export type Marketplace = {
  id: string;
  code: string;
  name: string;
  default_currency_code: string;
};

export type Workspace = {
  organisation_id: string;
  organisation_name: string;
  marketplaces: Marketplace[];
};

export type WorkspaceListResponse = {
  items: Workspace[];
};

export type WorkspaceCreateRequest = {
  organisation_name: string;
  marketplace_code: string;
  marketplace_name: string;
  currency_code: string;
};

export type ImportStatus = 'pending' | 'completed' | 'failed';

export type ColumnClassification = 'required' | 'optional' | 'unknown' | 'missing' | 'ambiguous';

export type ImportColumnMapping = {
  ordinal: number;
  header: string;
  normalized_header?: string;
  canonical_field?: string | null;
  classification: ColumnClassification;
  candidates?: string[];
  required_candidates?: string[];
  samples?: unknown[];
  explicitly_resolved?: boolean;
  reason_code?: string;
};

export type ImportMappingReport = {
  registry_id?: string;
  registry_version?: string;
  columns: ImportColumnMapping[];
  missing?: string[];
  required?: string[];
  optional?: string[];
  unknown?: string[];
  ambiguous?: string[];
  requires_confirmation?: boolean;
};

export type ImportDetailApiResponse = {
  id: string;
  organisation_id: string;
  marketplace_id: string;
  original_filename: string;
  checksum: string;
  status: ImportStatus;
  uploaded_at: string;
  confirmed_at: string | null;
  completed_at: string | null;
  workbook: {
    sheet_name: string | null;
    header_row_number: number | null;
    alias_registry_version: string | null;
  };
  mapping: {
    registry_id: string;
    registry_version: string;
    columns: Array<
      ImportColumnMapping & {
        is_required: boolean;
      }
    >;
    missing_required: string[];
    missing_optional: string[];
    requires_confirmation: boolean;
  };
  preview_rows: Array<{
    row_number: number;
    values: Record<string, unknown>;
    issues: Array<Record<string, unknown>>;
  }>;
  summary: (ImportSummary & { total: number; row_error_count: number }) | null;
  failure: { code: string; message: string } | null;
  duplicate: boolean;
};

export type ImportListApiResponse = {
  items: Array<{
    id: string;
    original_filename: string;
    status: ImportStatus;
    uploaded_at: string;
    completed_at: string | null;
    summary: (ImportSummary & { total: number; row_error_count: number }) | null;
  }>;
};

export type ImportSummary = {
  created: number;
  matched: number;
  skipped: number;
  failed: number;
  snapshots_created?: number;
};

export type ImportBatch = {
  id: string;
  organisation_id?: string;
  marketplace_id?: string;
  original_filename?: string;
  filename?: string;
  checksum_sha256?: string;
  status: ImportStatus;
  created_at?: string;
  uploaded_at?: string;
  completed_at?: string | null;
  row_count?: number;
  column_count?: number;
  selected_sheet?: string;
  sheet_names?: string[];
  header_row?: number;
  mapping?: ImportMappingReport;
  columns?: ImportColumnMapping[];
  preview_rows?: Array<Record<string, unknown>>;
  summary?: ImportSummary;
  error_message?: string | null;
  duplicate?: boolean;
};

export type ImportListResponse = {
  items: ImportBatch[];
  total?: number;
};

export type ImportMappingRequest = {
  mappings: Record<string, string | null>;
};

export type ScoreName =
  'demand' | 'competition' | 'price_stability' | 'data_confidence' | 'overall_opportunity' | string;

export type Score = {
  name: ScoreName;
  label?: string;
  value: number;
  formula_version?: string;
  reason_codes?: string[];
  inputs?: Record<string, unknown>;
};

export type Recommendation = {
  strategy: string;
  label?: string;
  confidence?: number;
  formula_version?: string;
  reason_codes?: string[];
  positive_signals?: string[];
  warnings?: string[];
  missing_data?: string[];
};

export type MoneyValue = {
  amount: number | string;
  currency_code: string | null;
};

export type ProductSummary = {
  id: string;
  asin: string;
  title: string | null;
  brand?: string | null;
  category?: string | null;
  image_url?: string | null;
  amazon_url?: string | null;
  strategy?: string;
  recommendation?: Recommendation;
  scores?: Score[];
  overall_score?: number;
  demand_score?: number;
  competition_score?: number;
  price_stability_score?: number;
  confidence_score?: number;
  offer_count?: number | null;
  buy_box_price?: MoneyValue | number | string | null;
  latest_snapshot_at?: string | null;
};

export type ProductListResponse = {
  items: ProductSummary[];
  total: number;
  page: number;
  page_size: number;
  total_pages?: number;
  available_filters?: {
    strategies?: string[];
    categories?: string[];
  };
};

export type PortfolioScope = {
  organisation_id: string;
  marketplace_id: string;
};

export type ProductListItemResponse = {
  product_id: string;
  asin: string;
  title: string | null;
  brand: string | null;
  category: string | null;
  subcategory: string | null;
  image_url: string | null;
  amazon_url: string | null;
  latest_snapshot_id: string | null;
  latest_snapshot_at: string | null;
  buy_box_price: string | null;
  currency_code: string | null;
  offer_count: number | null;
  overall_opportunity_score: number | null;
  data_confidence_score: number | null;
  strategy: string | null;
  recommendation_confidence: number | null;
  score_formula_version: string | null;
  strategy_rules_version: string | null;
  data_quality_codes: string[];
};

export type ProductListApiResponse = {
  scope: PortfolioScope;
  items: ProductListItemResponse[];
  pagination: {
    page: number;
    page_size: number;
    total_items: number;
    total_pages: number;
    has_previous: boolean;
    has_next: boolean;
  };
  query: Omit<ProductQuery, 'organisation_id' | 'marketplace_id'>;
};

export type RecommendationEvidenceResponse = {
  reason_code: string;
  polarity: 'positive' | 'negative' | 'informational';
  source: string;
  signal: string;
  observed_value: unknown;
  comparison: string | null;
  threshold_value: unknown;
  threshold_upper_value: unknown;
  statement: string;
};

export type ScoreResponse = {
  id: string;
  name: string;
  value: number;
  formula_version: string;
  configuration_checksum: string;
  inputs: Record<string, unknown>;
  reason_codes: string[];
  calculated_at: string;
};

export type RecommendationResponse = {
  id: string;
  strategy: string;
  rules_version: string;
  configuration_checksum: string;
  confidence: number;
  evidence: RecommendationEvidenceResponse[];
  calculated_at: string;
};

export type ProductSnapshotResponse = {
  id: string;
  import_batch_id: string | null;
  snapshot_kind: string;
  snapshot_at: string;
  metrics: Record<string, unknown>;
  scores: ScoreResponse[];
  recommendation: RecommendationResponse | null;
};

export type ProductDetailApiResponse = {
  scope: PortfolioScope;
  product: {
    product_id: string;
    asin: string;
    title: string | null;
    brand: string | null;
    category: string | null;
    subcategory: string | null;
    image_url: string | null;
    amazon_url: string | null;
    created_at: string;
  };
  latest_snapshot: ProductSnapshotResponse | null;
  notices: Array<{
    code: string;
    severity: string;
    field: string | null;
    message: string;
  }>;
  snapshot_history: ProductSnapshotResponse[];
  strategy_history: Array<{
    snapshot_id: string;
    snapshot_at: string;
    strategy: string;
    confidence: number;
    rules_version: string;
    evidence: RecommendationEvidenceResponse[];
  }>;
};

export type Snapshot = {
  id: string;
  captured_at?: string;
  snapshot_at?: string;
  metrics?: Record<string, unknown>;
  scores?: Score[];
  recommendation?: Recommendation;
};

export type ProductDetail = ProductSummary & {
  marketplace_code?: string;
  latest_metrics?: Record<string, unknown>;
  metrics?: Record<string, unknown>;
  snapshots?: Snapshot[];
  score_history?: Score[];
  raw_attributes?: Record<string, unknown>;
};

export type DashboardKpis = {
  tracked_products: number;
  data_quality_alerts: number;
  average_opportunity_score?: number | null;
  classified_products?: number;
  low_confidence_products?: number;
};

export type LatestImportSummary = {
  id: string;
  filename: string;
  status: ImportStatus;
  uploaded_at?: string;
  completed_at?: string | null;
};

export type StrategyDistributionItem = {
  strategy: string;
  count: number;
};

export type DataQualityAlert = {
  code: string;
  message: string;
  count?: number;
  severity?: 'info' | 'warning' | 'critical' | string;
};

export type DashboardResponse = {
  kpis: DashboardKpis;
  latest_import?: LatestImportSummary | null;
  strategy_distribution: StrategyDistributionItem[];
  data_quality_alerts?: DataQualityAlert[];
  top_opportunities: ProductSummary[];
  top_risks: ProductSummary[];
  definitions?: Record<string, string>;
};

export type DashboardApiResponse = {
  scope: PortfolioScope;
  tracked_product_count: number;
  kpis: Array<{
    id: string;
    label: string;
    value: number | string | null;
    unit: string | null;
    definition: string;
  }>;
  latest_import: {
    id: string;
    original_filename: string;
    status: ImportStatus;
    uploaded_at: string;
    completed_at: string | null;
    total_rows: number;
    created_rows: number;
    matched_rows: number;
    skipped_rows: number;
    failed_rows: number;
  } | null;
  strategy_distribution: StrategyDistributionItem[];
  data_quality_alerts: Array<{
    id: string;
    severity: 'warning' | 'error';
    count: number;
    title: string;
    description: string;
  }>;
  top_opportunities: ProductListItemResponse[];
  top_risks: Array<{
    product: ProductListItemResponse;
    reason_codes: string[];
  }>;
  empty_state: {
    code: 'upload_required';
    title: string;
    message: string;
    primary_action: 'open_imports';
  } | null;
};

export type ProductQuery = {
  organisation_id: string;
  marketplace_id: string;
  search?: string;
  strategy?: string;
  category?: string;
  min_score?: string;
  max_score?: string;
  min_offer_count?: string;
  max_offer_count?: string;
  min_price?: string;
  max_price?: string;
  min_confidence?: string;
  max_confidence?: string;
  sort_by?: string;
  sort_direction?: string;
  page?: string;
  page_size?: string;
};

export type EvidenceLabel =
  'observed' | 'calculated' | 'estimated' | 'recommended' | 'user_confirmed';

export type SellingPriceTaxBasis = 'tax_inclusive' | 'tax_exclusive';

export type CostInputs = {
  purchase_cost: string;
  gst_rate_percent: string;
  gst_recoverable_percent: string;
  freight_cost: string;
  prep_cost: string;
  packaging_cost: string;
  advertising_rate_percent: string;
  returns_rate_percent: string;
  overhead_cost: string;
  referral_fee_rate_percent: string | null;
  fulfilment_fee: string | null;
  closing_fee: string | null;
  storage_fee: string | null;
  minimum_margin_percent: string;
  target_margin_percent: string;
};

export type CostProfile = CostInputs & {
  id: string;
  organisation_id: string;
  marketplace_id: string;
  product_id: string | null;
  scope: 'product' | 'marketplace_default';
  currency_code: string;
  effective_from: string;
  effective_to: string | null;
  version: number;
  supersedes_profile_id: string | null;
  configuration_checksum: string;
  fee_source: string | null;
  fee_effective_at: string | null;
  fee_status: 'observed' | 'estimated' | 'user_confirmed' | null;
  created_at: string;
  evidence_label: 'user_confirmed';
  selling_price_tax_basis: SellingPriceTaxBasis | null;
};

export type CreateCostProfileRequest = CostInputs & {
  product_id: string | null;
  currency_code: string;
  effective_from: string;
  fee_source: string | null;
  fee_effective_at: string | null;
  fee_status: 'observed' | 'estimated' | 'user_confirmed' | null;
  selling_price_tax_basis: SellingPriceTaxBasis;
};

export type UnitEconomics = {
  formula_version: string;
  configuration_checksum: string;
  status: 'calculated' | 'partial';
  decision_label: 'calculated';
  selling_price_tax_basis: SellingPriceTaxBasis | null;
  inputs: Record<string, string | null>;
  formulas: Record<string, string>;
  outputs: {
    landed_cost: string;
    net_revenue: string | null;
    output_gst: string | null;
    amazon_fees: string | null;
    contribution_profit: string | null;
    margin_percent: string | null;
    roi_percent: string | null;
    break_even_price: string | null;
    minimum_acceptable_price: string | null;
    target_price: string | null;
  };
  reason_codes: string[];
  fee_evidence: {
    status: 'observed' | 'estimated' | 'user_confirmed' | null;
    source: string | null;
    effective_at: string | null;
  };
};

export type ProductEconomicsResponse = {
  scope: PortfolioScope;
  product: {
    product_id: string;
    asin: string;
    title: string | null;
  };
  observed_price: {
    amount: string;
    currency_code: string;
    evidence_label: 'observed';
    source: 'keepa_import';
    source_at: string;
  } | null;
  currency_code: string;
  profile_source: 'product' | 'marketplace_default' | null;
  active_profile: CostProfile | null;
  profiles_by_scope: {
    product: CostProfile | null;
    marketplace_default: CostProfile | null;
  };
  profile_history: CostProfile[];
  calculation: UnitEconomics | null;
  notices: Array<{
    code: string;
    severity: 'missing' | 'warning';
    message: string;
    evidence_label: 'observed' | 'calculated' | 'estimated' | 'user_confirmed';
  }>;
  audit_history: Array<{
    id: string;
    event_type: string;
    profile_id: string;
    profile_version: number;
    occurred_at: string;
  }>;
};

export type SupplierPriceTier = {
  minimum_quantity: number;
  unit_cost: string;
};

export type SupplierOffer = {
  id: string;
  product_id: string;
  supplier: {
    id: string;
    name: string;
  };
  currency_code: string;
  minimum_order_quantity: number;
  unit_cost: string;
  lead_time_days: number;
  quotation_date: string;
  valid_until: string | null;
  notes: string | null;
  price_tiers: SupplierPriceTier[];
  created_at: string;
  evidence_label: 'user_confirmed';
};

export type SupplierOfferListResponse = {
  scope: PortfolioScope;
  product: {
    product_id: string;
    asin: string;
    title: string | null;
  };
  items: SupplierOffer[];
  pagination: {
    page: number;
    page_size: number;
    total_items: number;
    total_pages: number;
    has_previous: boolean;
    has_next: boolean;
  };
  comparison_dimensions: Array<'unit_cost' | 'minimum_order_quantity' | 'lead_time_days'>;
  selection_note: string;
};

export type CreateSupplierOfferRequest = {
  product_id: string;
  supplier_name: string;
  currency_code: string;
  minimum_order_quantity: number;
  unit_cost: string;
  lead_time_days: number;
  quotation_date: string;
  valid_until: string | null;
  notes: string | null;
  price_tiers: SupplierPriceTier[];
};

export type TestBuyScenarioName = 'conservative' | 'expected' | 'aggressive';

export type TestBuyScenario = {
  scenario: TestBuyScenarioName;
  quantity: number;
  unit_cost: string | null;
  required_investment: string;
  expected_sell_through_days: string | null;
  status: 'recommended' | 'blocked';
  reason_codes: string[];
};

export type TestBuyRecommendation = {
  id: string;
  scope: PortfolioScope;
  product: {
    product_id: string;
    asin: string;
    title: string | null;
  };
  formula_version: string;
  configuration_checksum: string;
  created_at: string;
  advisory_only: true;
  outcome: 'recommended' | 'blocked';
  decision_label: 'recommended' | null;
  supplier_offer_id: string;
  budget_amount: string;
  budget_currency_code: string;
  inputs: Record<string, string | number | null>;
  evidence: {
    source_snapshot_id: string | null;
    monthly_demand_units: number | null;
    monthly_demand_label: 'estimated' | null;
    monthly_demand_source: 'keepa_monthly_sold' | null;
    market_snapshot_at: string | null;
    data_confidence_score_result_id: string | null;
    data_confidence_score: number | null;
    data_confidence_label: 'calculated' | null;
    data_confidence_formula_version: string | null;
    supplier_offer_label: 'user_confirmed';
    budget_label: 'user_confirmed';
  };
  scenarios: TestBuyScenario[];
  notices: Array<{
    code: string;
    severity: 'missing' | 'warning';
    message: string;
    evidence_label: 'estimated' | 'calculated' | 'recommended' | 'user_confirmed';
  }>;
};

export type CreateTestBuyRequest = {
  supplier_offer_id: string;
  budget_amount: string;
  budget_currency_code: string;
};
