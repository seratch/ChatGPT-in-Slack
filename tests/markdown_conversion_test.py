from app.markdown_conversion import (
    markdown_to_slack,
    slack_to_markdown,
)


def test_markdown_to_slack():
    for content, expected in [
        (
            "Sentence with **bold text**, __bold text__, *italic text*, _italic text_ and ~~strikethrough text~~.",
            "Sentence with *bold text*, *bold text*, _italic text_, _italic text_ and ~strikethrough text~.",
        ),
        (
            "Sentence with ***bold and italic text***, **_bold and italic text_**, and _**bold and italic text**_.",
            "Sentence with _*bold and italic text*_, *_bold and italic text_*, and _*bold and italic text*_.",
        ),
        (
            "Code block ```**text**, __text__, *text*, _text_ and ~~text~~``` shouldn't be changed.",
            "Code block ```**text**, __text__, *text*, _text_ and ~~text~~``` shouldn't be changed.",
        ),
        (
            "```Some `**bold text** inside inline code` inside a code block``` shouldn't be changed.",
            "```Some `**bold text** inside inline code` inside a code block``` shouldn't be changed.",
        ),
        (
            "Inline code `**text**, __text__, *text*, _text_ and ~~text~~` shouldn't be changed.",
            "Inline code `**text**, __text__, *text*, _text_ and ~~text~~` shouldn't be changed.",
        ),
        ("* bullets shouldn't\n* be changed", "* bullets shouldn't\n* be changed"),
        (
            "** not bold**, **not bold **, ** not bold **, ****, ** **, **  **, **   **",
            "** not bold**, **not bold **, ** not bold **, ****, ** **, **  **, **   **",
        ),
        (
            "__ not bold__, __not bold __, __ not bold __, ____, __ __, __  __, __   __",
            "__ not bold__, __not bold __, __ not bold __, ____, __ __, __  __, __   __",
        ),
        (
            "* not italic*, *not italic *, * not italic *, **, * *, *  *, *   *",
            "* not italic*, *not italic *, * not italic *, **, * *, *  *, *   *",
        ),
        (
            "_ not italic_, _not italic _, _ not italic _, __, _ _, _  _, _   _",
            "_ not italic_, _not italic _, _ not italic _, __, _ _, _  _, _   _",
        ),
        (
            "~~ not strikethrough~~, ~~not strikethrough ~~, ~~ not strikethrough ~~, ~~~~, ~~ ~~, ~~  ~~, ~~   ~~",
            "~~ not strikethrough~~, ~~not strikethrough ~~, ~~ not strikethrough ~~, ~~~~, ~~ ~~, ~~  ~~, ~~   ~~",
        ),
        (
            """The following multiline code block shouldn't be translated:
```
if 4*q + r - t < n*t:
    q, r, t, k, n, l = 10*q, 10*(r-n*t), t, k, (10*(3*q+r))//t - 10*n, l
else:
    q, r, t, k, n, l = q*l, (2*q+r)*l, t*l, k+1, (q*(7*k+2)+r*l)//(t*l), l+2
```""",
            """The following multiline code block shouldn't be translated:
```
if 4*q + r - t < n*t:
    q, r, t, k, n, l = 10*q, 10*(r-n*t), t, k, (10*(3*q+r))//t - 10*n, l
else:
    q, r, t, k, n, l = q*l, (2*q+r)*l, t*l, k+1, (q*(7*k+2)+r*l)//(t*l), l+2
```""",
        ),
    ]:
        result = markdown_to_slack(content)
        assert result == expected


