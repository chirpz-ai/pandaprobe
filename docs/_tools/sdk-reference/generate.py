#!/usr/bin/env python3
"""Generate reviewed SDK reference MDX from Python AST and TypeScript symbols.

Run with --sdk /path/to/pandaprobe-sdk. --check verifies generated files/coverage.
Requires Python 3.10+ and the TypeScript SDK's installed development dependencies.
"""

import argparse
import json
import re
import subprocess
from collections import defaultdict
from pathlib import Path

from content import INTRO, LANGUAGE_NOTES, METHOD_NOTES, PAGES
from extract_python import inventory

HERE = Path(__file__).resolve().parent
FIELD_NOTES = json.loads((HERE / "field-notes.json").read_text()) if (HERE / "field-notes.json").exists() else {}


def cell(value):
    return (
        str(value)
        .replace("|", "&#124;")
        .replace("\n", " ")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace("{", "&#123;")
        .replace("}", "&#125;")
    )


def code(value):
    return "`" + str(value).replace("|", "\\|").replace("\n", " ").replace("`", "") + "`"


def prose(value):
    # Source docstrings use Python/Sphinx and JSDoc markup, not MDX.
    value = re.sub(r":(?:class|func|meth|attr):`([^`]+)`", r"`\1`", value)
    value = value.replace("``", "`")
    value = value.split("\n\n")[0].strip()
    return (
        re.sub(r"(?<!`)\{@link ([^}]+)\}", r"`\1`", value)
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace("{", "&#123;")
        .replace("}", "&#125;")
    )


def heading(name):
    return name.lower()


def route(item):
    file = item["file"].replace("src/pandaprobe/", "").replace("src/", "")
    name = item.get("display", item["name"])
    if file in ("__init__.py", "index.ts"):
        return (
            "tracing"
            if name
            in (
                "trace",
                "span",
                "start_trace",
                "startTrace",
                "set_session",
                "session",
                "set_user",
                "user",
                "setSession",
                "setUser",
            )
            else "client"
        )
    if file in ("_version.py", "version.ts", "client.py", "client.ts"):
        return "client"
    if file in ("config.py", "config.ts"):
        return "configuration"
    if file in ("schemas.py", "schemas.ts", "validation.py"):
        return "data"
    if file.startswith("tracing/") or file in ("decorators.py", "decorators.ts"):
        return "tracing"
    if file.startswith("wrappers/"):
        return "wrappers"
    if file.startswith("integrations/"):
        return "integrations"
    if file.startswith("api/"):
        return (
            "platform-models" if "/models." in file else "platform-errors" if "/errors." in file else "platform-client"
        )
    if file.startswith("reflect/"):
        if "/config." in file:
            return "reflect-config"
        if "/models." in file:
            return "reflect-models"
        if "/validation." in file:
            return "reflect-validation"
        if "/execution." in file or name == "Invocation":
            return "reflect-execution"
        return "reflect-runtime"
    raise ValueError(f"Unassigned public symbol {item['id']}")


def signature_block(signature, display=None, original=None):
    text = signature["text"]
    if display and original and display != original:
        text = re.sub(r"\b" + re.escape(original) + r"\b", display, text)
    if len(text) > 110 and "(" in text:
        # Parameters are structured by the source parsers; wrap the outer list only.
        start = text.index("(")
        depth = 0
        end = None
        for i in range(start, len(text)):
            if text[i] == "(":
                depth += 1
            if text[i] == ")":
                depth -= 1
                if depth == 0:
                    end = i
                    break
        if end:
            inner = text[start + 1 : end]
            parts = []
            begin = 0
            depth = 0
            quote = None
            for i, ch in enumerate(inner):
                if quote:
                    if ch == quote and (i == 0 or inner[i - 1] != "\\"):
                        quote = None
                    continue
                if ch in ('"', "'"):
                    quote = ch
                elif ch in "([{<":
                    depth += 1
                elif ch in ")]}>":
                    depth -= 1
                elif ch == "," and depth == 0:
                    parts.append(inner[begin:i].strip())
                    begin = i + 1
            parts.append(inner[begin:].strip())
            text = text[: start + 1] + "\n" + "".join("  " + part + ",\n" for part in parts if part) + text[end:]
    out = ["```text", text, "```", ""]
    params = signature.get("parameters", [])
    if params:
        out += ["| Parameter | Type | Default / passing |", "| --- | --- | --- |"]
        for p in params:
            default = (
                code(p["default"])
                if p.get("default") is not None
                else ("Optional" if p.get("optional") else "Required")
            )
            if p.get("kind") == "keyword-only":
                default += "; keyword only"
            if p.get("kind") in ("variadic", "keywords") or p.get("rest"):
                default = "Additional arguments"
            out.append(f"| {code(p['name'])} | {code(p['type'])} | {default} |")
        out += [""]
    return "\n".join(out)


