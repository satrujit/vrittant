"""Seed layout templates for org-pragativadi based on real Pragativadi newspaper references."""

import uuid
from datetime import datetime, timezone

import psycopg2

DB_HOST = "127.0.0.1"
DB_PORT = 9471
DB_USER = "postgres"
DB_PASS = "KEispmgwm2q8ZO85NOudsp2KZU1SpRVJ"
DB_NAME = "vrittant"
ORG_ID = "org-pragativadi"

# ─── Template 1: Photo-Top News (345242 / 345300 style) ──────────────────
# Large image on top, bold red/maroon Odia headline, location line, 3-column body text
PHOTO_TOP_NEWS = """<!DOCTYPE html>
<html lang="or">
<head>
<meta charset="UTF-8">
<title>Photo-Top News</title>
<style>
@import url('https://fonts.googleapis.com/css2?family=Noto+Serif+Odia:wght@400;700;900&family=Noto+Sans+Odia:wght@400;600;700&display=swap');

* { margin: 0; padding: 0; box-sizing: border-box; }

body {
  max-width: 580px;
  margin: 0 auto;
  background: #fff;
  font-family: 'Noto Serif Odia', serif;
  color: #1a1a1a;
  padding: 0;
}

.article-image {
  width: 100%;
  aspect-ratio: 4/3;
  object-fit: cover;
  display: block;
  border-bottom: 3px solid #8B0000;
}

.content {
  padding: 14px 16px 20px;
}

h1 {
  font-family: 'Noto Sans Odia', sans-serif;
  font-size: 32px;
  font-weight: 900;
  line-height: 1.25;
  color: #8B0000;
  margin-bottom: 8px;
  letter-spacing: -0.3px;
}

.location-line {
  font-family: 'Noto Sans Odia', sans-serif;
  font-size: 12px;
  color: #333;
  margin-bottom: 12px;
  padding-bottom: 8px;
  border-bottom: 1px solid #ddd;
}

.location-line .marker {
  display: inline-block;
  width: 8px;
  height: 8px;
  background: #333;
  margin-right: 4px;
  vertical-align: middle;
}

.location-line .source {
  color: #666;
  font-size: 11px;
}

.body-text {
  font-size: 13.5px;
  line-height: 1.7;
  text-align: justify;
  column-count: 3;
  column-gap: 16px;
  column-rule: 1px solid #e0e0e0;
}

.body-text p { margin-bottom: 8px; }

@media print {
  body { max-width: 100%; padding: 0; }
}
</style>
</head>
<body>
  <img class="article-image" src="https://placehold.co/580x435/e8e8e8/999?text=Story+Image" alt="Article image">
  <div class="content">
    <h1>ଏଠାରେ ମୁଖ୍ୟ ଶୀର୍ଷକ ଲେଖାଯିବ</h1>
    <div class="location-line">
      <span class="marker"></span> ସ୍ଥାନ, ତାରିଖ <span class="source">(ପ୍ରତିନିଧି)</span>
    </div>
    <div class="body-text">
      <p>ଏଠାରେ ଖବରର ପ୍ରଥମ ଅନୁଚ୍ଛେଦ ଲେଖାଯିବ। ଏହା ଏକ ନମୁନା ପାଠ୍ୟ ଯାହା ପ୍ରକୃତ ଖବର ଦ୍ୱାରା ବଦଳାଯିବ।</p>
      <p>ଦ୍ୱିତୀୟ ଅନୁଚ୍ଛେଦରେ ଅଧିକ ବିବରଣୀ ରହିବ। ପ୍ରଗତିବାଦୀ ଖବରକାଗଜର ଶୈଳୀରେ ଏହା ତିନି ସ୍ତମ୍ଭରେ ବିଭକ୍ତ ହେବ।</p>
      <p>ତୃତୀୟ ଅନୁଚ୍ଛେଦ ଖବରର ଅନ୍ୟ ଦିଗ ଉପସ୍ଥାପନ କରିବ। ସ୍ଥାନୀୟ ଘଟଣା ସମ୍ପର୍କରେ ଅଧିକ ତଥ୍ୟ।</p>
    </div>
  </div>
</body>
</html>"""


