#!/usr/bin/env python3
"""
Local MCP approval server that sends WhatsApp messages via Twilio
"""

import os
import json
import uuid
import asyncio
from datetime import datetime, timedelta
from typing import Optional
from dotenv import load_dotenv
from fastmcp import FastMCP
from fastapi import Request
from fastapi.responses import JSONResponse
from sqlmodel import Field, SQLModel, Session, create_engine, select
from twilio.rest import Client

# Load environment variables
load_dotenv()

# Initialize MCP server
mcp = FastMCP("approval-server")

# Database models
class ApprovalRequest(SQLModel, table=True):
    id: str = Field(primary_key=True)
    request_id: str = Field(unique=True, index=True)
    description: str
    requester: str
    phone_number: str
    status: str = Field(default="pending")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    responded_at: Optional[datetime] = None
    response: Optional[str] = None
    expires_at: datetime

# Database setup
DATABASE_URL = "sqlite:///approvals.db"
engine = create_engine(DATABASE_URL)
SQLModel.metadata.create_all(engine)

# Server configuration
SERVER_PORT = int(os.environ.get("SERVER_PORT", 8000))

# Twilio configuration
TWILIO_ACCOUNT_SID = os.environ.get("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.environ.get("TWILIO_AUTH_TOKEN")
TWILIO_WHATSAPP_FROM = os.environ.get("TWILIO_WHATSAPP_FROM", "whatsapp:+14155238886")
TWILIO_CONTENT_SID = os.environ.get("TWILIO_CONTENT_SID")
APPROVAL_PHONE = os.environ.get("APPROVAL_PHONE")

twilio_client = None
if TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN:
    twilio_client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)


@mcp.tool()
async def permissions__approve(tool_name: str, input: dict, reason: str = "") -> dict:
    """Request approval via WhatsApp before executing a tool."""
    
    # Format the request description in a more readable way
    if tool_name == "Bash" and isinstance(input, dict):
        command = input.get("command", "")
        description = input.get("description", "")
        request = f"Execute command: `{command}`\n*Reason:* {description}"
    else:
        request = f"*Tool:* {tool_name}"
        if input:
            # Format parameters more nicely
            params = []
            for key, value in input.items():
                if isinstance(value, str) and len(value) > 50:
                    value = value[:50] + "..."
                params.append(f"  • {key}: {value}")
            if params:
                request += "\n" + "\n".join(params)
    
    if reason:
        request = f"*Reason:* {reason}\n\n{request}"
    
    print(f"🤖 Claude requesting approval: {request}")
    
    if not twilio_client:
        print("❌ Twilio not configured")
        return {"error": "Twilio not configured"}
    
    if not APPROVAL_PHONE:
        print("❌ APPROVAL_PHONE not configured")
        return {"error": "APPROVAL_PHONE not configured in environment variables"}
    
    request_id = str(uuid.uuid4())
    short_id = request_id[:8]
    expires_at = datetime.utcnow() + timedelta(minutes=5)
    
    # Create approval request
    approval = ApprovalRequest(
        id=short_id,
        request_id=request_id,
        description=request,
        requester="Claude",
        phone_number=APPROVAL_PHONE,
        expires_at=expires_at
    )
    
    # Store in database
    with Session(engine) as session:
        session.add(approval)
        session.commit()
    
    # Send WhatsApp message
    to_number = f"whatsapp:{APPROVAL_PHONE}" if not APPROVAL_PHONE.startswith("whatsapp:") else APPROVAL_PHONE
    
    try:
        if TWILIO_CONTENT_SID:
            # Use content template (quick-reply buttons)
            message = twilio_client.messages.create(
                from_=TWILIO_WHATSAPP_FROM,
                to=to_number,
                content_sid=TWILIO_CONTENT_SID,
                content_variables=json.dumps({
                    "1": request,
                    "2": short_id
                })
            )
        else:
            # Fallback to regular message with cleaner formatting
            message_body = f"""🔔 *Approval Request*

{request}

*Request ID:* `{short_id}`

Reply:
• *APPROVE {short_id}*
• *DENY {short_id}*

⏱️ Expires in 5 minutes"""
            message = twilio_client.messages.create(
                body=message_body.strip(),
                from_=TWILIO_WHATSAPP_FROM,
                to=to_number
            )
        
        print(f"✅ Sent approval request {short_id} to {APPROVAL_PHONE}")
        
        # Wait for approval (poll database)
        max_wait_time = 300  # 5 minutes
        check_interval = 2   # Check every 2 seconds
        start_time = datetime.utcnow()
        
        while (datetime.utcnow() - start_time).total_seconds() < max_wait_time:
            with Session(engine) as session:
                statement = select(ApprovalRequest).where(ApprovalRequest.id == short_id)
                current_approval = session.exec(statement).first()
                
                if current_approval and current_approval.status != "pending":
                    print(f"📱 Received response: {current_approval.status}")
                    if current_approval.status == "approved":
                        return {"approved": True}
                    else:
                        return {"denied": True, "message": "Request was denied"}
                
                # Check if expired
                if datetime.utcnow() > expires_at:
                    print(f"⏰ Request {short_id} expired")
                    return {"error": "Request expired"}
            
            await asyncio.sleep(check_interval)
        
        print(f"⏰ Request {short_id} timed out")
        return {"error": "Request timed out"}
        
    except Exception as e:
        # Clean up database entry on failure
        with Session(engine) as session:
            approval_to_delete = session.get(ApprovalRequest, short_id)
            if approval_to_delete:
                session.delete(approval_to_delete)
                session.commit()
        return {"error": f"Failed to send WhatsApp message: {str(e)}"}


