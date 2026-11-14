"""Build phone-friendly Markdown from src/*.md.

Inline math  $`...`$  -> HTML (italic letters, <sub>, <sup>, ×, …).
Display math ```math``` -> SVG image rendered with matplotlib mathtext.
Footnotes    [^id]      -> numbered <sup>[n]</sup> + ## Notes section at chapter end.
Run:  python -I -X utf8 src/build.py   (from the book folder)
"""
import hashlib, pathlib, re, sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

matplotlib.rcParams["mathtext.fontset"] = "cm"
matplotlib.rcParams["svg.fonttype"] = "path"

BOOK = pathlib.Path(__file__).resolve().parent.parent
EQ = BOOK / "equations"
EQ.mkdir(exist_ok=True)
PNG = BOOK / ".eqpng"   # previews for checking, not published
RENDERED = []

MATRIX_ENVS = ("pmatrix", "bmatrix", "Bmatrix", "vmatrix", "Vmatrix", "matrix", "cases")
ENV_BEGIN_RE = re.compile(r"\\begin\{(" + "|".join(MATRIX_ENVS) + r")\}")
ENV_END_RE = re.compile(r"\\end\{(" + "|".join(MATRIX_ENVS) + r")\}")

# ---------- inline -> HTML ----------
SIMPLE = {
    r"\times": "×", r"\div": "÷", r"\cdots": "…", r"\dots": "…", r"\ldots": "…",
    r"\qquad": "&emsp;&emsp;", r"\quad": "&emsp;", r"\;": " ", r"\,": " ", r"\:": " ",
    r"\left": "", r"\right": "", r"\vdots": "⋮", r"\ddots": "⋱", r"\!": "", r"\ ": " ",
    r"\alpha": "α", r"\beta": "β", r"\gamma": "γ", r"\delta": "δ", r"\epsilon": "ε",
    r"\varepsilon": "ε", r"\zeta": "ζ", r"\eta": "η", r"\theta": "θ", r"\vartheta": "ϑ",
    r"\kappa": "κ", r"\lambda": "λ", r"\mu": "μ", r"\nu": "ν", r"\xi": "ξ", r"\pi": "π",
    r"\varpi": "ϖ", r"\rho": "ρ", r"\varrho": "ϱ", r"\sigma": "σ", r"\varsigma": "ς",
    r"\tau": "τ", r"\upsilon": "υ", r"\phi": "φ", r"\varphi": "φ", r"\chi": "χ",
    r"\psi": "ψ", r"\omega": "ω", r"\Gamma": "Γ", r"\Delta": "Δ", r"\Theta": "Θ",
    r"\Lambda": "Λ", r"\Xi": "Ξ", r"\Pi": "Π", r"\Sigma": "Σ", r"\Upsilon": "Υ",
    r"\Phi": "Φ", r"\Psi": "Ψ", r"\Omega": "Ω",
    r"\cdot": "·", r"\pm": "±", r"\mp": "∓", r"\leq": "≤", r"\le": "≤", r"\leqq": "≤",
    r"\geq": "≥", r"\ge": "≥", r"\geqq": "≥", r"\neq": "≠", r"\ne": "≠", r"\approx": "≈",
    r"\infty": "∞", r"\int": "∫", r"\iint": "∬", r"\iiint": "∭", r"\oint": "∮",
    r"\sum": "Σ", r"\prod": "Π", r"\partial": "∂", r"\nabla": "∇",
    r"\perp": "⊥", r"\parallel": "∥", r"\angle": "∠", r"\measuredangle": "∡",
    r"\circ": "°", r"\degree": "°", r"\to": "→", r"\rightarrow": "→", r"\leftarrow": "←",
    r"\leftrightarrow": "↔", r"\Rightarrow": "⇒", r"\Leftarrow": "⇐", r"\Leftrightarrow": "⇔",
    r"\iff": "⇔", r"\implies": "⇒", r"\mapsto": "↦", r"\uparrow": "↑", r"\downarrow": "↓",
    r"\equiv": "≡", r"\triangle": "△", r"\square": "□", r"\sim": "∼", r"\simeq": "≃", r"\cong": "≅",
    r"\propto": "∝", r"\prime": "′", r"\varnothing": "⌀", r"\emptyset": "∅",
    r"\in": "∈", r"\notin": "∉", r"\ni": "∋", r"\subset": "⊂", r"\supset": "⊃",
    r"\subseteq": "⊆", r"\supseteq": "⊇", r"\cup": "∪", r"\cap": "∩", r"\setminus": "∖",
    r"\forall": "∀", r"\exists": "∃", r"\nexists": "∄", r"\neg": "¬", r"\lnot": "¬",
    r"\land": "∧", r"\wedge": "∧", r"\lor": "∨", r"\vee": "∨",
    r"\mid": "|", r"\|": "‖", r"\Vert": "‖", r"\vert": "|", r"\backslash": "∖",
    r"\langle": "⟨", r"\rangle": "⟩", r"\lfloor": "⌊", r"\rfloor": "⌋", r"\lceil": "⌈", r"\rceil": "⌉",
    r"\aleph": "ℵ", r"\ell": "ℓ", r"\hbar": "ℏ", r"\wp": "℘",
    r"\mathfrak": "", r"\displaystyle": "", r"\textstyle": "", r"\tfrac": "", r"\dfrac": "",
    r"\sin": "\x00sin\x01", r"\cos": "\x00cos\x01", r"\tan": "\x00tan\x01", r"\cot": "\x00cot\x01",
    r"\sec": "\x00sec\x01", r"\csc": "\x00csc\x01",
    r"\tg": "\x00tg\x01", r"\cotg": "\x00cotg\x01", r"\ctg": "\x00ctg\x01",
    r"\sinh": "\x00sinh\x01", r"\cosh": "\x00cosh\x01", r"\tanh": "\x00tanh\x01", r"\coth": "\x00coth\x01",
    r"\arsinh": "\x00arsinh\x01", r"\arcosh": "\x00arcosh\x01", r"\artanh": "\x00artanh\x01", r"\arcoth": "\x00arcoth\x01",
    r"\arcsin": "\x00arcsin\x01", r"\arccos": "\x00arccos\x01", r"\arctan": "\x00arctan\x01", r"\arccot": "\x00arccot\x01",
    r"\arcctg": "\x00arcctg\x01", r"\arctg": "\x00arctg\x01",
    r"\log": "\x00log\x01", r"\ln": "\x00ln\x01", r"\lg": "\x00lg\x01", r"\exp": "\x00exp\x01",
    r"\lim": "\x00lim\x01", r"\max": "\x00max\x01", r"\min": "\x00min\x01",
    r"\sup": "\x00sup\x01", r"\inf": "\x00inf\x01", r"\det": "\x00det\x01",
    r"\dim": "\x00dim\x01", r"\ker": "\x00ker\x01", r"\arg": "\x00arg\x01",
    r"\deg": "\x00deg\x01", r"\gcd": "\x00gcd\x01", r"\cis": "\x00cis\x01", r"\sgn": "\x00sgn\x01",
    r"\ggT": "\x00ggT\x01", r"\kgV": "\x00kgV\x01",
    r"\Re": "\x00Re\x01", r"\Im": "\x00Im\x01", r"\Var": "\x00Var\x01", r"\Cov": "\x00Cov\x01",
    r"\{": "{", r"\}": "}", r"\%": "%", r"\&": "&", r"\_": "_",
    r"\gtrless": "≷", r"\lessgtr": "≶", r"\ll": "≪", r"\gg": "≫",
    r"\big": "", r"\Big": "", r"\bigg": "", r"\Bigg": "",
    r"\bigl": "", r"\bigr": "", r"\Bigl": "", r"\Bigr": "", r"\biggl": "", r"\biggr": "", r"\Biggl": "", r"\Biggr": "",
}
BB_MAP = {"N": "ℕ", "Z": "ℤ", "Q": "ℚ", "I": "𝕀", "R": "ℝ", "C": "ℂ", "P": "ℙ", "E": "𝔼", "L": "𝕃", "D": "𝔻", "W": "𝕎", "G": "𝔾", "B": "𝔹", "A": "𝔸"}
UNKNOWN = set()


