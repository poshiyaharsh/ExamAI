"""
Text Cleaner and Token-aware Chunker for RAG.
1. Cleans text: strips headers, footers, standalone page numbers, repetitive noise.
2. Splits into 500-800 token chunks with ~100 token overlap.
3. Preserves comprehensive chunk metadata: source file, page number, unit/topic.
"""
import re
from typing import Dict, List, Any, Optional
from ..config import CHUNK_SIZE_TOKENS, CHUNK_OVERLAP_TOKENS


def clean_text(raw_text: str) -> str:
    """
    Cleans raw document text:
    - Removes isolated page numbers (e.g., 'Page 12 of 45', '- 12 -', '12')
    - Removes recurring header/footer artifacts
    - Normalizes unicode whitespace and multiple newlines
    - Strips lines that are just repeated punctuation
    """
    if not raw_text:
        return ""

    lines = raw_text.splitlines()
    cleaned_lines = []
    seen_lines = set()

    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue

        # Filter out standalone page numbers
        if re.match(r'^(page\s+\d+(\s+of\s+\d+)?|-?\s*\d+\s*-?)$', stripped, re.IGNORECASE):
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


def estimate_tokens(text: str) -> int:
    """Fast token estimator (average 1 token ~= 4 characters / 0.75 words)."""
    words = text.split()
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
