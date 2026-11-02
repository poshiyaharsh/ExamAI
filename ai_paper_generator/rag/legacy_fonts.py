"""
Legacy 8-bit Font Converter for Indian Regional Languages.
Supports transparent decoding of legacy publishing formats (such as Shree-Lipi / Saral Gujarati)
into standard Unicode NFC text during PDF extraction.
Preserves English spans intact while converting regional glyphs.
"""
import re
import unicodedata
from typing import Dict, List, Any
from pathlib import Path


# Shree-Lipi / Saral Gujarati 8-bit to Unicode Gujarati mapping
SHREE_GUJARATI_MAP: Dict[str, str] = {
    # Quotes & Punctuation
    '\u00d2': '"', '\u00d3': '"', '\u02c6': '-',

    # Independent Vowels
    '\u00b1\u00eb': 'આ', '\u00b1\u00f9': 'ઓ', '\u00b1\u00fa': 'ઔ',
    '\u00b1\u00f5': 'એ', '\u00b1\u00f6': 'ઐ', '\u00b1': 'અ',
    '\u00b3': 'ઇ', '\u00b4': 'ઈ', '\u00b5': 'ઉ', '\u00b6': 'ઊ', '\u00ba': 'ઋ',

    # Dependent Vowel Signs (Matras)
    '\u00eb': 'ા', '\u00ed': 'ી', '\u00f5': 'ે', '\u00f6': 'ૈ',
    '\u00f9': 'ો', '\u00fa': 'ૌ', '\u00f0': 'ુ', '\u00f1': 'ૂ',
    '\u00f2': 'ૃ', '\u00a7': 'ૃ',
    '_': 'ં', '~': 'ઁ',

    # Consonants
    '\u00c0': 'ક', '\u00c1': 'ખ', '\u00c2': 'ખ', '\u00c3': 'ગ', '\u00c4': 'ઘ', 'C': 'ઘ', 'C\u00eb': 'ઘા',
    '\u00c7': 'ચ', '\u00c8': 'છ', '\u00c9': 'જ', '\u00ca': 'ઝ', '{': 'ઝ',
    '\u00cb': 'ટ', '\u00cc': 'ઠ', '\u00cd': 'ડ', '\u00ce': 'ઢ', '\u00cf': 'ઢ',
    'H': 'ણ', '\u00d0': 'ણ',
    '\u00d6': 'ત', '\u00d1': 'ત', '\u00d7': 'થ', '\u00d8': 'દ', '\u00d9': 'દ', '\u00d4': 'ધ', '\u00de': 'ન',
    '\u00d5': 'પ', '\u00da': 'બ', '\u00db': 'ભ', '\u00dc': 'મ',
    '\u00dd': 'ય', '\u00df': 'ર', '\u00e0': 'લ', '\u00e1': 'લ', '\u00e2': 'ળ', '\u00e3': 'ળ', '\u00e4': 'વ',
    '\u00e5': 'શ', '\u00e6': 'ષ', '\u00e7': 'સ', '\u00e8': 'હ', '\u00e9': 'હ',

    # Conjuncts & Half Consonants
    'Zë': 'ક્ષ', 'Z': 'ક્ષ', 'h': 'ત્ર', '\u00bd': 'જા', 'l': 'શ્રે', '\u00ac': 'શ્ર',
    'Q': 'મ્', 'M': 'પ્', 'V': 'સ્', 'I': 'ત્', 'L': 'ન્',
    'S': 'સ્', 'N\u00fb': 'ફ્ટ', 'N': 'ફ્',
    '\u00bf': 'ક્ર', '\u00fe': '્ર', '\u00ef': 'ત્',
    'AÝ': 'ખ્ય', 'A': 'ખ્ય', 'B': 'ગ્ય', 'O': 'બ્દ', 'w': 'રૂ', '¦': 'દ્વા',
    '²': 'પૃ', 'J': 'થ્થ', 't': 'દ્દો', 'T': 'વ્ય', '@': 'ક્ક',
    'K': 'ક્લ', 'd': 'દ્ર', 'j': 'જ્ઞ', 'G': 'ધ્ર', 'W': 'ષ્ટ્ર',
    'F': 'ષ્ટ', 'Y': 'હ્મ', 'R': 'હ્ય', '−': 'પ્ર', '‘': 'શ્ન',

    # Composite vowels
    '\u00eb\u00f9': 'ો', '\u00eb\u00f5': 'ો',

    # Reph & Modifiers
    '\u00fd': 'ર્', '\u00f3': 'ર્',
}


def convert_shree_to_unicode(text: str) -> str:
    """Converts a raw 8-bit Shree-Lipi / Saral string to Unicode Gujarati."""
    if not text:
        return ""

    # 1. Handle hrasva-i prefix '\u00ec' (ì)
    # In legacy 8-bit fonts, 'ì' precedes the consonant it attaches to
    def repl_i(m):
        char = m.group(1)
        mapped = SHREE_GUJARATI_MAP.get(char, char)
        return mapped + 'િ'

    text_processed = re.sub(r'\u00ec(.)', repl_i, text)

    # 2. Multi-character and standard character mappings (longest matches first)
    for k in sorted(SHREE_GUJARATI_MAP.keys(), key=len, reverse=True):
        text_processed = text_processed.replace(k, SHREE_GUJARATI_MAP[k])

    # 3. Handle Reph: '\u00fd' (ý) or '\u00f3' (ó) placed after a consonant means 'ર્' before it
    text_processed = re.sub(r'([^\s])\u00fd', r'ર્\1', text_processed)
    text_processed = re.sub(r'([^\s])\u00f3', r'ર્\1', text_processed)

    # 4. Canonical Gujarati vowel composition
    # 'ા' (aa) + 'ે' (e) -> 'ો' (o)
    # 'ા' (aa) + 'ૈ' (ai) -> 'ૌ' (au)
    text_processed = text_processed.replace('ાે', 'ો').replace('ાૈ', 'ૌ')

    # 5. Unicode NFC normalization
    return unicodedata.normalize('NFC', text_processed)


def extract_legacy_pdf(file_path: str) -> List[Dict[str, Any]]:
    """
    Extracts text from a legacy 8-bit encoded PDF using font-aware block inspection.
    Spans using standard English fonts are preserved verbatim.
    Spans using legacy Indian fonts (Shree-Lipi, Saral) are converted to Unicode Gujarati.
    """
    try:
        import pymupdf as fitz
    except ImportError:
        import fitz

    doc = fitz.open(file_path)
    pages = []
    base_name = Path(file_path).name

    for page_idx, page in enumerate(doc, start=1):
        d = page.get_text('dict')
        page_lines = []
        for b in d.get('blocks', []):
            if b.get('type') == 0:  # Text block
                for l in b.get('lines', []):
                    line_str = ''
                    for s in l.get('spans', []):
                        font = s.get('font', '').lower()
                        stext = s.get('text', '')
                        # If the span uses a recognized Latin font, keep it intact
                        if any(eng in font for eng in ['times', 'arial', 'helvetica', 'courier', 'calibri', 'symbol']):
                            line_str += stext
                        else:
                            line_str += convert_shree_to_unicode(stext)
                    if line_str.strip():
                        page_lines.append(line_str.strip())

        full_page_text = "\n".join(page_lines).strip()
        if full_page_text:
            pages.append({
                'page_number': page_idx,
                'text': full_page_text,
                'source': base_name,
            })

    doc.close()
    return pages