def group(s, i):
    """Return (content, next_index) for a {..} group or single char at s[i]."""
    while i < len(s) and s[i] == " ":
        i += 1
    if i >= len(s):
        return "", i
    if s[i] == "{":
        depth, j = 1, i + 1
        while j < len(s) and depth:
            depth += {"{": 1, "}": -1}.get(s[j], 0)
            j += 1
        return s[i + 1:j - 1], j
    if s[i] == "\\":
        m = re.match(r"\\[A-Za-z]+|\\.", s[i:])
        return m.group(0), i + len(m.group(0))
    return s[i], i + 1


def inline(s):
    out, i = [], 0
    while i < len(s):
        c = s[i]
        if (s.startswith(r"\tfrac", i) or s.startswith(r"\dfrac", i) or s.startswith(r"\frac", i)) and not s[i + (6 if s[i+1] in "td" else 5):i + (7 if s[i+1] in "td" else 6)].isalpha():
            i += 6 if s[i + 1] in "td" else 5
            a, i = group(s, i)
            b, i = group(s, i)
            out.append(f"{wrap(inline(a))}/{wrap(inline(b))}")
        elif s.startswith(r"\binom", i) and not s[i + 6:i + 7].isalpha():
            i += 6
            a, i = group(s, i)
            b, i = group(s, i)
            out.append(f"\x00(\x01{inline(a)}; {inline(b)}\x00)\x01")
        elif (s.startswith(r"\text", i) or s.startswith(r"\mathrm", i) or s.startswith(r"\operatorname", i)) and "{" in s[i:]:
            cmd_m = re.match(r"\\[A-Za-z]+", s[i:])
            if cmd_m and cmd_m.group(0) in (r"\text", r"\textrm", r"\textbf", r"\textit", r"\mathrm", r"\operatorname"):
                b_idx = s.index("{", i + len(cmd_m.group(0)) - 1)
                a, i = group(s, b_idx)
                a = a.replace("---", "—").replace("--", "–")
                if cmd_m.group(0) == r"\textbf":
                    out.append(f"<b>\x00{a}\x01</b>")
                elif cmd_m.group(0) == r"\textit":
                    out.append(f"<i>\x00{a}\x01</i>")
                else:
                    out.append(f"\x00{a}\x01")
            else:
                out.append(c); i += 1
        elif s.startswith(r"\mathbf", i) and not s[i + 7:i + 8].isalpha():
            a, i = group(s, i + 7)
            out.append(f"<b>{inline(a)}</b>")
        elif s.startswith(r"\mathbb", i) and not s[i + 7:i + 8].isalpha():
            a, i = group(s, i + 7)
            out.append(f"\x00{BB_MAP.get(a.strip(), a.strip())}\x01")
        elif s.startswith(r"\mathcal", i) and not s[i + 8:i + 9].isalpha():
            a, i = group(s, i + 8)
            out.append(f"<i>{a.strip()}</i>")
        elif s.startswith(r"\mathfrak", i) and not s[i + 9:i + 10].isalpha():
            a, i = group(s, i + 9)
            m_map = {"M": "𝔐", "N": "𝔑", "Q": "𝔔", "R": "ℜ", "I": "ℑ"}
            out.append(f"\x00{m_map.get(a.strip(), a.strip())}\x01")
        elif (s.startswith(r"\vec", i) and not s[i + 4:i + 5].isalpha()) or (s.startswith(r"\overrightarrow", i) and not s[i + 15:i + 16].isalpha()):
            step = 15 if s.startswith(r"\overrightarrow", i) else 4
            a, i = group(s, i + step)
            inner = inline(a)
            out.append(inner + "\u20d7")
        elif (s.startswith(r"\dot", i) and not s[i + 4:i + 5].isalpha()) or (s.startswith(r"\ddot", i) and not s[i + 5:i + 6].isalpha()):
            is_dd = s.startswith(r"\ddot", i)
            a, i = group(s, i + (5 if is_dd else 4))
            out.append(inline(a) + ("\u0308" if is_dd else "\u0307"))
        elif (s.startswith(r"\hat", i) and not s[i + 4:i + 5].isalpha()) or (s.startswith(r"\widehat", i) and not s[i + 8:i + 9].isalpha()):
            step = 8 if s.startswith(r"\widehat", i) else 4
            a, i = group(s, i + step)
            out.append(inline(a) + "\u0302")
        elif (s.startswith(r"\tilde", i) and not s[i + 6:i + 7].isalpha()) or (s.startswith(r"\widetilde", i) and not s[i + 10:i + 11].isalpha()):
            step = 10 if s.startswith(r"\widetilde", i) else 6
            a, i = group(s, i + step)
            out.append(inline(a) + "\u0303")
        elif s.startswith(r"\underline", i) and not s[i + 10:i + 11].isalpha():
            a, i = group(s, i + 10)
            out.append(f"<u>{inline(a)}</u>")
        elif s.startswith(r"\boxed", i) and not s[i + 6:i + 7].isalpha():
            a, i = group(s, i + 6)
            out.append(f"<b>{inline(a)}</b>")
        elif s.startswith(r"\not\in", i):
            out.append("∉"); i += 7
        elif s.startswith(r"\not=", i) or s.startswith(r"\not\equiv", i):
            if s.startswith(r"\not=", i):
                out.append("≠"); i += 5
            else:
                out.append("≢"); i += 10
        elif c in "^_":
            a, i = group(s, i + 1)
            inner = inline(a)
            if c == "^" and inner.strip() == "°":
                out.append("°")
            else:
                tag = "sup" if c == "^" else "sub"
                out.append(f"<{tag}>{inner}</{tag}>")
        elif s.startswith(r"\sqrt", i) and not s[i + 5:i + 6].isalpha():
            j = i + 5
            while j < len(s) and s[j] == " ":
                j += 1
            deg = ""
            if j < len(s) and s[j] == "[":
                k = s.index("]", j)
                deg = f"<sup>{inline(s[j + 1:k])}</sup>"
                j = k + 1
            a, i = group(s, j)
            rad = f"√({inline(a)})" if len(a) > 1 else f"√{inline(a)}"
            out.append(deg + rad)
        elif (s.startswith(r"\overline", i) and not s[i + 9:i + 10].isalpha()) or (s.startswith(r"\bar", i) and not s[i + 4:i + 5].isalpha()):
            i += 9 if s.startswith(r"\overline", i) else 4
            a, i = group(s, i)
            plain_a = re.sub(r"<[^>]+>", "", inline(a))
            out.append(inline(a) + "\u0305" if len(plain_a) <= 2 else f"\x00overline(\x01{inline(a)}\x00)\x01")
        elif c == "\\":
            m = re.match(r"\\[A-Za-z]+|\\.", s[i:])
            tok = m.group(0)
            if tok not in SIMPLE:
                UNKNOWN.add(tok)
            out.append(SIMPLE.get(tok, tok))
            i += len(tok)
        elif c in "{}":
            i += 1
        elif c == "'":
            out.append("′")
            i += 1
        else:
            out.append(c)
            i += 1
    return "".join(out)