# ─── Template 2: Wide Landscape Banner (345269 style) ─────────────────────
# Full-width landscape image, large headline above, compact 2-column body
WIDE_BANNER = """<!DOCTYPE html>
<html lang="or">
<head>
<meta charset="UTF-8">
<title>Wide Banner Story</title>
<style>
@import url('https://fonts.googleapis.com/css2?family=Noto+Serif+Odia:wght@400;700;900&family=Noto+Sans+Odia:wght@400;600;700;800&display=swap');

* { margin: 0; padding: 0; box-sizing: border-box; }

body {
  max-width: 680px;
  margin: 0 auto;
  background: #fff;
  font-family: 'Noto Serif Odia', serif;
  color: #1a1a1a;
  padding: 0;
}

.header {
  padding: 12px 16px 0;
}

.kicker {
  font-family: 'Noto Sans Odia', sans-serif;
  font-size: 18px;
  font-weight: 700;
  color: #8B0000;
  line-height: 1.3;
  margin-bottom: 2px;
}

h1 {
  font-family: 'Noto Sans Odia', sans-serif;
  font-size: 36px;
  font-weight: 900;
  line-height: 1.2;
  color: #1a0a0a;
  margin-bottom: 8px;
}

.article-image {
  width: 100%;
  aspect-ratio: 16/7;
  object-fit: cover;
  display: block;
  border-top: 2px solid #8B0000;
  border-bottom: 2px solid #8B0000;
}

.content {
  padding: 10px 16px 20px;
}

.location-line {
  font-family: 'Noto Sans Odia', sans-serif;
  font-size: 11px;
  color: #444;
  margin-bottom: 10px;
}

.location-line .marker {
  display: inline-block;
  width: 7px;
  height: 7px;
  background: #333;
  margin-right: 3px;
  vertical-align: middle;
}

.body-text {
  font-size: 13px;
  line-height: 1.7;
  text-align: justify;
  column-count: 2;
  column-gap: 18px;
  column-rule: 1px solid #ddd;
}

.body-text p { margin-bottom: 6px; }

@media print { body { max-width: 100%; } }
</style>
</head>
<body>
  <div class="header">
    <div class="kicker">ଭାରତର ବିଭିନ୍ନ ସ୍ଥାନରେ</div>
    <h1>ଏଠାରେ ମୁଖ୍ୟ ଶୀର୍ଷକ ଲେଖାଯିବ</h1>
  </div>
  <img class="article-image" src="https://placehold.co/680x300/e8e8e8/999?text=Wide+Image" alt="Banner image">
  <div class="content">
    <div class="location-line">
      <span class="marker"></span> ସ୍ଥାନ, ତାରିଖ:
    </div>
    <div class="body-text">
      <p>ଏଠାରେ ଖବରର ବିସ୍ତୃତ ବିବରଣୀ ଲେଖାଯିବ। ଏହା ଏକ ପ୍ରଶସ୍ତ ବ୍ୟାନର ଶୈଳୀର ଖବର ଯେଉଁଥିରେ ବଡ଼ ଛବି ଓ ଦୁଇ ସ୍ତମ୍ଭ ପାଠ୍ୟ ରହିଛି।</p>
      <p>ଦ୍ୱିତୀୟ ଅନୁଚ୍ଛେଦ ଅଧିକ ସନ୍ଦର୍ଭ ଏବଂ ପୃଷ୍ଠଭୂମି ପ୍ରଦାନ କରେ।</p>
    </div>
  </div>
</body>
</html>"""


