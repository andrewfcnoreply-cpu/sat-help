"""
Safe formatting for text that came back from the AI.

Claude is asked to use a few simple HTML tags (like <sup> for exponents).
Before we show that text on screen we escape EVERYTHING, then turn back on
only a short list of harmless tags. That way odd output can never break the
layout or inject anything unexpected.
"""

import html
import re

# Tags we allow through. Anything else is shown as plain text.
_ALLOWED = ["sup", "sub", "i", "b", "u", "em", "strong"]


def to_display_html(text: str) -> str:
    """Convert AI text into safe HTML for a Qt label."""
    safe = html.escape(text or "", quote=False)
    for tag in _ALLOWED:
        safe = safe.replace(f"&lt;{tag}&gt;", f"<{tag}>")
        safe = safe.replace(f"&lt;/{tag}&gt;", f"</{tag}>")
    # <br> in any common spelling, plus real newlines, become line breaks.
    safe = re.sub(r"&lt;br\s*/?&gt;", "<br>", safe)
    safe = safe.replace("\n", "<br>")
    return safe


def to_plain(text: str) -> str:
    """Strip tags, for places like the navigator that only show plain text."""
    return html.unescape(re.sub(r"<[^>]+>", "", text or ""))