def wrap(x):
    plain = re.sub(r"<[^>]+>|[\x00\x01]", "", x).strip()
    if len(plain) <= 2 or plain.isalnum() or re.fullmatch(r"\d[\d .]*", plain):
        return x
    return f"({x})"


def italicize(html):
    parts = re.split(r"(<[^>]+>|&\w+;|\x00.*?\x01)", html)
    res = []
    for p in parts:
        if p.startswith("\x00"):
            res.append(p[1:-1].replace("=", " = "))
        elif p.startswith("<") or p.startswith("&"):
            res.append(p)
        else:
            s = re.sub(r"[A-Za-z]+", lambda m: f"<i>{m.group(0)}</i>", p)
            s = s.replace("-", "−").replace("=", " = ")
            res.append(s)
    out = "".join(res)
    out = re.sub(
        r"\b(arsinh|arcosh|artanh|arcoth|arcsin|arccos|arctan|arccot|arcctg|arctg|sinh|cosh|tanh|coth|cotg|ctg|sin|cos|tan|cot|sec|csc|tg|log|ln|lg|exp|lim|max|min|sup|inf|det|dim|ker|arg|deg|gcd|cis|sgn)(?=(?:<i>|[A-Za-zα-ωΑ-Ω0-9]))",
        r"\1 ",
        out,
    )
    out = re.sub(r" {2,}", " ", out).strip()
    return out