# ─── Template 3: Opinion Column with Author Photo (345283 style) ─────────
# Circular author photo, author name, title, single-column long text, label at bottom
OPINION_COLUMN = """<!DOCTYPE html>
<html lang="or">
<head>
<meta charset="UTF-8">
<title>Opinion Column</title>
<style>
@import url('https://fonts.googleapis.com/css2?family=Noto+Serif+Odia:wght@400;700;900&family=Noto+Sans+Odia:wght@400;600;700;800&display=swap');

* { margin: 0; padding: 0; box-sizing: border-box; }

body {
  max-width: 340px;
  margin: 0 auto;
  background: #fff;
  font-family: 'Noto Serif Odia', serif;
  color: #1a1a1a;
  padding: 12px 14px 16px;
}

h1 {
  font-family: 'Noto Sans Odia', sans-serif;
  font-size: 24px;
  font-weight: 900;
  line-height: 1.25;
  color: #1a1a1a;
  text-align: center;
  margin-bottom: 10px;
}

.author-block {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 12px;
  padding-bottom: 10px;
  border-bottom: 2px solid #8B0000;
}

.author-photo {
  width: 56px;
  height: 56px;
  border-radius: 50%;
  object-fit: cover;
  border: 2px solid #8B0000;
  flex-shrink: 0;
}

.author-name {
  font-family: 'Noto Sans Odia', sans-serif;
  font-size: 13px;
  font-weight: 700;
  color: #8B0000;
}

.author-name::before {
  content: '✦ ';
  font-size: 10px;
}

.body-text {
  font-size: 13px;
  line-height: 1.75;
  text-align: justify;
}

.body-text p {
  margin-bottom: 8px;
  text-indent: 1.5em;
}

.body-text p:first-child { text-indent: 0; }

.tag-label {
  display: inline-block;
  margin-top: 14px;
  float: right;
  background: #8B0000;
  color: #fff;
  font-family: 'Noto Sans Odia', sans-serif;
  font-size: 10px;
  font-weight: 700;
  padding: 3px 10px;
  border-radius: 2px;
}

@media print { body { max-width: 100%; } }
</style>
</head>
<body>
  <h1>ଏଠାରେ ସ୍ତମ୍ଭ ଶୀର୍ଷକ</h1>
  <div class="author-block">
    <img class="author-photo" src="https://placehold.co/56x56/e8e8e8/999?text=Author" alt="Author">
    <span class="author-name">ଲେଖକଙ୍କ ନାମ</span>
  </div>
  <div class="body-text">
    <p>ଏଠାରେ ମତାମତ ସ୍ତମ୍ଭର ପ୍ରଥମ ଅନୁଚ୍ଛେଦ ଲେଖାଯିବ। ଏହା ଏକ ବ୍ୟକ୍ତିଗତ ସ୍ତମ୍ଭ ଶୈଳୀ ଯେଉଁଥିରେ ଲେଖକଙ୍କ ଛବି ଓ ନାମ ଥାଏ।</p>
    <p>ଦ୍ୱିତୀୟ ଅନୁଚ୍ଛେଦ ବିଷୟର ଗଭୀର ବିଶ୍ଳେଷଣ ପ୍ରଦାନ କରେ। ପ୍ରତ୍ୟେକ ଅନୁଚ୍ଛେଦ ଇଣ୍ଡେଣ୍ଟ ହୋଇଥାଏ।</p>
    <p>ତୃତୀୟ ଅନୁଚ୍ଛେଦରେ ସିଦ୍ଧାନ୍ତ ଏବଂ ଉପସଂହାର ଥାଏ।</p>
  </div>
  <span class="tag-label">ଓ ଲେଖା ଆମକୁ ପଠାନ୍ତୁ</span>
</body>
</html>"""


