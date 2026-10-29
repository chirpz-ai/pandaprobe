// Read actual package exports with the SDK's TypeScript compiler. No provider imports.
import fs from "node:fs";
import path from "node:path";
import { createRequire } from "node:module";
const root = path.resolve(process.argv[2]);
const require = createRequire(path.join(root, "package.json"));
const ts = require("typescript");
const src = path.join(root, "src");
const files = [];
function walk(dir) {
	for (const e of fs.readdirSync(dir, { withFileTypes: true })) {
		const p = path.join(dir, e.name);
		if (e.isDirectory()) walk(p);
		else if (p.endsWith(".ts")) files.push(p);
	}
}
walk(src);
const program = ts.createProgram(files, {
	target: ts.ScriptTarget.ES2022,
	module: ts.ModuleKind.NodeNext,
	moduleResolution: ts.ModuleResolutionKind.NodeNext,
	strict: true,
	skipLibCheck: true,
});
const checker = program.getTypeChecker();
const flags =
	ts.TypeFormatFlags.NoTruncation |
	ts.TypeFormatFlags.UseAliasDefinedOutsideCurrentScope;
const isOwn = (n) => n && n.getSourceFile().fileName.startsWith(src + path.sep);
const doc = (s) =>
	ts.displayPartsToString(s?.getDocumentationComment(checker) ?? []);
const hidden = (n) =>
	ts.getCombinedModifierFlags(n) &
		(ts.ModifierFlags.Private | ts.ModifierFlags.Protected) ||
	ts.getJSDocTags(n).some((t) => t.tagName.text === "internal");
const typeText = (s, n) =>
	checker.typeToString(checker.getTypeOfSymbolAtLocation(s, n), n, flags);
const source = (n) => ({
	file: path.relative(root, n.getSourceFile().fileName),
	line: n.getSourceFile().getLineAndCharacterOfPosition(n.getStart()).line + 1,
});
const id = (n) =>
	`${path.relative(src, n.getSourceFile().fileName)}#${n.name?.text ?? ""}`;