def inline_html(tex):
    return italicize(inline(tex.strip()))


# ---------- display -> SVG ----------
CUSTOM_OPS = (
    "arsinh", "arcosh", "artanh", "arcoth", "arccot", "arcctg", "arctg", "cotg", "ctg", "tg",
    "cis", "lg", "Var", "Cov", "grad", "div", "rot", "sgn", "ggT", "kgV",
)


def split_top_level_lines(tex):
    """Split display math on \\\\ (with optional [...]) ONLY outside matrix/cases environments."""
    lines, cur, i, env_depth = [], [], 0, 0
    while i < len(tex):
        mb = ENV_BEGIN_RE.match(tex, i)
        if mb:
            env_depth += 1
            cur.append(mb.group(0))
            i = mb.end()
            continue
        me = ENV_END_RE.match(tex, i)
        if me:
            env_depth = max(0, env_depth - 1)
            cur.append(me.group(0))
            i = me.end()
            continue
        if env_depth == 0 and tex.startswith(r"\\", i):
            m = re.match(r"\\\\(?:\s*\[[^\]]*\])?", tex[i:])
            s = "".join(cur).strip()
            if s:
                lines.append(s)
            cur = []
            i += len(m.group(0))
            continue
        cur.append(tex[i])
        i += 1
    s = "".join(cur).strip()
    if s:
        lines.append(s)
    return lines


