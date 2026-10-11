import os, ast, json, re, sys, urllib.request, urllib.error

API_KEY = "sk-caa1cb4f093049099131cd65ee400270"
BASE_URL = "https://api.deepseek.com"
MODEL = "deepseek-chat"


def read_file(path):
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def analyze_python_structure(code):
    try:
        tree = ast.parse(code)
    except SyntaxError as e:
        return {"syntax_error": str(e), "functions": [], "classes": [], "imports": []}

    functions, classes, imports = [], [], []
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef):
            length = None
            if hasattr(node, "end_lineno") and node.end_lineno:
                length = node.end_lineno - node.lineno + 1
            functions.append({
                "name": node.name,
                "lineno": node.lineno,
                "args": [a.arg for a in node.args.args],
                "docstring": ast.get_docstring(node) is not None,
                "length": length,
            })
        elif isinstance(node, ast.ClassDef):
            classes.append({
                "name": node.name,
                "lineno": node.lineno,
                "docstring": ast.get_docstring(node) is not None,
            })
        elif isinstance(node, ast.Import):
            for alias in node.names:
                imports.append(alias.name)
        elif isinstance(node, ast.ImportFrom):
            imports.append(node.module)
    return {"syntax_error": None, "functions": functions, "classes": classes, "imports": imports}


def simple_static_checks(code):
    issues = []
    lines = code.splitlines()
    for i, line in enumerate(lines, 1):
        if len(line) > 120:
            issues.append({"line": i, "severity": "low", "message": "行长度超过120", "code": line.strip()})
        if "TODO" in line or "FIXME" in line:
            issues.append({"line": i, "severity": "low", "message": "TODO/FIXME", "code": line.strip()})
        if "eval(" in line:
            issues.append({"line": i, "severity": "high", "message": "eval 安全风险", "code": line.strip()})
        if re.match(r"\s*except\s*:", line):
            issues.append({"line": i, "severity": "medium", "message": "裸 except", "code": line.strip()})
        if re.match(r"\s*except\s+Exception\s*:\s*pass", line):
            issues.append({"line": i, "severity": "medium", "message": "异常 pass", "code": line.strip()})

    try:
        tree = ast.parse(code)
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                length = (node.end_lineno or node.lineno) - node.lineno + 1
                if length > 50:
                    issues.append({"line": node.lineno, "severity": "medium",
                                   "message": "函数 " + node.name + " 过长 " + str(length) + " 行", "code": ""})
                if ast.get_docstring(node) is None:
                    issues.append({"line": node.lineno, "severity": "low",
                                   "message": "函数 " + node.name + " 缺 docstring", "code": ""})
    except SyntaxError:
        pass
    return issues


def call_llm(system_prompt, user_prompt):
    url = BASE_URL.rstrip("/") + "/chat/completions"
    headers = {
        "Content-Type": "application/json",
        "Authorization": "Bearer " + API_KEY,
    }
    data = {
        "model": MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": 0.2,
    }
    req = urllib.request.Request(
        url,
        data=json.dumps(data).encode("utf-8"),
        headers=headers,
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            result = json.loads(resp.read().decode("utf-8"))
            return result["choices"][0]["message"]["content"]
    except urllib.error.HTTPError as e:
        return "HTTP Error: " + str(e.code) + "\n" + e.read().decode("utf-8")
    except Exception as e:
        return "Error: " + str(e)


def main():
    project_dir = os.path.dirname(os.path.abspath(__file__))
    path = os.path.join(project_dir, "bad_code.py")
    if not os.path.exists(path):
        print("找不到 bad_code.py，请确认它在项目目录：" + project_dir)
        return

    code = read_file(path)
    structure = analyze_python_structure(code)
    issues = simple_static_checks(code)

    system_prompt = (
        "你是一个资深的代码审查 Agent。分析代码和静态检查结果，发现 Bug、质量问题、安全风险，给出改进建议。\n"
        "按 critical / high / medium / low 分类。\n"
        "每个问题包含：位置、描述、原因、修复建议。\n"
        "输出 Markdown。"
    )

    user_prompt = (
        "审查以下代码。\n"
        "文件：bad_code.py\n"
        "代码：\n"
        "```python\n"
        + code + "\n"
        "```\n"
        "静态分析：\n"
        + json.dumps(issues, ensure_ascii=False, indent=2) + "\n"
        "代码结构：\n"
        + json.dumps(structure, ensure_ascii=False, indent=2) + "\n"
        "输出审查报告。"
    )

    print("正在审查，请稍等...\n")
    report = call_llm(system_prompt, user_prompt)
    print(report)

    out_path = os.path.join(project_dir, "report.md")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(report)
    print("\n已保存到 " + out_path)


if __name__ == "__main__":
    main()