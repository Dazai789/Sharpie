#!/usr/bin/python3
import sys
import re

file = sys.argv[1]
declare = False
need_sys = False
need_os = False
need_subprocess = False
need_glob = False
need_fnmatch = False
need_arg = False
body = []
indent = 0
backticks = []
backticks_name = ""
case_expr = ""
first_case = False
glob_vars = set()

python_keywords = [
    "False", "None", "True", "and", "as", "assert", "async", "await",
    "break", "class", "continue", "def", "del", "elif", "else", "except",
    "finally", "for", "from", "global", "if", "import", "in", "is",
    "lambda", "nonlocal", "not", "or", "pass", "raise", "return", "try",
    "while", "with", "yield", "match", "case"
]

# fix Python keyword name
def fix_name(name):
    if name in python_keywords or name == "print":
        return name + "_"
    return name

# split with statement + # + comment(optional)
def split_comment(text):
    if " #" in text:
        statement, comment = text.split(" #", 1)
        return statement.rstrip(), comment.strip()

    return text, ""

# split line like shell
def split_shell(line):
    tokens = []
    token = ""
    quote = ""

    for char in line:
        if quote:
            if char == quote:
                token += char
                quote = ""
            else:
                token += char
        else:
            if char in "'\"":
                token += char
                quote = char
            elif char.isspace():
                if token:
                    tokens.append(token)
                    token = ""
            else:
                token += char

    if token:
        tokens.append(token)

    return tokens

# find ) for $(...)
def sub_end(text, start):
    depth = 1
    i = start

    while i < len(text):
        if text[i] in "'\"":
            quote = text[i]
            i += 1
            while i < len(text) and text[i] != quote:
                i += 1
        elif text[i] == "$" and i + 1 < len(text) and text[i + 1] == "(":
            if i + 2 < len(text) and text[i + 2] == "(":
                i += 1
            else:
                depth += 1
                i += 1
        elif text[i] == ")":
            depth -= 1
            if depth == 0:
                return i
        i += 1

    return -1

# convert $var to {var} or $1,2,3...
def fix_var(var):
    global need_sys
    global need_arg
    has_var = False
    result = ""
    i = 0

    # scan char by char
    while i < len(var):
        if var[i] != "$":
            result += var[i]
            i += 1
            continue

        has_var = True
        i += 1
        name = ""

        # ${var}
        if i < len(var) and var[i] == "{":
            i += 1
            while i < len(var) and var[i] != "}":
                name += var[i]
                i += 1
            if i < len(var) and var[i] == "}":
                i += 1
        # $# / $@
        elif i < len(var) and (var[i] == "#" or var[i] == "@"):
            name = var[i]
            i += 1
        # $var / $1
        else:
            # read name after $
            while i < len(var) and (var[i].isalnum() or var[i] == "_"):
                name += var[i]
                i += 1

        if name == "":
            result += "$"
        # $0 / $1 / $2 ...
        elif name.isdigit():
            need_sys = True
            if name == "0":
                result += "{sys.argv[0]}"
            else:
                need_arg = True
                result += f'{{arg({name})}}'
        # $#
        elif name == "#":
            need_sys = True
            result += "{len(sys.argv[1:])}"
        # $@
        elif name == "@":
            need_sys = True
            result += "{' '.join(sys.argv[1:])}"
        else:
            name = fix_name(name)
            result += f'{{{name}}}'

    return result, has_var