def strip_top_level_amps(s):
    """Remove alignment '&' outside matrix/cases environments while keeping '&' inside them."""
    out, i, env_depth = [], 0, 0
    while i < len(s):
        mb = ENV_BEGIN_RE.match(s, i)
        if mb:
            env_depth += 1
            out.append(mb.group(0))
            i = mb.end()
            continue
        me = ENV_END_RE.match(s, i)
        if me:
            env_depth = max(0, env_depth - 1)
            out.append(me.group(0))
            i = me.end()
            continue
        if s[i] == "&" and env_depth == 0 and (i == 0 or s[i - 1] != "\\"):
            i += 1
            continue
        out.append(s[i])
        i += 1
    return "".join(out)


def smart_dfrac(s, allow_in_lr=True):
    """Promote \\frac to \\dfrac only at brace depth 0 and outside matrix/cases environments
    so compound expressions never overflow cmex10 delimiter heights."""
    s = s.replace(r"\tfrac", r"\frac")
    out, i, depth, lr_depth, env_depth = [], 0, 0, 0, 0
    while i < len(s):
        mb = ENV_BEGIN_RE.match(s, i)
        if mb:
            env_depth += 1
            out.append(mb.group(0))
            i = mb.end()
            continue
        me = ENV_END_RE.match(s, i)
        if me:
            env_depth = max(0, env_depth - 1)
            out.append(me.group(0))
            i = me.end()
            continue
        if s[i] == "{" and (i == 0 or s[i - 1] != "\\"):
            depth += 1
            out.append("{")
            i += 1
        elif s[i] == "}" and (i == 0 or s[i - 1] != "\\"):
            depth = max(0, depth - 1)
            out.append("}")
            i += 1
        elif s.startswith(r"\left", i) and not s[i + 5:i + 6].isalpha():
            lr_depth += 1
            out.append(r"\left")
            i += 5
        elif s.startswith(r"\right", i) and not s[i + 6:i + 7].isalpha():
            lr_depth = max(0, lr_depth - 1)
            out.append(r"\right")
            i += 6
        elif s.startswith(r"\frac", i) and not s[i + 5:i + 6].isalpha():
            promote = (depth == 0) and (env_depth == 0) and (allow_in_lr or lr_depth == 0)
            out.append(r"\dfrac" if promote else r"\frac")
            i += 5
        else:
            out.append(s[i])
            i += 1
    return "".join(out)