def symbol_block(item, language, revision, defaults):
    name = item["display"]
    out = [f"## `{name}`", ""]
    imports = item["imports"]
    if imports:
        unique = list(dict.fromkeys((e["importPath"], e["name"]) for e in imports))
        first = unique[0]
        expression = (
            f"from {first[0]} import {first[1]}"
            if language == "python"
            else f'import {{ {first[1]} }} from "{first[0]}";'
        )
        if language == "typescript" and (item["kind"] in ("interface", "type") or name == "TraceCapture"):
            expression = expression.replace("import {", "import type {")
        out += ["```" + ("python" if language == "python" else "ts"), expression, "```", ""]
        if len(unique) > 1:
            out += ["Also exported from " + ", ".join(code(p) for p, n in unique[1:]) + ".", ""]
    else:
        out += ["Supporting contract used by the API below; it is not a separate package export.", ""]
    if item["doc"]:
        out += [prose(item["doc"]), ""]
    if item.get("generics"):
        out += ["Type parameters: " + ", ".join(code(g) for g in item["generics"]) + ".", ""]
    link = f"https://github.com/chirpz-ai/pandaprobe-sdk/blob/{revision}/libraries/{language}/{item['file']}#L{item['line']}"
    out += [f"[Source declaration]({link})", ""]
    if item.get("dataclass"):
        out += ["Construct with the fields below as arguments. Defaults apply when omitted.", ""]
    if item.get("model"):
        out += [
            "Construct with keyword fields below. Pydantic validates the model and provides its standard serialization methods.",
            "",
        ]
    if item.get("definition"):
        definition = item["definition"]
        if name in ("ReflectOptions", "ResolvedReflectConfig"):
            out += [
                "All fields below are "
                + ("optional overrides." if name == "ReflectOptions" else "read-only resolved values."),
                "",
            ]
        else:
            generic = "<" + ", ".join(item["generics"]) + ">" if item.get("generics") else ""
            out += ["```text", name + generic + " = " + definition, "```", ""]
    if item.get("type"):
        out += ["Type: " + code(item["type"]) + ".", ""]
    if item.get("default") is not None:
        out += ["Value: " + code(item["default"]) + ".", ""]
    for ctor in item.get("constructors", []):
        if language == "python":
            ctor = {**ctor, "text": re.sub(r" -> None$", "", ctor["text"])}
        out += ["### Constructor", "", signature_block(ctor, name, item["name"])]
    for sig in item.get("signatures", []):
        out += [signature_block(sig, name, item["name"])]
    fields = item.get("fields", [])
    if item.get("indexes"):
        out += [
            "Additional indexed fields: "
            + ", ".join(code("[" + i["key"] + "]: " + i["type"]) for i in item["indexes"])
            + ".",
            "",
        ]
    if fields:
        out += [
            "### " + ("Values" if item["kind"] == "enum" else "Fields and properties"),
            "",
            "| Name | Type | Default / contract |",
            "| --- | --- | --- |",
        ]
        for f in fields:
            default = f.get("default")
            if route(item) == "reflect-config" and f["name"] in defaults:
                default = defaults[f["name"]]
            contract = (
                code(default)
                if default is not None
                else (
                    "Optional"
                    if f.get("optional")
                    else "Required"
                    if item.get("dataclass") or item.get("model") or item["kind"] == "interface"
                    else "Instance value"
                )
            )
            if f.get("readonly"):
                contract += "; read-only"
            if f.get("doc"):
                contract += "; " + cell(prose(f["doc"]))
            note = FIELD_NOTES.get(name + "." + f["name"]) or (
                FIELD_NOTES.get("ReflectConfig." + f["name"])
                if name in ("ReflectOptions", "ResolvedReflectConfig")
                else None
            )
            if note:
                contract += "; " + cell(note)
            out.append(f"| {code(f['name'])} | {code(f['type'])} | {contract} |")
        out += [""]
    methods = item.get("methods", [])
    if methods:
        out += ["### Methods", "", "<AccordionGroup>"]
        for method in methods:
            label = method["name"]
            out += [f'<Accordion title="{label}">', ""]
            if method.get("static"):
                out += ["Static method on " + code(name) + ".", ""]
            note = METHOD_NOTES.get(f"{name}.{label}") or method["doc"]
            if note:
                out += [prose(note), ""]
            for sig in method["signatures"]:
                out += [signature_block(sig)]
            out += ["</Accordion>", ""]
        out += ["</AccordionGroup>", ""]
    return "\n".join(out)