# convert to Python string / f-string
def fix_word(word):
    global need_sys
    global need_arg

    if word == "$#":
        need_sys = True
        return "str(len(sys.argv[1:]))"

    if word == "$@":
        need_sys = True
        return '" ".join(sys.argv[1:])'

    if re.fullmatch(r'\$\{[A-Za-z_][A-Za-z0-9_]*\}', word):
        return fix_name(word[2:-1])

    if re.fullmatch(r'\$\{[0-9]+\}', word):
        need_sys = True
        number = word[2:-1]
        if number == "0":
            return "sys.argv[0]"
        need_arg = True
        return f'arg({number})'

    if len(word) >= 2 and word[0] == "'" and word[-1] == "'":
        return repr(word[1:-1])

    if len(word) >= 2 and word[0] == '"' and word[-1] == '"':
        return fix_double(word[1:-1])

    if re.fullmatch(r'\$[A-Za-z_][A-Za-z0-9_]*', word):
        return fix_name(word[1:])

    if re.fullmatch(r'\$[0-9]+', word):
        need_sys = True
        number = word[1:]
        if number == "0":
            return "sys.argv[0]"
        need_arg = True
        return f'arg({number})'

    if len(word) >= 5 and word.startswith("$((") and word.endswith("))"):
        return f"str({fix_arith(word[3:-2].strip())})"

    if len(word) >= 4 and word.startswith("$(") and word.endswith(")") and sub_end(word, 2) == len(word) - 1:
        return fix_sub(word[2:-1].strip())

    if re.search(r'\$(?:[a-zA-Z0-9_]+|[#@])', word):
        word, has_var = fix_var(word)
        return f'f"{word}"'

    return repr(word)

# convert $((...)) to Python expr
def fix_arith(expr):
    global need_sys
    global need_arg
    parts = []

    for part in expr.split():
        if part.isdigit():
            parts.append(part)
        elif re.fullmatch(r'\$[0-9]+', part):
            need_sys = True
            if part[1:] == "0":
                parts.append("int(sys.argv[0])")
            else:
                need_arg = True
                parts.append(f"int(arg({part[1:]}))")
        elif re.fullmatch(r'\$[A-Za-z_][A-Za-z0-9_]*', part):
            parts.append(f"int({fix_name(part[1:])})")
        elif re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]*', part):
            parts.append(f"int({fix_name(part)})")
        else:
            parts.append(part)

    return " ".join(parts)

# convert command args to Python list
def fix_args(words):
    global need_sys
    parts = []
    cur = []

    def push():
        nonlocal cur
        if cur:
            parts.append(f'[{", ".join(cur)}]')
            cur = []

    for word in words:
        if word in ("$@", '"$@"', "'$@'"):
            need_sys = True
            push()
            parts.append("sys.argv[1:]")
        elif len(word) >= 2 and word[0] in "'\"" and word[-1] == word[0]:
            cur.append(fix_word(word))
        else:
            cur.append(fix_word(word))

    push()

    if not parts:
        return "[]"

    return " + ".join(parts)

# split cmd + < > >>
def fix_redirect(tokens):
    cmd = tokens[:]
    in_file = ""
    out_file = ""
    append = False

    while cmd:
        if len(cmd) >= 2 and cmd[-2] in ("<", ">", ">>"):
            op = cmd[-2]
            path = cmd[-1]
            cmd = cmd[:-2]
        elif cmd[-1].startswith(">>"):
            op = ">>"
            path = cmd[-1][2:]
            cmd = cmd[:-1]
        elif cmd[-1].startswith(">"):
            op = ">"
            path = cmd[-1][1:]
            cmd = cmd[:-1]
        elif cmd[-1].startswith("<"):
            op = "<"
            path = cmd[-1][1:]
            cmd = cmd[:-1]
        else:
            break

        if op == "<":
            in_file = path
        else:
            out_file = path
            append = (op == ">>")

    return cmd, in_file, out_file, append