def add_denom_sqrt_clearance(s):
    """Insert \\overset{\\,}{...} around \\sqrt{...} when it begins a \\dfrac denominator,
    and inside \\overline{...} when it contains superscripts so bars never collide."""
    out, i = [], 0
    while i < len(s):
        if s.startswith(r"\dfrac", i) and not s[i + 6:i + 7].isalpha():
            out.append(r"\dfrac")
            num, j = group(s, i + 6)
            den, k = group(s, j)
            den_s = den.strip()
            if den_s.startswith(r"\sqrt"):
                den = r"\overset{\,}{" + den + "}"
            out.append("{" + num + "}{" + den + "}")
            i = k
        elif s.startswith(r"\overline", i) and not s[i + 9:i + 10].isalpha():
            body, j = group(s, i + 9)
            if "^" in body:
                body = r"\overset{\,}{" + body + "}"
            out.append(r"\overline{" + body + "}")
            i = j
        else:
            out.append(s[i])
            i += 1
    return "".join(out)


def unwrap_cmd(s, cmd):
    """Unwrap \\cmd{body} -> body while respecting nested braces."""
    out, i, n = [], 0, len(cmd)
    while i < len(s):
        if s.startswith(cmd, i) and not s[i + n:i + n + 1].isalpha():
            body, i = group(s, i + n)
            out.append(unwrap_cmd(body, cmd))
        else:
            out.append(s[i])
            i += 1
    return "".join(out)


ENV_DELIMS = {
    "pmatrix": (r"\left(\,", r"\,\right)"),
    "bmatrix": (r"\left[\,", r"\,\right]"),
    "Bmatrix": (r"\left\{\,", r"\,\right\}"),
    "vmatrix": (r"\left|\,", r"\,\right|"),
    "Vmatrix": (r"\left\|\,", r"\,\right\|"),
    "matrix": ("", ""),
    "cases": (r"\left\{\,", r"\right."),
}
INNER_ENV_RE = re.compile(
    r"\\begin\{(" + "|".join(MATRIX_ENVS) + r")\}((?:(?!\\begin\{(?:" + "|".join(MATRIX_ENVS) + r")\}).)*?)\\end\{\1\}",
    re.S,
)


def convert_matrix_envs(s):
    """Convert \\begin{pmatrix|bmatrix|vmatrix|cases|...} into per-column \\substack blocks for matplotlib mathtext."""
    def _repl(m):
        env, body = m.group(1), m.group(2).strip()
        raw_rows = [r.strip() for r in re.split(r"\\\\(?:\s*\[[^\]]*\])?", body) if r.strip()]
        if not raw_rows:
            return ""
        grid = [[c.strip() for c in re.split(r"(?<!\\)&", r)] for r in raw_rows]
        ncols = max(len(r) for r in grid)
        for r in grid:
            while len(r) < ncols:
                r.append(r"\ ")
        cols = []
        for j in range(ncols):
            col_cells = [(grid[i][j] if grid[i][j] else r"\ ") for i in range(len(grid))]
            cols.append(r"\substack{" + r" \\ ".join(col_cells) + "}")
        sep = r" \quad " if env == "cases" else r" \ \ \ "
        ld, rd = ENV_DELIMS[env]
        return f"{ld}{sep.join(cols)}{rd}"

    prev = None
    while prev != s:
        prev = s
        s = INNER_ENV_RE.sub(_repl, s)
    return s


