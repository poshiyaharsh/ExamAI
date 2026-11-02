"""
Automatic Language Detection and Script Analysis Engine.
Offline, fast, and deterministic.
Uses lingua-language-detector combined with Unicode codepoint script analysis.
"""
import re
import unicodedata
import logging
from typing import Dict, List, Tuple, Optional, Any

from lingua import Language, LanguageDetectorBuilder

logger = logging.getLogger(__name__)

# Target languages supported by the exam platform
SUPPORTED_LANGUAGES = [
    Language.ENGLISH,
    Language.HINDI,
    Language.GUJARATI,
    Language.MARATHI,
    Language.TAMIL,
    Language.BENGALI,
    Language.URDU,
    Language.ARABIC,
    Language.FRENCH,
    Language.SPANISH,
    Language.GERMAN,
    Language.CHINESE,
    Language.JAPANESE,
]

# Initialize Lingua detector once at module load
_DETECTOR = LanguageDetectorBuilder.from_languages(*SUPPORTED_LANGUAGES).with_preheating().build()

# ISO 639-1 code mapping
LINGUA_TO_ISO = {
    Language.ENGLISH: 'en',
    Language.HINDI: 'hi',
    Language.GUJARATI: 'gu',
    Language.MARATHI: 'mr',
    Language.TAMIL: 'ta',
    Language.BENGALI: 'bn',
    Language.URDU: 'ur',
    Language.ARABIC: 'ar',
    Language.FRENCH: 'fr',
    Language.SPANISH: 'es',
    Language.GERMAN: 'de',
    Language.CHINESE: 'zh',
    Language.JAPANESE: 'ja',
}

ISO_TO_NAME = {
    'en': 'English',
    'hi': 'Hindi',
    'gu': 'Gujarati',
    'mr': 'Marathi',
    'ta': 'Tamil',
    'bn': 'Bengali',
    'ur': 'Urdu',
    'ar': 'Arabic',
    'fr': 'French',
    'es': 'Spanish',
    'de': 'German',
    'zh': 'Chinese',
    'ja': 'Japanese',
}

ISO_TO_SCRIPT = {
    'en': 'Latin',
    'hi': 'Devanagari',
    'gu': 'Gujarati',
    'mr': 'Devanagari',
    'ta': 'Tamil',
    'bn': 'Bengali',
    'ur': 'Arabic',
    'ar': 'Arabic',
    'fr': 'Latin',
    'es': 'Latin',
    'de': 'Latin',
    'zh': 'Simplified Chinese',
    'ja': 'Japanese (Kanji/Kana)',
}

RTL_LANGUAGES = {'ar', 'ur', 'he', 'fa'}


def get_unicode_script(char: str) -> str:
    """Returns the primary script category for a Unicode character."""
    code = ord(char)
    # Devanagari: U+0900 - U+097F
    if 0x0900 <= code <= 0x097F:
        return 'Devanagari'
    # Gujarati: U+0A80 - U+0AFF
    if 0x0A80 <= code <= 0x0AFF:
        return 'Gujarati'
    # Bengali: U+0980 - U+09FF
    if 0x0980 <= code <= 0x09FF:
        return 'Bengali'
    # Tamil: U+0B80 - U+0BFF
    if 0x0B80 <= code <= 0x0BFF:
        return 'Tamil'
    # Arabic: U+0600 - U+06FF, U+0750 - U+077F, U+FB50 - U+FDFF, U+FE70 - U+FEFF
    if (0x0600 <= code <= 0x06FF) or (0x0750 <= code <= 0x077F) or (0xFB50 <= code <= 0xFDFF) or (0xFE70 <= code <= 0xFEFF):
        return 'Arabic'
    # CJK Unified Ideographs: U+4E00 - U+9FFF
    if 0x4E00 <= code <= 0x9FFF:
        return 'CJK'
    # Hiragana: U+3040 - U+309F, Katakana: U+30A0 - U+30FF
    if 0x3040 <= code <= 0x30FF:
        return 'JapaneseKana'
    # Latin: Basic Latin & Extended
    if (0x0041 <= code <= 0x005A) or (0x0061 <= code <= 0x007A) or (0x00C0 <= code <= 0x024F):
        return 'Latin'
    return 'Other'