@mcp.custom_route("/twilio-webhook", methods=["GET"])
async def webhook_test():
    """Test endpoint to verify webhook URL is reachable"""
    print("🔥 WEBHOOK GET TEST CALLED!")
    return {"status": "webhook endpoint reachable", "message": "Configure Twilio to POST here"}


@mcp.custom_route("/twilio-webhook", methods=["POST"])
async def twilio_webhook(request: Request):
    """Handle incoming WhatsApp messages"""
    print("🔥 WEBHOOK CALLED!")
    
    # Parse form data
    form_data = await request.form()
    
    # Extract fields
    Body = form_data.get("Body")
    From = form_data.get("From")
    To = form_data.get("To")
    ListId = form_data.get("ListId")
    ListTitle = form_data.get("ListTitle")
    ButtonText = form_data.get("ButtonText")
    ButtonPayload = form_data.get("ButtonPayload")
    MessageStatus = form_data.get("MessageStatus")
    MessageSid = form_data.get("MessageSid")
    
    print(f"📱 MessageStatus: {MessageStatus}")
    print(f"📱 From: {From}, To: {To}")
    print(f"📱 Body: {Body}")
    print(f"🔍 ListId: {ListId}")
    print(f"🔍 ButtonPayload: {ButtonPayload}")
    print(f"🔍 ButtonText: {ButtonText}")
    
    # Debug: Print all form data
    print("📋 All form data:")
    for key, value in form_data.items():
        print(f"  {key}: {value}")
    
    # If this is just a status callback (not an actual message), ignore it
    if MessageStatus and not Body:
        print("📊 Status callback received, ignoring")
        return JSONResponse({"status": "ok", "message": "Status callback received"})
    
    # Ensure we have From field (Body is optional for button responses)
    if not From:
        print("❌ Missing From field")
        return JSONResponse({"status": "error", "message": "Missing From field"})
    
    # Handle button responses (quick-reply)
    if ButtonPayload:
        parts = ButtonPayload.split("_")
        if len(parts) == 2:
            action, short_id = parts
            if action in ["approve", "deny"]:
                response = "approved" if action == "approve" else "denied"
                response_text = ButtonText or f"{action}_{short_id}"
            else:
                return JSONResponse({"status": "ignored", "reason": "Invalid button payload"})
        else:
            return JSONResponse({"status": "ignored", "reason": "Invalid button payload format"})
    # Handle list-picker responses (fallback)
    elif ListId:
        parts = ListId.split(":")
        if len(parts) == 2:
            action, short_id = parts
            if action in ["approve", "deny"]:
                response = "approved" if action == "approve" else "denied"
                response_text = f"{action}:{short_id}"
            else:
                return JSONResponse({"status": "ignored", "reason": "Invalid list selection"})
        else:
            return JSONResponse({"status": "ignored", "reason": "Invalid list ID format"})
    else:
        # Handle text responses (fallback)
        if not Body:
            print("❌ No body content")
            return JSONResponse({"status": "ignored", "reason": "No body content"})
            
        body = Body.strip().upper()
        
        # Parse response
        if body.startswith("APPROVE "):
            short_id = body.replace("APPROVE ", "").strip()
            response = "approved"
            response_text = body
        elif body.startswith("DENY "):
            short_id = body.replace("DENY ", "").strip()
            response = "denied"
            response_text = body
        else:
            print(f"❌ Invalid format: {body}")
            return JSONResponse({"status": "ignored", "reason": "Invalid format"})
    
    # Update database
    with Session(engine) as session:
        # Extract phone number from From field (remove "whatsapp:" prefix if present)
        from_phone = From.replace("whatsapp:", "") if From and From.startswith("whatsapp:") else From
        
        # Check if request exists and is still pending
        statement = select(ApprovalRequest).where(
            ApprovalRequest.id == short_id,
            ApprovalRequest.phone_number == from_phone
        )
        approval = session.exec(statement).first()
        
        if not approval:
            print(f"❌ Request {short_id} not found")
            return JSONResponse({"status": "error", "reason": "Request not found"})
        
        if approval.status != "pending":
            print(f"❌ Request {short_id} already processed")
            return JSONResponse({"status": "error", "reason": "Request already processed"})
        
        if datetime.utcnow() > approval.expires_at:
            print(f"❌ Request {short_id} expired")
            return JSONResponse({"status": "error", "reason": "Request expired"})
        
        # Update the request
        approval.status = response
        approval.response = response_text
        approval.responded_at = datetime.utcnow()
        session.add(approval)
        session.commit()
        session.refresh(approval)
        
        print(f"✅ Request {short_id} {response}")
        
        request_id = approval.request_id
    
    # Send confirmation message
    if twilio_client:
        if response == "approved":
            confirmation = f"✅ Request {short_id} has been approved."
        else:
            confirmation = f"❌ Request {short_id} has been denied."
        twilio_client.messages.create(
            body=confirmation,
            from_=To,
            to=From
        )
    
    return JSONResponse({
        "status": "success",
        "request_id": request_id,
        "response": response
    })