def to_mathtext(line, allow_in_lr=True):
    line = unwrap_cmd(line, r"\boxed")
    line = re.sub(r"\\(?:displaystyle|textstyle)(?![A-Za-z])", "", line)
    for op in CUSTOM_OPS:
        line = re.sub(rf"\\{op}(?![A-Za-z])", rf"\\mathrm{{{op}}}\,", line)
    line = re.sub(r"\\operatorname\{([^}]*)\}", r"\\mathrm{\1}\,", line)
    line = line.replace(r"\implies", r"\Rightarrow").replace(r"\iff", r"\Leftrightarrow")
    line = line.replace(r"\le ", r"\leq ").replace(r"\ge ", r"\geq ").replace(r"\ne ", r"\neq ")
    line = line.replace(r"\leqq", r"\leq").replace(r"\geqq", r"\geq")
    line = re.sub(r"\\le(?![A-Za-z])", r"\\leq", line)
    line = re.sub(r"\\ge(?![A-Za-z])", r"\\geq", line)
    line = re.sub(r"\\ne(?![A-Za-z])", r"\\neq", line)
    line = re.sub(r"\\land(?![A-Za-z])", r"\\wedge", line)
    line = re.sub(r"\\lor(?![A-Za-z])", r"\\vee", line)
    line = re.sub(r"\\lnot(?![A-Za-z])", r"\\neg", line)
    line = re.sub(r"\\degree(?![A-Za-z])", r"^\\circ", line)
    line = re.sub(r"\\varnothing(?![A-Za-z])", r"\\emptyset", line)
    line = smart_dfrac(line, allow_in_lr=allow_in_lr).replace(r"\;", r"\ ").replace(r"\:", r"\ ")
    line = add_denom_sqrt_clearance(line)
    line = re.sub(r"\\text\{([^}]*)\}", lambda m: r"\mathrm{" + m.group(1).replace(" ", r"\ ") + "}", line)
    line = re.sub(r"\\textbf\{([^}]*)\}", lambda m: r"\mathbf{" + m.group(1).replace(" ", r"\ ") + "}", line)
    line = strip_top_level_amps(line)
    line = convert_matrix_envs(line)
    # x'_1 -> x_{1}^{\prime} so the prime and subscript stack as in the print
    line = re.sub(r"([A-Za-z])('+)_(\{[^{}]*\}|[A-Za-z0-9])",
                  lambda m: m.group(1) + "_" + (m.group(3) if m.group(3).startswith("{") else "{" + m.group(3) + "}")
                  + "^{" + r"\prime" * len(m.group(2)) + "}", line)
    return line


def _line_weight(line):
    """Height weight in row units, accounting for multi-row substacks inside a line."""
    subs = re.findall(r"\\substack\{((?:[^{}]|\{[^{}]*\})*)\}", line)
    extra = max((len(re.findall(r"\\\\", s)) for s in subs), default=0)
    return 1.0 + 0.55 * extra


def _render_lines(lines):
    key = hashlib.sha1("\n".join(lines).encode()).hexdigest()[:12]
    path = EQ / f"eq-{key}.svg"
    if not path.exists() or not (PNG / f"eq-{key}.png").exists():
        weights = [_line_weight(l) for l in lines]
        total_w = sum(weights)
        fig = plt.figure(figsize=(6, 0.62 * total_w + 0.25))
        fig.patch.set_facecolor("white")
        acc = 0.0
        for l, w in zip(lines, weights):
            y = 1.0 - (acc + 0.5 * w) / total_w
            fig.text(0.5, y, f"${l}$", ha="center", va="center", fontsize=15)
            acc += w
        fig.savefig(path, bbox_inches="tight", pad_inches=0.12, facecolor="white")
        PNG.mkdir(parents=True, exist_ok=True)
        fig.savefig(PNG / f"eq-{key}.png", bbox_inches="tight", pad_inches=0.12, facecolor="white", dpi=110)
        plt.close(fig)
    return key, path, path.read_text(encoding="utf-8")


