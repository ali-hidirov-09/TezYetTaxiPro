import logging
import requests
from django.conf import settings

logger = logging.getLogger(__name__)


def send_otp_sms(phone: str, code: str) -> bool:
    """
    Infobip orqali OTP SMS yuboradi.
    SMS_SKIP_IN_DEV=True bo'lsa console ga chiqaradi.
    """
    masked = f"...{phone[-4:]}"

    if getattr(settings, "SMS_SKIP_IN_DEV", False):
        logger.warning(f"[DEV] SMS skip. Tel: {masked} | OTP: {code}")
        return True

    url = f"https://{settings.INFOBIP_BASE_URL}/sms/2/text/advanced"
    headers = {
        "Authorization": f"App {settings.INFOBIP_API_KEY}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    payload = {
        "messages": [
            {
                "destinations": [{"to": phone}],
                "from": settings.INFOBIP_SENDER,
                "text": f"TezYet: Tasdiqlash kodingiz {code}. Kod 2 daqiqa amal qiladi.",
            }
        ]
    }

    try:
        response = requests.post(url, json=payload, headers=headers, timeout=10)
        response.raise_for_status()
        logger.info(f"SMS yuborildi: {masked}")
        return True
    except requests.RequestException as e:
        logger.error(f"SMS xatosi ({masked}): {e}")
        return False
