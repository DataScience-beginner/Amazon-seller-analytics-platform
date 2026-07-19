import { useRef, useState, type FormEvent } from 'react';

import { ApiError } from '../../api/client';
import type { CreateSupplierOfferRequest, SupplierOffer } from '../../api/contracts';
import { formatUtcDateInput } from '../../utils/format';
import { FormFieldError } from './FormFieldError';
import { validateSupplierOffer, type FieldErrors } from './validation';

type SubmissionState =
  | { status: 'idle' }
  | { status: 'submitting' }
  | { status: 'success' }
  | { status: 'error'; message: string; requestId?: string };

type EditableTier = {
  id: string;
  minimumQuantity: string;
  unitCost: string;
};

function formString(form: FormData, name: string): string {
  return String(form.get(name) ?? '').trim();
}

export function SupplierOfferForm({
  productId,
  currencyCode,
  onCreate,
}: {
  productId: string;
  currencyCode: string;
  onCreate: (command: CreateSupplierOfferRequest) => Promise<SupplierOffer>;
}) {
  const [tiers, setTiers] = useState<EditableTier[]>([]);
  const tierSequence = useRef(0);
  const [errors, setErrors] = useState<FieldErrors>({});
  const [submission, setSubmission] = useState<SubmissionState>({ status: 'idle' });
  const today = formatUtcDateInput();

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const formElement = event.currentTarget;
    const form = new FormData(formElement);
    const command: CreateSupplierOfferRequest = {
      product_id: productId,
      supplier_name: formString(form, 'supplier_name'),
      currency_code: currencyCode,
      unit_cost: formString(form, 'unit_cost'),
      minimum_order_quantity: Number(formString(form, 'minimum_order_quantity')),
      lead_time_days: Number(formString(form, 'lead_time_days')),
      quotation_date: formString(form, 'quotation_date'),
      valid_until: formString(form, 'valid_until') || null,
      notes: formString(form, 'notes') || null,
      price_tiers: tiers.map((tier) => ({
        minimum_quantity: Number(tier.minimumQuantity),
        unit_cost: tier.unitCost.trim(),
      })),
    };
    const nextErrors = validateSupplierOffer(command);
    setErrors(nextErrors);
    setSubmission({ status: 'idle' });
    if (Object.keys(nextErrors).length > 0) return;

    setSubmission({ status: 'submitting' });
    try {
      await onCreate(command);
      formElement.reset();
      setTiers([]);
      setSubmission({ status: 'success' });
    } catch (caught: unknown) {
      const failure =
        caught instanceof Error ? caught : new Error('Unable to save supplier offer.');
      setSubmission({
        status: 'error',
        message: failure.message,
        requestId: failure instanceof ApiError ? failure.requestId : undefined,
      });
    }
  }

  function addTier() {
    tierSequence.current += 1;
    setTiers((current) => [
      ...current,
      {
        id: `supplier-tier-${tierSequence.current}`,
        minimumQuantity: '',
        unitCost: '',
      },
    ]);
    setErrors({});
  }

  function updateTier(id: string, field: 'minimumQuantity' | 'unitCost', value: string) {
    setTiers((current) =>
      current.map((tier) => (tier.id === id ? { ...tier, [field]: value } : tier)),
    );
    setErrors({});
  }

  function removeTier(id: string) {
    setTiers((current) => current.filter((tier) => tier.id !== id));
    setErrors({});
  }

  return (
    <form className="panel economics-form" onSubmit={submit} noValidate>
      <div className="section-heading">
        <div>
          <p className="data-label">User input</p>
          <h2>Record supplier offer</h2>
        </div>
      </div>
      <p className="muted">
        SellerOS compares cost together with MOQ, lead time and quotation validity. No offer is
        automatically accepted.
      </p>
      <div className="form-grid economics-form__fields">
        <label className="field">
          <span>Supplier name</span>
          <input
            name="supplier_name"
            required
            maxLength={255}
            aria-invalid={Boolean(errors.supplier_name)}
            aria-describedby={errors.supplier_name ? 'supplier-name-error' : undefined}
          />
          <FormFieldError id="supplier-name-error" message={errors.supplier_name} />
        </label>
        <div className="field">
          <label htmlFor="supplier-offer-currency">Marketplace currency</label>
          <input id="supplier-offer-currency" value={currencyCode} readOnly />
          <small>
            Must match the selected marketplace. Currency conversion is blocked until explicit FX
            support exists.
          </small>
          <FormFieldError id="offer-currency-error" message={errors.currency_code} />
        </div>
        <label className="field">
          <span>Base unit cost</span>
          <input
            name="unit_cost"
            type="number"
            inputMode="decimal"
            min="0"
            step="0.0001"
            required
            aria-invalid={Boolean(errors.unit_cost)}
            aria-describedby={errors.unit_cost ? 'unit-cost-error' : undefined}
          />
          <FormFieldError id="unit-cost-error" message={errors.unit_cost} />
        </label>
        <label className="field">
          <span>Minimum order quantity (units)</span>
          <input
            name="minimum_order_quantity"
            type="number"
            inputMode="numeric"
            min="1"
            step="1"
            required
            aria-invalid={Boolean(errors.minimum_order_quantity)}
            aria-describedby={errors.minimum_order_quantity ? 'moq-error' : undefined}
          />
          <FormFieldError id="moq-error" message={errors.minimum_order_quantity} />
        </label>
        <label className="field">
          <span>Lead time (days)</span>
          <input
            name="lead_time_days"
            type="number"
            inputMode="numeric"
            min="0"
            step="1"
            required
            aria-invalid={Boolean(errors.lead_time_days)}
            aria-describedby={errors.lead_time_days ? 'lead-time-error' : undefined}
          />
          <FormFieldError id="lead-time-error" message={errors.lead_time_days} />
        </label>
        <div className="field">
          <label htmlFor="supplier-quotation-date">Quotation date (UTC)</label>
          <input
            id="supplier-quotation-date"
            name="quotation_date"
            type="date"
            required
            defaultValue={today}
            aria-invalid={Boolean(errors.quotation_date)}
            aria-describedby="quotation-date-help quotation-date-error"
          />
          <small id="quotation-date-help">
            Uses the UTC calendar to match server validation. Seller timezone will become an
            explicit workspace setting in a future phase.
          </small>
          <FormFieldError id="quotation-date-error" message={errors.quotation_date} />
        </div>
        <label className="field">
          <span>Valid until (UTC, optional)</span>
          <input
            name="valid_until"
            type="date"
            aria-invalid={Boolean(errors.valid_until)}
            aria-describedby={errors.valid_until ? 'valid-until-error' : undefined}
          />
          <FormFieldError id="valid-until-error" message={errors.valid_until} />
        </label>
        <label className="field field--wide">
          <span>Notes (optional)</span>
          <textarea
            name="notes"
            rows={3}
            maxLength={2000}
            aria-invalid={Boolean(errors.notes)}
            aria-describedby={errors.notes ? 'offer-notes-error' : undefined}
          />
          <FormFieldError id="offer-notes-error" message={errors.notes} />
        </label>
      </div>

      <fieldset className="tier-editor">
        <legend>Price tiers (optional)</legend>
        {tiers.length === 0 ? (
          <p className="muted">No quantity discount tiers recorded.</p>
        ) : (
          <div className="tier-editor__rows">
            {tiers.map((tier, index) => {
              const quantityError = errors[`price_tiers.${index}.minimum_quantity`];
              const costError = errors[`price_tiers.${index}.unit_cost`];
              return (
                <div className="tier-editor__row" key={tier.id}>
                  <label className="field">
                    <span>Minimum units</span>
                    <input
                      name={`tier_quantity_${tier.id}`}
                      type="number"
                      min="1"
                      step="1"
                      required
                      value={tier.minimumQuantity}
                      onChange={(event) =>
                        updateTier(tier.id, 'minimumQuantity', event.target.value)
                      }
                      aria-invalid={Boolean(quantityError)}
                      aria-describedby={quantityError ? `tier-quantity-${index}-error` : undefined}
                    />
                    <FormFieldError id={`tier-quantity-${index}-error`} message={quantityError} />
                  </label>
                  <label className="field">
                    <span>Unit cost</span>
                    <input
                      name={`tier_cost_${tier.id}`}
                      type="number"
                      min="0"
                      step="0.0001"
                      required
                      value={tier.unitCost}
                      onChange={(event) => updateTier(tier.id, 'unitCost', event.target.value)}
                      aria-invalid={Boolean(costError)}
                      aria-describedby={costError ? `tier-cost-${index}-error` : undefined}
                    />
                    <FormFieldError id={`tier-cost-${index}-error`} message={costError} />
                  </label>
                  <button
                    className="button button--ghost"
                    type="button"
                    disabled={submission.status === 'submitting'}
                    onClick={() => removeTier(tier.id)}
                  >
                    Remove tier {index + 1}
                  </button>
                </div>
              );
            })}
          </div>
        )}
        <button
          className="button button--secondary"
          type="button"
          disabled={tiers.length >= 25 || submission.status === 'submitting'}
          onClick={addTier}
        >
          Add price tier
        </button>
        <FormFieldError id="price-tiers-error" message={errors.price_tiers} />
      </fieldset>

      {submission.status === 'success' && (
        <div className="form-message form-message--success" role="status">
          Supplier offer saved for comparison.
        </div>
      )}
      {submission.status === 'error' && (
        <div className="form-message form-message--error" role="alert">
          {submission.message}
          {submission.requestId && (
            <span className="support-reference"> Support reference: {submission.requestId}</span>
          )}
        </div>
      )}
      <div className="form-actions">
        <button className="button" type="submit" disabled={submission.status === 'submitting'}>
          {submission.status === 'submitting' ? 'Saving offer…' : 'Save supplier offer'}
        </button>
      </div>
    </form>
  );
}