# ─── Template 4: Text-Only Multi-Column (345243 / 345291 style) ──────────
# No image, bold headline, optional highlighted inset, 2-3 column body
TEXT_ONLY = """<!DOCTYPE html>
<html lang="or">
<head>
<meta charset="UTF-8">
<title>Text-Only News</title>
<style>
@import url('https://fonts.googleapis.com/css2?family=Noto+Serif+Odia:wght@400;700;900&family=Noto+Sans+Odia:wght@400;600;700;800;900&display=swap');

* { margin: 0; padding: 0; box-sizing: border-box; }

body {
  max-width: 520px;
  margin: 0 auto;
  background: #fff;
  font-family: 'Noto Serif Odia', serif;
  color: #1a1a1a;
  padding: 14px 16px 20px;
}

h1 {
  font-family: 'Noto Sans Odia', sans-serif;
  font-size: 30px;
  font-weight: 900;
  line-height: 1.2;
  color: #111;
  margin-bottom: 6px;
  border-bottom: 2px solid #333;
  padding-bottom: 6px;
}

.location-line {
  font-family: 'Noto Sans Odia', sans-serif;
  font-size: 11px;
  color: #444;
  margin-bottom: 12px;
}

.location-line .marker {
  display: inline-block;
  width: 7px;
  height: 7px;
  background: #333;
  margin-right: 3px;
  vertical-align: middle;
}

.inset-box {
  float: left;
  width: 42%;
  margin: 0 14px 10px 0;
  padding: 10px 12px;
  background: #FFF9E6;
  border: 2px solid #D4A017;
  border-radius: 2px;
}

.inset-box h3 {
  font-family: 'Noto Sans Odia', sans-serif;
  font-size: 15px;
  font-weight: 800;
  color: #8B6508;
  line-height: 1.3;
  margin-bottom: 4px;
}

.inset-box p {
  font-size: 11.5px;
  line-height: 1.6;
  color: #555;
}

.body-text {
  font-size: 13px;
  line-height: 1.7;
  text-align: justify;
}

.body-text p { margin-bottom: 8px; }

@media print { body { max-width: 100%; } }
</style>
</head>
<body>
  <h1>ଏଠାରେ ମୁଖ୍ୟ ଶୀର୍ଷକ ଲେଖାଯିବ</h1>
  <div class="location-line">
    <span class="marker"></span> ସ୍ଥାନ, ତାରିଖ <span>(ପ୍ରତିନିଧି)</span>
  </div>
  <div class="inset-box">
    <h3>ସମ୍ପର୍କିତ ଖବର ଶୀର୍ଷକ</h3>
    <p>ଏଠାରେ ସମ୍ପର୍କିତ ଛୋଟ ଖବର ବା ହାଇଲାଇଟ ବକ୍ସ ଲେଖାଯିବ।</p>
  </div>
  <div class="body-text">
    <p>ଏଠାରେ ମୂଳ ଖବରର ପ୍ରଥମ ଅନୁଚ୍ଛେଦ ଲେଖାଯିବ। ଏହା ପାଠ୍ୟ-ମାତ୍ର ଶୈଳୀ ଯେଉଁଥିରେ ଛବି ନାହିଁ କିନ୍ତୁ ଏକ ହାଇଲାଇଟ ବକ୍ସ ଅଛି।</p>
    <p>ଦ୍ୱିତୀୟ ଅନୁଚ୍ଛେଦ ଅଧିକ ବିବରଣୀ ଏବଂ ସନ୍ଦର୍ଭ ପ୍ରଦାନ କରେ। ପାଠ୍ୟ ହାଇଲାଇଟ ବକ୍ସ ଚାରିପାଖରେ ପ୍ରବାହିତ ହୁଏ।</p>
    <p>ତୃତୀୟ ଅନୁଚ୍ଛେଦ ଉପସଂହାର ପ୍ରଦାନ କରେ ଏବଂ ଭବିଷ୍ୟତ ପଦକ୍ଷେପ ସମ୍ପର୍କରେ ସୂଚନା ଦିଏ।</p>
  </div>
</body>
</html>"""


