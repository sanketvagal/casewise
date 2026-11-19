# Customize and troubleshoot automated appointment reminders

Configure your patient notifications by navigating to **Settings > Communications > Reminders**. Here, you can adjust SMS and email templates and set the dispatch window from 24 to 72 hours before the visit.

### Conditions and Limits
* Patients must have a verified mobile number or email address.
* SMS messages are capped at 160 characters; longer texts will split into multiple segments.
* Reminders will not send if the appointment status is marked as 'Cancelled' or 'Arrived'.

### Step-by-Step Setup
1. Go to **Settings > Communications > Reminders**.
2. Select **Edit** next to the desired channel (SMS or Email).
3. Use allowed merge tags like `[PatientName]` and `[AppointmentTime]` to personalize the content.
4. Click **Save Changes** to apply.

### Troubleshooting
If a patient does not receive a reminder, first check the patient profile to ensure communication opt-in is enabled. Next, review **Reports > Message Log** to check delivery status. If the log shows a 'Failed' status due to carrier blocking, verify the phone number supports SMS. For persistent delivery failures, contact support with the affected patient ID and timestamp.