def analyze_scripts(text: str) -> Dict[str, float]:
    """Computes the distribution percentage of Unicode scripts in text."""
    if not text:
        return {}
    script_counts = {}
    total_letters = 0
    for char in text:
        if unicodedata.category(char).startswith('L'):  # Letter
            s = get_unicode_script(char)
            script_counts[s] = script_counts.get(s, 0) + 1
            total_letters += 1

    if total_letters == 0:
        return {}
    return {s: count / total_letters for s, count in script_counts.items()}


def clean_text_for_detection(text: str) -> str:
    """Strips URLs, email addresses, formulas, and numeric sequences to focus detection."""
    # Strip URLs and emails
    t = re.sub(r'https?://\S+|www\.\S+|\S+@\S+', ' ', text)
    # Strip math expressions and brackets with only numbers
    t = re.sub(r'\b\d+([.,]\d+)?\b', ' ', t)
    # Strip common code snippets
    t = re.sub(r'[{}\[\]()<>;=+\-*/\\]', ' ', t)
    # Normalize whitespace
    return re.sub(r'\s+', ' ', t).strip()


def detect_language(text: str) -> Tuple[str, float, Dict[str, Any]]:
    """
    Detects language of a text block.
    Returns: (iso_code, confidence_score, metadata_dict)
    """
    if not text or len(text.strip()) < 10:
        return 'en', 1.0, {'reason': 'text_too_short', 'fallback': 'en'}

    normalized = unicodedata.normalize('NFC', text)
    cleaned = clean_text_for_detection(normalized)
    if len(cleaned) < 10:
        return 'en', 1.0, {'reason': 'cleaned_text_too_short', 'fallback': 'en'}

    scripts = analyze_scripts(cleaned)

    # 1. First-class Unicode Script Anchors:
    # If text is heavily Gujarati script (>40%), it is unambiguously Gujarati
    if scripts.get('Gujarati', 0) >= 0.35:
        return 'gu', max(0.95, scripts['Gujarati']), {'script': 'Gujarati', 'script_share': scripts['Gujarati']}
    # If text has Tamil script (>35%)
    if scripts.get('Tamil', 0) >= 0.35:
        return 'ta', max(0.95, scripts['Tamil']), {'script': 'Tamil', 'script_share': scripts['Tamil']}
    # If text has Bengali script (>35%)
    if scripts.get('Bengali', 0) >= 0.35:
        return 'bn', max(0.95, scripts['Bengali']), {'script': 'Bengali', 'script_share': scripts['Bengali']}
    # If text has Japanese Kana
    if scripts.get('JapaneseKana', 0) >= 0.15:
        return 'ja', 0.95, {'script': 'JapaneseKana', 'script_share': scripts['JapaneseKana']}

    # 2. Lingua Multi-Language Scoring
    try:
        confidences = _DETECTOR.compute_language_confidence_values(cleaned)
        if not confidences:
            return 'en', 0.5, {'reason': 'no_lingua_confidence'}

        best_lang = confidences[0].language
        best_score = confidences[0].value
        best_iso = LINGUA_TO_ISO.get(best_lang, 'en')

        # Devanagari Disambiguation (Hindi vs Marathi)
        dev_share = scripts.get('Devanagari', 0)
        if dev_share >= 0.35:
            # Check Hindi vs Marathi scores
            hi_score = next((c.value for c in confidences if c.language == Language.HINDI), 0.0)
            mr_score = next((c.value for c in confidences if c.language == Language.MARATHI), 0.0)
            if mr_score > hi_score and mr_score > 0.2:
                best_iso = 'mr'
                best_score = mr_score
            else:
                best_iso = 'hi'
                best_score = max(hi_score, dev_share)

        # Arabic Script Disambiguation (Arabic vs Urdu)
        arab_share = scripts.get('Arabic', 0)
        if arab_share >= 0.35:
            ur_score = next((c.value for c in confidences if c.language == Language.URDU), 0.0)
            ar_score = next((c.value for c in confidences if c.language == Language.ARABIC), 0.0)
            if ur_score > ar_score:
                best_iso = 'ur'
                best_score = ur_score
            else:
                best_iso = 'ar'
                best_score = max(ar_score, arab_share)

        # Hinglish Detection (Hindi written in Devanagari with technical English terms)
        # If Devanagari is dominant or substantial (>25%), treat as Hindi
        if dev_share >= 0.25 and best_iso == 'en':
            best_iso = 'hi'
            best_score = 0.85

        return best_iso, float(best_score), {
            'scripts': scripts,
            'top_score': float(best_score),
            'detected_name': ISO_TO_NAME.get(best_iso, 'English'),
        }
    except Exception as exc:
        logger.warning(f"Language detection exception: {exc}")
        return 'en', 0.5, {'error': str(exc), 'fallback': 'en'}