# ─── Template 5: Devotional / Spiritual Column (345281 style) ────────────
# Decorative header, bordered layout, lotus icon, author name, phone at bottom
DEVOTIONAL_COLUMN = """<!DOCTYPE html>
<html lang="or">
<head>
<meta charset="UTF-8">
<title>Devotional Column</title>
<style>
@import url('https://fonts.googleapis.com/css2?family=Noto+Serif+Odia:wght@400;700;900&family=Noto+Sans+Odia:wght@400;600;700;800;900&display=swap');

* { margin: 0; padding: 0; box-sizing: border-box; }

body {
  max-width: 320px;
  margin: 0 auto;
  background: #fff;
  font-family: 'Noto Serif Odia', serif;
  color: #1a1a1a;
  padding: 0;
}

.column-wrapper {
  border: 2px solid #444;
  padding: 0;
}

.header {
  background: #1a1a1a;
  text-align: center;
  padding: 8px 10px;
}

.header h1 {
  font-family: 'Noto Sans Odia', sans-serif;
  font-size: 26px;
  font-weight: 900;
  color: #fff;
  line-height: 1.2;
}

.sub-header {
  text-align: center;
  padding: 6px 10px;
  border-bottom: 1px solid #ccc;
}

.sub-header .author-name {
  font-family: 'Noto Sans Odia', sans-serif;
  font-size: 13px;
  font-weight: 700;
  color: #8B0000;
}

.content {
  padding: 12px 14px;
}

.body-text {
  font-size: 12.5px;
  line-height: 1.75;
  text-align: justify;
}

.body-text p {
  margin-bottom: 8px;
  text-indent: 1.2em;
}

.body-text p:first-child { text-indent: 0; }

.icon-divider {
  text-align: center;
  margin: 12px 0;
  font-size: 24px;
  color: #D4637A;
}

.footer {
  text-align: center;
  padding: 8px 14px 10px;
  border-top: 1px solid #ccc;
  font-family: 'Noto Sans Odia', sans-serif;
  font-size: 10px;
  color: #666;
}

@media print { body { max-width: 100%; } }
</style>
</head>
<body>
  <div class="column-wrapper">
    <div class="header">
      <h1>ଭକ୍ତି ଓ ଭୁକ୍ତି</h1>
    </div>
    <div class="sub-header">
      <span class="author-name">ଲେଖକଙ୍କ ନାମ</span>
    </div>
    <div class="content">
      <div class="body-text">
        <p>ଏଠାରେ ଆଧ୍ୟାତ୍ମିକ ସ୍ତମ୍ଭର ପ୍ରଥମ ଅନୁଚ୍ଛେଦ। ଏହା ଭକ୍ତି, ଧର୍ମ, ଦର୍ଶନ ବିଷୟରେ ଲେଖା ପାଇଁ ଏକ ସୁନ୍ଦର ବର୍ଡର ଶୈଳୀ।</p>
        <p>ଦ୍ୱିତୀୟ ଅନୁଚ୍ଛେଦ ଗଭୀର ଆଧ୍ୟାତ୍ମିକ ଚିନ୍ତନ ପ୍ରଦାନ କରେ। ପ୍ରତ୍ୟେକ ଅନୁଚ୍ଛେଦ ଇଣ୍ଡେଣ୍ଟ ହୋଇଥାଏ।</p>
        <p>ତୃତୀୟ ଅନୁଚ୍ଛେଦ ଉପଦେଶ ଏବଂ ଶିକ୍ଷା ସହିତ ସମାପ୍ତ ହୁଏ।</p>
      </div>
      <div class="icon-divider">🪷</div>
    </div>
    <div class="footer">
      ମୋ: ୯୮୫୪୦୪୦୨୯୭
    </div>
  </div>
</body>
</html>"""


