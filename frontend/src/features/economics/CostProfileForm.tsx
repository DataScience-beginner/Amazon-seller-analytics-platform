import { useEffect, useState, type FormEvent } from 'react';

import type {
  CostProfile,
  CostInputs,
  CreateCostProfileRequest,
  ProductEconomicsResponse,
  SellingPriceTaxBasis,
} from '../../api/contracts';
import { ApiError } from '../../api/client';
import { FormFieldError } from './FormFieldError';
import {
  costProfileWindowStatus,
  latestScopedRevision,
  type CostProfileTarget,
} from './profileModel';
import { validateCostProfile, type FieldErrors } from './validation';

const zeroInputs: CostInputs = {
  purchase_cost: '',
  gst_rate_percent: '0',
  gst_recoverable_percent: '0',
  freight_cost: '0',
  prep_cost: '0',
  packaging_cost: '0',
  advertising_rate_percent: '0',
  returns_rate_percent: '0',
  overhead_cost: '0',
  referral_fee_rate_percent: null,
  fulfilment_fee: null,
  closing_fee: null,
  storage_fee: null,
  minimum_margin_percent: '0',
  target_margin_percent: '0',
};

type SubmissionState =
  | { status: 'idle'; message: null }
  | { status: 'submitting'; message: null }
  | { status: 'success'; message: string }
  | { status: 'error'; message: string; requestId?: string };

function inputValue(form: FormData, name: keyof CostInputs): string {
  return String(form.get(name) ?? '').trim();
}

function optionalInputValue(form: FormData, name: keyof CostInputs): string | null {
  const value = String(form.get(name) ?? '').trim();
  return value || null;
}

function utcDate(value: string): string {
  return `${value}T00:00:00Z`;
}

function explicitUtcTimestamp(value: string): string {
  const timestamp = new Date(value);
  return Number.isNaN(timestamp.getTime()) ? value : timestamp.toISOString();
}

function localDateTimeValue(timestamp: number): string {
  const date = new Date(timestamp);
  const part = (value: number) => String(value).padStart(2, '0');
  return `${date.getFullYear()}-${part(date.getMonth() + 1)}-${part(date.getDate())}T${part(
    date.getHours(),
  )}:${part(date.getMinutes())}:${part(date.getSeconds())}`;
}

function numericField({
  name,
  label,
  defaultValue,
  errors,
  suffix,
  help,
  required = true,
}: {
  name: keyof CostInputs;
  label: string;
  defaultValue: string | null;
  errors: FieldErrors;
  suffix?: string;
  help?: string;
  required?: boolean;
}) {
  const errorId = `${name}-error`;
  const helpId = `${name}-help`;
  return (
    <div className="field">
      <label htmlFor={`cost-${name}`}>
        {label}
        {suffix ? ` (${suffix})` : ''}
      </label>
      <input
        id={`cost-${name}`}
        name={name}
        type="number"
        min="0"
        max={suffix === '%' ? '100' : undefined}
        step="0.0001"
        inputMode="decimal"
        required={required}
        defaultValue={defaultValue ?? ''}
        aria-invalid={Boolean(errors[name])}
        aria-describedby={
          [help ? helpId : null, errors[name] ? errorId : null].filter(Boolean).join(' ') ||
          undefined
        }
      />
      {help && <small id={helpId}>{help}</small>}
      <FormFieldError id={errorId} message={errors[name]} />
    </div>
  );
}

