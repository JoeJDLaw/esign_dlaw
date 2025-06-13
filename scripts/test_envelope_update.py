from app.integrations.salesforce.updater import update_envelope_record

record_id = "a01HS0000001abc"  # Replace with your real Envelope__c record ID
updates = {
    "Signed_Status__c": "Signed",
    "Signed_Date__c": "2025-06-11",
    "Signed_File_Path__c": "/signed/20250611/example.pdf"
}

update_envelope_record(record_id, updates)