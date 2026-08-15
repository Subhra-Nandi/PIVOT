"""Checks that an extracted value actually appears in the source content it
cites — catches outright fabrication without a second LLM call.

This is the salvageable idea from evaluating RAGAS-style "faithfulness"
scoring for Phase 4, done as a free rule check instead of an LLM-judge call.

Uses word-overlap rather than exact substring matching: the extraction
prompt encourages normalizing/summarizing values (e.g. a source saying
"User button that can also put the chip into bootloading mode" gets
extracted as "User button (bootloading mode)") — an exact-phrase match would
wrongly flag that legitimate paraphrase as ungrounded. Word overlap accepts
paraphrases while still catching a value whose words don't appear in the
cited source at all.
"""

from __future__ import annotations

import re

from app.ingestion.models import BlockType, ContentBlock

# Below this fraction of the value's significant words found in the block
# text, the value is considered ungrounded. High enough to catch fabrication,
# low enough to tolerate paraphrasing/normalization.
_OVERLAP_THRESHOLD = 0.6

_STOPWORDS = {
    "a", "an", "the", "and", "or", "of", "to", "in", "on", "for", "with",
    "is", "are", "was", "were", "be", "as", "at", "by", "this", "that",
}

# Digits and letters are matched as separate tokens so a value like "12"
# still overlaps with source text written as "12V" (one glued alphanumeric
# token) rather than being swallowed into an unmatchable "12v" chunk.
_WORD_PATTERN = re.compile(r"[a-z]+|[0-9]+(?:\.[0-9]+)?")

# A boolean-flag value ("Yes"/"No"/"True"/"False"/"N/A") is the LLM's
# judgment about a feature's presence, synthesized from descriptive prose —
# not a verbatim fact that should appear in the source text. "Level shifting
# on the UART and reset pin" grounds a spec valued "Yes" perfectly well even
# though the word "yes" never appears anywhere in that sentence. Treated as
# trivially grounded, same as an empty value: nothing quotable to fabricate.
_BOOLEAN_VALUES = {"yes", "no", "true", "false", "n/a", "na", "none", "present", "absent"}


def _significant_words(text: str) -> set[str]:
    words = _WORD_PATTERN.findall(text.lower())
    return {w for w in words if w not in _STOPWORDS}


def _block_text(block: ContentBlock) -> str:
    if block.type == BlockType.TABLE and block.table:
        return " ".join(cell for row in block.table for cell in row if cell)
    return block.text or ""


def find_block(blocks: list[ContentBlock], block_id: str) -> ContentBlock | None:
    for block in blocks:
        if block.block_id == block_id:
            return block
    return None


def check_groundedness(value: str, block: ContentBlock) -> bool:
    """True if at least `_OVERLAP_THRESHOLD` of `value`'s significant words
    appear in `block`'s text/table content. An empty value, a boolean-flag
    value, or one with no significant words (e.g. pure punctuation), is
    trivially grounded — nothing quotable to fabricate."""
    if value.strip().lower() in _BOOLEAN_VALUES:
        return True

    value_words = _significant_words(value)
    if not value_words:
        return True

    block_words = _significant_words(_block_text(block))
    overlap = len(value_words & block_words) / len(value_words)
    return overlap >= _OVERLAP_THRESHOLD