if __name__ == "__main__":
    
    print("🚀 Starting approval MCP server...")
    print(f"📱 Approval messages will be sent to: {APPROVAL_PHONE or 'NOT CONFIGURED'}")
    print(f"🔧 Twilio configured: {twilio_client is not None}")
    
    if not APPROVAL_PHONE:
        print("⚠️  WARNING: APPROVAL_PHONE not set in environment variables")
    print()
    print("🌐 Server endpoints:")
    print(f"   • MCP: http://localhost:{SERVER_PORT} (FastMCP HTTP server)") 
    print("   • Webhook: POST /twilio-webhook (for Twilio)")
    print("   • Test: GET /twilio-webhook (browser test)")
    print()
    print("📡 Expose webhook with ngrok:")
    print(f"   ngrok http {SERVER_PORT}")
    print()
    print("⚙️  Configure Twilio webhook:")
    print("   Method: POST")
    print("   URL: https://your-ngrok-url.ngrok.io/twilio-webhook")
    print()
    print("💡 To test:")
    print("1. Configure Claude to connect to this server")
    print("2. Ask Claude to request approval for something")
    print("3. Respond to the WhatsApp message")
    print("\n🛑 Press Ctrl+C to stop")
    
    # FastMCP runs with SSE transport
    try:
        mcp.run(transport="sse", host="127.0.0.1", port=SERVER_PORT)
    except Exception as e:
        print(f"❌ Server error: {e}")
        sys.exit(1)