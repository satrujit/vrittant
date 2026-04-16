import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { checkPhone, requestOtp, verifyOtp, resendOtp } from '../services/api';
import styles from './LoginPage.module.css';

/* ── SVG Components ── */

/** Large tilted V watermark for the brand panel */
function VWatermark({ className }) {
  return (
    <svg className={className} viewBox="0 0 320 280" fill="none" xmlns="http://www.w3.org/2000/svg">
      <path
        d="M40 30C80 230 240 230 280 30"
        stroke="#fff"
        strokeWidth="28"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <path
        opacity="0.6"
        d="M80 70C108 210 212 210 240 70"
        stroke="#fff"
        strokeWidth="18"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <path
        opacity="0.3"
        d="M120 110C132 180 188 180 200 110"
        stroke="#fff"
        strokeWidth="10"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

/** Curved V logo — uses `color` prop for stroke, defaults to white */
function VLogo({ className, color = '#fff' }) {
  return (
    <svg className={className} viewBox="80 90 160 130" fill="none" xmlns="http://www.w3.org/2000/svg">
      <path d="M112 122C128 202 192 202 208 122" stroke={color} strokeWidth="19.2" strokeLinecap="round" strokeLinejoin="round"/>
      <path opacity="0.7" d="M128 138C140 186 180 186 192 138" stroke={color} strokeWidth="12.8" strokeLinecap="round" strokeLinejoin="round"/>
      <path opacity="0.4" d="M144 154C148 174 172 174 176 154" stroke={color} strokeWidth="6.4" strokeLinecap="round" strokeLinejoin="round"/>
    </svg>
  );
}

/* ── OTP Input Component ── */

function OTPInput({ value, onChange }) {
  const inputRefs = useRef([]);
  const digits = Array.from({ length: 6 }, (_, i) => value[i] || '');

  const focusBox = useCallback((idx) => {
    if (idx >= 0 && idx < 6) inputRefs.current[idx]?.focus();
  }, []);

  function handleChange(idx, e) {
    const val = e.target.value.replace(/\D/g, '');
    if (!val) return;
    const newDigits = [...digits];
    const chars = val.split('');
    for (let i = 0; i < chars.length && idx + i < 6; i++) {
      newDigits[idx + i] = chars[i];
    }
    onChange(newDigits.join('').slice(0, 6));
    focusBox(Math.min(idx + chars.length, 5));
  }

  function handleKeyDown(idx, e) {
    if (e.key === 'Backspace') {
      e.preventDefault();
      const newDigits = [...digits];
      if (newDigits[idx]) {
        newDigits[idx] = '';
        onChange(newDigits.join(''));
      } else if (idx > 0) {
        newDigits[idx - 1] = '';
        onChange(newDigits.join(''));
        focusBox(idx - 1);
      }
    } else if (e.key === 'ArrowLeft') {
      focusBox(idx - 1);
    } else if (e.key === 'ArrowRight') {
      focusBox(idx + 1);
    }
  }

  function handlePaste(e) {
    e.preventDefault();
    const pasted = e.clipboardData.getData('text').replace(/\D/g, '').slice(0, 6);
    if (pasted) {
      onChange(pasted);
      focusBox(Math.min(pasted.length, 5));
    }
  }

  return (
    <div className={styles.otpGrid}>
      {digits.map((d, i) => (
        <input
          key={i}
          ref={(el) => { inputRefs.current[i] = el; }}
          className={styles.otpBox}
          type="text"
          inputMode="numeric"
          maxLength={1}
          value={d.trim()}
          placeholder="-"
          autoFocus={i === 0}
          onChange={(e) => handleChange(i, e)}
          onKeyDown={(e) => handleKeyDown(i, e)}
          onPaste={handlePaste}
        />
      ))}
    </div>
  );
}

/* ── Mask phone for display ── */

function maskPhone(phone) {
  if (!phone || phone.length < 4) return phone;
  const last2 = phone.slice(-2);
  const prefix = phone.slice(0, 4);
  return `${prefix} ${'*'.repeat(Math.max(0, phone.length - 6))} **${last2}`;
}

/* ── Main LoginPage ── */

function LoginPage() {
  const { login } = useAuth();
  const navigate = useNavigate();

  const [step, setStep] = useState('phone'); // 'phone' | 'otp'
  const [phone, setPhone] = useState('');
  const [otp, setOtp] = useState('');
  const [reqId, setReqId] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  async function handleSendOTP(e) {
    e.preventDefault();
    setError('');
    setLoading(true);
    try {
      // Check if phone is registered first
      await checkPhone(phone);

      // Send OTP via backend (goes through Cloud Run's whitelisted IP)
      const data = await requestOtp(phone);
      setReqId(data.req_id || '');
      setStep('otp');
    } catch (err) {
      console.error('Send OTP error:', err);
      const msg = typeof err === 'string' ? err : err?.message || '';
      if (msg.includes('404') || msg.includes('not registered')) {
        setError('This phone number is not registered. Contact admin for access.');
      } else if (msg.includes('403') || msg.includes('deactivated')) {
        setError('Your account has been deactivated. Contact admin.');
      } else {
        setError(msg || 'Failed to send OTP. Please try again.');
      }
    } finally {
      setLoading(false);
    }
  }

  async function handleVerifyOTP(e) {
    e.preventDefault();
    setError('');
    setLoading(true);
    try {
      // Verify OTP via backend → returns JWT directly
      const data = await verifyOtp(phone, otp, reqId);
      await login(data.access_token);
      navigate('/');
    } catch (err) {
      console.error('OTP verify error:', err);
      const msg = typeof err === 'string' ? err : err?.message || '';
      if (msg.includes('404') || msg.includes('not registered')) {
        setError('Phone number not registered. Contact admin for access.');
      } else if (msg.includes('403') || msg.includes('deactivated')) {
        setError('Account is deactivated. Contact admin.');
      } else {
        setError('Invalid OTP code. Please check and try again.');
      }
    } finally {
      setLoading(false);
    }
  }

  function handleBack() {
    setStep('phone');
    setOtp('');
    setReqId('');
    setError('');
  }

  async function handleResendOTP() {
    setError('');
    setLoading(true);
    try {
      const data = await resendOtp(phone, reqId);
      if (data.req_id) setReqId(data.req_id);
    } catch (err) {
      console.error('Resend error:', err);
      setError('Failed to resend OTP. Please try again.');
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className={styles.page}>
      {/* ── Left: Brand Panel ── */}
      <div className={styles.brandPanel}>
        <VWatermark className={styles.watermark} />
        <div className={styles.brandContent}>
          <VLogo className={styles.brandLogo} />
          <div className={styles.tagline}>
            {step === 'phone' ? 'Your story, simplified.' : 'The Narrative Wave'}
          </div>
          <div className={styles.subtitle}>
            {step === 'phone'
              ? 'Experience minimalist, AI-led reporting designed for a digital-first world.'
              : 'Where every story finds its voice.'}
          </div>
        </div>
      </div>

      {/* ── Right: Form Panel ── */}
      <div className={styles.formPanel}>
        <div className={styles.card}>
          {/* Vrittant wordmark with curved V logo */}
          <div className={styles.wordmark}>
            <VLogo className={styles.wordmarkLogo} color="#fa6c38" />
            <div className={styles.wordmarkTextRow}>
              <span className={styles.wordmarkV}>V</span>
              <span className={styles.wordmarkText}>rittant</span>
            </div>
          </div>

          {step === 'phone' ? (
            <>
              <h1 className={styles.title}>Welcome back</h1>
              <p className={styles.subtitleText}>
                Enter your mobile number to receive a one-time verification code
              </p>

              {error && <p className={styles.error}>{error}</p>}

              <form className={styles.form} onSubmit={handleSendOTP}>
                <div className={styles.fieldGroup}>
                  <label className={styles.label}>Mobile Number</label>
                  <div className={styles.phoneInputWrap}>
                    <span className={styles.phonePrefix}>+91</span>
                    <input
                      className={styles.phoneInput}
                      type="tel"
                      placeholder="000 000 0000"
                      value={phone.startsWith('+91') ? phone.slice(3) : phone}
                      onChange={(e) => {
                        const val = e.target.value.replace(/[^\d\s]/g, '');
                        setPhone('+91' + val.replace(/\s/g, ''));
                      }}
                      required
                      autoFocus
                    />
                  </div>
                </div>
                <button
                  className={styles.primaryBtn}
                  type="submit"
                  disabled={loading || phone.replace(/\D/g, '').length < 12}
                >
                  {loading ? '...' : 'Send OTP'}
                  {!loading && (
                    <svg className={styles.btnIcon} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                      <path d="M21 2l-2 2m-7.61 7.61a5.5 5.5 0 1 1-7.778 7.778 5.5 5.5 0 0 1 7.777-7.777zm0 0L15.5 7.5m0 0l3 3L22 7l-3-3m-3.5 3.5L19 4" />
                    </svg>
                  )}
                </button>
              </form>

              <p className={styles.terms}>
                By continuing, you agree to our Terms of Service &amp; Privacy Policy
              </p>
            </>
          ) : (
            <>
              <h1 className={styles.title}>Verify OTP</h1>
              <p className={styles.phoneMasked}>
                Enter the 6-digit code sent to <strong>{maskPhone(phone)}</strong>
              </p>

              {error && <p className={styles.error}>{error}</p>}

              <form className={styles.form} onSubmit={handleVerifyOTP}>
                <OTPInput value={otp} onChange={setOtp} />

                <button
                  className={styles.primaryBtn}
                  type="submit"
                  disabled={loading || otp.replace(/\D/g, '').length < 6}
                >
                  {loading ? '...' : 'Verify OTP'}
                  {!loading && (
                    <svg className={styles.btnIcon} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                      <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14" />
                      <polyline points="22 4 12 14.01 9 11.01" />
                    </svg>
                  )}
                </button>
              </form>

              <div className={styles.resendRow}>
                Didn&apos;t receive the code?{' '}
                <button
                  type="button"
                  className={styles.resendLink}
                  onClick={handleResendOTP}
                  disabled={loading}
                >
                  Resend OTP
                </button>
              </div>

              <button
                type="button"
                className={styles.backLink}
                onClick={handleBack}
              >
                &larr; Back to phone number
              </button>
            </>
          )}
        </div>
      </div>
    </div>
  );
}

export default LoginPage;
