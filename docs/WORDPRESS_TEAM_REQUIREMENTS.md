# Vrittant → WordPress Integration: Setup Requirements

**For:** WordPress site administrator at the publishing org (e.g. Pragativadi).
**From:** Vrittant editorial-system team.
**Goal:** Vrittant will auto-translate approved Odia stories to English and create them on your WP site as **drafts**. Your team reviews each draft in the WP admin and decides Publish / Trash. Vrittant doesn't touch posts after that.

Once the items below are ready, share them with us and we'll switch the integration on. Until then it's idle on our side — no changes to your WP site, no traffic.

---

## 1. WordPress version + plugins

| Requirement | Reason |
|---|---|
| WordPress **5.6 or newer** | Application Passwords are built in; no plugin needed. Most modern WP installs already qualify — just confirm with **Dashboard → Updates**. |
| **REST API enabled** (default) | We push posts via `POST /wp-json/wp/v2/posts`. If your hosting or a security plugin (Wordfence, Sucuri, iThemes) blocks the REST API, allowlist the URL `/wp-json/wp/v2/*` for the IP we'll send from. |
| (Recommended) **Yoast SEO or Rank Math** | Optional. We populate `excerpt` and category; Yoast/Rank Math can use those to fill SEO meta automatically. |
| (Optional) **Disable XML-RPC** | Not used by us. Safe to keep off. |

---

## 2. Create a dedicated bot user

We need a WP user account that Vrittant authenticates as. **Don't use a real human account** — separating it lets you see clearly which posts came from Vrittant vs. people, and you can revoke access in one step if needed.

In **Users → Add New**:

| Field | Suggested value |
|---|---|
| Username | `vrittant-bot` |
| Email | `vrittant-bot@<your-domain>` (any inbox you control) |
| Role | **Author** (can write & upload media; cannot publish — perfect for our "always create as draft" model). If you want the bot to be able to set a featured image without restriction, **Editor** also works. |
| Password | Set anything strong; Vrittant doesn't use this. |

Send us back: **the bot username** (e.g. `vrittant-bot`).

---

## 3. Generate an Application Password

In WP, log in **as the bot user** (or as an admin who can edit the bot user) → **Profile** → scroll to **Application Passwords** → enter "Vrittant API" as the name → click **Add New Application Password**.

WP shows a 24-character password like `abcd EFGH ijkl MNOP qrst UVWX`. **Copy it once — WP doesn't show it again.**

