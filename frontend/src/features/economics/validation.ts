import type {
  CreateCostProfileRequest,
  CreateSupplierOfferRequest,
  CreateTestBuyRequest,
} from '../../api/contracts';

export type FieldErrors = Record<string, string>;

const decimalPattern = /^(?:0|[1-9]\d*)(?:\.\d{1,4})?$/;
const currencyAmountPattern = /^(?:0|[1-9]\d*)(?:\.\d{1,2})?$/;

function requireText(value: string, label: string, errors: FieldErrors, field: string) {
  if (!value.trim()) errors[field] = `${label} is required.`;
}

function nonNegativeDecimal(value: string, label: string, errors: FieldErrors, field: string) {
  if (!decimalPattern.test(value.trim())) {
    errors[field] = `${label} must be zero or a positive decimal with up to 4 decimal places.`;
  }
}

function percentage(value: string, label: string, errors: FieldErrors, field: string) {
  nonNegativeDecimal(value, label, errors, field);
  if (!errors[field] && Number(value) > 100) errors[field] = `${label} cannot exceed 100%.`;
}

function validDate(value: string, label: string, errors: FieldErrors, field: string) {
  const timestamp = value.includes('T') ? value : `${value}T00:00:00Z`;
  if (!value || Number.isNaN(Date.parse(timestamp))) {
    errors[field] = `${label} must be a valid date.`;
  }
}

export function validateCostProfile(command: CreateCostProfileRequest): FieldErrors {
  const errors: FieldErrors = {};
  if (!['tax_inclusive', 'tax_exclusive'].includes(command.selling_price_tax_basis)) {
    errors.selling_price_tax_basis = 'Select whether the observed selling price includes GST.';
  }
  if (!/^[A-Z]{3}$/.test(command.currency_code)) {
    errors.currency_code = 'Currency must be a three-letter ISO code.';
  }
  validDate(command.effective_from, 'Effective date', errors, 'effective_from');

  const moneyFields: Array<[keyof CreateCostProfileRequest, string]> = [
    ['purchase_cost', 'Purchase cost'],
    ['freight_cost', 'Freight cost'],
    ['prep_cost', 'Prep cost'],
    ['packaging_cost', 'Packaging cost'],
    ['overhead_cost', 'Overhead cost'],
  ];
  moneyFields.forEach(([field, label]) =>
    nonNegativeDecimal(String(command[field]), label, errors, field),
  );

  const percentageFields: Array<[keyof CreateCostProfileRequest, string]> = [
    ['gst_rate_percent', 'GST rate'],
    ['gst_recoverable_percent', 'Recoverable GST'],
    ['advertising_rate_percent', 'Advertising allowance'],
    ['returns_rate_percent', 'Returns provision'],
    ['minimum_margin_percent', 'Minimum margin'],
    ['target_margin_percent', 'Target margin'],
  ];
  percentageFields.forEach(([field, label]) =>
    percentage(String(command[field]), label, errors, field),
  );
  if (!errors.minimum_margin_percent && Number(command.minimum_margin_percent) >= 100) {
    errors.minimum_margin_percent = 'Minimum margin must be less than 100%.';
  }
  if (!errors.target_margin_percent && Number(command.target_margin_percent) >= 100) {
    errors.target_margin_percent = 'Target margin must be less than 100%.';
  }
  if (
    !errors.minimum_margin_percent &&
    !errors.target_margin_percent &&
    Number(command.target_margin_percent) < Number(command.minimum_margin_percent)
  ) {
    errors.target_margin_percent = 'Target margin cannot be below minimum margin.';
  }
  const optionalFeeFields: Array<[keyof CreateCostProfileRequest, string, 'money' | 'percent']> = [
    ['referral_fee_rate_percent', 'Amazon referral fee', 'percent'],
    ['fulfilment_fee', 'Amazon fulfilment fee', 'money'],
    ['closing_fee', 'Amazon closing fee', 'money'],
    ['storage_fee', 'Amazon storage fee', 'money'],
  ];
  optionalFeeFields.forEach(([field, label, kind]) => {
    const value = command[field];
    if (value === null) return;
    if (kind === 'percent') percentage(String(value), label, errors, field);
    else nonNegativeDecimal(String(value), label, errors, field);
  });
  const hasFeeInput = optionalFeeFields.some(([field]) => command[field] !== null);
  if (hasFeeInput) {
    if (!command.fee_source?.trim()) errors.fee_source = 'Fee source is required for fee inputs.';
    if (!command.fee_effective_at) {
      errors.fee_effective_at = 'Fee source date is required for fee inputs.';
    } else {
      validDate(command.fee_effective_at, 'Fee source date', errors, 'fee_effective_at');
    }
    if (!command.fee_status) errors.fee_status = 'Select how the fee inputs were established.';
  } else if (command.fee_source || command.fee_effective_at || command.fee_status) {
    errors.fee_source = 'Clear fee evidence metadata when no fee inputs are provided.';
  }
  return errors;
}