export function CostProfileForm({
  productId,
  currencyCode,
  profilesByScope,
  history,
  onCreate,
}: {
  productId: string;
  currencyCode: string;
  profilesByScope: ProductEconomicsResponse['profiles_by_scope'];
  history: CostProfile[];
  onCreate: (command: CreateCostProfileRequest) => Promise<void>;
}) {
  const [profileTarget, setProfileTarget] = useState<CostProfileTarget>('product');
  const [errors, setErrors] = useState<FieldErrors>({});
  const [submission, setSubmission] = useState<SubmissionState>({
    status: 'idle',
    message: null,
  });

  const latestProfiles = {
    product: latestScopedRevision(history, 'product', productId, profilesByScope.product),
    marketplace_default: latestScopedRevision(
      history,
      'marketplace_default',
      productId,
      profilesByScope.marketplace_default,
    ),
  };

  useEffect(() => {
    setProfileTarget('product');
    setErrors({});
    setSubmission({ status: 'idle', message: null });
  }, [productId]);

  useEffect(() => {
    setErrors({});
    setSubmission({ status: 'idle', message: null });
  }, [latestProfiles.marketplace_default?.id, latestProfiles.product?.id]);

  const matchingProfile = latestProfiles[profileTarget];
  const hasAnyProfile = Boolean(latestProfiles.product || latestProfiles.marketplace_default);
  const defaults = matchingProfile ?? zeroInputs;
  const matchingEffectiveTime = matchingProfile
    ? Date.parse(matchingProfile.effective_from)
    : Number.NaN;
  const earliestRevisionTime = Number.isNaN(matchingEffectiveTime)
    ? Date.now()
    : matchingEffectiveTime + 1_000;
  const effectiveFromDefault = localDateTimeValue(Math.max(Date.now(), earliestRevisionTime));

  function selectProfileTarget(target: CostProfileTarget) {
    setProfileTarget(target);
    setErrors({});
    setSubmission({ status: 'idle', message: null });
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    const command: CreateCostProfileRequest = {
      product_id: profileTarget === 'product' ? productId : null,
      currency_code: String(form.get('currency_code') ?? '')
        .trim()
        .toUpperCase(),
      effective_from: explicitUtcTimestamp(String(form.get('effective_from') ?? '')),
      fee_source: String(form.get('fee_source') ?? '').trim() || null,
      fee_effective_at: form.get('fee_effective_at')
        ? utcDate(String(form.get('fee_effective_at')))
        : null,
      fee_status:
        (String(form.get('fee_status') ?? '') as CreateCostProfileRequest['fee_status']) || null,
      selling_price_tax_basis: String(
        form.get('selling_price_tax_basis') ?? '',
      ) as SellingPriceTaxBasis,
      purchase_cost: inputValue(form, 'purchase_cost'),
      gst_rate_percent: inputValue(form, 'gst_rate_percent'),
      gst_recoverable_percent: inputValue(form, 'gst_recoverable_percent'),
      freight_cost: inputValue(form, 'freight_cost'),
      prep_cost: inputValue(form, 'prep_cost'),
      packaging_cost: inputValue(form, 'packaging_cost'),
      advertising_rate_percent: inputValue(form, 'advertising_rate_percent'),
      returns_rate_percent: inputValue(form, 'returns_rate_percent'),
      overhead_cost: inputValue(form, 'overhead_cost'),
      referral_fee_rate_percent: optionalInputValue(form, 'referral_fee_rate_percent'),
      fulfilment_fee: optionalInputValue(form, 'fulfilment_fee'),
      closing_fee: optionalInputValue(form, 'closing_fee'),
      storage_fee: optionalInputValue(form, 'storage_fee'),
      minimum_margin_percent: inputValue(form, 'minimum_margin_percent'),
      target_margin_percent: inputValue(form, 'target_margin_percent'),
    };
    const nextErrors = validateCostProfile(command);
    setErrors(nextErrors);
    setSubmission({ status: 'idle', message: null });
    if (Object.keys(nextErrors).length > 0) return;

    setSubmission({ status: 'submitting', message: null });
    try {
      await onCreate(command);
      setSubmission({
        status: 'success',
        message: 'Cost profile saved as a new effective-dated version.',
      });
    } catch (caught: unknown) {
      const failure = caught instanceof Error ? caught : new Error('Unable to save cost profile.');
      setSubmission({
        status: 'error',
        message: failure.message,
        requestId: failure instanceof ApiError ? failure.requestId : undefined,
      });
    }
  }

  return (
    <form className="panel economics-form" onSubmit={submit} noValidate>
      <div className="section-heading">
        <div>
          <p className="data-label">User input</p>
          <h2>Cost profile</h2>
        </div>
        {matchingProfile ? (
          <span>
            Prefilled from the latest {costProfileWindowStatus(matchingProfile)}{' '}
            {matchingProfile.scope === 'product' ? 'product' : 'marketplace-default'} revision
          </span>
        ) : hasAnyProfile ? (
          <span>No matching scoped revision · inputs reset</span>
        ) : null}
      </div>
      <p className="muted">
        Saving creates a new dated version. Imported market data can never replace these inputs.
      </p>

      <fieldset
        className="choice-group"
        aria-describedby={errors.scope ? 'scope-error' : undefined}
      >
        <legend>Apply this profile to</legend>
        <label>
          <input
            type="radio"
            name="scope"
            value="product"
            checked={profileTarget === 'product'}
            disabled={submission.status === 'submitting'}
            onChange={() => selectProfileTarget('product')}
          />
          This product
        </label>
        <label>
          <input
            type="radio"
            name="scope"
            value="marketplace_default"
            checked={profileTarget === 'marketplace_default'}
            disabled={submission.status === 'submitting'}
            onChange={() => selectProfileTarget('marketplace_default')}
          />
          Marketplace default
        </label>
      </fieldset>
      <FormFieldError id="scope-error" message={errors.scope} />

      <div key={`${profileTarget}-${matchingProfile?.id ?? 'blank'}`}>
        <div className="form-grid economics-form__dates">
          <div className="field">
            <label htmlFor="cost-currency">Marketplace currency</label>
            <input
              id="cost-currency"
              name="currency_code"
              value={currencyCode}
              readOnly
              aria-describedby="currency-help"
              aria-invalid={Boolean(errors.currency_code)}
            />
            <small id="currency-help">Explicitly inherited from the selected marketplace.</small>
            <FormFieldError id="currency-error" message={errors.currency_code} />
          </div>
          <div className="field">
            <label htmlFor="cost-effective-from">Effective from (local time)</label>
            <input
              id="cost-effective-from"
              name="effective_from"
              type="datetime-local"
              step="1"
              required
              defaultValue={effectiveFromDefault}
              aria-invalid={Boolean(errors.effective_from)}
              aria-describedby="effective-from-help effective-from-error"
            />
            <small id="effective-from-help">
              Includes local time and is saved with an explicit UTC offset. A revision must be later
              than the current version.
            </small>
            <FormFieldError id="effective-from-error" message={errors.effective_from} />
          </div>
          <div className="field field--wide">
            <label htmlFor="cost-selling-price-tax-basis">Observed selling-price tax basis</label>
            <select
              id="cost-selling-price-tax-basis"
              name="selling_price_tax_basis"
              required
              defaultValue={matchingProfile?.selling_price_tax_basis ?? ''}
              aria-invalid={Boolean(errors.selling_price_tax_basis)}
              aria-describedby={
                errors.selling_price_tax_basis
                  ? 'selling-price-tax-basis-help selling-price-tax-basis-error'
                  : 'selling-price-tax-basis-help'
              }
            >
              <option value="" disabled>
                Select a tax basis
              </option>
              <option value="tax_inclusive">Price includes GST</option>
              <option value="tax_exclusive">Price excludes GST</option>
            </select>
            <small id="selling-price-tax-basis-help">
              Required because SellerOS will not guess whether the imported selling price includes
              output GST.
            </small>
            <FormFieldError
              id="selling-price-tax-basis-error"
              message={errors.selling_price_tax_basis}
            />
          </div>
        </div>

        <h3>Purchase and handling</h3>
        <p className="muted">
          All fixed cost amounts in this section are per sellable unit, not shipment or monthly
          totals.
        </p>
        <div className="form-grid economics-form__fields">
          {numericField({
            name: 'purchase_cost',
            label: 'Supplier purchase cost (GST-exclusive)',
            defaultValue: defaults.purchase_cost,
            errors,
            help: 'Enter the supplier price before GST. Recoverable input GST is handled separately.',
          })}
          {numericField({
            name: 'freight_cost',
            label: 'Freight',
            defaultValue: defaults.freight_cost,
            errors,
          })}
          {numericField({
            name: 'prep_cost',
            label: 'Prep',
            defaultValue: defaults.prep_cost,
            errors,
          })}
          {numericField({
            name: 'packaging_cost',
            label: 'Packaging',
            defaultValue: defaults.packaging_cost,
            errors,
          })}
          {numericField({
            name: 'overhead_cost',
            label: 'Overhead allocation',
            defaultValue: defaults.overhead_cost,
            errors,
          })}
        </div>

        <h3>Tax and provisions</h3>
        <div className="form-grid economics-form__fields">
          {numericField({
            name: 'gst_rate_percent',
            label: 'GST rate',
            defaultValue: defaults.gst_rate_percent,
            errors,
            suffix: '%',
          })}
          {numericField({
            name: 'gst_recoverable_percent',
            label: 'Recoverable GST',
            defaultValue: defaults.gst_recoverable_percent,
            errors,
            suffix: '%',
          })}
          {numericField({
            name: 'advertising_rate_percent',
            label: 'Advertising allowance',
            defaultValue: defaults.advertising_rate_percent,
            errors,
            suffix: '%',
          })}
          {numericField({
            name: 'returns_rate_percent',
            label: 'Return and damage provision',
            defaultValue: defaults.returns_rate_percent,
            errors,
            suffix: '%',
          })}
        </div>

        <h3>Amazon fees and margin policy</h3>
        <p className="muted">
          Fulfilment, closing and storage fees are per sellable unit; referral fees are a percentage
          of the selling price.
        </p>
        <div className="form-grid economics-form__fields">
          {numericField({
            name: 'referral_fee_rate_percent',
            label: 'Referral fee',
            defaultValue: defaults.referral_fee_rate_percent,
            errors,
            suffix: '%',
            required: false,
          })}
          {numericField({
            name: 'fulfilment_fee',
            label: 'Fulfilment fee',
            defaultValue: defaults.fulfilment_fee,
            errors,
            required: false,
          })}
          {numericField({
            name: 'closing_fee',
            label: 'Closing fee',
            defaultValue: defaults.closing_fee,
            errors,
            required: false,
          })}
          {numericField({
            name: 'storage_fee',
            label: 'Storage fee',
            defaultValue: defaults.storage_fee,
            errors,
            required: false,
          })}
          {numericField({
            name: 'minimum_margin_percent',
            label: 'Minimum acceptable margin',
            defaultValue: defaults.minimum_margin_percent,
            errors,
            suffix: '%',
          })}
          {numericField({
            name: 'target_margin_percent',
            label: 'Target margin',
            defaultValue: defaults.target_margin_percent,
            errors,
            suffix: '%',
          })}
          <div className="field">
            <label htmlFor="cost-fee-source">Fee source</label>
            <input
              id="cost-fee-source"
              name="fee_source"
              defaultValue={matchingProfile?.fee_source ?? ''}
              placeholder="e.g. Amazon fee schedule"
              aria-invalid={Boolean(errors.fee_source)}
              aria-describedby={errors.fee_source ? 'fee-source-error' : 'fee-source-help'}
            />
            <small id="fee-source-help">Record where these fee inputs came from.</small>
            <FormFieldError id="fee-source-error" message={errors.fee_source} />
          </div>
          <div className="field">
            <label htmlFor="cost-fee-date">Fee source date (UTC)</label>
            <input
              id="cost-fee-date"
              name="fee_effective_at"
              type="date"
              defaultValue={matchingProfile?.fee_effective_at?.slice(0, 10) ?? ''}
              aria-invalid={Boolean(errors.fee_effective_at)}
              aria-describedby="fee-date-help fee-date-error"
            />
            <small id="fee-date-help">
              Recorded as a UTC calendar date; no browser timezone shift is applied when displayed.
            </small>
            <FormFieldError id="fee-date-error" message={errors.fee_effective_at} />
          </div>
          <div className="field">
            <label htmlFor="cost-fee-status">Fee evidence status</label>
            <select
              id="cost-fee-status"
              name="fee_status"
              defaultValue={matchingProfile?.fee_status ?? ''}
              aria-invalid={Boolean(errors.fee_status)}
              aria-describedby={errors.fee_status ? 'fee-status-error' : 'fee-status-help'}
            >
              <option value="">Not provided</option>
              <option value="observed">Observed from a published source</option>
              <option value="estimated">Estimated assumption</option>
              <option value="user_confirmed">User confirmed</option>
            </select>
            <small id="fee-status-help">Missing fee inputs remain visibly estimated.</small>
            <FormFieldError id="fee-status-error" message={errors.fee_status} />
          </div>
        </div>
      </div>

      {submission.status === 'error' && (
        <div className="form-message form-message--error" role="alert">
          {submission.message}
          {submission.requestId && (
            <span className="support-reference"> Support reference: {submission.requestId}</span>
          )}
        </div>
      )}
      {submission.status === 'success' && (
        <div className="form-message form-message--success" role="status">
          {submission.message}
        </div>
      )}
      <div className="form-actions">
        <button className="button" type="submit" disabled={submission.status === 'submitting'}>
          {submission.status === 'submitting' ? 'Saving profile…' : 'Save new profile version'}
        </button>
      </div>
    </form>
  );
}