def test_slack_to_markdown():
    for content, expected in [
        (
            "Sentence with *bold text*, _italic text_ and ~strikethrough text~.",
            "Sentence with **bold text**, *italic text* and ~~strikethrough text~~.",
        ),
        (
            "Sentence with _*bold and italic text*_ and *_bold and italic text_*.",
            "Sentence with ***bold and italic text*** and ***bold and italic text***.",
        ),
        (
            "Code block ```*text*, _text_ and ~text~``` shouldn't be changed.",
            "Code block ```*text*, _text_ and ~text~``` shouldn't be changed.",
        ),
        (
            "Inline code `*text*, _text_ and ~text~` shouldn't be changed.",
            "Inline code `*text*, _text_ and ~text~` shouldn't be changed.",
        ),
        (
            "```Some `*bold text* inside inline code` inside a code block``` shouldn't be changed.",
            "```Some `*bold text* inside inline code` inside a code block``` shouldn't be changed.",
        ),
        ("* bullets shouldn't\n* be changed", "* bullets shouldn't\n* be changed"),
        (
            "* not bold*, *not bold *, * not bold *, **, * *, *  *, *   *",
            "* not bold*, *not bold *, * not bold *, **, * *, *  *, *   *",
        ),
        (
            "_ not italic_, _not italic _, _ not italic _, __, _ _, _  _, _   _",
            "_ not italic_, _not italic _, _ not italic _, __, _ _, _  _, _   _",
        ),
        (
            "~ not strikethrough~, ~not strikethrough ~, ~ not strikethrough ~, ~~, ~ ~, ~  ~, ~   ~",
            "~ not strikethrough~, ~not strikethrough ~, ~ not strikethrough ~, ~~, ~ ~, ~  ~, ~   ~",
        ),
        (
            """The following multiline code block shouldn't be translated:
```
if 4*q + r - t < n*t:
    q, r, t, k, n, l = 10*q, 10*(r-n*t), t, k, (10*(3*q+r))//t - 10*n, l
else:
    q, r, t, k, n, l = q*l, (2*q+r)*l, t*l, k+1, (q*(7*k+2)+r*l)//(t*l), l+2
```""",
            """The following multiline code block shouldn't be translated:
```
if 4*q + r - t < n*t:
    q, r, t, k, n, l = 10*q, 10*(r-n*t), t, k, (10*(3*q+r))//t - 10*n, l
else:
    q, r, t, k, n, l = q*l, (2*q+r)*l, t*l, k+1, (q*(7*k+2)+r*l)//(t*l), l+2
```""",
        ),
    ]:
        result = slack_to_markdown(content)
        assert result == expected


def test_markdown_to_slack_eaw_spacing():
    # Ensure spacing is inserted around Slack markers next to East Asian wide
    # characters and fullwidth punctuation, and not inserted for halfwidth.
    for content, expected in [
        ("這是**粗體**文字。", "這是 *粗體* 文字。"),
        ("中文_斜體_中文", "中文 _斜體_ 中文"),
        ("中文~~刪除~~中文，標點", "中文 ~刪除~ 中文，標點"),
        ("括號：「**強調**」", "括號：「 *強調* 」"),
        ("ひらがな**強調**ひらがな", "ひらがな *強調* ひらがな"),
        ("한글**강조**한글", "한글 *강조* 한글"),
        ("ㄅㄆㄇ**強調**ㄈㄉㄊ", "ㄅㄆㄇ *強調* ㄈㄉㄊ"),
        # Halfwidth Katakana neighbors should not add spaces
        ("ｶﾀｶﾅ**強調**ｶﾀｶﾅ", "ｶﾀｶﾅ*強調*ｶﾀｶﾅ"),
        # Code spans should not be changed
        ("Inline code `**粗體**` test", "Inline code `**粗體**` test"),
    ]:
        result = markdown_to_slack(content)
        assert result == expected


def test_markdown_to_slack_code_eaw_spacing():
    for content, expected in [
        ("中文`程式`中文", "中文 `程式` 中文"),
        ("中文```程式```中文", "中文 ```程式``` 中文"),
        ("括號：「`程式`」", "括號：「 `程式` 」"),
    ]:
        result = markdown_to_slack(content)
        assert result == expected
