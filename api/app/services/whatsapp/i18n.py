"""WhatsApp reply localisation.

One catalog, three locales (or/hi/en). Lookup falls back to English
on missing keys or unknown locales. Variable substitution via .format().

Resolution chain (resolve_lang):
    user.org.default_language → 'or' (platform default)

Translations are journalism-register Odia and Hindi, idiomatic for
regional newspaper reporters. Tone is conversational and terse — these
are inline replies, not UI labels. Edit a string in place if the
register feels off; do not re-translate via a tool.
"""
from __future__ import annotations
from typing import Optional


STRINGS: dict[str, dict[str, str]] = {
    # ── Thread progress messages ─────────────────────────────────
    "thread.first": {
        "or": "📥 ୧ଟି ବାର୍ତ୍ତା ପାଇଲି।\nଆଉ ଫରୱାର୍ଡ କରନ୍ତୁ କିମ୍ବା ସରିଲେ ଟ୍ୟାପ କରନ୍ତୁ।",
        "hi": "📥 1 संदेश मिला।\nऔर भेजें या समाप्त हो जाने पर टैप करें।",
        "en": "📥 Got 1 message.\nForward more, or tap when finished.",
    },
    "thread.update": {
        "or": "📥 {count}ଟି ବାର୍ତ୍ତା ପାଇଲି ({text} ଲେଖା + {media} ମିଡିଆ)।\nଆଉ ଫରୱାର୍ଡ କରନ୍ତୁ କିମ୍ବା ସରିଲେ ଟ୍ୟାପ କରନ୍ତୁ।",
        "hi": "📥 {count} संदेश मिले ({text} पाठ + {media} मीडिया)।\nऔर भेजें या समाप्त हो जाने पर टैप करें।",
        "en": "📥 Got {count} messages ({text} text + {media} media).\nForward more, or tap when finished.",
    },

    # ── Buttons ───────────────────────────────────────────────────
    "btn.submit":  {"or": "✓ ଖବର ଦାଖଲ କରନ୍ତୁ", "hi": "✓ खबर जमा करें", "en": "✓ Submit Story"},
    "btn.cancel":  {"or": "✕ ବାତିଲ କରନ୍ତୁ",     "hi": "✕ रद्द करें",       "en": "✕ Cancel"},
    "btn.add":     {"or": "➕ ଅଧିକ ଯୋଡ଼ନ୍ତୁ",   "hi": "➕ और जोड़ें",       "en": "➕ Add more"},
    "btn.today":   {"or": "📋 ଆଜିର ଖବର",       "hi": "📋 आज की खबरें",   "en": "📋 Today"},
    "btn.openApp": {"or": "📱 ଆପରେ ଦେଖନ୍ତୁ",  "hi": "📱 ऐप में खोलें",   "en": "📱 Open in app"},
    "btn.saveAdd": {"or": "✓ ଯୋଡ଼ାଣ ସଞ୍ଚୟ",   "hi": "✓ जोड़ सहेजें",      "en": "✓ Save additions"},
    "btn.discard": {"or": "✕ ତ୍ୟାଗ କରନ୍ତୁ",     "hi": "✕ छोड़ें",           "en": "✕ Discard"},
    "btn.menu":    {"or": "☰ ମେନୁ ଖୋଲନ୍ତୁ",    "hi": "☰ मेनू खोलें",       "en": "☰ Open menu"},

    # ── Story saved ──────────────────────────────────────────────
    "saved.header": {"or": "✓ ଖବର ସଞ୍ଚୟ ହୋଇଛି", "hi": "✓ खबर सहेजी गई",   "en": "✓ Story saved"},
    "saved.id":     {"or": "ID: {display_id}",   "hi": "ID: {display_id}", "en": "ID: {display_id}"},

    # ── Add-to-story ─────────────────────────────────────────────
    "adding.header": {
        "or": "➕ {display_id}ରେ ଯୋଡ଼ୁଛି",
        "hi": "➕ {display_id} में जोड़ रहे हैं",
        "en": "➕ Adding to {display_id}",
    },
    "adding.update": {
        "or": "ଆଉ {count}ଟି ପାଇଲି ({text} ଲେଖା + {media} ମିଡିଆ)।",
        "hi": "और {count} मिले ({text} पाठ + {media} मीडिया)।",
        "en": "Got {count} more ({text} text + {media} media).",
    },

    # ── Today's stories list ─────────────────────────────────────
    "today.header": {
        "or": "📋 ଆଜିର ଆପଣଙ୍କର ଖବର ({count}):",
        "hi": "📋 आज की आपकी खबरें ({count}):",
        "en": "📋 Your stories today ({count}):",
    },
    "today.empty": {
        "or": "📭 ଆଜି କିଛି ଖବର ଦାଖଲ ହୋଇନାହିଁ। ଏକ ଖବର ଫରୱାର୍ଡ କରନ୍ତୁ।",
        "hi": "📭 आज कोई खबर जमा नहीं हुई। एक खबर भेजें।",
        "en": "📭 No stories filed today. Forward a story to submit.",
    },
    "today.overflow": {
        "or": "(+{n}ଟି ଅଧିକ — ଆପରେ ଦେଖନ୍ତୁ)",
        "hi": "(+{n} और — ऐप में देखें)",
        "en": "(+{n} more — tap below to see all)",
    },

    # ── Edge-case error replies ──────────────────────────────────
    "err.unregistered": {
        "or": "ଆପଣଙ୍କ ନମ୍ବର ବ୍ରତ୍ତାନ୍ତର ସାମ୍ବାଦିକ ରୂପେ ପଞ୍ଜିକୃତ ନୁହେଁ। ସମ୍ପାଦକଙ୍କ ସହ ଯୋଗାଯୋଗ କରନ୍ତୁ।",
        "hi": "आपका नंबर वृत्तांत के संवाददाता के रूप में पंजीकृत नहीं है। संपादक से संपर्क करें।",
        "en": "Your number isn't registered. Please contact your editor.",
    },
    "err.tooShort": {
        "or": "ଯଥେଷ୍ଟ ବିଷୟବସ୍ତୁ ଖୋଜା ଗଲା ନାହିଁ (୨୦+ ଶବ୍ଦ ଦରକାର)। ଅଧିକ ବିବରଣୀ ସହ ପୁନଃ ଫରୱାର୍ଡ କରନ୍ତୁ।",
        "hi": "पर्याप्त सामग्री नहीं मिली (20+ शब्द चाहिए)। अधिक विवरण के साथ दोबारा भेजें।",
        "en": "Couldn't read enough content (need 20+ words). Please re-forward with more detail.",
    },
    "err.sticker": {
        "or": "ଷ୍ଟିକର/ସ୍ଥାନ ସଞ୍ଚୟ ହୋଇନାହିଁ। ଖବର ଦାଖଲ ପାଇଁ ଲେଖା କିମ୍ବା ଫଟୋ ଫରୱାର୍ଡ କରନ୍ତୁ।",
        "hi": "स्टिकर/स्थान सहेजा नहीं गया। खबर जमा करने के लिए पाठ या फोटो भेजें।",
        "en": "Sticker/location not saved. Forward text or photos to submit a story.",
    },
    "err.locked": {
        "or": "ଖବର {display_id} ଲକ୍ କରାଯାଇଛି। ନୂଆ ବିଷୟବସ୍ତୁ ଏକ ନୂଆ ଖବର ଭାବେ ସଞ୍ଚୟ ହେବ।",
        "hi": "खबर {display_id} लॉक हो चुकी है। नई सामग्री एक नई खबर के रूप में सहेजी जाएगी।",
        "en": "Story {display_id} is locked. New content will be saved as a fresh story.",
    },
    "err.crossReporter": {
        "or": "ଅନ୍ୟ ସାମ୍ବାଦିକଙ୍କ ଖବରକୁ ସମ୍ପାଦନ କରିହେବ ନାହିଁ।",
        "hi": "अन्य संवाददाता की खबर संपादित नहीं की जा सकती।",
        "en": "Cannot edit another reporter's story.",
    },
    "err.empty": {
        "or": "ଦାଖଲ କରିବାକୁ କିଛି ନାହିଁ। ପ୍ରଥମେ ଆପଣଙ୍କ ଖବର ଫରୱାର୍ଡ କରନ୍ତୁ।",
        "hi": "जमा करने के लिए कुछ नहीं है। पहले अपनी खबर भेजें।",
        "en": "Nothing to submit yet. Forward your story first.",
    },
    "err.cancelled": {
        "or": "ବାତିଲ ହୋଇଛି। ଆପଣଙ୍କ ଫରୱାର୍ଡ ସଞ୍ଚୟ ହୋଇନାହିଁ।",
        "hi": "रद्द किया गया। आपकी फॉरवर्ड सहेजी नहीं गईं।",
        "en": "Cancelled. Your forwards were not saved.",
    },
    "err.tooOld": {
        "or": "ଏହି ଖବରଟି ୱାଟସ୍ଆପରୁ ସମ୍ପାଦନ କରିବାକୁ ବହୁତ ପୁରୁଣା। ମୋବାଇଲ ଆପ ବ୍ୟବହାର କରନ୍ତୁ।",
        "hi": "यह खबर WhatsApp से संपादित करने के लिए बहुत पुरानी है। मोबाइल ऐप का उपयोग करें।",
        "en": "This story is too old to edit from WhatsApp. Use the mobile app.",
    },
    "hint.audio": {
        "or": "ଓଡ଼ିଆ ଡିକ୍ଟେସନ ପାଇଁ, ବ୍ରତ୍ତାନ୍ତ ମୋବାଇଲ ଆପ ଲାଇଭ୍ ଟ୍ରାନ୍ସକ୍ରିପସନ ଦିଏ।",
        "hi": "ओडिया डिक्टेशन के लिए, वृत्तांत मोबाइल ऐप लाइव ट्रांसक्रिप्शन देता है।",
        "en": "For Odia dictation, the Vrittant mobile app gives you live transcription.",
    },

    # ── Menu prompt ──────────────────────────────────────────────
    "menu.prompt": {
        "or": "☰ ଆପଣ କ'ଣ କରିବାକୁ ଚାହାଁନ୍ତି?",
        "hi": "☰ आप क्या करना चाहते हैं?",
        "en": "☰ What would you like to do?",
    },
}


def t(key: str, lang: str, **vars) -> str:
    """Translate `key` into `lang`, falling back to English on miss.

    Substitutes `vars` via str.format if any are provided. Missing
    keys return the key itself (so a typo is diagnosable in chat
    rather than crashing the webhook).
    """
    bucket = STRINGS.get(key)
    if bucket is None:
        return key
    s = bucket.get(lang) or bucket.get("en") or key
    return s.format(**vars) if vars else s


def resolve_lang(user) -> str:
    """Resolve a User to their org's WhatsApp reply language.

    Returns 'or' (Odia) by default — appropriate for the existing
    Pragativadi/Sambad orgs. Org admins flip to 'hi' or 'en' via the
    Settings panel (UI dropdown TBD; for now seeded via SQL per org).
    """
    if user is None:
        return "or"
    org = getattr(user, "org", None)
    if org is None:
        return "or"
    return getattr(org, "default_language", None) or "or"
