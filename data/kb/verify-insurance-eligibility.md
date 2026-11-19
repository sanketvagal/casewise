# Check real-time patient insurance eligibility

Front desk staff can verify patient coverage instantly before scheduled appointments using our integrated clearinghouse connection.

### Steps to Verify Coverage
1. Open the patient's appointment and click **Billing > Insurance Eligibility**.
2. Select the active policy from the dropdown menu and confirm the primary subscriber's date of birth.
3. Click **Run Real-Time Check** to query the payer database.

### Limits and Conditions
* Real-time checks require an active internet connection and valid payer ID on the patient profile.
* Verification results only confirm active coverage status, copay amounts, and deductible balances at the exact moment of the query; benefits are subject to final payer adjudication.

### Troubleshooting
If the system returns a connection timeout or clearinghouse error:
1. Navigate to **Settings > Billing Integration** and click **Test Clearinghouse Connection**.
2. Verify that the patient's Member ID contains no spaces or special characters.
3. If the error persists, contact support with the specific error code displayed on the screen.