const param = (p) => ({
	name: p.name.getText(),
	type:
		p.type?.getText() ??
		checker.typeToString(checker.getTypeAtLocation(p), p, flags),
	default: p.initializer?.getText() ?? null,
	optional: !!p.questionToken || !!p.initializer,
	rest: !!p.dotDotDotToken,
});
function signature(s, name) {
	const d = s.getDeclaration();
	return {
		text: name + checker.signatureToString(s, d, flags),
		parameters: d?.parameters?.map(param) ?? [],
		returns: checker.typeToString(s.getReturnType(), d, flags),
		doc: ts.displayPartsToString(s.getDocumentationComment(checker)),
	};
}
const symbols = {};
function describe(n) {
	const key = id(n);
	if (symbols[key]) return key;
	const symbol = checker.getSymbolAtLocation(n.name);
	if (!symbol) return;
	const item = {
		id: key,
		name: n.name.text,
		...source(n),
		doc: doc(symbol),
		kind: "value",
		fields: [],
		methods: [],
		imports: [],
		generics: n.typeParameters?.map((p) => p.getText()) ?? [],
	};
	symbols[key] = item;
	if (ts.isClassDeclaration(n) || ts.isInterfaceDeclaration(n)) {
		item.kind = ts.isClassDeclaration(n) ? "class" : "interface";
		item.bases =
			n.heritageClauses?.flatMap((c) => c.types.map((t) => t.getText())) ?? [];
		const type = checker.getDeclaredTypeOfSymbol(symbol);
		if (ts.isClassDeclaration(n))
			item.constructors = checker
				.getTypeOfSymbolAtLocation(symbol, n)
				.getConstructSignatures()
				.map((s) => signature(s, "new " + item.name));
		for (const p of checker.getPropertiesOfType(type)) {
			const d = p.valueDeclaration ?? p.declarations?.[0];
			if (!isOwn(d) || hidden(d) || p.name.startsWith("_")) continue;
			const signatures = checker
				.getTypeOfSymbolAtLocation(p, d)
				.getCallSignatures();
			const method = ts.isMethodDeclaration(d) || ts.isMethodSignature(d);
			if (method)
				item.methods.push({
					name: p.name,
					doc: doc(p),
					signatures: signatures.map((s) => signature(s, p.name)),
					...source(d),
				});
			else
				item.fields.push({
					name: p.name,
					type: typeText(p, d),
					optional: !!(p.flags & ts.SymbolFlags.Optional),
					default: d.initializer?.getText() ?? null,
					readonly:
						!!(ts.getCombinedModifierFlags(d) & ts.ModifierFlags.Readonly) ||
						ts.isGetAccessorDeclaration(d),
					doc: doc(p),
				});
		}
		if (ts.isClassDeclaration(n)) {
			for (const p of checker.getPropertiesOfType(
				checker.getTypeOfSymbolAtLocation(symbol, n),
			)) {
				const d = p.valueDeclaration ?? p.declarations?.[0];
				if (!isOwn(d) || hidden(d) || !ts.isMethodDeclaration(d)) continue;
				item.methods.push({
					name: p.name,
					static: true,
					doc: doc(p),
					signatures: checker
						.getTypeOfSymbolAtLocation(p, d)
						.getCallSignatures()
						.map((s) => signature(s, p.name)),
					...source(d),
				});
			}
		}
		item.indexes = checker
			.getIndexInfosOfType(type)
			.map((info) => ({
				key: checker.typeToString(info.keyType),
				type: checker.typeToString(info.type, undefined, flags),
			}));
		// Preserve defaults assigned in constructors, not just field initializers.
		function constructorDefaults(node) {
			if (
				ts.isBinaryExpression(node) &&
				node.operatorToken.kind === ts.SyntaxKind.EqualsToken &&
				ts.isPropertyAccessExpression(node.left) &&
				node.left.expression.kind === ts.SyntaxKind.ThisKeyword
			) {
				const field = item.fields.find((f) => f.name === node.left.name.text);
				if (
					field &&
					ts.isBinaryExpression(node.right) &&
					node.right.operatorToken.kind === ts.SyntaxKind.QuestionQuestionToken
				)
					field.default = node.right.right.getText();
			}
			ts.forEachChild(node, constructorDefaults);
		}
		for (const member of n.members)
			if (ts.isConstructorDeclaration(member)) constructorDefaults(member);
	} else if (ts.isFunctionDeclaration(n)) {
		item.kind = "function";
		item.signatures = checker
			.getTypeOfSymbolAtLocation(symbol, n)
			.getCallSignatures()
			.map((s) => signature(s, item.name));
	} else if (ts.isTypeAliasDeclaration(n)) {
		item.kind = "type";
		item.definition = n.type.getText();
		if (
			item.name === "ReflectOptions" ||
			item.name === "ResolvedReflectConfig"
		) {
			for (const p of checker.getPropertiesOfType(
				checker.getDeclaredTypeOfSymbol(symbol),
			)) {
				const d = p.valueDeclaration ?? p.declarations?.[0];
				item.fields.push({
					name: p.name,
					type: typeText(p, d),
					optional: !!(p.flags & ts.SymbolFlags.Optional),
					default: d.initializer?.getText() ?? null,
					doc: doc(p),
				});
			}
		}
	} else if (ts.isEnumDeclaration(n)) {
		item.kind = "enum";
		item.fields = n.members.map((m) => ({
			name: m.name.getText(),
			type: "string",
			default: m.initializer?.getText() ?? "",
			doc: "",
		}));
	} else {
		let initial = n.initializer;
		while (
			initial &&
			(ts.isAsExpression(initial) || ts.isSatisfiesExpression(initial))
		)
			initial = initial.expression;
		if (
			initial &&
			ts.isObjectLiteralExpression(initial) &&
			symbol.declarations?.some(ts.isTypeAliasDeclaration)
		) {
			item.kind = "enum";
			item.fields = initial.properties
				.filter(ts.isPropertyAssignment)
				.map((p) => ({
					name: p.name.getText(),
					type: "string",
					default: p.initializer.getText(),
					doc: "",
				}));
		} else {
			item.type = typeText(symbol, n);
			item.default = n.initializer?.getText() ?? null;
		}
	}
	return key;
}
for (const file of files) {
	const sf = program.getSourceFile(file);
	for (const statement of sf.statements) {
		if (ts.isVariableStatement(statement)) {
			if (!(ts.getCombinedModifierFlags(statement) & ts.ModifierFlags.Export))
				continue;
			for (const declaration of statement.declarationList.declarations)
				if (ts.isIdentifier(declaration.name)) describe(declaration);
		} else if (statement.name && !statement.name.text.startsWith("_"))
			describe(statement);
	}
}
const exports = [];
const pkg = JSON.parse(
	fs.readFileSync(path.join(root, "package.json"), "utf8"),
);
for (const [subpath, definition] of Object.entries(pkg.exports)) {
	const file = path.join(
		root,
		definition.types.replace("./dist/", "src/").replace(/\.d\.ts$/, ".ts"),
	);
	const module = checker.getSymbolAtLocation(program.getSourceFile(file));
	for (const symbol of checker.getExportsOfModule(module)) {
		const resolved =
			symbol.flags & ts.SymbolFlags.Alias
				? checker.getAliasedSymbol(symbol)
				: symbol;
		const d = resolved.valueDeclaration ?? resolved.declarations?.[0];
		if (!isOwn(d))
			throw Error(`Unresolved package export ${subpath}:${symbol.name}`);
		const key = describe(d);
		if (!key) throw Error(`Missing declaration for ${symbol.name}`);
		const importPath =
			subpath === "." ? "pandaprobe" : "pandaprobe" + subpath.slice(1);
		const entry = { name: symbol.name, importPath, id: key };
		symbols[key].imports.push(entry);
		exports.push(entry);
	}
}
// Resolved defaults are source data, not type declarations.
const defaultsFile = program.getSourceFile(path.join(src, "reflect/config.ts"));
const defaults = {};
function defaultsVisit(n) {
	if (
		ts.isVariableDeclaration(n) &&
		n.name.getText() === "defaults" &&
		n.initializer
	) {
		let value = n.initializer;
		while (ts.isAsExpression(value) || ts.isSatisfiesExpression(value))
			value = value.expression;
		if (ts.isObjectLiteralExpression(value))
			for (const p of value.properties)
				if (ts.isPropertyAssignment(p)) {
					let init = p.initializer;
					while (ts.isAsExpression(init) || ts.isSatisfiesExpression(init))
						init = init.expression;
					defaults[p.name.getText().replaceAll('"', "")] = init.getText();
				}
	}
	ts.forEachChild(n, defaultsVisit);
}
defaultsVisit(defaultsFile);
process.stdout.write(JSON.stringify({ exports, symbols, defaults }, null, 2));
