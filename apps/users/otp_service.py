import secrets
import logging
from django.core.cache import cache

logger = logging.getLogger(__name__)

OTP_EXPIRE_SECONDS = 120    # Kod 2 daqiqa amal qiladi
OTP_COOLDOWN_SECONDS = 60   # Qayta yuborishdan oldin kutish yani 60 soniya ichida faqat 1 marta kod yuborishi mumkin
MAX_VERIFY_ATTEMPTS = 5     # Noto'g'ri urinishlar limiti


def _otp_key(phone: str) -> str:
    return f"otp:{phone}"


def _cooldown_key(phone: str) -> str:
    return f"otp_cooldown:{phone}"


def _attempts_key(phone: str) -> str:
    return f"otp_attempts:{phone}"


def generate_otp(phone: str) -> str | None:
    """
    Yangi OTP yaratadi, Redis ga saqlaydi.
    Cooldown davomida None qaytaradi.
    secrets.randbelow() — kriptografik tasodifiy son.
    """
    if cache.get(_cooldown_key(phone)):
        return None

    # 100000–999999 oralig'ida tasodifiy 6 xonali son yasab beradi
    code = str(secrets.randbelow(900_000) + 100_000)

    cache.set(_otp_key(phone), code, timeout=OTP_EXPIRE_SECONDS)
    cache.set(_cooldown_key(phone), True, timeout=OTP_COOLDOWN_SECONDS)
    # Yangi kod yaratilganda urinishlar hisoblagichini tozalaydi
    cache.delete(_attempts_key(phone))

    logger.info(f"OTP yuborildi: ...{phone[-4:]}")
    return code


def verify_otp(phone: str, code: str) -> bool:
    """
    OTP ni tekshiradi.
    MAX_VERIFY_ATTEMPTS dan oshsa kod bekor qilinadi.
    To'g'ri bo'lsa Redis dan o'chiradi — bir martalik.
    """
    attempts = cache.get(_attempts_key(phone), 0)

    if attempts >= MAX_VERIFY_ATTEMPTS:
        # Kod bloklanganini bilish uchun uni o'chiramiz
        cache.delete(_otp_key(phone))
        logger.warning(f"OTP bruteforce bloklandi: ...{phone[-4:]}")
        return False

    saved_code = cache.get(_otp_key(phone))

    if not saved_code or saved_code != code:
        cache.set(_attempts_key(phone), attempts + 1, timeout=OTP_EXPIRE_SECONDS)
        logger.warning(
            f"Noto'g'ri OTP: ...{phone[-4:]}, urinish {attempts + 1}/{MAX_VERIFY_ATTEMPTS}"
        )
        return False

    cache.delete(_otp_key(phone))
    cache.delete(_cooldown_key(phone))
    cache.delete(_attempts_key(phone))
    return True


def get_remaining_seconds(phone: str) -> int:
    try:
        ttl = cache.ttl(_cooldown_key(phone))
        return max(ttl, 0)
    except AttributeError:
        return OTP_COOLDOWN_SECONDS


def is_blocked(phone: str) -> bool:
    """Telefon raqami bruteforce tufayli bloklanganmi? shuni tekshiradi"""
    return cache.get(_attempts_key(phone), 0) >= MAX_VERIFY_ATTEMPTS
