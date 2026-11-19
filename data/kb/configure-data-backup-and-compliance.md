# Configure Data Backups and Compliance Archive Settings

Protect sensitive patient records and maintain regulatory compliance by setting up automated system backups and executing your required Business Associate Agreement (BAA).

### Requirements and Limits
* Only users with the **Administrator** role can modify backup and compliance settings.
* Automated backups occur daily at midnight UTC and are retained for 90 days.
* You must execute a digital BAA before enabling external cloud storage sync.

### Configuration Steps
1. Go to **Settings > Security > Compliance**. 
2. Review the BAA text and click **Accept and Sign**.
3. Navigate to **Settings > Data Management > Backups**.
4. Toggle on **Automated Daily Backups**.
5. Select your retention tier (**90-Day Standard** or **1-Year Extended**).
6. Click **Save Changes**.

### Troubleshooting
If backup generation fails or your export link returns an error, verify that your storage bucket permissions allow write access from the application IP whitelist. If historical data exports do not appear within 24 hours, contact support to manually trigger the retrieval queue.
