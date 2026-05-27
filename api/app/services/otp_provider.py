"""
OTP provider — Twilio Verify.

Mobile OTP (send / verify / resend) uses Twilio Verify.
Web login uses MSG91 Widget (verify_access_token in msg91.py).
"""

from .twilio_verify import send_otp, verify_otp, resend_otp  # noqa: F401