export function validateSupplierOffer(command: CreateSupplierOfferRequest): FieldErrors {
  const errors: FieldErrors = {};
  requireText(command.supplier_name, 'Supplier name', errors, 'supplier_name');
  if (command.supplier_name.length > 255) {
    errors.supplier_name = 'Supplier name cannot exceed 255 characters.';
  }
  if (!/^[A-Z]{3}$/.test(command.currency_code)) {
    errors.currency_code = 'Currency must be a three-letter ISO code.';
  }
  nonNegativeDecimal(command.unit_cost, 'Unit cost', errors, 'unit_cost');
  if (
    !Number.isInteger(command.minimum_order_quantity) ||
    command.minimum_order_quantity < 1 ||
    command.minimum_order_quantity > 10_000_000
  ) {
    errors.minimum_order_quantity = 'MOQ must be a whole number from 1 through 10,000,000.';
  }
  if (
    !Number.isInteger(command.lead_time_days) ||
    command.lead_time_days < 0 ||
    command.lead_time_days > 3_650
  ) {
    errors.lead_time_days = 'Lead time must be a whole number from 0 through 3,650 days.';
  }
  validDate(command.quotation_date, 'Quotation date', errors, 'quotation_date');
  if (command.valid_until) {
    validDate(command.valid_until, 'Valid until', errors, 'valid_until');
    if (
      !errors.valid_until &&
      Date.parse(
        command.valid_until.includes('T')
          ? command.valid_until
          : `${command.valid_until}T00:00:00Z`,
      ) <
        Date.parse(
          command.quotation_date.includes('T')
            ? command.quotation_date
            : `${command.quotation_date}T00:00:00Z`,
        )
    ) {
      errors.valid_until = 'Valid until cannot be earlier than the quotation date.';
    }
  }
  command.price_tiers.forEach((tier, index) => {
    if (!Number.isInteger(tier.minimum_quantity) || tier.minimum_quantity > 10_000_000) {
      errors[`price_tiers.${index}.minimum_quantity`] =
        'Tier quantity must be a whole number no greater than 10,000,000.';
    }
    if (tier.minimum_quantity <= command.minimum_order_quantity) {
      errors[`price_tiers.${index}.minimum_quantity`] =
        'Discount tier quantity must be greater than the base MOQ.';
    }
    nonNegativeDecimal(tier.unit_cost, 'Tier unit cost', errors, `price_tiers.${index}.unit_cost`);
    if (
      index > 0 &&
      tier.minimum_quantity <= (command.price_tiers[index - 1]?.minimum_quantity ?? 0)
    ) {
      errors[`price_tiers.${index}.minimum_quantity`] =
        'Tier quantities must increase without duplicates.';
    }
  });
  if (command.price_tiers.length > 25) {
    errors.price_tiers = 'No more than 25 additional price tiers are allowed.';
  }
  if (command.notes && command.notes.length > 2_000) {
    errors.notes = 'Notes cannot exceed 2,000 characters.';
  }
  return errors;
}

export function validateTestBuy(command: CreateTestBuyRequest): FieldErrors {
  const errors: FieldErrors = {};
  requireText(command.supplier_offer_id, 'Supplier offer', errors, 'supplier_offer_id');
  if (!currencyAmountPattern.test(command.budget_amount.trim())) {
    errors.budget_amount = 'Budget must be zero or a positive decimal with up to 2 decimal places.';
  }
  if (!/^[A-Z]{3}$/.test(command.budget_currency_code)) {
    errors.currency_code = 'Currency must be a three-letter ISO code.';
  }
  return errors;
}
