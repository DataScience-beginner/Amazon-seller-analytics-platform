# GST India filing-preparation workflow

SellerOS prepares a calculated working paper from user-supplied evidence. It does not log into the
GST Portal, determine legal entitlement to input tax credit, pay tax, sign or file a return.

## Guided workflow

1. Add a GST registration to an Amazon India workspace. SellerOS stores the GSTIN as scoped business
   evidence and returns only a masked value through workflow APIs.
2. Create a monthly filing period. A registration and month may have only one workflow.
3. Upload the Amazon GST Ready-to-File GSTR-1 `.xlsx` report. The filename period and GSTIN, OOXML
   archive, required sheets, dimensions, headers and numeric fields are validated.
4. Review B2B, B2B credit/debit note, B2C Large, B2C Small and HSN record counts, calculated totals
   and any exceptions. Individual source rows remain preserved in the immutable parsed document.
5. Explicitly confirm that the evidence contains all outward supplies and approve the draft.
6. Download the versioned SellerOS JSON working paper. This is not certified GST Offline Tool JSON
   and is not proof of filing.
7. File through the GST Portal with the authorised user's EVC/DSC, then record the ARN. Only this
   explicit action changes the workflow to `user_confirmed_filed`.

## State machine

`collecting → validating → needs_attention | draft_ready → approved → exported →
user_confirmed_filed`

Approved, exported and filed periods reject new source evidence. Source documents and calculated
drafts are append-only. Corrections require a new draft version before approval.

## Agent boundary

Future Gmail or GSP adapters may create collection tasks, retrieve explicitly authorised documents,
verify sender and checksum, and attach immutable evidence. AI may classify evidence and explain
structured exceptions. It may not change totals, resolve a tax-policy ambiguity, confirm
completeness, approve, pay, sign or file.

GST Portal credentials, passwords, OTPs, EVCs and DSC key material must never enter SellerOS.