# ─── Template 6: Market Rates Card (345298 style) ────────────────────────
# Structured price display with colored sections, icons
MARKET_RATES = """<!DOCTYPE html>
<html lang="or">
<head>
<meta charset="UTF-8">
<title>Market Rates</title>
<style>
@import url('https://fonts.googleapis.com/css2?family=Noto+Sans+Odia:wght@400;600;700;800;900&display=swap');

* { margin: 0; padding: 0; box-sizing: border-box; }

body {
  max-width: 240px;
  margin: 0 auto;
  background: #fff;
  font-family: 'Noto Sans Odia', sans-serif;
  color: #1a1a1a;
  padding: 0;
}

.card {
  border: 2px solid #333;
  border-radius: 4px;
  overflow: hidden;
}

.card-header {
  background: linear-gradient(135deg, #DAA520, #FFD700);
  text-align: center;
  padding: 8px 10px;
}

.card-header h2 {
  font-size: 20px;
  font-weight: 900;
  color: #1a1a1a;
}

.card-header .date {
  font-size: 10px;
  color: #555;
  font-weight: 600;
}

.rate-item {
  display: flex;
  align-items: center;
  padding: 8px 12px;
  border-bottom: 1px solid #e8e8e8;
  gap: 10px;
}

.rate-item:last-child { border-bottom: none; }

.rate-icon {
  font-size: 28px;
  flex-shrink: 0;
  width: 36px;
  text-align: center;
}

.rate-details {
  flex: 1;
}

.rate-label {
  font-size: 11px;
  color: #666;
  font-weight: 600;
}

.rate-value {
  font-size: 15px;
  font-weight: 800;
  color: #111;
}

.section-header {
  padding: 5px 12px;
  font-size: 11px;
  font-weight: 800;
  color: #fff;
}

.section-gold { background: #B8860B; }
.section-oil { background: #C0392B; }
.section-food { background: #27AE60; }

@media print { body { max-width: 100%; } }
</style>
</head>
<body>
  <div class="card">
    <div class="card-header">
      <h2>ସୁନା ଦର</h2>
      <div class="date">(ସ୍ଥାନୀୟ ବଜାର)</div>
    </div>

    <div class="section-header section-gold">ସୁନା ଓ ରୂପା</div>
    <div class="rate-item">
      <div class="rate-icon">🥇</div>
      <div class="rate-details">
        <div class="rate-label">୧୦ଗ୍ରାମ:</div>
        <div class="rate-value">₹ ୧,୨୧,୦୧୦ ଟଙ୍କା</div>
      </div>
    </div>
    <div class="rate-item">
      <div class="rate-icon">🥈</div>
      <div class="rate-details">
        <div class="rate-label">ରୂପା (କିଗ୍ରା):</div>
        <div class="rate-value">₹ ୩,୧୪୮,୦୦୦ ଟଙ୍କା</div>
      </div>
    </div>

    <div class="section-header section-oil">ତେଲ ଦର (ଲିଟର ପିଛା)</div>
    <div class="rate-item">
      <div class="rate-icon">⛽</div>
      <div class="rate-details">
        <div class="rate-label">ପେଟ୍ରୋଲ:</div>
        <div class="rate-value">₹ ୨୦୧.୯୧ ଟଙ୍କା</div>
      </div>
    </div>
    <div class="rate-item">
      <div class="rate-icon">🛢️</div>
      <div class="rate-details">
        <div class="rate-label">ଡିଜେଲ:</div>
        <div class="rate-value">₹ ୯୬.୭୧ ଟଙ୍କା</div>
      </div>
    </div>

    <div class="section-header section-food">ଅଣ୍ଡା ଓ ଚିକେନ ଦର</div>
    <div class="rate-item">
      <div class="rate-icon">🥚</div>
      <div class="rate-details">
        <div class="rate-label">ଅଣ୍ଡା (୨୫ଟା):</div>
        <div class="rate-value">₹ ୭.୦୦ ଟଙ୍କା</div>
      </div>
    </div>
    <div class="rate-item">
      <div class="rate-icon">🍗</div>
      <div class="rate-details">
        <div class="rate-label">ଚିକେନ (କି.ଗ୍ରା.):</div>
        <div class="rate-value">₹ ୧୪୦ ଟଙ୍କା</div>
      </div>
    </div>
  </div>
</body>
</html>"""