Send us back: **the application password** (treat it like a secret; we'll store it in our Secret Manager).

If your WP install doesn't show the Application Passwords section, see [the WP docs](https://wordpress.org/documentation/article/application-passwords/) — most likely the site has them disabled in `wp-config.php` (`define('WP_APPLICATION_PASSWORDS_AVAILABLE', false);`) or via a security plugin.

---

## 4. Decide categories and send us the IDs

Vrittant tags each story with one of: `crime`, `politics`, `sports`, `governance`, `entertainment`, `accident`, `science`, `general`. We need to know which **WP category ID** each one maps to on your site.

In WP: **Posts → Categories**. Either:
- **(Easiest)** Create one category per Vrittant key (e.g. WP category named "Crime"), then hover the row — the URL shows `tag_ID=5`. Send us the number.
- **(If you have existing categories)** Map our keys to your existing categories. E.g. you may already have "Government / Administration" → that becomes the target for our `governance` key.

Send us back a table like:

| Vrittant category | WP category name | WP category ID |
|---|---|---|
| crime | Crime | 5 |
| politics | Politics | 8 |
| sports | Sports | 14 |
| governance | Government | 17 |
| entertainment | Entertainment | 21 |
| accident | Accident | 23 |
| science | Science & Tech | 24 |
| general | General | 26 |

If you don't want to map all of them, just send the ones you do — others will be created with no category.

---

## 5. Default author for the post byline

Each post needs a WP **author** (who shows in the byline). Two options:

- **(A) Single bot byline:** the post is authored by the `vrittant-bot` user. Simplest. The byline reads "Vrittant Bot" or whatever display name you set on the bot. **We'll need the WP user ID** of the bot — you can find it by clicking **Users → All Users**, hovering on the bot row, and reading the URL: `user_id=12`. Send us **12**.
- **(B) Per-reporter mapping:** we map each Vrittant reporter to a real WP user (so the WP byline matches the reporter's name). This is more setup — requires creating a WP user for every reporter (47 currently) and mapping them. **Not recommended** for the initial rollout; we can move to this later.

Send us back: **single bot author** (recommended for now) **plus the WP user ID** of the bot.

---

## 6. Post status & workflow

By default, every post Vrittant creates is `status=draft`. Your team:
- Sees them in **Posts → Drafts** (or **Posts** filtered by Drafts).
- Edits / formats / sets featured image / approves SEO meta.
- Clicks **Publish** when ready.
- Or **Move to Trash** to reject.

**Once you click Publish or Move to Trash, Vrittant stops touching the post.** If the Vrittant editor later edits the story content, our side detects that you've taken ownership and skips the update. The Vrittant editor sees a chip saying "Live on website" with a link to the published URL.

If you need a different default — e.g. `pending` (review) status instead of `draft` — let us know and we'll switch. We don't recommend `publish` (auto-go-live) for v1.

---

## 7. Featured image handling

If a Vrittant story has at least one photo, we upload the first photo to WP via `POST /wp-json/wp/v2/media` and attach it as `featured_media`. Two things to know:

- **Image size limit**: WP's default is the value of `upload_max_filesize` and `post_max_size` in PHP, typically 2–8 MB. Vrittant story photos are usually under 2 MB, but please confirm. If we try to upload a file over your limit, the post is still created without a featured image and the editor sees a `wp_push_error` — not a failure.
- **Featured-image plugins**: WP needs the **Set Featured Image** capability on the bot user's role (Author and Editor have it by default). If your site has a custom role plugin that strips this, please add it back.

---

## 8. Network / firewall

Our API lives at `https://vrittant-api-829303072442.asia-south1.run.app` (production). It uses **Cloud Run's egress**, which **doesn't have a static IP** — outbound traffic comes from a Google IP pool that rotates. So:

- **Don't IP-allowlist us** (we'd break next time the IP rotates).
- **Allow basic-auth-over-HTTPS to `/wp-json/*`** for any user-agent — that's how WP REST API works by default; Cloudflare / hosting WAF may block it as "API abuse" until you whitelist the path.

If you're behind Cloudflare with strict bot management, allowlist requests with header `Authorization: Basic …` to URLs starting `/wp-json/wp/v2/`.

---

## 9. What you'll send back

A single message with the items below is enough to flip the integration on. Mark anything you can't / won't provide and we'll work around it.

```
[ ] WordPress base URL: https://________________
[ ] Bot WP username:                 ___________________
[ ] Application Password (24 chars): ___________________
[ ] Bot WP user ID (number):         ___________________
[ ] Category map (table from §4)
[ ] Default post status (draft / pending):  ___________________
[ ] Approximate WP upload size limit (MB):  ___________________
[ ] WP version:                              ___________________
[ ] Any plugins blocking REST or basic auth: ___________________
```

We'll store the password in our Secret Manager (encrypted at rest, never in source). If you need to rotate it, generate a new Application Password, send us the new value, and we'll roll the secret in <5 minutes — no downtime.

---

## 10. What we provide on our side (no action from you needed)

- Translation: every Odia story is translated to English by Anthropic Claude before posting. We pass title, body (with paragraph breaks), excerpt.
- Idempotency: if our cron retries a push, the existing draft is updated, never duplicated.
- Lifecycle mirror: when you Publish, the live URL appears on the Vrittant story view; when you Trash, Vrittant marks it as rejected.
- Cost: WP-side work is free; the translation cost (~₹0.50 per story) is on our Anthropic bill.
- Volume: at current pace, ~30 stories/day; expected ~150–300/day at full reporter rollout.

Reach out with any questions.
