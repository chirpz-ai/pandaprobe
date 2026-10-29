"""Static public-contract inventory: no SDK/provider import side effects."""

import ast
from pathlib import Path


def inventory(root):
    root = Path(root)
    modules = {}
    for file in (root / "src/pandaprobe").rglob("*.py"):
        relative = file.relative_to(root / "src").with_suffix("")
        parts = list(relative.parts)
        if parts[-1] == "__init__":
            parts.pop()
        module = ".".join(parts)
        tree = ast.parse(file.read_text())
        local, imports, exports = {}, {}, None
        for node in tree.body:
            if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
                local[node.name] = node
            elif isinstance(node, (ast.Assign, ast.AnnAssign)):
                targets = node.targets if isinstance(node, ast.Assign) else [node.target]
                for target in targets:
                    if isinstance(target, ast.Name):
                        local[target.id] = node
                        if target.id == "__all__":
                            exports = ast.literal_eval(node.value)
            elif isinstance(node, ast.ImportFrom):
                base = module if file.name == "__init__.py" else module.rsplit(".", 1)[0]
                if node.level:
                    base = ".".join(base.split(".")[: len(base.split(".")) - node.level + 1])
                    origin = base + ("." + node.module if node.module else "")
                else:
                    origin = node.module
                for name in node.names:
                    imports[name.asname or name.name] = (origin, name.name)
        modules[module] = dict(file=file, tree=tree, local=local, imports=imports, exports=exports)

    def resolve(module, name, seen=None):
        seen = set() if seen is None else seen
        if (module, name) in seen or module not in modules:
            return None
        seen.add((module, name))
        data = modules[module]
        if name in data["local"]:
            return module, name, data["local"][name]
        if name in data["imports"]:
            return resolve(*data["imports"][name], seen)
        return None

    def expr(node):
        return ast.unparse(node) if node is not None else None

    def parameter(a, default=None, kind="positional"):
        return dict(
            name=a.arg,
            type=expr(a.annotation) or "Not annotated",
            default=expr(default),
            optional=default is not None,
            kind=kind,
        )

    def signature(node, name=None):
        args = node.args
        positional = args.posonlyargs + args.args
        defaults = [None] * (len(positional) - len(args.defaults)) + args.defaults
        params = [
            parameter(a, d, "positional-only" if i < len(args.posonlyargs) else "positional")
            for i, (a, d) in enumerate(zip(positional, defaults))
            if a.arg not in ("self", "cls")
        ]
        if args.vararg:
            params.append(parameter(args.vararg, kind="variadic"))
        params += [parameter(a, d, "keyword-only") for a, d in zip(args.kwonlyargs, args.kw_defaults)]
        if args.kwarg:
            params.append(parameter(args.kwarg, kind="keywords"))
        # Preserve keyword-only separators and defaults in the displayed signature.
        copied = ast.arguments(
            posonlyargs=[a for a in args.posonlyargs if a.arg not in ("self", "cls")],
            args=[a for a in args.args if a.arg not in ("self", "cls")],
            vararg=args.vararg,
            kwonlyargs=args.kwonlyargs,
            kw_defaults=args.kw_defaults,
            kwarg=args.kwarg,
            defaults=args.defaults,
        )
        text = (
            ("async " if isinstance(node, ast.AsyncFunctionDef) else "")
            + (name or node.name)
            + "("
            + ast.unparse(copied)
            + ")"
        )
        if node.returns:
            text += " -> " + expr(node.returns)
        return dict(text=text, parameters=params, returns=expr(node.returns), doc=ast.get_docstring(node) or "")

    def field(name, annotation, value):
        default, constraints = expr(value), []
        if isinstance(value, ast.Call) and expr(value.func) in ("Field", "field"):
            default = expr(value.args[0]) if value.args else None
            for kw in value.keywords:
                if kw.arg == "default":
                    default = expr(kw.value)
                elif kw.arg == "default_factory":
                    default = "factory: " + expr(kw.value)
                else:
                    constraints.append(f"{kw.arg}={expr(kw.value)}")
        return dict(
            name=name,
            type=expr(annotation) or "Any",
            default=default,
            doc="; ".join(constraints),
            optional=default is not None,
        )

    symbols = {}

    def describe(module, name, node):
        key = module + "#" + name
        if key in symbols:
            return key
        file = modules[module]["file"]
        item = dict(
            id=key,
            name=name,
            file=str(file.relative_to(root)),
            line=node.lineno,
            doc=ast.get_docstring(node) or ""
            if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef))
            else "",
            kind="value",
            fields=[],
            methods=[],
            imports=[],
        )
        symbols[key] = item
        if isinstance(node, ast.ClassDef):
            item["kind"] = "enum" if any(expr(base).endswith(("Enum", "StrEnum")) for base in node.bases) else "class"
            item["bases"] = [expr(base) for base in node.bases]
            methods, fields = {}, {}
            for base in reversed(node.bases):
                found = resolve(module, expr(base))
                if found and isinstance(found[2], ast.ClassDef):
                    parent = symbols[describe(*found)]
                    methods.update({m["name"]: m for m in parent["methods"]})
                    fields.update({f["name"]: f for f in parent["fields"]})
                    if parent.get("constructors"):
                        item["constructors"] = parent["constructors"]
            for child in node.body:
                if (
                    isinstance(child, ast.AnnAssign)
                    and isinstance(child.target, ast.Name)
                    and not child.target.id.startswith("_")
                ):
                    fields[child.target.id] = field(child.target.id, child.annotation, child.value)
                elif isinstance(child, ast.Assign):
                    for target in child.targets:
                        if isinstance(target, ast.Name) and not target.id.startswith("_"):
                            annotation = None
                            try:
                                annotation = ast.Name(id=type(ast.literal_eval(child.value)).__name__)
                            except (ValueError, TypeError):
                                pass
                            fields[target.id] = field(target.id, annotation, child.value)
                elif isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    if child.name == "__init__":
                        item["constructors"] = [signature(child, name)]
                        parameter_types = {p["name"]: p["type"] for p in item["constructors"][0]["parameters"]}
                        # Only declared instance fields; values depending on arguments are not defaults.
                        for statement in ast.walk(child):
                            if isinstance(statement, (ast.Assign, ast.AnnAssign)):
                                targets = (
                                    statement.targets if isinstance(statement, ast.Assign) else [statement.target]
                                )
                                for target in [
                                    part
                                    for target in targets
                                    for part in ast.walk(target)
                                    if isinstance(part, ast.Attribute)
                                ]:
                                    if (
                                        isinstance(target, ast.Attribute)
                                        and isinstance(target.value, ast.Name)
                                        and target.value.id == "self"
                                        and not target.attr.startswith("_")
                                    ):
                                        inferred = (
                                            parameter_types.get(statement.value.id)
                                            if isinstance(statement.value, ast.Name)
                                            else None
                                        )
                                        fields.setdefault(
                                            target.attr,
                                            dict(
                                                name=target.attr,
                                                type=expr(getattr(statement, "annotation", None))
                                                or inferred
                                                or "Not annotated",
                                                default=None,
                                                doc="Instance attribute.",
                                                optional=False,
                                            ),
                                        )
                    elif child.name.startswith("_"):
                        continue
                    elif any(expr(d) == "property" for d in child.decorator_list):
                        fields[child.name] = dict(
                            name=child.name,
                            type=expr(child.returns) or "Any",
                            default=None,
                            doc=ast.get_docstring(child) or "Read-only property.",
                            readonly=True,
                            optional=False,
                        )
                    else:
                        methods[child.name] = dict(
                            name=child.name,
                            doc=ast.get_docstring(child) or "",
                            signatures=[signature(child)],
                            file=str(file.relative_to(root)),
                            line=child.lineno,
                        )
            item["fields"], item["methods"] = list(fields.values()), list(methods.values())
            if item.get("constructors"):
                item["constructors"] = [
                    {**s, "text": name + s["text"][s["text"].index("(") :]} for s in item["constructors"]
                ]
            if any(expr(d).startswith("dataclass") for d in node.decorator_list) and not item.get("constructors"):
                item["dataclass"] = True
            if any(b in ("BaseModel", "Record", "ApiModel") for b in item["bases"]):
                item["model"] = True
            item["fields"] = [f for f in item["fields"] if f["name"] != "model_config"]
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            item["kind"] = "function"
            item["signatures"] = [signature(node)]
        else:
            item["definition"] = expr(node.value)
        return key

    exports = []
    for module, data in sorted(modules.items()):
        if data["exports"] is not None:
            for name in data["exports"]:
                found = resolve(module, name)
                if not found:
                    raise ValueError(f"Unresolved export {module}.{name}")
                key = describe(*found)
                entry = dict(importPath=module, name=name, id=key)
                symbols[key]["imports"].append(entry)
                exports.append(entry)
    # Document importable data/utility contracts and types returned by the public API.
    supplemental = {
        "pandaprobe.config": ["SdkConfig", "resolve_config"],
        "pandaprobe.schemas": [
            "SpanKind",
            "SpanStatusCode",
            "TraceStatus",
            "ScoreDataType",
            "SpanData",
            "TraceData",
            "ScoreData",
        ],
        "pandaprobe.validation": [
            "validate_messages_format",
            "warn_if_invalid_messages",
            "extract_last_user_message",
            "extract_last_assistant_message",
        ],
        "pandaprobe.tracing.context": ["get_current_trace", "get_span_stack"],
        "pandaprobe.tracing.session": [
            "get_current_session_id",
            "set_current_session_id",
            "reset_current_session_id",
            "get_current_user_id",
            "set_current_user_id",
            "reset_current_user_id",
        ],
        "pandaprobe.tracing.capture": ["TraceCapture"],
        "pandaprobe.api.models": ["ApiModel", "EvaluationRequest"],
        "pandaprobe.api.resources": ["Traces", "Evaluations"],
        "pandaprobe.reflect.models": ["FailureNotice"],
        "pandaprobe.reflect.validation": ["Replay", "Validator"],
    }
    for module, names in supplemental.items():
        for name in names:
            key = describe(*resolve(module, name))
            entry = dict(importPath=module, name=name, id=key, supplemental=True)
            symbols[key]["imports"].append(entry)
            exports.append(entry)
    return dict(symbols=symbols, exports=exports)
