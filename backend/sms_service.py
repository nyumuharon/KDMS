"""
sms_service.py — Africa's Talking SMS integration for KDMS.
Reads AFRICASTALKING_USERNAME from .env — set to your real username for live SMS,
or leave as "sandbox" for free testing.
"""
import os
from dotenv import load_dotenv

load_dotenv()

AT_USERNAME = os.getenv("AFRICASTALKING_USERNAME", "sandbox").strip()
AT_API_KEY  = os.getenv("AFRICASTALKING_API_KEY", "").strip()


def _get_sms_client():
    if not AT_API_KEY:
        return None
    try:
        import africastalking
        africastalking.initialize(AT_USERNAME, AT_API_KEY)
        return africastalking.SMS
    except Exception as e:
        print(f"[SMS] Init error: {e}")
        return None


async def send_bulk_sms(phone_numbers: list[str], message: str) -> dict:
    """
    Send bulk SMS via Africa's Talking.
    - Sandbox (AFRICASTALKING_USERNAME=sandbox): free, no real SMS sent
    - Production (real username): real SMS at ~KES 0.80/msg
    Returns: {sent, failed, sandbox, mock}
    """
    if not phone_numbers:
        return {"sent": 0, "failed": 0, "sandbox": True, "error": "No recipients"}

    # Normalise to E.164 (+254...)
    formatted = []
    for num in phone_numbers:
        n = num.strip().replace(" ", "")
        if n.startswith("07") or n.startswith("01"):
            n = "+254" + n[1:]
        elif n.startswith("254") and not n.startswith("+"):
            n = "+" + n
        if n:
            formatted.append(n)

    sms = _get_sms_client()
    if not sms:
        # No API key configured — log and return mock result
        print(f"[SMS] No API key — logged {len(formatted)} messages (not sent)")
        return {"sent": len(formatted), "failed": 0, "sandbox": True, "mock": True}

    try:
        resp = sms.send(message, formatted, sender_id="NDMA-KE")
        recipients = resp.get("SMSMessageData", {}).get("Recipients", [])
        sent   = sum(1 for r in recipients if r.get("status") == "Success")
        failed = len(formatted) - sent
        is_sandbox = AT_USERNAME == "sandbox"
        print(f"[SMS] {'Sandbox' if is_sandbox else 'LIVE'} — sent={sent}, failed={failed}")
        return {
            "sent":    sent,
            "failed":  failed,
            "sandbox": is_sandbox,
            "live":    not is_sandbox,
        }
    except Exception as e:
        print(f"[SMS] Send error: {e}")
        return {"sent": 0, "failed": len(formatted), "error": str(e)}