# convert test / [ ] to Python condition
def fix_test(tokens):
    global need_os

    if len(tokens) >= 2 and tokens[0] == "[" and tokens[-1] == "]":
        tokens = ["test"] + tokens[1:-1]

    if not tokens or tokens[0] != "test":
        return ""

    if len(tokens) == 8 and tokens[4] == "-o":
        left = fix_test(tokens[:4])
        right = fix_test(["test"] + tokens[5:])
        if left and right:
            return f"{left} or {right}"
        return ""

    if len(tokens) == 4 and tokens[2] == "=":
        return f"{fix_word(tokens[1])} == {fix_word(tokens[3])}"

    if len(tokens) == 4 and tokens[2] == "!=":
        return f"{fix_word(tokens[1])} != {fix_word(tokens[3])}"

    if len(tokens) == 4 and tokens[2] == "-eq":
        return f"int({fix_word(tokens[1])}) == int({fix_word(tokens[3])})"

    if len(tokens) == 4 and tokens[2] == "-ne":
        return f"int({fix_word(tokens[1])}) != int({fix_word(tokens[3])})"

    if len(tokens) == 4 and tokens[2] == "-lt":
        return f"int({fix_word(tokens[1])}) < int({fix_word(tokens[3])})"

    if len(tokens) == 4 and tokens[2] == "-le":
        return f"int({fix_word(tokens[1])}) <= int({fix_word(tokens[3])})"

    if len(tokens) == 4 and tokens[2] == "-gt":
        return f"int({fix_word(tokens[1])}) > int({fix_word(tokens[3])})"

    if len(tokens) == 4 and tokens[2] == "-ge":
        return f"int({fix_word(tokens[1])}) >= int({fix_word(tokens[3])})"

    if len(tokens) == 3 and tokens[1] == "-z":
        return f"{fix_word(tokens[2])} == ''"

    if len(tokens) == 3 and tokens[1] == "-n":
        return f"{fix_word(tokens[2])} != ''"

    if len(tokens) == 3 and tokens[1] == "-e":
        need_os = True
        return f"os.path.exists({fix_word(tokens[2])})"

    if len(tokens) == 3 and tokens[1] == "-f":
        need_os = True
        return f"os.path.isfile({fix_word(tokens[2])})"

    if len(tokens) == 3 and tokens[1] == "-s":
        need_os = True
        return f"os.path.exists({fix_word(tokens[2])}) and os.path.getsize({fix_word(tokens[2])}) > 0"

    if len(tokens) == 3 and tokens[1] == "-r":
        need_os = True
        return f"os.access({fix_word(tokens[2])}, os.R_OK)"

    if len(tokens) == 3 and tokens[1] == "-w":
        need_os = True
        return f"os.access({fix_word(tokens[2])}, os.W_OK)"

    if len(tokens) == 3 and tokens[1] == "-x":
        need_os = True
        return f"os.access({fix_word(tokens[2])}, os.X_OK)"

    if len(tokens) == 3 and tokens[1] == "-d":
        need_os = True
        return f"os.path.isdir({fix_word(tokens[2])})"

    return ""

# convert cond to Python condition
def fix_cond(tokens):
    global need_subprocess

    if "&&" in tokens:
        i = tokens.index("&&")
        left = fix_cond(tokens[:i])
        right = fix_cond(tokens[i + 1:])
        if left and right:
            return f"{left} and {right}"
        return ""

    if "||" in tokens:
        i = tokens.index("||")
        left = fix_cond(tokens[:i])
        right = fix_cond(tokens[i + 1:])
        if left and right:
            return f"{left} or {right}"
        return ""

    cond = fix_test(tokens)
    if cond:
        return cond

    if tokens:
        need_subprocess = True
        return f"not subprocess.run({fix_args(tokens)}).returncode"

    return ""

