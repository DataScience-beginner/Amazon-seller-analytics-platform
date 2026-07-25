import type {
  CostProfile,
  ConfirmImportRequest,
  CreateCostProfileRequest,
  CreateSupplierOfferRequest,
  CreateTestBuyRequest,
  DashboardResponse,
  DashboardApiResponse,
  CategoryCostEstimateResponse,
  ImportBatch,
  ImportDetailApiResponse,
  ImportListApiResponse,
  ImportListResponse,
  ImportMappingRequest,
  ProductDetail,
  ProductDetailApiResponse,
  ProductListApiResponse,
  ProductListResponse,
  ProductQuery,
  TargetCostAssumptions,
  ProductEconomicsResponse,
  SupplierOffer,
  SupplierOfferListResponse,
  TestBuyRecommendation,
  Workspace,
  WorkspaceCreateRequest,
  WorkspaceListResponse,
} from './contracts';
import {
  normalizeDashboard,
  normalizeImportDetail,
  normalizeImportList,
  normalizeProductDetail,
  normalizeProductList,
} from './normalizers';
import type { HealthResponse } from '../types/health';

const API_ORIGIN = (import.meta.env.VITE_API_BASE_URL ?? '').replace(/\/$/, '');
const API_ROOT = `${API_ORIGIN}/api/v1`;

type ErrorBody = {
  error?: {
    code?: string;
    message?: string;
    details?: unknown;
    correlation_id?: string;
  };
  code?: string;
  message?: string;
  detail?: unknown;
  request_id?: string;
  correlation_id?: string;
};

export class ApiError extends Error {
  readonly status: number;
  readonly code: string;
  readonly details?: unknown;
  readonly requestId?: string;

  constructor(options: {
    message: string;
    status: number;
    code?: string;
    details?: unknown;
    requestId?: string;
  }) {
    super(options.message);
    this.name = 'ApiError';
    this.status = options.status;
    this.code = options.code ?? 'request_failed';
    this.details = options.details;
    this.requestId = options.requestId;
  }
}

function validationMessage(detail: unknown): string | undefined {
  if (typeof detail === 'string') return detail;
  if (!Array.isArray(detail)) return undefined;

  const messages = detail
    .map((item: unknown) => {
      if (!item || typeof item !== 'object') return null;
      const record = item as { loc?: unknown; msg?: unknown };
      if (typeof record.msg !== 'string') return null;
      const location = Array.isArray(record.loc) ? record.loc.slice(1).join('.') : '';
      return location ? `${location}: ${record.msg}` : record.msg;
    })
    .filter((message): message is string => Boolean(message));

  return messages.length > 0 ? messages.join('; ') : undefined;
}

async function parseError(response: Response): Promise<ApiError> {
  let body: ErrorBody = {};
  try {
    body = (await response.json()) as ErrorBody;
  } catch {
    // A proxy may return an empty or non-JSON error response.
  }

  const nested = body.error;
  const message =
    nested?.message ??
    body.message ??
    validationMessage(body.detail) ??
    `Request failed with status ${response.status}`;

  return new ApiError({
    message,
    status: response.status,
    code: nested?.code ?? body.code,
    details: nested?.details ?? body.detail,
    requestId:
      nested?.correlation_id ??
      body.request_id ??
      body.correlation_id ??
      response.headers.get('x-correlation-id') ??
      response.headers.get('x-request-id') ??
      undefined,
  });
}

type RequestOptions = Omit<RequestInit, 'body'> & {
  body?: BodyInit | Record<string, unknown>;
};

export async function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const headers = new Headers(options.headers);
  let body: BodyInit | undefined;

  if (options.body instanceof FormData || typeof options.body === 'string') {
    body = options.body;
  } else if (options.body !== undefined) {
    headers.set('content-type', 'application/json');
    body = JSON.stringify(options.body);
  }

  headers.set('accept', 'application/json');
  const response = await fetch(`${API_ROOT}${path}`, { ...options, body, headers });
  if (!response.ok) throw await parseError(response);
  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}

function queryString(values: Record<string, string | undefined>): string {
  const params = new URLSearchParams();
  Object.entries(values).forEach(([key, value]) => {
    if (value !== undefined && value !== '') params.set(key, value);
  });
  const query = params.toString();
  return query ? `?${query}` : '';
}

export function fetchHealth(signal?: AbortSignal): Promise<HealthResponse> {
  return request<HealthResponse>('/health', { signal });
}

export function fetchWorkspaces(signal?: AbortSignal): Promise<WorkspaceListResponse> {
  return request<WorkspaceListResponse>('/workspaces', { signal });
}

export function createWorkspace(command: WorkspaceCreateRequest): Promise<Workspace> {
  return request<Workspace>('/workspaces', { method: 'POST', body: command });
}

export async function fetchImports(
  organisationId: string,
  marketplaceId: string,
  signal?: AbortSignal,
): Promise<ImportListResponse> {
  const response = await request<ImportListApiResponse>(
    `/imports${queryString({ organisation_id: organisationId, marketplace_id: marketplaceId })}`,
    { signal },
  );
  return normalizeImportList(response);
}

export function uploadImport(options: {
  file: File;
  organisationId: string;
  marketplaceId: string;
}): Promise<ImportBatch> {
  const form = new FormData();
  form.set('file', options.file);
  form.set('organisation_id', options.organisationId);
  form.set('marketplace_id', options.marketplaceId);
  return request<ImportDetailApiResponse>('/imports', { method: 'POST', body: form }).then(
    normalizeImportDetail,
  );
}

