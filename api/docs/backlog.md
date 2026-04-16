# Backlog

## Security

- [ ] **Phone enumeration**: `/check-phone` returns 404 vs 200, letting attackers probe registered numbers. Fix: remove `/check-phone`, let `/request-otp` return a generic error for unregistered numbers.
- [ ] **OTP spam**: If attacker knows a registered number, they can start new Widget sessions repeatedly. MSG91 widget limits resends per session (2 max, 60s cooldown) but not across sessions. Consider DB-based per-phone cooldown.
- [ ] **Captcha bypass**: MSG91 captcha only protects the web widget; backend API calls via authkey bypass it. Consider adding server-side captcha verification for mobile OTP requests.
- [ ] **Long-lived JWT**: 90-day token expiry with no revocation. Consider shorter expiry + refresh tokens, or a token blacklist table.
