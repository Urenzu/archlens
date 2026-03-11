"""AST parsing — extract functions, classes, and call relationships from Python files."""

from __future__ import annotations

import ast
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class FunctionInfo:
    name: str
    qualified_name: str  # module.Class.method or module.func
    module: str
    class_name: str | None
    lineno: int
    end_lineno: int
    loc: int
    calls: list[str] = field(default_factory=list)  # names of called functions
    complexity: int = 1
    params: int = 0
    max_nesting: int = 0
    vulnerabilities: list[str] = field(default_factory=list)


@dataclass
class ClassInfo:
    name: str
    qualified_name: str
    module: str
    lineno: int
    end_lineno: int
    methods: list[str] = field(default_factory=list)


@dataclass
class ModuleInfo:
    path: str
    name: str
    functions: list[FunctionInfo] = field(default_factory=list)
    classes: list[ClassInfo] = field(default_factory=list)
    imports: list[str] = field(default_factory=list)  # module names this file imports from


def _compute_complexity(node: ast.AST) -> int:
    """Compute cyclomatic complexity of an AST node."""
    complexity = 1
    for child in ast.walk(node):
        if isinstance(child, (ast.If, ast.IfExp)):
            complexity += 1
        elif isinstance(child, (ast.For, ast.AsyncFor, ast.While)):
            complexity += 1
        elif isinstance(child, ast.ExceptHandler):
            complexity += 1
        elif isinstance(child, ast.With):
            complexity += 1
        elif isinstance(child, ast.Assert):
            complexity += 1
        elif isinstance(child, ast.BoolOp):
            # Each 'and'/'or' adds a branch
            complexity += len(child.values) - 1
    return complexity


def _compute_max_nesting(node: ast.AST) -> int:
    """Compute maximum block nesting depth within a function body."""
    def _depth(n: ast.AST, current: int) -> int:
        max_d = current
        for child in ast.iter_child_nodes(n):
            if isinstance(child, (ast.If, ast.For, ast.While, ast.With,
                                  ast.Try, ast.AsyncFor, ast.AsyncWith)):
                max_d = max(max_d, _depth(child, current + 1))
            else:
                max_d = max(max_d, _depth(child, current))
        return max_d
    return _depth(node, 0)


def _extract_calls(node: ast.AST) -> list[str]:
    """Extract names of functions called within an AST node."""
    calls = []
    for child in ast.walk(node):
        if isinstance(child, ast.Call):
            if isinstance(child.func, ast.Name):
                calls.append(child.func.id)
            elif isinstance(child.func, ast.Attribute):
                calls.append(child.func.attr)
    return calls


# Vulnerability detection patterns
_VULN_PATTERNS = [
    ("SQL injection", {"execute", "executemany", "raw", "rawSQL"}),
    ("Command injection", {"system", "popen", "call", "run", "Popen"}),
    ("Code injection", {"eval", "exec"}),
    ("Unsafe deserialization", {"loads", "load"}),
]

_DANGEROUS_SUBPROCESS_KWARGS = {"shell"}


def _detect_vulnerabilities(node: ast.FunctionDef) -> list[str]:
    """Detect potential security vulnerabilities in a function."""
    vulns: list[str] = []
    for child in ast.walk(node):
        if not isinstance(child, ast.Call):
            continue
        func_name = ""
        if isinstance(child.func, ast.Name):
            func_name = child.func.id
        elif isinstance(child.func, ast.Attribute):
            func_name = child.func.attr

        # Check for SQL injection (string formatting in execute calls)
        if func_name in ("execute", "executemany", "raw", "rawSQL"):
            for arg in child.args:
                if isinstance(arg, (ast.JoinedStr, ast.BinOp, ast.Mod)):
                    vulns.append(f"SQL injection — string formatting in {func_name}()")
                    break

        # Check for eval/exec with non-literal args
        if func_name in ("eval", "exec"):
            if child.args and not isinstance(child.args[0], ast.Constant):
                vulns.append(f"Code injection — {func_name}() with dynamic input")

        # Check for subprocess with shell=True
        if func_name in ("call", "run", "Popen", "system", "popen"):
            for kw in child.keywords:
                if kw.arg == "shell" and isinstance(kw.value, ast.Constant) and kw.value.value:
                    vulns.append(f"Command injection — {func_name}() with shell=True")

    return vulns


def parse_file(path: Path, repo_root: Path) -> ModuleInfo | None:
    """Parse a Python file and extract functions, classes, and calls."""
    try:
        source = path.read_text(encoding="utf-8", errors="replace")
        tree = ast.parse(source, filename=str(path))
    except (SyntaxError, ValueError):
        return None

    rel = path.relative_to(repo_root)
    module_name = str(rel.with_suffix("")).replace("/", ".").replace("\\", ".")
    module = ModuleInfo(path=str(rel), name=module_name)

    for node in ast.iter_child_nodes(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                module.imports.append(alias.name)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                module.imports.append(node.module)

        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            fi = _make_function_info(node, module_name, class_name=None)
            module.functions.append(fi)

        elif isinstance(node, ast.ClassDef):
            qname = f"{module_name}.{node.name}"
            ci = ClassInfo(
                name=node.name,
                qualified_name=qname,
                module=module_name,
                lineno=node.lineno,
                end_lineno=node.end_lineno or node.lineno,
            )
            for item in node.body:
                if isinstance(item, ast.FunctionDef | ast.AsyncFunctionDef):
                    fi = _make_function_info(item, module_name, class_name=node.name)
                    module.functions.append(fi)
                    ci.methods.append(fi.qualified_name)
            module.classes.append(ci)

    return module


def _make_function_info(
    node: ast.FunctionDef | ast.AsyncFunctionDef,
    module_name: str,
    class_name: str | None,
) -> FunctionInfo:
    prefix = f"{module_name}.{class_name}" if class_name else module_name
    qname = f"{prefix}.{node.name}"
    end = node.end_lineno or node.lineno
    # Exclude 'self'/'cls' from param count for methods
    raw_params = node.args.args
    param_count = len(raw_params) - (1 if class_name and raw_params else 0)
    return FunctionInfo(
        name=node.name,
        qualified_name=qname,
        module=module_name,
        class_name=class_name,
        lineno=node.lineno,
        end_lineno=end,
        loc=end - node.lineno + 1,
        calls=_extract_calls(node),
        complexity=_compute_complexity(node),
        params=param_count,
        max_nesting=_compute_max_nesting(node),
        vulnerabilities=_detect_vulnerabilities(node),
    )