# convert shell cmd to Python line(s)
def fix_cmd(tokens):
    global need_sys
    global need_os
    global need_subprocess

    if not tokens:
        return []

    cmd, in_file, out_file, append = fix_redirect(tokens)
    if cmd:
        tokens = cmd

    if tokens[0] == "echo":
        no_newline = len(tokens) > 1 and tokens[1] == "-n"
        args = tokens[2:] if no_newline else tokens[1:]

        if args:
            out = " + ' ' + ".join(fix_word(arg) for arg in args)
        else:
            out = "''"

        if out_file:
            mode = "a" if append else "w"
            line = f"print({out}, file=f_out"
            if no_newline:
                line += ", end=''"
            line += ")"
            return [
                f"with open({fix_word(out_file)}, {mode!r}) as f_out:",
                f"    {line}",
            ]

        if no_newline:
            return [f"print({out}, end='')"]
        return [f"print({out})"]

    if tokens[0] == "exit":
        need_sys = True
        if len(tokens) > 1:
            return [f"sys.exit({tokens[1]})"]
        return ["sys.exit()"]

    if tokens[0] == "cd" and len(tokens) > 1:
        need_os = True
        return [f"os.chdir({fix_word(tokens[1])})"]

    if tokens[0] == "read" and len(tokens) > 1:
        name = fix_name(tokens[1])
        return [
            "try:",
            f"    {name} = input()",
            "except EOFError:",
            f"    {name} = ''",
        ]

    if fix_test(tokens):
        return ["pass"]

    need_subprocess = True
    args = fix_args(tokens)

    if in_file and out_file:
        mode = "a" if append else "w"
        return [
            f"with open({fix_word(in_file)}) as f_in:",
            f"    with open({fix_word(out_file)}, {mode!r}) as f_out:",
            f"        subprocess.run({args}, stdin=f_in, stdout=f_out)",
        ]

    if in_file:
        return [
            f"with open({fix_word(in_file)}) as f_in:",
            f"    subprocess.run({args}, stdin=f_in)",
        ]

    if out_file:
        mode = "a" if append else "w"
        return [
            f"with open({fix_word(out_file)}, {mode!r}) as f_out:",
            f"    subprocess.run({args}, stdout=f_out)",
        ]

    return [f"subprocess.run({args})"]

# convert $(...) to Python expr
def fix_sub(text):
    words = text.split()

    if words and words[0] == "echo":
        args = words[1:]

        if args and args[0] == "-n":
            args = args[1:]

        if args:
            return " + ' ' + ".join(fix_word(arg) for arg in args)
        return "''"

    global need_subprocess
    need_subprocess = True
    cmd = fix_args(words)
    return f'subprocess.run({cmd}, text=True, stdout=subprocess.PIPE).stdout.rstrip("\\n")'

# convert `...` to Python line
def fix_backticks(text, name=""):
    out = fix_sub(text)

    if name:
        return f"{name} = {out}"

    return f"print({out})"

# convert text inside "..."
def fix_double(text):
    parts = []
    plain = ""
    i = 0

    while i < len(text):
        if text[i] == "`":
            j = text.find("`", i + 1)
            if j == -1:
                plain += text[i]
                i += 1
                continue

            if plain:
                parts.append(repr(plain))
                plain = ""

            parts.append(fix_sub(text[i + 1:j]))
            i = j + 1
        elif text[i] == "$" and i + 1 < len(text) and text[i + 1] == "(":
            if i + 2 < len(text) and text[i + 2] == "(":
                plain += "$(("
                i += 3
                continue

            j = sub_end(text, i + 2)
            if j == -1:
                plain += text[i]
                i += 1
                continue

            if plain:
                parts.append(repr(plain))
                plain = ""

            parts.append(fix_sub(text[i + 2:j].strip()))
            i = j + 1
        elif text[i] == "$":
            j = i + 1
            if j < len(text) and text[j] == "{":
                j += 1
                while j < len(text) and text[j] != "}":
                    j += 1
                if j < len(text):
                    j += 1
            elif j < len(text) and (text[j] == "#" or text[j] == "@"):
                j += 1
            else:
                while j < len(text) and (text[j].isalnum() or text[j] == "_"):
                    j += 1

            if j == i + 1:
                plain += text[i]
                i += 1
                continue

            if plain:
                parts.append(repr(plain))
                plain = ""

            parts.append(fix_word(text[i:j]))
            i = j
        else:
            plain += text[i]
            i += 1

    if plain:
        parts.append(repr(plain))

    if not parts:
        return "''"

    return " + ".join(parts)

