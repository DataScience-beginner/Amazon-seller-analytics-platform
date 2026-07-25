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

export type DatasetColumnClassification = 'registered_source' | 'unrecognized';

export type ImportColumnMapping = {
  ordinal: number;
  header: string;
  normalized_header?: string;
  canonical_field?: string | null;
  classification: ColumnClassification;
  dataset_classification: DatasetColumnClassification;
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

export type ImportDatasetMetadata = {
  schema_id: string | null;
  schema_version: string | null;
  schema_match: string;
  source_column_count: number;
  registered_column_count: number;
  matched_column_count: number;
  new_headers: string[];
  missing_headers: string[];
  source_header_checksum: string | null;
  dataset_schema_checksum: string;
  observed_on: string | null;
  period_month: string | null;
  revision: number | null;
  date_status: 'pending_confirmation' | 'confirmed' | 'legacy_unconfirmed';
  observed_on_suggestion: string | null;
  suggestion_source: string | null;
  observation_date_candidates: Array<{
    date: string;
    source: string;
  }>;
  observed_on_source: string | null;
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
  dataset: ImportDatasetMetadata;
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
    observed_on: string | null;
    period_month: string | null;
    revision: number | null;
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
  confirmed_at?: string | null;
  completed_at?: string | null;
  observed_on?: string | null;
  period_month?: string | null;
  revision?: number | null;
  row_count?: number;
  column_count?: number;
  selected_sheet?: string;
  sheet_names?: string[];
  header_row?: number;
  dataset?: ImportDatasetMetadata;
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

export type ConfirmImportRequest = {
  observed_on: string;
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

export type ResearchStatus =
  'priority_research' | 'promising' | 'monitor' | 'insufficient_evidence' | 'avoid';

export type BrandClassification = 'declared_brand' | 'likely_generic' | 'unknown';

export type ResearchAssessment = {
  status: ResearchStatus;
  brand_classification: BrandClassification;
  policy_version: string;
  configuration_checksum: string;
  reason_codes: string[];
  positive_signals: string[];
  risk_signals: string[];
  missing_evidence: string[];
};

export type ResearchScreen = {
  id:
    | 'priority_research'
    | 'promising'
    | 'low_competition'
    | 'stable_pricing'
    | 'needs_evidence'
    | 'all';
  label: string;
  description: string;
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
  buy_box_price_90d?: MoneyValue | number | string | null;
  sales_rank?: number | null;
  sales_rank_90d?: number | null;
  estimated_monthly_bought?: number | null;
  buy_box_winner_count_90d?: number | null;
  buy_box_oos_percentage_90d?: number | string | null;
  research?: ResearchAssessment | null;
  latest_snapshot_at?: string | null;
  latest_observed_on?: string | null;
};

export type ProductListResponse = {
  items: ProductSummary[];
  total: number;
  page: number;
  page_size: number;
  total_pages?: number;
  research_policy_version?: string;
  research_configuration_checksum?: string;
  screens?: ResearchScreen[];
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
  latest_observed_on: string | null;
  buy_box_price: string | null;
  buy_box_price_90d: string | null;
  currency_code: string | null;
  offer_count: number | null;
  sales_rank: number | null;
  sales_rank_90d: number | null;
  estimated_monthly_bought: number | null;
  buy_box_winner_count_90d: number | null;
  buy_box_oos_percentage_90d: string | null;
  demand_score: number | null;
  competition_score: number | null;
  price_stability_score: number | null;
  overall_opportunity_score: number | null;
  data_confidence_score: number | null;
  strategy: string | null;
  recommendation_confidence: number | null;
  score_formula_version: string | null;
  strategy_rules_version: string | null;
  research: ResearchAssessment | null;
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
  research_policy_version: string;
  research_configuration_checksum: string;
  screens: ResearchScreen[];
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
  observed_on?: string | null;
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
  research: ResearchAssessment | null;
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
    observed_on: string | null;
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
  observed_on?: string | null;
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
  observed_on?: string | null;
  period_month?: string | null;
  revision?: number | null;
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

export type DatasetOverview = {
  readiness: 'revenue_ready' | 'relative_research_only' | 'insufficient_evidence';
  readiness_title: string;
  readiness_message: string;
  product_count: number;
  category_count: number;
  subcategory_count: number;
  brand_count: number;
  monthly_demand_coverage_percentage: number | string;
  revenue_coverage_percentage: number | string;
  estimated_monthly_units: number | null;
  estimated_monthly_revenue: number | string | null;
  currency_code: string | null;
  coverage: Array<{
    id: string;
    label: string;
    populated_products: number;
    total_products: number;
    coverage_percentage: number | string;
  }>;
  top_categories: Array<DatasetDistribution>;
  top_subcategories: Array<DatasetDistribution>;
  top_brands: Array<DatasetDistribution>;
  conclusion_codes: string[];
};

export type DatasetDistribution = {
  label: string;
  product_count: number;
  product_percentage: number | string;
};

export type DashboardResponse = {
  kpis: DashboardKpis;
  latest_import?: LatestImportSummary | null;
  strategy_distribution: StrategyDistributionItem[];
  data_quality_alerts?: DataQualityAlert[];
  top_opportunities: ProductSummary[];
  top_risks: ProductSummary[];
  dataset_overview?: DatasetOverview | null;
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
    observed_on: string | null;
    period_month: string | null;
    revision: number | null;
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
  dataset_overview: DatasetOverview | null;
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
  import_batch_id?: string;
  search?: string;
  screen?: string;
  brand_classification?: string;
  strategy?: string;
  category?: string;
  subcategory?: string;
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

export type TargetCostAssumptions = {
  gst_rate_percent: string;
  amazon_fee_percent: string;
  shipping_percent: string;
  advertising_percent: string;
  returns_percent: string;
  target_profit_percent: string;
};

export type CategoryCostEstimateResponse = {
  subcategory: string;
  formula_version: string;
  configuration_checksum: string;
  assumptions: TargetCostAssumptions;
  items: Array<{
    product_id: string;
    asin: string;
    title: string | null;
    brand: string | null;
    currency_code: string | null;
    selling_price: string | null;
    selling_price_source: 'buy_box_90d_average' | 'current_buy_box' | 'unavailable';
    maximum_wholesale_cost_ex_gst: string | null;
    wholesale_cash_outlay_including_gst: string | null;
    target_profit: string | null;
    amazon_fee: string | null;
    shipping_allowance: string | null;
    advertising_allowance: string | null;
    returns_allowance: string | null;
    feasible: boolean;
  }>;
  pagination: {
    page: number;
    page_size: number;
    total_items: number;
    total_pages: number;
    has_previous: boolean;
    has_next: boolean;
  };
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
    observed_on: string | null;
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
    market_observed_on: string | null;
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
