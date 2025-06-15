# eSign Webhook Notifications

This document describes all webhook notifications sent during the eSign process to the `RC_WEBHOOK_URL`.

## Webhook Control

All webhooks respect the `DISABLE_WEBHOOKS` environment variable:
- `DISABLE_WEBHOOKS=true` - No webhooks sent (logs what would have been sent)
- `DISABLE_WEBHOOKS=false` or unset - Webhooks sent normally

## Notification Types

### 1. 📝 Document Initiation
**Trigger**: When a new signature request is created via `/api/v1/initiate`

**Content**:
```
📝 New document ready for signing:
🔗 URL: https://esign.dlaw.app/v1/sign/{token}
👤 Name: {client_name}
📧 Email: {client_email}
📄 Template: {template_type}
🏢 Salesforce Case ID: {salesforce_case_id}
📋 Envelope Document ID: {envelope_document_id}
📊 Status: Sent
⏰ Created: 2025-06-15 15:27:03 UTC
📅 Expires: 2025-07-15
🎫 Token: a8d154f1...
```

### 2. ✅ Document Signed & Uploaded Successfully
**Trigger**: When document is signed and successfully uploaded to Dropbox

**Content**:
```
✅ Document signed and uploaded to Dropbox:
Client: {client_name}
Email: {client_email}
Template: {template_type}
Local Path: /srv/apps/esign/signed/20250615/filename.pdf
Dropbox Path: /Potential Clients/_esign/20250615/filename.pdf
File Size: 119209 bytes
Signed At: 2025-06-15T15:27:03.123456+00:00
Salesforce Case: {salesforce_case_id}
Envelope ID: {envelope_document_id}
```

### 3. ❌ Document Signed but Dropbox Upload Failed
**Trigger**: When document is signed but Dropbox upload fails

**Content**:
```
❌ Document signed but Dropbox upload failed:
Client: {client_name}
Email: {client_email}
Template: {template_type}
Local Path: /srv/apps/esign/signed/20250615/filename.pdf
Error: Dropbox upload failed
Signed At: 2025-06-15T15:27:03.123456+00:00
Salesforce Case: {salesforce_case_id}
Envelope ID: {envelope_document_id}
```

### 4. ✅ Salesforce Updated Successfully
**Trigger**: When Salesforce envelope is successfully updated with Dropbox path

**Content**:
```
✅ Salesforce updated successfully:
Client: {client_name}
Envelope ID: {envelope_document_id}
Dropbox Path: /Potential Clients/_esign/20250615/filename.pdf
Status: Completed
Sign Date: 2025-06-15T15:27:03.123456+00:00
Salesforce Case: {salesforce_case_id}
```

### 5. ⚠️ Salesforce Update Retry Failures
**Trigger**: When Salesforce update attempts fail (sent for each retry)

**Content**:
```
Salesforce update retry {attempt} failed for Envelope Document {envelope_id}: {error_details}
```

### 6. ❌ Salesforce Update Final Failure
**Trigger**: When all Salesforce update attempts fail

**Content**:
```
Salesforce update failed for Envelope Document {envelope_id} after {max_attempts} attempts.
```

## Migration Weekend Behavior

During Salesforce migration (when envelope records don't exist):
- **Notifications 1-3**: Sent normally ✅
- **Notification 4**: Won't be sent (no successful Salesforce update)
- **Notifications 5-6**: Sent for expected failures during migration

## Information Included

Each notification includes relevant details:
- **Client Information**: Name, email
- **Document Details**: Template type, file paths, file size
- **Timestamps**: Creation time, signing time, expiration
- **Identifiers**: Salesforce case ID, envelope ID, token
- **Status Information**: Current status, success/failure indicators
- **Technical Details**: Local paths, Dropbox paths, error messages

## Testing

To test webhook notifications:
```bash
# Enable webhooks
export DISABLE_WEBHOOKS=false

# Run migration-safe test
cd /srv/apps/esign
PYTHONPATH=/srv/shared:/srv/apps/esign python tests/test_migration_safe_workflow.py

# Disable webhooks for silent testing
export DISABLE_WEBHOOKS=true
```

## Configuration

Set your webhook URL in the environment:
```bash
RC_WEBHOOK_URL=https://hooks.ringcentral.com/webhook/your-webhook-id
``` 