with open(file, "r") as f:
    for line in f:
        stripped_line = line.strip()

        # continue backticks
        if backticks:
            if stripped_line.endswith("`"):
                backticks.append(stripped_line[:-1])
                result = fix_backticks(" ".join(backticks), backticks_name)
                body.append("    " * indent + result)
                backticks = []
                backticks_name = ""
            else:
                backticks.append(stripped_line)

            continue

        # shell split
        tokens = split_shell(line)

        # declare statement
        if stripped_line.startswith("#!/bin/dash") or stripped_line.startswith("#!/usr/bin/dash"):
            declare = True

        # blank line
        elif stripped_line == "":
            body.append("")

        # comment
        elif line.lstrip().startswith("#"):
            body.append("    " * indent + line.strip())

        # assignment statement
        elif re.search(r'^[A-Za-z_][A-Za-z0-9_]*=.*$', stripped_line):
            statement, comment = split_comment(stripped_line)

            # name=value
            parts = statement.split('=', 1)
            name = parts[0].strip()
            value = parts[1].strip()

            name = fix_name(name)
            if len(value) >= 2 and value[0] == "`" and value[-1] == "`":
                result = fix_backticks(value[1:-1], name)
            elif value.startswith("`"):
                backticks = [value[1:]]
                backticks_name = name
                continue
            elif len(value) >= 5 and value.startswith("$((") and value.endswith("))"):
                result = f"{name} = {fix_arith(value[3:-2].strip())}"
            elif len(value) >= 4 and value.startswith("$(") and value.endswith(")") and sub_end(value, 2) == len(value) - 1:
                result = f"{name} = {fix_sub(value[2:-1].strip())}"
            elif len(value) >= 2 and value[0] == "'" and value[-1] == "'":
                result = f"{name} = {value[1:-1]!r}"
            elif len(value) >= 2 and value[0] == '"' and value[-1] == '"':
                result = f"{name} = {fix_double(value[1:-1])}"
            else:
                value, has_var = fix_var(value)
                if has_var:
                    result = f'{name} = f"{value}"'
                else:
                    result = f"{name} = {value!r}"

            if re.search(r'[*?\[]', parts[1].strip()):
                glob_vars.add(name)
            elif name in glob_vars:
                glob_vars.remove(name)

            if comment:
                result += f' # {comment}'

            body.append("    " * indent + result)

        # echo
        elif tokens and tokens[0] == "echo":
            no_newline = len(tokens) > 1 and tokens[1] == "-n"
            parts = line.split(maxsplit=2) if no_newline else line.split(maxsplit=1)

            if len(parts) == 1 or (no_newline and len(parts) == 2):
                if no_newline:
                    body.append("    " * indent + "print(end='')")
                else:
                    body.append("    " * indent + "print()")
            else:
                raw = parts[2].rstrip("\n") if no_newline else parts[1].rstrip("\n")
                raw, comment = split_comment(raw)
                redirect = ""
                append_mode = False

                raw_tokens = split_shell(raw)

                if len(raw_tokens) >= 2 and raw_tokens[-2] == ">>":
                    append_mode = True
                    redirect = raw_tokens[-1]
                    raw = raw.rsplit(">>", 1)[0].rstrip()
                elif len(raw_tokens) >= 2 and raw_tokens[-2] == ">":
                    redirect = raw_tokens[-1]
                    raw = raw.rsplit(">", 1)[0].rstrip()
                elif raw_tokens and raw_tokens[-1].startswith(">>"):
                    append_mode = True
                    redirect = raw_tokens[-1][2:]
                    raw = raw[:raw.rfind(raw_tokens[-1])].rstrip()
                elif raw_tokens and raw_tokens[-1].startswith(">"):
                    redirect = raw_tokens[-1][1:]
                    raw = raw[:raw.rfind(raw_tokens[-1])].rstrip()

                stripped = raw.strip()

                # `cmd`
                if len(stripped) >= 2 and stripped[0] == "`" and stripped[-1] == "`":
                    result = fix_backticks(stripped[1:-1])
                # `cmd next lines`
                elif stripped.startswith("`"):
                    backticks = [stripped[1:]]
                    backticks_name = ""
                    continue
                # $(( ))
                elif len(stripped) >= 5 and stripped.startswith("$((") and stripped.endswith("))"):
                    result = f"print({fix_arith(stripped[3:-2].strip())})"
                # $( )
                elif len(stripped) >= 4 and stripped.startswith("$(") and stripped.endswith(")") and sub_end(stripped, 2) == len(stripped) - 1:
                    result = f"print({fix_sub(stripped[2:-1].strip())})"
                # "..."
                elif len(stripped) >= 2 and stripped[0] == '"' and stripped[-1] == '"':
                    result = f"print({fix_double(stripped[1:-1])})"
                # '...'
                elif len(stripped) >= 2 and stripped[0] == "'" and stripped[-1] == "'":
                    result = f"print({stripped[1:-1]!r})"
                else:
                    # fix spaces
                    text = " ".join(raw.split())
                    var = text.strip()

                    # glob
                    has_glob = False
                    args = []
                    for arg in var.split():
                        if "*" in arg or "?" in arg or "[" in arg or "]" in arg:
                            has_glob = True
                            args.append(f'" ".join(sorted(glob.glob("{arg}")))')
                        else:
                            args.append(f'"{arg}"')

                    if has_glob:
                        need_glob = True
                        result = 'print(' + ' + " " + '.join(args) + ')'
                    # glob in variable
                    elif re.fullmatch(r'\$[A-Za-z_][A-Za-z0-9_]*', var) and fix_name(var[1:]) in glob_vars:
                        need_glob = True
                        name = fix_name(var[1:])
                        result = f'print(" ".join(sorted(glob.glob({name}))))'
                    # $var
                    elif re.search(r'\$(?:[a-zA-Z0-9_]+|[#@])', var):
                        var, has_var = fix_var(var)
                        result = f'print(" ".join(f"{var}".split()))'
                    else:
                        result = f"print({var!r})"

                if no_newline:
                    result = result[:-1] + ", end='')"

                if redirect:
                    mode = "a" if append_mode else "w"
                    target = fix_word(redirect)
                    result = result[:-1] + ", file=f)"
                    result = f"with open({target}, {mode!r}) as f: {result}"

                    # add comment back
                if comment:
                    result += f' # {comment}'

                body.append("    " * indent + result)

        # for
        elif tokens and tokens[0] == "for":
            var = tokens[1]
            vals, comment = split_comment(" ".join(tokens[3:]))
            vals = vals.split()
            args = []

            has_glob = len(vals) == 1 and (
                "*" in vals[0] or "?" in vals[0] or "[" in vals[0] or "]" in vals[0]
            )

            if has_glob:
                need_glob = True
                body.append("    " * indent + f'_files = sorted(glob.glob("{vals[0]}"))')
                body.append("    " * indent + f'if not _files:')
                body.append("    " * (indent + 1) + f'_files = ["{vals[0]}"]')
                result = f"for {var} in _files:"
            else:
                for val in vals:
                    args.append(f"'{val}'")

                result = f"for {var} in {', '.join(args)}:"

            if comment:
                result += f' # {comment}'

            body.append("    " * indent + result)

        # case
        elif tokens and tokens[0] == "case" and tokens[-1] == "in":
            case_expr = fix_word(tokens[1])
            first_case = True

        # pattern
        elif case_expr and stripped_line.endswith(")") and stripped_line != "esac":
            text, comment = split_comment(stripped_line)
            text = text.rstrip()
            need_fnmatch = True
            pats = []

            for pat in text[:-1].split("|"):
                pat = pat.strip()
                if len(pat) >= 2 and pat[0] in "'\"" and pat[-1] == pat[0]:
                    pat = pat[1:-1]
                pats.append(f"fnmatch.fnmatch({case_expr}, {pat!r})")

            if pats:
                if first_case:
                    result = "if " + " or ".join(pats) + ":"
                    first_case = False
                else:
                    result = "elif " + " or ".join(pats) + ":"

                if comment:
                    result += f' # {comment}'

                body.append("    " * indent + result)
                indent += 1

        # ;;
        elif case_expr and stripped_line == ";;":
            indent -= 1

        # esac
        elif case_expr and stripped_line == "esac":
            case_expr = ""
            first_case = False

        # && / ||
        elif tokens and tokens[0] not in ("if", "while") and ("&&" in tokens or "||" in tokens):
            op = "&&" if "&&" in tokens else "||"
            i = tokens.index(op)
            left = fix_cond(tokens[:i])
            right = fix_cmd(tokens[i + 1:])

            if left and right:
                if op == "&&":
                    body.append("    " * indent + f"if {left}:")
                else:
                    body.append("    " * indent + f"if not ({left}):")

                for line in right:
                    body.append("    " * (indent + 1) + line)

        # if
        elif tokens and tokens[0] == "if":
            cond = fix_cond(tokens[1:])
            if cond:
                body.append("    " * indent + f"if {cond}:")

        # then
        elif tokens and tokens[0] == "then":
            indent += 1

        # elif
        elif tokens and tokens[0] == "elif":
            indent -= 1
            cond = fix_cond(tokens[1:])
            if cond:
                body.append("    " * indent + f"elif {cond}:")

        # else
        elif tokens and tokens[0] == "else":
            indent -= 1
            body.append("    " * indent + "else:")
            indent += 1

        # fi
        elif tokens and tokens[0] == "fi":
            indent -= 1

        # while
        elif tokens and tokens[0] == "while":
            cond = fix_cond(tokens[1:])
            if cond:
                body.append("    " * indent + f"while {cond}:")

        # do
        elif tokens and tokens[0] == "do":
            indent += 1

        # done
        elif tokens and tokens[0] == "done":
            indent -= 1

        # exit
        elif tokens and tokens[0] == "exit":
            need_sys = True

            if len(tokens) > 1:
                body.append("    " * indent + f'sys.exit({tokens[1]})')
            else:
                body.append("    " * indent + "sys.exit()")

        # cd
        elif tokens and tokens[0] == "cd":
            need_os = True

            if len(tokens) > 1:
                body.append("    " * indent + f'os.chdir("{tokens[1]}")')

        # read
        elif tokens and tokens[0] == "read":
            if len(tokens) > 1:
                body.append("    " * indent + "try:")
                body.append("    " * (indent + 1) + f'{tokens[1]} = input()')
                body.append("    " * indent + "except EOFError:")
                body.append("    " * (indent + 1) + f'{tokens[1]} = ""')

        # external
        elif tokens:
            cmd, comment = split_comment(" ".join(tokens))
            cmd = split_shell(cmd)
            lines = fix_cmd(cmd)

            if lines:
                if comment:
                    lines[0] += f' # {comment}'

                for line in lines:
                    body.append("    " * indent + line)

if declare:
    print("#!/usr/bin/python3 -u")

if need_sys:
    print("import sys")

if need_os:
    print("import os")

if need_subprocess:
    print("import subprocess")

if need_glob:
    print("import glob")

if need_fnmatch:
    print("import fnmatch")

if need_arg:
    print("")
    print("def arg(number):")
    print("    if len(sys.argv) > number:")
    print("        return sys.argv[number]")
    print("    return ''")

for line in body:
    print(line)