def render(tex):
    raw_tex = tex
    tag = None
    m = re.search(r"\\tag\{([^}]*)\}", tex)
    if m:
        tag, tex = m.group(1), tex.replace(m.group(0), "")
    tex = re.sub(r"\\(begin|end)\{aligned\}", "", tex)
    tex = " ".join(tex.split("\n"))
    raw_lines = split_top_level_lines(tex)

    lines = [to_mathtext(l, allow_in_lr=True) for l in raw_lines]
    if tag and lines:
        lines[len(lines) // 2] += r"\qquad(" + tag + ")"
    key, path, svg_text = _render_lines(lines)

    if "!" not in raw_tex and "Cmr10-21" in svg_text:
        path.unlink(missing_ok=True)
        (PNG / f"eq-{key}.png").unlink(missing_ok=True)
        lines = [to_mathtext(l, allow_in_lr=False) for l in raw_lines]
        if tag and lines:
            lines[len(lines) // 2] += r"\qquad(" + tag + ")"
        key, path, svg_text = _render_lines(lines)

    if "!" not in raw_tex and "Cmr10-21" in svg_text:
        raise RuntimeError(f"Matplotlib emitted dummy '!' (Cmr10-21) in {path.name} for:\n{raw_tex}")
    RENDERED.append(PNG / f"eq-{key}.png")
    return f'<p align="center"><img src="equations/{path.name}" alt="equation"></p>'


def compile_footnotes(text, src_name):
    """Convert Markdown [^id] footnotes into numbered <sup>[n]</sup> markers and a clean ## Notes section."""
    defs = {}
    body_lines = []
    for line in text.splitlines():
        m = re.match(r"^\[\^([^\]]+)\]:\s*(.+)$", line)
        if m:
            fid, fbody = m.group(1), m.group(2).strip()
            if fid in defs:
                raise ValueError(f"{src_name}: duplicate footnote definition [^{fid}]")
            defs[fid] = fbody
        else:
            body_lines.append(line)

    body = "\n".join(body_lines).rstrip() + "\n"
    num_of = {}
    ordered_ids = []

    def repl_seq(m):
        ids = re.findall(r"\[\^([^\]]+)\]", m.group(0))
        nums = []
        for fid in ids:
            if fid not in defs:
                raise ValueError(f"{src_name}: undefined footnote reference [^{fid}]")
            if fid not in num_of:
                num_of[fid] = len(ordered_ids) + 1
                ordered_ids.append(fid)
            nums.append(str(num_of[fid]))
        return f"<sup>[{', '.join(nums)}]</sup>"

    body = re.sub(r"(?:\[\^[^\]]+\])+", repl_seq, body)

    unused = set(defs) - set(num_of)
    if unused:
        raise ValueError(f"{src_name}: unreferenced footnote definitions: {sorted(unused)}")

    if ordered_ids:
        notes_md = ["", "---", "", "## Notes", ""]
        for fid in ordered_ids:
            notes_md.append(f"{num_of[fid]}. {defs[fid]}")
        body = body.rstrip() + "\n" + "\n".join(notes_md) + "\n"
    return body


def build(src):
    text = src.read_text(encoding="utf-8")
    text = compile_footnotes(text, src.name)
    text = re.sub(r"> ```math\n(.*?)\n> ```",
                  lambda m: "> " + render("\n".join(l[2:] for l in m.group(1).splitlines())), text, flags=re.S)
    text = re.sub(r"```math\n(.*?)\n```", lambda m: render(m.group(1)), text, flags=re.S)
    text = re.sub(r"\$`(.*?)`\$", lambda m: inline_html(m.group(1)), text)
    (BOOK / src.name).write_text(text, encoding="utf-8")
    left = re.findall(r"\$`|```math|\[\^", text)
    print(src.name, "unconverted:", len(left), "| unknown inline commands:", sorted(UNKNOWN) or "none")
    # contact sheet of every display equation in this file, for checking against the scan
    from PIL import Image
    ims = [Image.open(p) for p in RENDERED if p.exists()]
    for k in range(0, len(ims), 12):
        grp = ims[k:k + 12]
        W = max(i.width for i in grp); H = sum(i.height + 10 for i in grp)
        sheet = Image.new("RGB", (W, H), "white"); y = 0
        for im in grp:
            sheet.paste(im, ((W - im.width) // 2, y)); y += im.height + 10
        out = PNG / f"sheet-{src.stem}-{k // 12 + 1:02d}.png"
        sheet.save(out); print("equation sheet:", out)
    RENDERED.clear(); UNKNOWN.clear()


if __name__ == "__main__":
    names = sys.argv[1:]
    files = [(pathlib.Path(n) if pathlib.Path(n).is_absolute() else BOOK / "src" / n) for n in names] if names else sorted((BOOK / "src").glob("*.md"))
    for f in files:
        build(f)
