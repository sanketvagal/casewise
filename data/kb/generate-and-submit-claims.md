# Generate, review, and submit insurance claims

Follow these steps to process and submit electronic claims to your clearinghouse:

1. Navigate to **Billing > Claim Center** and select the **Ready to Batch** tab.
2. Filter by payer or date range, then click **Generate Claims** to compile all finalized encounters.
3. Review the generated list on the **Validation Queue** tab. Claims with missing modifiers, invalid subscriber IDs, or unmapped diagnosis codes will display a red error icon.
4. Click any flagged claim to open the editor, correct the highlighted errors, and click **Save & Re-validate**.
5. Select the validated claims and click **Batch & Submit** to transmit them to the clearinghouse.

### Limits and Conditions
- Claims must be generated within 90 days of the service date.
- Batch sizes cannot exceed 500 claims per transmission.

### Troubleshooting
If a claim repeatedly fails validation despite correct data entry, go to **Billing > Payer Rules** to verify that the specific payer's current electronic format requirements are up to date. If transmission errors persist after a successful batch, check the **Clearinghouse Log** under **Reports** for specific rejection codes.
