# Task: terminal-aware word wrap

Implement in `wrap.py` (stdlib only, `unicodedata` is fine):

## `display_width(s: str) -> int`
Terminal column width of a string:
- characters whose `unicodedata.east_asian_width` is `"W"` or `"F"` → 2 columns
- combining characters (`unicodedata.combining(c) != 0`), U+200B and U+200D → 0 columns
- everything else → 1 column

## `wrap(text: str, width: int) -> list[str]`
- `width` must be an int >= 1, else `ValueError`.
- **Paragraphs** are separated by one or more blank lines (lines that are empty or whitespace-only).
  Output the wrapped lines of each paragraph, with exactly one `""` between paragraphs.
  Leading/trailing blank lines produce nothing. Empty or whitespace-only text → `[]`.
- Inside a paragraph, words are separated by any whitespace (single newlines and tabs too).
  Lines are filled greedily: words joined by a single space while the line's display width stays `<= width`.
- **Long words** (display width > `width`) always start on a new line (unless the current line is empty)
  and are cut into chunks of at most `width` columns. The last chunk becomes the current line, and later
  words may be appended to it if they fit.
- Cutting must never separate a combining mark / zero-width char from the character before it. A wide
  character that doesn't fit in the rest of a chunk moves to the next chunk. If `width == 1` a wide
  character goes alone on its own line.
- No line has leading or trailing spaces.

Examples:
```
wrap("The quick brown fox", 10)  == ["The quick", "brown fox"]
wrap("hi abcdefg xy", 4)        == ["hi", "abcd", "efg", "xy"]
wrap("abcdef x", 4)              == ["abcd", "ef x"]
wrap("日本語", 5)                == ["日本", "語"]
```
