# Manage result release rules and patient portal visibility

You can configure automated release timers so sensitive lab reports and diagnostic results appear in the patient portal only after clinical review. 

### Configuration Steps

1. Go to **Settings > Patient Portal > Result Rules**.
2. Click **Add Rule** to create a new category mapping.
3. Select the target lab category (e.g., *Pathology* or *Imaging*).
4. Enter the desired delay in hours under **Hold Period**.
5. Toggle **Auto-Release** to active, then click **Save**.

### Limits and Conditions

* Delay timers apply to all clinicians unless an override is set on the individual order.
* The maximum hold period is 168 hours (7 days).
* Critical-flagged results bypass the hold period and require manual provider sign-off.

### Troubleshooting

If results fail to appear after the timer expires, check **Reports > Portal Log** to confirm the auto-release job ran. If the entry shows an error, verify that the patient has an active portal account and valid contact preferences, then select **Resend to Portal** from the patient's chart.
