import re
import unicodedata


def _cw(c):
    if unicodedata.combining(c) or c in "​‍":
        return 0
    return 2 if unicodedata.east_asian_width(c) in ("W", "F") else 1


def display_width(s):
    return sum(_cw(c) for c in s)


def _clusters(word):
    out = []
    for c in word:
        if out and _cw(c) == 0:
            out[-1] += c
        else:
            out.append(c)
    return out


def _chop(word, width):
    chunks, cur, w = [], "", 0
    for cl in _clusters(word):
        cw = display_width(cl)
        if cur and w + cw > width:
            chunks.append(cur)
            cur, w = "", 0
        cur += cl
        w += cw
    if cur:
        chunks.append(cur)
    return chunks


def _para(words, width):
    lines, cur = [], ""
    for wd in words:
        ww = display_width(wd)
        if ww > width:
            if cur:
                lines.append(cur)
            chunks = _chop(wd, width)
            lines += chunks[:-1]
            cur = chunks[-1]
        elif not cur:
            cur = wd
        elif display_width(cur) + 1 + ww <= width:
            cur += " " + wd
        else:
            lines.append(cur)
            cur = wd
    if cur:
        lines.append(cur)
    return lines


def wrap(text, width):
    if not isinstance(width, int) or isinstance(width, bool) or width < 1:
        raise ValueError("width")
    paras = re.split(r"\n[ \t\r\f\v]*\n(?:[ \t\r\f\v]*\n)*", text.replace("\r\n", "\n"))
    out = []
    for p in paras:
        words = p.split()
        if not words:
            continue
        if out:
            out.append("")
        out += _para(words, width)
    return out
