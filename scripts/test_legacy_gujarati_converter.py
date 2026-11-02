import sys
import os
import re
import pymupdf

if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

mapping = {
    # Quotes & Punctuation
    '\u00d2': '"', '\u00d3': '"', '\u02c6': '-',
    
    # Vowels
    '\u00b1\u00eb': 'આ', '\u00b1\u00f9': 'ઓ', '\u00b1\u00fa': 'ઔ', '\u00b1\u00f5': 'એ', '\u00b1\u00f6': 'ઐ', '\u00b1': 'અ',
    '\u00b3': 'ઇ', '\u00b4': 'ઈ', '\u00b5': 'ઉ', '\u00b6': 'ઊ', '\u00ba': 'ઋ',

    # Matras
    '\u00eb': 'ા', '\u00ed': 'ી', '\u00f5': 'ે', '\u00f6': 'ૈ', '\u00f9': 'ો', '\u00fa': 'ૌ',
    '\u00f0': 'ુ', '\u00f1': 'ૂ', '\u00f2': 'ૃ', '\u00a7': 'ૃ',
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

    # Conjuncts / Half-letters
    'Z': 'ક્ષ', 'h': 'ત્ર', '\u00bd': 'જા', 'l': 'શ્રે', '\u00ac': 'શ્ર',
    'Q': 'મ્', 'M': 'પ', 'V': 'સ્', 'I': 'ત્', 'L': 'ન્',
    'S': 'સ્', 'N\u00fb': 'ફ્ટ', 'N': 'ફ્',
    '\u00bf': 'ક્ર', '\u00fe': '્ર', '\u00ef': 'ત્',

    # Common Saral ligatures
    'A': 'ખ્ય', 'B': 'ગ્ય', 'O': 'બ્દ', 'w': 'રૂ', '¦': 'દ્વા',
    '²': 'પૃ', 'J': 'થ્થ', 't': 'દ્દો', 'T': 'વ્ય', '@': 'ક્ક',
    'K': 'ક્લ', 'd': 'દ્ર', 'j': 'જ્ઞ', 'G': 'ધ્ર', 'W': 'ષ્ટ્ર',
    'F': 'ષ્ટ', 'Y': 'હ્મ', 'R': 'હ્ય', '−': 'પ્ર', '‘': 'શ્ન',

    # Modifiers
    '\u00fd': 'ર્', '\u00f3': 'ર્',
}

def convert_shree_to_unicode(text: str) -> str:
    def repl_i(m):
        char = m.group(1)
        mapped = mapping.get(char, char)
        return mapped + 'િ'
    text_processed = re.sub(r'\u00ec(.)', repl_i, text)
    for k in sorted(mapping.keys(), key=len, reverse=True):
        text_processed = text_processed.replace(k, mapping[k])
    text_processed = re.sub(r'([^\s])\u00fd', r'ર્\1', text_processed)
    text_processed = re.sub(r'([^\s])\u00f3', r'ર્\1', text_processed)
    return text_processed.replace('ાે', 'ો').replace('ાૈ', 'ૌ')

def extract_pdf_page_smart(page) -> str:
    d = page.get_text('dict')
    page_lines = []
    for b in d.get('blocks', []):
        if b.get('type') == 0:  # text block
            for l in b.get('lines', []):
                line_str = ''
                for s in l.get('spans', []):
                    font = s.get('font', '').lower()
                    stext = s.get('text', '')
                    # If it's a standard latin font, keep as is
                    if any(eng in font for eng in ['times', 'arial', 'helvetica', 'courier', 'calibri', 'symbol']):
                        line_str += stext
                    else:
                        line_str += convert_shree_to_unicode(stext)
                if line_str.strip():
                    page_lines.append(line_str.strip())
    return '\n'.join(page_lines)

if __name__ == '__main__':
    doc = pymupdf.open(r'C:\Users\Harsh Poshiya\Downloads\computer-book.PDF')
    print("Page 11 Smart Extracted:")
    print(extract_pdf_page_smart(doc[10])[:800])