def is_garbled_legacy_text(text: str) -> Tuple[bool, str]:
    """
    Detects if text extracted from a PDF/DOCX represents legacy 8-bit font gibberish
    (such as Kruti Dev, DevLys, Shree-Lipi, or Saral).
    Characteristics:
    - High concentration of unusual ASCII punctuation sequences (e.g. 'iz'u', 'dksbZ', ';k', 'vFkok')
    - Absence of actual Devanagari/Gujarati codepoints while having non-English word patterns
    - High frequency of unpronounceable consonant clusters in ASCII
    """
    if not text or len(text) < 40:
        return False, ""

    sample = text[:3000]
    total_chars = len(sample)

    # Legacy font marker sequences commonly found in Kruti Dev / DevLys
    kruti_markers = [
        'iz\'u', 'dksbZ', ';k', 'vFkok', 'fuEufyf[kr', 'mRrj', 'izdkj',
        'lafgrk', 'Hkkjr', 'le;k', 'gksrk', 'djsa', 'fdrkc', 'iBu'
    ]
    kruti_hits = sum(1 for m in kruti_markers if m in sample)
    if kruti_hits >= 2:
        return True, "Legacy Kruti Dev/DevLys 8-bit font detected."

    # Shree-Lipi / Saral Gujarati markers
    shree_markers = ['Á', 'Â', 'Ã', 'Ä', 'Å', 'Æ', 'Ç', 'È', 'É', 'Ê', 'Ë', 'Ì', 'Í', 'Î', 'Ï']
    shree_hits = sum(sample.count(ch) for ch in shree_markers)
    if shree_hits >= 15:
        return True, "Legacy Shree-Lipi/Saral 8-bit font detected."

    # Extreme ratio of misplaced symbols
    weird_symbols = sum(1 for ch in sample if ch in '^~`|\\_§±')
    if weird_symbols / total_chars > 0.08:
        return True, "Abnormal symbol density indicating non-Unicode encoding."

    return False, ""


def determine_paper_language(documents_text: List[Dict[str, Any]]) -> Tuple[str, float, Dict[str, Any]]:
    """
    Deterministically determines the paper language across all uploaded documents.
    Weighted by text length.
    If syllabus is explicitly marked, syllabus language takes precedence.
    """
    if not documents_text:
        return 'en', 1.0, {'status': 'default', 'reason': 'no_documents'}

    language_weights: Dict[str, float] = {}
    syllabus_lang: Optional[str] = None
    syllabus_conf: float = 0.0
    total_weight = 0.0

    for doc in documents_text:
        raw_text = doc.get('text', '')
        if not raw_text:
            continue

        weight = max(1.0, float(len(raw_text)))
        lang_code, conf, meta = detect_language(raw_text)

        is_syllabus = doc.get('is_syllabus', False) or 'syllabus' in doc.get('source', '').lower()
        if is_syllabus and syllabus_lang is None:
            syllabus_lang = lang_code
            syllabus_conf = conf

        language_weights[lang_code] = language_weights.get(lang_code, 0.0) + (weight * conf)
        total_weight += weight

    if not language_weights or total_weight == 0:
        return 'en', 1.0, {'status': 'default', 'reason': 'empty_weights'}

    # Normalize weights into percentages
    shares = {lang: w / total_weight for lang, w in language_weights.items()}
    sorted_shares = sorted(shares.items(), key=lambda x: x[1], reverse=True)
    dominant_lang, top_share = sorted_shares[0]

    # If syllabus language was detected with high confidence and has substantial share (>20%)
    if syllabus_lang and syllabus_lang != dominant_lang and shares.get(syllabus_lang, 0) >= 0.20:
        decision = syllabus_lang
        decision_conf = syllabus_conf
        reason = f"Prioritized syllabus language '{syllabus_lang}' ({shares.get(syllabus_lang, 0):.1%} share)"
    else:
        decision = dominant_lang
        decision_conf = top_share
        reason = f"Dominant language by text share ({top_share:.1%})"

    return decision, decision_conf, {
        'decision': decision,
        'confidence': decision_conf,
        'shares': shares,
        'reason': reason,
        'is_rtl': decision in RTL_LANGUAGES,
        'language_name': ISO_TO_NAME.get(decision, 'English'),
        'script': ISO_TO_SCRIPT.get(decision, 'Latin'),
    }
