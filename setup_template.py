#!/usr/bin/env python3
"""
Script to create Twilio WhatsApp content template for approval requests
"""

import os
import json
import sys
from dotenv import load_dotenv
from twilio.rest import Client

def load_template_config():
    """Load template configuration from JSON file"""
    config_file = 'template_config.json'
    
    if not os.path.exists(config_file):
        print(f"❌ Error: {config_file} not found")
        sys.exit(1)
    
    try:
        with open(config_file, 'r') as f:
            return json.load(f)
    except Exception as e:
        print(f"❌ Error loading {config_file}: {str(e)}")
        sys.exit(1)

def create_template():
    """Create the Twilio content template and return the SID"""
    
    # Load environment variables
    load_dotenv()
    
    account_sid = os.getenv('TWILIO_ACCOUNT_SID')
    auth_token = os.getenv('TWILIO_AUTH_TOKEN')
    
    if not account_sid or not auth_token:
        print("❌ Error: TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN must be set in .env file")
        sys.exit(1)
    
    # Load template configuration
    template_config = load_template_config()
    
    try:
        client = Client(account_sid, auth_token)
        
        print("🔧 Creating Twilio content template...")
        
        # Create the content template using the configuration
        content = client.content.v1.contents.create(**template_config)
        
        print(f"✅ Template created successfully!")
        print(f"📋 Template SID: {content.sid}")
        print(f"📝 Friendly Name: {content.friendly_name}")
        
        return content.sid
        
    except Exception as e:
        print(f"❌ Error creating template: {str(e)}")
        sys.exit(1)

def update_env_file(template_sid):
    """Update the .env file with the new template SID"""
    
    env_file = '.env'
    
    if not os.path.exists(env_file):
        print(f"❌ Error: {env_file} file not found")
        return False
    
    try:
        # Read current .env file
        with open(env_file, 'r') as f:
            lines = f.readlines()
        
        # Update or add TWILIO_CONTENT_SID
        updated = False
        for i, line in enumerate(lines):
            if line.startswith('TWILIO_CONTENT_SID='):
                lines[i] = f'TWILIO_CONTENT_SID={template_sid}\n'
                updated = True
                break
        
        # If not found, add it
        if not updated:
            lines.append(f'TWILIO_CONTENT_SID={template_sid}\n')
        
        # Write back to file
        with open(env_file, 'w') as f:
            f.writelines(lines)
        
        print(f"✅ Updated {env_file} with new template SID")
        return True
        
    except Exception as e:
        print(f"❌ Error updating {env_file}: {str(e)}")
        return False

def main():
    """Main function"""
    print("🚀 Twilio WhatsApp Template Setup")
    print("=" * 40)
    
    # Create the template
    template_sid = create_template()
    
    # Update .env file
    if update_env_file(template_sid):
        print("\n🎉 Setup complete!")
        print("\nNext steps:")
        print("1. Restart your approval server if it's running")
        print("2. Test the approval system with Claude")
        print(f"\n💡 Your template SID is: {template_sid}")
    else:
        print(f"\n⚠️  Template created but failed to update .env file")
        print(f"   Please manually add this line to your .env file:")
        print(f"   TWILIO_CONTENT_SID={template_sid}")

if __name__ == "__main__":
    main()