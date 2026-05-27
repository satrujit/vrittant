"""
OTP provider switch — select backend via OTP_PROVIDER env var.

- "msg91": MSG91 SendOTP API (~₹0.25/OTP)
- "twilio" (default): Twilio Verify (~₹4/OTP)
"""

from ..config import settings

if settings.OTP_PROVIDER == "msg91":
    from .msg91 import send_otp, verify_otp, resend_otp  # noqa: F401
else:
    from .twilio_verify import send_otp, verify_otp, resend_otp  # noqa: F401
