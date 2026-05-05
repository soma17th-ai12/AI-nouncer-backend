from jamo import hangul_to_jamo, j2hcj

INS_DEL_COST = 3

def _is_hangul_syllable(ch: str) -> bool:
    return len(ch) == 1 and 0xAC00 <= ord(ch) <= 0xD7A3

def _hangul_only(text: str) -> str:
    return "".join(c for c in text if _is_hangul_syllable(c))

def decompose(syl: str) -> tuple[str, str, str]:
    parts = list(hangul_to_jamo(syl))
    cho = j2hcj(parts[0])
    jung = j2hcj(parts[1])
    jong = j2hcj(parts[2]) if len(parts) == 3 else ""
    return cho, jung, jong

def jamo_distance(a: str, b: str) -> int:
    if a == b:
        return 0
    ca, ja, ta = decompose(a)
    cb, jb, tb = decompose(b)
    return int(ca != cb) + int(ja != jb) + int(ta != tb)

def align(expected: str, heard: str) -> list[dict]:
    e = _hangul_only(expected)
    h = _hangul_only(heard)
    n, m = len(e), len(h)

    dp = [[0] * (m + 1) for _ in range(n + 1)]
    for i in range(1, n + 1):
        dp[i][0] = i * INS_DEL_COST
    for j in range(1, m + 1):
        dp[0][j] = j * INS_DEL_COST
    for i in range(1, n + 1):
        for j in range(1, m + 1):
            sub = dp[i - 1][j - 1] + jamo_distance(e[i - 1], h[j - 1])
            ins = dp[i][j - 1] + INS_DEL_COST
            dlt = dp[i - 1][j] + INS_DEL_COST
            dp[i][j] = min(sub, ins, dlt)

    result: list[dict] = []
    i, j = n, m
    while i > 0 or j > 0:
        if (
            i > 0
            and j > 0
            and dp[i][j] == dp[i - 1][j - 1] + jamo_distance(e[i - 1], h[j - 1])
        ):
            ch_e, ch_h = e[i - 1], h[j - 1]
            result.append(
                {
                    "expected": ch_e,
                    "heard": ch_h,
                    "type": "match" if ch_e == ch_h else "sub",
                }
            )
            i -= 1
            j -= 1
        elif j > 0 and dp[i][j] == dp[i][j - 1] + INS_DEL_COST:
            result.append({"expected": "", "heard": h[j - 1], "type": "ins"})
            j -= 1
        else:
            result.append({"expected": e[i - 1], "heard": "", "type": "del"})
            i -= 1
    result.reverse()
    return result