# ─── Template 7: Vertical Article with Bottom Image (345273 style) ───────
# Section label at top, headline, single-column body, image at bottom
VERTICAL_WITH_IMAGE = """<!DOCTYPE html>
<html lang="or">
<head>
<meta charset="UTF-8">
<title>Vertical Story with Image</title>
<style>
@import url('https://fonts.googleapis.com/css2?family=Noto+Serif+Odia:wght@400;700;900&family=Noto+Sans+Odia:wght@400;600;700;800;900&display=swap');

* { margin: 0; padding: 0; box-sizing: border-box; }

body {
  max-width: 300px;
  margin: 0 auto;
  background: #fff;
  font-family: 'Noto Serif Odia', serif;
  color: #1a1a1a;
  padding: 0;
}

.section-label {
  background: #1a3a6a;
  color: #FFD700;
  font-family: 'Noto Sans Odia', sans-serif;
  font-size: 14px;
  font-weight: 800;
  text-align: center;
  padding: 5px 10px;
  letter-spacing: 1px;
}

.content {
  padding: 10px 14px;
}

h1 {
  font-family: 'Noto Sans Odia', sans-serif;
  font-size: 22px;
  font-weight: 900;
  line-height: 1.3;
  color: #1a3a6a;
  text-align: center;
  margin-bottom: 8px;
}

.location-line {
  font-family: 'Noto Sans Odia', sans-serif;
  font-size: 10px;
  color: #555;
  margin-bottom: 10px;
}

.location-line .marker {
  display: inline-block;
  width: 6px;
  height: 6px;
  background: #333;
  margin-right: 3px;
  vertical-align: middle;
}

.body-text {
  font-size: 12.5px;
  line-height: 1.7;
  text-align: justify;
  margin-bottom: 12px;
}

.body-text p { margin-bottom: 6px; }

.bottom-image {
  width: 100%;
  aspect-ratio: 4/3;
  object-fit: cover;
  display: block;
  border: 1px solid #ddd;
  border-radius: 2px;
}

.image-caption {
  font-family: 'Noto Sans Odia', sans-serif;
  font-size: 9px;
  color: #888;
  text-align: center;
  margin-top: 4px;
  padding-bottom: 10px;
}

@media print { body { max-width: 100%; } }
</style>
</head>
<body>
  <div class="section-label">ପ୍ରଗତିବାଦୀ ବିଶେଷ</div>
  <div class="content">
    <h1>ଏଠାରେ ଶୀର୍ଷକ ଲେଖାଯିବ</h1>
    <div class="location-line">
      <span class="marker"></span> ସ୍ଥାନ, ତାରିଖ (ପ୍ରତିନିଧି)
    </div>
    <div class="body-text">
      <p>ଏଠାରେ ଖବରର ପ୍ରଥମ ଅନୁଚ୍ଛେଦ ଲେଖାଯିବ। ଏହା ଏକ ଲମ୍ବ ସ୍ତମ୍ଭ ଶୈଳୀ ଯେଉଁଥିରେ ଚିତ୍ର ତଳେ ରହିଛି।</p>
      <p>ଦ୍ୱିତୀୟ ଅନୁଚ୍ଛେଦ ଅଧିକ ବିବରଣୀ ପ୍ରଦାନ କରେ।</p>
    </div>
    <img class="bottom-image" src="https://placehold.co/300x225/e8e8e8/999?text=Image" alt="Story image">
    <div class="image-caption">ଫଟୋ ବିବରଣୀ ଏଠାରେ</div>
  </div>
</body>
</html>"""


# ─── Insert all templates ────────────────────────────────────────────────

TEMPLATES = [
    {
        "name": "Photo-Top News",
        "mode": "flexible",
        "html_content": PHOTO_TOP_NEWS,
        "category": None,
    },
    {
        "name": "Wide Banner Story",
        "mode": "flexible",
        "html_content": WIDE_BANNER,
        "category": None,
    },
    {
        "name": "Opinion Column",
        "mode": "fixed",
        "html_content": OPINION_COLUMN,
        "category": None,
    },
    {
        "name": "Text-Only with Inset",
        "mode": "flexible",
        "html_content": TEXT_ONLY,
        "category": None,
    },
    {
        "name": "Devotional Column",
        "mode": "fixed",
        "html_content": DEVOTIONAL_COLUMN,
        "category": None,
    },
    {
        "name": "Market Rates Card",
        "mode": "fixed",
        "html_content": MARKET_RATES,
        "category": "business",
    },
    {
        "name": "Vertical with Bottom Image",
        "mode": "flexible",
        "html_content": VERTICAL_WITH_IMAGE,
        "category": None,
    },
]


def main():
    conn = psycopg2.connect(
        host=DB_HOST, port=DB_PORT, user=DB_USER, password=DB_PASS, dbname=DB_NAME
    )
    cur = conn.cursor()

    for tpl in TEMPLATES:
        tpl_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc)
        cur.execute(
            """INSERT INTO layout_templates (id, name, mode, html_content, category, organization_id, created_at, updated_at)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s)""",
            (tpl_id, tpl["name"], tpl["mode"], tpl["html_content"], tpl["category"], ORG_ID, now, now),
        )
        print(f"  ✓ Inserted: {tpl['name']} ({tpl['mode']}) → {tpl_id}")

    conn.commit()
    cur.close()
    conn.close()
    print(f"\nDone! {len(TEMPLATES)} templates inserted for {ORG_ID}")


if __name__ == "__main__":
    main()
