# Twilio WhatsApp Quick Reply Button Template

## Create Content Template with Buttons

To create a content template with quick reply buttons for approval requests:

### Using Twilio Console:
1. Go to Twilio Console > Messaging > Content Editor
2. Create a new template with:
   - **Name**: `approval_request_buttons`
   - **Language**: English (en)
   - **Category**: Utility/Notification

### Template Content (Quick Reply):
```json
{
  "body": "🔔 *Approval Request*\n\n{{1}}\n\n*Request ID:* {{2}}\n\n⏱️ Expires in 5 minutes",
  "actions": [
    {
      "title": "✅ Approve",
      "id": "approve_{{2}}"
    },
    {
      "title": "❌ Deny", 
      "id": "deny_{{2}}"
    }
  ]
}
```

### Using Twilio API:
```bash
curl -X POST https://content.twilio.com/v1/Content \
  -u $TWILIO_ACCOUNT_SID:$TWILIO_AUTH_TOKEN \
  -H "Content-Type: application/json" \
  -d '{
    "friendly_name": "approval_request_buttons",
    "language": "en",
    "variables": {
      "1": "request_description",
      "2": "request_id"
    },
    "types": {
      "twilio/quick-reply": {
        "body": "🔔 *Approval Request*\n\n{{1}}\n\n*Request ID:* {{2}}\n\n⏱️ Expires in 5 minutes",
        "actions": [
          {
            "title": "✅ Approve",
            "id": "approve_{{2}}"
          },
          {
            "title": "❌ Deny",
            "id": "deny_{{2}}"
          }
        ]
      }
    }
  }'
```

**Note**: Quick-reply templates only work when the user is in a 24-hour session with your WhatsApp number. For the first message or if outside the session window, the server will fall back to a regular text message.

After creating the template, you'll receive a Content SID (like `HXxxxx`). Set this as the `TWILIO_CONTENT_SID` environment variable.

## Differences from List Picker:
- **Quick Reply**: Shows buttons directly in the message (max 3 buttons)
- **List Picker**: Shows a "Choose Action" button that opens a menu (max 10 items)

Quick reply is better for simple approve/deny scenarios as it requires fewer taps.