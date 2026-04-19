"""
OTP provider switch.

Selects the active mobile-OTP backend at import time based on
``settings.OTP_PROVIDER``. Routes call ``send_otp / verify_otp / resend_otp``
from this module without caring which vendor is on the other end.

- ``twilio`` (default): Twilio Verify. No DLT registration needed. ~₹4–5/OTP.
- ``msg91``: legacy MSG91 Widget API. Cheaper but vulnerable to IP-block traps.

Web (verifyAccessToken) still goes directly through MSG91 — it's tied to the
JS widget and not part of this switch.
"""

from ..config import settings

if settings.OTP_PROVIDER == "msg91":
    from .msg91 import send_otp, verify_otp, resend_otp  # noqa: F401
else:
    from .twilio_verify import send_otp, verify_otp, resend_otp  # noqa: F401
