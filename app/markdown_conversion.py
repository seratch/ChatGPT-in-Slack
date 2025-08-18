import re
import unicodedata


# Conversion from Slack mrkdwn to OpenAI markdown
# See also: https://api.slack.com/reference/surfaces/formatting#basics
def slack_to_markdown(content: str) -> str:
    # Split the input string into parts based on code blocks and inline code
    parts = re.split(r"(?s)(```.+?```|`[^`\n]+?`)", content)

    # Apply the bold, italic, and strikethrough formatting to text not within code
    result = ""
    for part in parts:
        if part.startswith("```") or part.startswith("`"):
            result += part
        else:
            for o, n in [
                (r"\*(?!\s)([^\*\n]+?)(?<!\s)\*", r"**\1**"),  # *bold* to **bold**
                (r"_(?!\s)([^_\n]+?)(?<!\s)_", r"*\1*"),  # _italic_ to *italic*
                (r"~(?!\s)([^~\n]+?)(?<!\s)~", r"~~\1~~"),  # ~strike~ to ~~strike~~
            ]:
                part = re.sub(o, n, part)
            result += part
    return result


# Conversion from OpenAI markdown to Slack mrkdwn
# See also: https://api.slack.com/reference/surfaces/formatting#basics
def markdown_to_slack(content: str) -> str:
    # Split the input string into parts based on code blocks and inline code
    parts = re.split(r"(?s)(```.+?```|`[^`\n]+?`)", content)

    # Apply the bold, italic, and strikethrough formatting to text not within code
    result = ""
    for idx, part in enumerate(parts):
        if part.startswith("```") or part.startswith("`"):
            # Insert ASCII spaces around code spans/blocks when adjacent to
            # East Asian wide/fullwidth characters to improve readability.
            left_space = False
            right_space = False
            if result:
                prev = result[-1]
                if (not prev.isspace()) and unicodedata.east_asian_width(prev) in ("W", "F"):
                    left_space = True
            if idx + 1 < len(parts):
                nxt_part = parts[idx + 1]
                if nxt_part:
                    nxt = nxt_part[0]
                    if (not nxt.isspace()) and unicodedata.east_asian_width(nxt) in ("W", "F"):
                        right_space = True
            if left_space:
                result += " "
            result += part
            if right_space:
                result += " "
        else:
            for o, n in [
                (
                    r"\*\*\*(?!\s)([^\*\n]+?)(?<!\s)\*\*\*",
                    r"_*\1*_",
                ),  # ***bold italic*** to *_bold italic_*
                (
                    r"(?<![\*_])\*(?!\s)([^\*\n]+?)(?<!\s)\*(?![\*_])",
                    r"_\1_",
                ),  # *italic* to _italic_
                (r"\*\*(?!\s)([^\*\n]+?)(?<!\s)\*\*", r"*\1*"),  # **bold** to *bold*
                (r"__(?!\s)([^_\n]+?)(?<!\s)__", r"*\1*"),  # __bold__ to *bold*
                (r"~~(?!\s)([^~\n]+?)(?<!\s)~~", r"~\1~"),  # ~~strike~~ to ~strike~
            ]:
                part = re.sub(o, n, part)
            # Insert ASCII spaces around Slack formatting when adjacent to
            # East Asian wide/fullwidth characters (e.g., CJK, Hiragana,
            # Katakana, Hangul, Bopomofo, and fullwidth punctuation).
            # This improves mrkdwn rendering when tokens touch wide chars.

            def _is_eaw_wide(ch: str) -> bool:
                # East Asian Width: W (wide) and F (fullwidth)
                return unicodedata.east_asian_width(ch) in ("W", "F")

            def _add_space_around_matches(text: str, pattern: re.Pattern) -> str:
                out = []
                last = 0
                for m in pattern.finditer(text):
                    start, end = m.start(), m.end()
                    out.append(text[last:start])
                    if start > 0:
                        prev = text[start - 1]
                        if not prev.isspace() and _is_eaw_wide(prev):
                            out.append(" ")
                    out.append(m.group(0))
                    if end < len(text):
                        nxt = text[end]
                        if not nxt.isspace() and _is_eaw_wide(nxt):
                            out.append(" ")
                    last = end
                out.append(text[last:])
                return "".join(out)

            patterns = [
                re.compile(r"_\*(?!\s)(.+?)(?<!\s)\*_"),  # *_bold italic_*
                re.compile(r"\*(?!\s)([^\*\n]+?)(?<!\s)\*"),  # *bold*
                re.compile(r"_(?!\s)([^_\n]+?)(?<!\s)_"),  # _italic_
                re.compile(r"~(?!\s)([^~\n]+?)(?<!\s)~"),  # ~strike~
            ]

            for ptn in patterns:
                part = _add_space_around_matches(part, ptn)
            result += part
    return result