export function fetchImport(
  importId: string,
  organisationId: string,
  marketplaceId: string,
  signal?: AbortSignal,
): Promise<ImportBatch> {
  const scope = queryString({
    organisation_id: organisationId,
    marketplace_id: marketplaceId,
  });
  return request<ImportDetailApiResponse>(`/imports/${encodeURIComponent(importId)}${scope}`, {
    signal,
  }).then(normalizeImportDetail);
}

export function updateImportMapping(
  importId: string,
  organisationId: string,
  marketplaceId: string,
  mappings: ImportMappingRequest['mappings'],
): Promise<ImportBatch> {
  const scope = queryString({
    organisation_id: organisationId,
    marketplace_id: marketplaceId,
  });
  return request<ImportDetailApiResponse>(
    `/imports/${encodeURIComponent(importId)}/mapping${scope}`,
    {
      method: 'PUT',
      body: { mappings },
    },
  ).then(normalizeImportDetail);
}

export function confirmImport(
  importId: string,
  organisationId: string,
  marketplaceId: string,
  observedOn: ConfirmImportRequest['observed_on'],
): Promise<ImportBatch> {
  const scope = queryString({
    organisation_id: organisationId,
    marketplace_id: marketplaceId,
  });
  return request<ImportDetailApiResponse>(
    `/imports/${encodeURIComponent(importId)}/confirm${scope}`,
    {
      method: 'POST',
      body: { observed_on: observedOn },
    },
  ).then(normalizeImportDetail);
}

export async function fetchDashboard(
  organisationId: string,
  marketplaceId: string,
  signal?: AbortSignal,
): Promise<DashboardResponse> {
  const response = await request<DashboardApiResponse>(
    `/dashboard${queryString({ organisation_id: organisationId, marketplace_id: marketplaceId })}`,
    { signal },
  );
  return normalizeDashboard(response);
}

export function fetchDatasetOverview(
  organisationId: string,
  marketplaceId: string,
  category: string,
  signal?: AbortSignal,
) {
  return request<NonNullable<DashboardApiResponse['dataset_overview']>>(
    `/dashboard/dataset-overview${queryString({
      organisation_id: organisationId,
      marketplace_id: marketplaceId,
      category,
    })}`,
    { signal },
  );
}

export function fetchCategoryCostEstimate(
  organisationId: string,
  marketplaceId: string,
  subcategory: string,
  assumptions: TargetCostAssumptions,
  signal?: AbortSignal,
) {
  return request<CategoryCostEstimateResponse>(
    `/dashboard/category-cost-estimate${queryString({
      organisation_id: organisationId,
      marketplace_id: marketplaceId,
      subcategory,
      page: '1',
      page_size: '25',
    })}`,
    {
      method: 'POST',
      body: JSON.stringify(assumptions),
      signal,
    },
  );
}

export async function fetchProducts(
  query: ProductQuery,
  signal?: AbortSignal,
): Promise<ProductListResponse> {
  const response = await request<ProductListApiResponse>(`/products${queryString(query)}`, {
    signal,
  });
  return normalizeProductList(response);
}

export function fetchProduct(
  productId: string,
  organisationId: string,
  marketplaceId: string,
  signal?: AbortSignal,
): Promise<ProductDetail> {
  return request<ProductDetailApiResponse>(
    `/products/${encodeURIComponent(productId)}${queryString({ organisation_id: organisationId, marketplace_id: marketplaceId })}`,
    { signal },
  ).then(normalizeProductDetail);
}

export function fetchProductEconomics(
  productId: string,
  organisationId: string,
  marketplaceId: string,
  signal?: AbortSignal,
): Promise<ProductEconomicsResponse> {
  const scope = queryString({
    organisation_id: organisationId,
    marketplace_id: marketplaceId,
  });
  return request<ProductEconomicsResponse>(
    `/products/${encodeURIComponent(productId)}/economics${scope}`,
    { signal },
  );
}

export function createCostProfile(
  organisationId: string,
  marketplaceId: string,
  command: CreateCostProfileRequest,
): Promise<CostProfile> {
  const scope = queryString({
    organisation_id: organisationId,
    marketplace_id: marketplaceId,
  });
  return request<CostProfile>(`/cost-profiles${scope}`, {
    method: 'POST',
    body: command,
  });
}

export function fetchSupplierOffers(
  productId: string,
  organisationId: string,
  marketplaceId: string,
  page: number,
  signal?: AbortSignal,
): Promise<SupplierOfferListResponse> {
  const scope = queryString({
    organisation_id: organisationId,
    marketplace_id: marketplaceId,
    page: String(page),
    page_size: '100',
  });
  return request<SupplierOfferListResponse>(
    `/products/${encodeURIComponent(productId)}/supplier-offers${scope}`,
    { signal },
  );
}

export function createSupplierOffer(
  organisationId: string,
  marketplaceId: string,
  command: CreateSupplierOfferRequest,
): Promise<SupplierOffer> {
  const scope = queryString({
    organisation_id: organisationId,
    marketplace_id: marketplaceId,
  });
  return request<SupplierOffer>(`/supplier-offers${scope}`, {
    method: 'POST',
    body: command,
  });
}

export function createTestBuyRecommendation(
  productId: string,
  organisationId: string,
  marketplaceId: string,
  command: CreateTestBuyRequest,
): Promise<TestBuyRecommendation> {
  const scope = queryString({
    organisation_id: organisationId,
    marketplace_id: marketplaceId,
  });
  return request<TestBuyRecommendation>(
    `/products/${encodeURIComponent(productId)}/test-buy-scenarios${scope}`,
    { method: 'POST', body: command },
  );
}
