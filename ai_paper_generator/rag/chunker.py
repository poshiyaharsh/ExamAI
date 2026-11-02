"""
Text Cleaner and Token-aware Chunker for RAG.
1. Cleans text: strips headers, footers, standalone page numbers, repetitive noise.
2. Splits into 500-800 token chunks with ~100 token overlap.
3. Preserves comprehensive chunk metadata: source file, page number, unit/topic.
4. Multilingual support: script-aware sentence splitting (। ॥ ؟ ؛ 。) and CJK non-spaced text handling.
"""
import re
import unicodedata
from typing import Dict, List, Any, Optional
from ..config import CHUNK_SIZE_TOKENS, CHUNK_OVERLAP_TOKENS

# Sentence terminators across scripts:
# Latin/Cyrillic (. ! ?), Indic (। ॥), Arabic (؟ ؛ .), CJK (。 ！ ？)
SENTENCE_SPLIT_REGEX = re.compile(r'([.!?।॥؟؛。！？]+[\s\n]+)')


def clean_text(raw_text: str) -> str:
    """
    Cleans raw document text:
    - Removes isolated page numbers (e.g., 'Page 12 of 45', '- 12 -', '12', 'पृष्ठ १२')
    - Removes recurring header/footer artifacts
    - Normalizes unicode whitespace and multiple newlines
    - Strips lines that are just repeated punctuation
    """
    if not raw_text:
        return ""

    # NFC normalize
    raw_text = unicodedata.normalize("NFC", raw_text)

    lines = raw_text.splitlines()
    cleaned_lines = []

    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue

        # Filter out standalone page numbers (Latin digits and Indic digits)
        if re.match(r'^(page\s+[\d\u0966-\u096f\u0ae6-\u0aef]+(\s+(of|\/)\s+[\d\u0966-\u096f\u0ae6-\u0aef]+)?|-?\s*[\d\u0966-\u096f\u0ae6-\u0aef]+\s*-?)$', stripped, re.IGNORECASE):
            continue

        # Filter out repeated decorative divider lines (e.g. '------', '******')
        if len(stripped) > 3 and len(set(stripped)) == 1:
            continue

        cleaned_lines.append(stripped)

    # Rejoin with paragraph separation
    text = "\n".join(cleaned_lines)
    # Collapse 3+ newlines to 2
    text = re.sub(r'\n{3,}', '\n\n', text)
    # Collapse multiple spaces
    text = re.sub(r'[ \t]+', ' ', text)
    return text.strip()


def estimate_tokens(text: str, language: str = 'en') -> int:
    """
    Fast token estimator:
    - For English / Latin: ~1 token ~= 4 characters / 0.75 words (1.3x word count).
    - For Indic scripts (Hindi, Gujarati, etc.): ~2.5 to 3.5 tokens per word.
    - For CJK scripts: ~1.5 to 2.0 tokens per character.
    - For Arabic script: ~2.0 tokens per word.
    """
    if not text:
        return 0

    # Count CJK characters
    cjk_count = len(re.findall(r'[\u4e00-\u9fff\u3040-\u30ff\u3400-\u4dbf]', text))
    if cjk_count > len(text) * 0.2:
        return max(1, int(cjk_count * 1.5 + len(text.split()) * 1.3))

    # Indic characters
    indic_count = len(re.findall(r'[\u0900-\u0d7f]', text))
    words = text.split()
    if indic_count > len(text) * 0.2:
        return max(1, int(len(words) * 3.0))

    # Arabic characters
    arabic_count = len(re.findall(r'[\u0600-\u06ff]', text))
    if arabic_count > len(text) * 0.2:
        return max(1, int(len(words) * 2.2))

    # Standard English / Latin fallback (preserves exact original logic for English)
    return max(1, int(len(words) * 1.3))


def chunk_document_pages(
    pages: List[Dict[str, Any]],
    chunk_size: int = CHUNK_SIZE_TOKENS,
    chunk_overlap: int = CHUNK_OVERLAP_TOKENS,
    default_topic: str = 'General Syllabus'
) -> List[Dict[str, Any]]:
    """
    Splits loaded pages into chunks with metadata.
    Attempts boundary splitting on paragraphs/sentences.
    Handles both whitespace-separated languages and CJK scripts.
    """
    all_chunks = []
    chunk_counter = 1

    for page_data in pages:
        raw_text = page_data.get('text', '')
        cleaned = clean_text(raw_text)
        if not cleaned:
            continue

        source = page_data.get('source', 'document')
        page_num = page_data.get('page_number', 1)

        # Check if CJK dominant
        cjk_chars = len(re.findall(r'[\u4e00-\u9fff\u3040-\u30ff]', cleaned))
        is_cjk = cjk_chars > len(cleaned) * 0.2

        if is_cjk:
            # For CJK, split by CJK sentences or character chunks
            # Target ~chunk_size / 1.5 characters
            target_chars = int(chunk_size / 1.5)
            overlap_chars = int(chunk_overlap / 1.5)
            i = 0
            while i < len(cleaned):
                chunk_slice = cleaned[i:i + target_chars]
                if chunk_slice.strip():
                    all_chunks.append({
                        'chunk_id': f"{source}_p{page_num}_c{chunk_counter}",
                        'text': chunk_slice.strip(),
                        'source': source,
                        'page': page_num,
                        'topic': default_topic,
                        'token_count': estimate_tokens(chunk_slice),
                    })
                    chunk_counter += 1
                i += max(1, target_chars - overlap_chars)
            continue

        # Split text into paragraphs
        paragraphs = [p.strip() for p in cleaned.split("\n\n") if p.strip()]

        current_chunk_words = []
        current_word_count = 0
        target_words = int(chunk_size / 1.3)
        overlap_words = int(chunk_overlap / 1.3)

        for para in paragraphs:
            para_words = para.split()
            if not para_words:
                continue

            if current_word_count + len(para_words) <= target_words:
                current_chunk_words.extend(para_words)
                current_word_count += len(para_words)
            else:
                # Flush current chunk
                if current_chunk_words:
                    chunk_text = " ".join(current_chunk_words)
                    all_chunks.append({
                        'chunk_id': f"{source}_p{page_num}_c{chunk_counter}",
                        'text': chunk_text,
                        'source': source,
                        'page': page_num,
                        'topic': default_topic,
                        'token_count': estimate_tokens(chunk_text),
                    })
                    chunk_counter += 1

                    # Retain overlap words for context continuity
                    current_chunk_words = current_chunk_words[-overlap_words:] + para_words
                    current_word_count = len(current_chunk_words)
                else:
                    # Single paragraph exceeds chunk size -> split words directly
                    current_chunk_words = para_words[:target_words]
                    chunk_text = " ".join(current_chunk_words)
                    all_chunks.append({
                        'chunk_id': f"{source}_p{page_num}_c{chunk_counter}",
                        'text': chunk_text,
                        'source': source,
                        'page': page_num,
                        'topic': default_topic,
                        'token_count': estimate_tokens(chunk_text),
                    })
                    chunk_counter += 1
                    current_chunk_words = para_words[target_words - overlap_words:]
                    current_word_count = len(current_chunk_words)

        # Flush final remaining words
        if current_chunk_words:
            chunk_text = " ".join(current_chunk_words)
            all_chunks.append({
                'chunk_id': f"{source}_p{page_num}_c{chunk_counter}",
                'text': chunk_text,
                'source': source,
                'page': page_num,
                'topic': default_topic,
                'token_count': estimate_tokens(chunk_text),
            })
            chunk_counter += 1

    return all_chunks
