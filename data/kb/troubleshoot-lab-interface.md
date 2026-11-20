# Troubleshoot lab interface connections and missing feeds

When electronic diagnostic results stop populating, clinic staff can resolve most interface disruptions using the administrative console.

### Steps to Restart the Feed
1. Navigate to **Admin > Interfaces > Lab Connectivity**.
2. Locate the affected vendor in the active connections list.
3. Click **Diagnostics** to run a live ping test.
4. If the status reads offline, click **Action > Restart Service**.
5. Wait three minutes for the queue to flush and refresh the dashboard.

### Limits and Conditions
Only users with the *System Administrator* role can restart interface services. The system processes up to 500 queued results per batch; backlog clearing for extended outages may take up to thirty minutes.

### Troubleshooting
If the connection status remains red after a manual restart, verify that your local firewall permits outbound traffic on port 443 to the designated gateway IP. Should results still fail to appear, document the error code displayed in the event log and submit a support ticket with the specimen requisition numbers for the missing labs.
