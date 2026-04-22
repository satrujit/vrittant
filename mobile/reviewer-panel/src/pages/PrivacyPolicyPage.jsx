export default function PrivacyPolicyPage() {
  return (
    <div className="min-h-screen bg-white">
      <div className="mx-auto max-w-3xl px-6 py-16">
        <div className="mb-8 flex items-center gap-3">
          <svg width="40" height="40" viewBox="0 0 32 32" fill="none" xmlns="http://www.w3.org/2000/svg" className="rounded-lg">
            <rect width="32" height="32" rx="8" fill="#FA6C38"/>
            <path d="M8 9C12 25 20 25 24 9" stroke="white" strokeWidth="4" strokeLinecap="round" strokeLinejoin="round"/>
            <path opacity="0.7" d="M11 13C13.5 23 18.5 23 21 13" stroke="white" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"/>
            <path opacity="0.4" d="M14 17C14.8 21 17.2 21 18 17" stroke="white" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
          </svg>
          <span className="text-xl font-semibold text-gray-900">Vrittant</span>
        </div>

        <h1 className="mb-2 text-3xl font-bold text-gray-900">Privacy Policy</h1>
        <p className="mb-10 text-sm text-gray-500">Last updated: March 3, 2026</p>

        <div className="space-y-8 text-gray-700 leading-relaxed">
          <section>
            <h2 className="mb-3 text-lg font-semibold text-gray-900">1. Introduction</h2>
            <p>
              Vrittant (&quot;we&quot;, &quot;our&quot;, or &quot;us&quot;) is a newsroom productivity app operated by AttentionStack. This Privacy Policy explains how we collect, use, and protect information when you use the Vrittant mobile application and web platform (collectively, the &quot;Service&quot;).
            </p>
          </section>

          <section>
            <h2 className="mb-3 text-lg font-semibold text-gray-900">2. Information We Collect</h2>
            <h3 className="mb-2 font-medium text-gray-800">Account Information</h3>
            <p className="mb-3">When your organization creates an account for you, we collect your name, phone number, and organizational role (reporter or editor).</p>

            <h3 className="mb-2 font-medium text-gray-800">Content You Create</h3>
            <p className="mb-3">We store news stories, articles, photos, and audio recordings that you create through the app. This content is associated with your organization&apos;s account.</p>

            <h3 className="mb-2 font-medium text-gray-800">Device Permissions</h3>
            <ul className="ml-6 list-disc space-y-1">
              <li><strong>Microphone:</strong> Used for voice-to-text story dictation. Audio is sent to our servers for transcription and is not stored after processing.</li>
              <li><strong>Camera:</strong> Used to capture photos of news events or newspaper clippings. Photos are uploaded to your organization&apos;s storage.</li>
              <li><strong>Internet:</strong> Required for syncing stories, transcription, and OCR processing.</li>
            </ul>
          </section>

          <section>
            <h2 className="mb-3 text-lg font-semibold text-gray-900">3. How We Use Your Information</h2>
            <ul className="ml-6 list-disc space-y-1">
              <li>To provide and maintain the Service</li>
              <li>To process voice recordings into text via speech-to-text</li>
              <li>To extract text from photos via optical character recognition (OCR)</li>
              <li>To enable editorial review workflows within your organization</li>
              <li>To generate translations and summaries of news content using AI</li>
            </ul>
          </section>

          <section>
            <h2 className="mb-3 text-lg font-semibold text-gray-900">4. Third-Party Services</h2>
            <p>
              We use trusted third-party service providers for cloud hosting, data storage, authentication, AI-powered speech and language processing, and push notifications. These providers process data on our behalf under strict contractual obligations to protect your information. Data shared with these providers is limited to what is necessary to deliver the Service.
            </p>
          </section>

          <section>
            <h2 className="mb-3 text-lg font-semibold text-gray-900">5. Data Storage &amp; Security</h2>
            <p>
              Your data is stored on secure cloud servers. We use industry-standard encryption for data in transit (TLS/SSL) and implement access controls to protect your information. Only members of your organization can access your organization&apos;s content.
            </p>
          </section>

          <section>
            <h2 className="mb-3 text-lg font-semibold text-gray-900">6. Data Retention</h2>
            <p>
              We retain your content for as long as your organization&apos;s account is active. When an organization account is terminated, associated data is deleted within 90 days.
            </p>
          </section>

          <section>
            <h2 className="mb-3 text-lg font-semibold text-gray-900">7. Your Rights</h2>
            <p>You have the right to:</p>
            <ul className="ml-6 list-disc space-y-1">
              <li>Access the personal data we hold about you</li>
              <li>Request correction of inaccurate data</li>
              <li>Request deletion of your data</li>
              <li>Withdraw consent for data processing</li>
            </ul>
            <p className="mt-3">To exercise these rights, contact your organization administrator or reach out to us directly.</p>
          </section>

          <section>
            <h2 className="mb-3 text-lg font-semibold text-gray-900">8. Children&apos;s Privacy</h2>
            <p>
              The Service is not intended for use by individuals under the age of 18. We do not knowingly collect personal information from children.
            </p>
          </section>

          <section>
            <h2 className="mb-3 text-lg font-semibold text-gray-900">9. Changes to This Policy</h2>
            <p>
              We may update this Privacy Policy from time to time. We will notify users of any material changes through the app or by other means.
            </p>
          </section>

          <section>
            <h2 className="mb-3 text-lg font-semibold text-gray-900">10. Contact Us</h2>
            <p>
              If you have questions about this Privacy Policy, please contact us at:
            </p>
            <p className="mt-2 font-medium">
              AttentionStack<br />
              Email: hello@attentionstack.ai
            </p>
          </section>
        </div>

        <div className="mt-16 border-t border-gray-200 pt-6 text-center text-sm text-gray-400">
          &copy; {new Date().getFullYear()} AttentionStack. All rights reserved.
        </div>
      </div>
    </div>
  );
}
