# Configure notification rules for critical lab values

Ensure urgent patient results are addressed immediately by setting up automated threshold alerts for your clinical team.

### Steps to Configure
1. Navigate to **Clinical > Lab Settings > Critical Alerts**.
2. Click **Add Rule** in the top right corner.
3. Select the target lab test from the dropdown menu (e.g., *Serum Potassium*).
4. Enter the numerical low and high boundaries in the **Threshold Parameters** fields.
5. Check the box for **Instant Staff Notification** and assign the alert to **Role: On-Call Nurse** or specific provider queues.
6. Click **Save Rule**.

### Limits and Conditions
* Rules apply only to incoming electronic lab feeds (HL7/FHIR).
* Manual lab entry will not trigger these automated threshold flags.
* Staff must have the *Manage Lab Settings* permission enabled in **Settings > Staff** to edit rules.

### Troubleshooting
If alerts are not routing to the designated staff, verify that the user profile notifications are enabled under **My Profile > Notifications**, and ensure the lab vendor's LOINC code matches the parameter configuration exactly.
