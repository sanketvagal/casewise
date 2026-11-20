# Customize patient notification and message templates

Practice managers can tailor automated patient alerts to match clinic branding. Only administrators and designated managers have permission to edit these settings.

1. Navigate to **Settings > Communications > Templates**.
2. Select the category tab, such as **Appointment Confirmations** or **Billing Notices**.
3. Choose the template you wish to modify and click **Edit**.
4. Draft your message using available placeholder tags from the sidebar (e.g., `{{patient_first_name}}`, `{{appointment_date}}`).
5. Click **Preview** to review the rendered text, then select **Save Changes**.

### Limits and Conditions
* Templates cannot exceed 480 characters to comply with standard SMS gateway limits.
* Custom HTML styling is supported only in email templates.

### Troubleshooting
If placeholder tags fail to populate when sent, verify that the tag syntax matches the exact spelling in the sidebar glossary. Unmatched brackets (like missing the closing `}}`) will trigger a syntax validation error and prevent saving. If emails fail to deliver after updating, check that your sender domain authentication remains active under **Settings > Communications > Domain Setup**.