def overview(language, groups, export_rows, revision):
    label = "Python" if language == "python" else "TypeScript"
    install = (
        "pip install pandaprobe\n# or\nuv add pandaprobe"
        if language == "python"
        else "npm install pandaprobe\n# or\nyarn add pandaprobe\n# or\npnpm add pandaprobe"
    )
    text = f'''---
title: "{label} SDK"
description: "Public imports, classes, functions, options, and data contracts for the {label} package"
---

The `{"pandaprobe"}` package includes tracing, native platform access, and opt-in Reflect. This reference lists the public imports and their complete source-declared signatures, options, and fields. For a first integration, start with [Trace](/tracing/get-started/quickstart) or [Reflect](/reflect/quickstart).

```bash
{install}
```

{"Python 3.10+ is supported. Install only the provider/framework extras you use; Reflect uses the optional `[reflect]` extra. Some frameworks require newer Python versions." if language == "python" else "The core package supports Node.js 18+ and ESM/CommonJS. Optional framework and native Reflect dependencies may require a newer runtime; the native Reflect examples use Node.js 22+. Import only documented package subpaths."}

## Find an API

| Area | Reference |
| --- | --- |
'''
    for slug, (title, description) in PAGES.items():
        text += f"| [{title}](/reference/{language}/{slug}) | {description} |\n"
    text += """
## Reading the contracts

Signatures and field tables are generated from the SDK source. Defaults are shown where declared; an instance property without a declared default is not necessarily a constructor input. Framework callbacks are shown for completeness and are normally called by the framework. Helper types used by an API are identified when they are not separately exported.

This reference covers package APIs and their supporting contracts, not private transport workers, workspace mutation internals, or third-party SDK methods. Source links identify the exact code snapshot used to generate each entry. See the HTTP API reference for the complete server endpoint surface.

## Public import index

| Import path | Export | Details |
| --- | --- | --- |
"""
    for e in sorted(export_rows, key=lambda e: (e["importPath"], e["name"])):
        item = groups[e["id"]]
        text += f"| {code(e['importPath'])} | {code(e['name'])} | [{item['display']}](/reference/{language}/{route(item)}#{heading(item['display'])}) |\n"
    text += f"\n[Source snapshot](https://github.com/chirpz-ai/pandaprobe-sdk/tree/{revision}/libraries/{language}).\n"
    return text


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sdk", type=Path, required=True)
    parser.add_argument("--docs", type=Path, default=HERE.parents[1])
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    sdk = args.sdk.resolve()
    docs = args.docs.resolve()
    revision = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=sdk, text=True).strip()
    py = inventory(sdk / "libraries/python")
    ts = json.loads(
        subprocess.check_output(
            ["node", str(HERE / "extract-typescript.mjs"), str(sdk / "libraries/typescript")], text=True
        )
    )
    # Public method argument/result types that are not standalone package exports.
    supporting = [
        "schemas.ts#SpanDataInit",
        "schemas.ts#TraceDataInit",
        "schemas.ts#ScoreDataInit",
        "reflect/evaluation.ts#SubmissionOptions",
        "reflect/validation.ts#Validator",
        "reflect/models.ts#FailureNotice",
    ]
    outputs = {}
    manifest = {"sdk_revision": revision, "languages": {}}
    for language, data in [("python", py), ("typescript", ts)]:
        selected = {e["id"]: data["symbols"][e["id"]] for e in data["exports"]}
        if language == "typescript":
            for key in supporting:
                selected[key] = data["symbols"][key]
            for name in ("SpanData", "TraceData", "ScoreData"):
                defaults = {
                    f["name"]: f["default"]
                    for f in selected["schemas.ts#" + name]["fields"]
                    if f.get("default") is not None
                }
                for field in selected["schemas.ts#" + name + "Init"]["fields"]:
                    if field["name"] in defaults:
                        field["default"] = defaults[field["name"]]
        for item in selected.values():
            item["display"] = item["imports"][0]["name"] if item["imports"] else item["name"]
        grouped = defaultdict(list)
        for item in selected.values():
            grouped[route(item)].append(item)
        outputs[f"reference/{language}/overview.mdx"] = overview(language, selected, data["exports"], revision)
        for slug, (title, description) in PAGES.items():
            body = f'---\ntitle: {json.dumps(title)}\ndescription: {json.dumps(description)}\n---\n\n'
            body += INTRO[slug] + "\n\n" + LANGUAGE_NOTES.get((language, slug), "") + "\n\n"
            body += (
                "## On this page\n\n"
                + ", ".join(
                    f"[{item['display']}](#{heading(item['display'])})"
                    for item in sorted(grouped[slug], key=lambda x: x["display"])
                )
                + ".\n\n"
            )
            example = HERE / "examples" / language / (slug + ".md")
            if example.exists():
                body += "## Example\n\n" + example.read_text().strip() + "\n\n"
            for item in sorted(grouped[slug], key=lambda x: x["display"]):
                body += symbol_block(item, language, revision, data.get("defaults", {})) + "\n"
            body += (
                "---\n\nSignatures and fields are generated from the [SDK source](https://github.com/chirpz-ai/pandaprobe-sdk/tree/"
                + revision
                + "/libraries/"
                + language
                + "). See the [import index](/reference/"
                + language
                + "/overview#public-import-index) for available entry points.\n"
            )
            outputs[f"reference/{language}/{slug}.mdx"] = body
        manifest["languages"][language] = {
            "exports": [
                {
                    **e,
                    "page": f"reference/{language}/{route(selected[e['id']])}",
                    "anchor": heading(selected[e["id"]]["display"]),
                }
                for e in data["exports"]
            ],
            "symbols": [
                {
                    "id": item["id"],
                    "page": f"reference/{language}/{route(item)}",
                    "name": item["display"],
                    "methods": [m["name"] for m in item.get("methods", [])],
                    "fields": [f["name"] for f in item.get("fields", [])],
                }
                for item in sorted(selected.values(), key=lambda x: x["id"])
            ],
        }
    outputs["reference/sdk-reference-manifest.json"] = json.dumps(manifest, indent=2) + "\n"
    stale = []
    for relative, value in outputs.items():
        destination = docs / relative
        if not destination.exists() or destination.read_text() != value:
            stale.append(relative)
            if not args.check:
                destination.parent.mkdir(parents=True, exist_ok=True)
                destination.write_text(value)
    if args.check and stale:
        raise SystemExit("Reference files need regeneration:\n" + "\n".join(stale))
    for language, data in manifest["languages"].items():
        print(
            f"{language}: {len(data['exports'])} import entries, {len(data['symbols'])} documented symbols; "
            + ("checked" if args.check else "generated")
        )
    print(f"{len(outputs) - 1} SDK reference pages; every inventoried public export has a page and anchor.")


if __name__ == "__main__":
    main()
