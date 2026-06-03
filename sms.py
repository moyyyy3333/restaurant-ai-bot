"""SMS outreach via Twilio — alternative to email for restaurant demo links"""
import os, sys
sys.path.insert(0, os.path.dirname(__file__))

from config import TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_FROM_NUMBER, USE_TWILIO
from twilio.rest import Client
import db

def send_sms_outreach(phone: str, restaurant_name: str, demo_url: str, lead_id: int) -> dict:
    """Send SMS with demo link to restaurant owner"""
    if not USE_TWILIO:
        return {"success": False, "error": "Twilio not configured"}
    
    client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
    
    message_body = (
        f"👋 Hi! A custom website was built for {restaurant_name}. "
        f"View your demo here (expires in 72h): {demo_url}\n\n"
        f"Want this site live? Reply YES or visit the link to purchase."
    )
    
    try:
        message = client.messages.create(
            body=message_body,
            from_=TWILIO_FROM_NUMBER,
            to=phone
        )
        
        # Log in database
        db.get_db().execute(
            "UPDATE leads SET sms_sent = 1, sms_sid = ? WHERE id = ?",
            (message.sid, lead_id)
        )
        db.get_db().commit()
        
        return {"success": True, "sid": message.sid, "status": message.status}
    
    except Exception as e:
        return {"success": False, "error": str(e)}

def check_sms_replies() -> list:
    """Check for incoming SMS replies (YES = interested)"""
    if not USE_TWILIO:
        return []
    
    client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
    
    # Get recent incoming messages
    messages = client.messages.list(
        to=TWILIO_FROM_NUMBER,
        limit=20
    )
    
    replies = []
    for msg in messages:
        body = msg.body.strip().upper()
        if body in ("YES", "Y", "YES PLEASE", "INTERESTED"):
            # Find which lead this phone belongs to
            lead = db.get_db().execute(
                "SELECT id, name, restaurant FROM leads WHERE phone = ? AND sms_sent = 1",
                (msg.from_,)
            ).fetchone()
            
            if lead:
                replies.append({
                    "lead_id": lead["id"],
                    "name": lead["name"],
                    "restaurant": lead["restaurant"],
                    "phone": msg.from_,
                    "message": msg.body,
                    "timestamp": msg.date_sent.isoformat() if hasattr(msg.date_sent, 'isoformat') else str(msg.date_sent)
                })
    
    return replies
