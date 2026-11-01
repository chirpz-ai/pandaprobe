# PandaProbe Documentation

This directory contains the PandaProbe documentation site, built with [Mintlify](https://mintlify.com/).

## Prerequisites

- [Node.js](https://nodejs.org/) v20.17.0 or higher (LTS recommended)

## Local Development

### Install the Mintlify CLI

```bash
npm i -g mint
```

Or with pnpm:

```bash
pnpm add -g mint
```

See the [Mintlify CLI installation docs](https://mintlify.com/docs/installation) for full details and troubleshooting.

### Preview locally

Run the following command from the `docs/` directory:

```bash
mint dev
```

The site will be available at [http://localhost:3000](http://localhost:3000). Changes to `.mdx` files are reflected automatically via hot reload.

To use a custom port:

```bash
mint dev --port 3001
```

### Push changes

Commit and push to trigger an automatic deployment:

```bash
git add .
git commit -m "Update docs"
git push
```

Mintlify automatically deploys changes when connected to your GitHub repository.

## Project Structure

```text
docs/
├── docs.json             # Theme, navigation, branding, and API routes
├── _tools/sdk-reference/ # SDK reference maintenance tools (excluded from publishing)
├── assets/               # Logos, provider icons, and evaluation media
├── overview.mdx          # Single product overview page
├── tracing/              # Provider/framework/manual tracing in both SDKs
├── evaluation/           # Metrics, UI/API setup, and scheduled monitors
├── reflect/              # Quickstart, guides, and compact runtime reference
├── reference/            # Central API and SDK references
│   ├── api/              # HTTP introduction and openapi.json endpoint source
│   ├── python/           # Generated Python SDK contracts
│   ├── typescript/       # Generated TypeScript SDK contracts
│   └── tools/            # CLI and Skill pages
└── changelog/            # Python/TypeScript SDK, core-service, and CLI releases
```

## Configuration

All site configuration lives in `docs.json`. Key settings:

| Setting | Description |
|---|---|
| `theme` | Mintlify theme (`aspen`) |
| `colors` | Neutral accents (`#18181B` / `#E4E4E7`); blue (`#2F86FF`) reserved for primary button backgrounds in `style.css` |
| `background.color.dark` | Dark mode background (`#0c0c0b`) |
| `logo` | Logo images for light/dark mode |
| `navigation` | Full sidebar and tab structure |

See the [Mintlify docs.json reference](https://mintlify.com/docs/organize/settings-reference) for all options.

## Writing Content

- All pages are `.mdx` files with YAML frontmatter (`title`, `description`, `icon`)
- Use [Mintlify components](https://mintlify.com/docs/content/components) for rich content: `<CodeGroup>`, `<Tabs>`, `<Note>`, `<Warning>`, `<Tip>`, `<Steps>`, `<Card>`, `<CardGroup>`, `<Accordion>`
- Cross-reference pages with absolute paths (e.g., `/tracing/get-started/concepts`)
- Add new pages to the `navigation` section in `docs.json`
- Keep product tabs ordered Trace → Evaluate → Reflect.
- Use matching `Python` / `TypeScript` titles in `<CodeGroup>` for language examples; identify application-provided helpers explicitly.
- Check SDK signatures and released versions before publishing examples. Reflect acceptance requires independent outcomes, not a model-generated explanation.

### Overview component

The setup prompt and copy controls live directly in `overview.mdx`. Keep the inline `OnboardingPrompt` export as one continuous block, without blank lines or standalone JavaScript comments: the current Mintlify preview failed to compile the spaced version on a fresh startup even though `mint validate` passed. After changing this component, restart `mint dev`, open `/overview`, and check both copy buttons; hot reload alone is not sufficient verification.

## Adding a New Page

1. Create a new `.mdx` file in the appropriate directory
2. Add YAML frontmatter:
   ```yaml
   ---
   title: "Page Title"
   description: "Brief description"
   icon: "icon-name"
   ---
   ```
3. Add the page path (without `.mdx`) to `docs.json` under the correct navigation group
4. Run `mint validate` and `mint broken-links --check-anchors`.
5. Preview the page in both language tabs with `mint dev`.

## Deployment

Mintlify handles deployment automatically when connected to a GitHub repository. Push changes to the configured branch and the site updates within minutes.

For manual deployment or CI/CD integration, see the [Mintlify deployment docs](https://mintlify.com/docs/quickstart#deployment).

## Useful Commands

| Command | Description |
|---|---|
| `mint dev` | Start local dev server on port 3000 |
| `mint dev --port 3001` | Start on a custom port |
| `mint validate` | Validate MDX, configuration, and the documentation build |
| `mint broken-links --check-anchors` | Check internal pages and heading links |

## Maintaining SDK references

The **Reference** tab contains Python SDK, TypeScript SDK, and HTTP API references. Keep `reference/api/openapi.json` as the HTTP source of truth; do not replace generated endpoint definitions with hand-written SDK descriptions.

The HTTP introduction and schema live together in `reference/api/`. Mintlify reads the schema path in `docs.json` and retains its existing generated `/api-reference/…` endpoint URLs. A redirect preserves the former introduction URL.

SDK API pages under `reference/python/` and `reference/typescript/` are generated from the sibling SDK checkout. The generator reads Python AST and TypeScript package exports/compiler symbols; it does not import optional agent/model runtimes or need provider credentials. Install the TypeScript SDK's development dependencies so its TypeScript compiler is available.

Maintenance tools and their source fragments live in `docs/_tools/sdk-reference/`. `docs/.mintignore` excludes `_tools/` from the published site.

From the core repository root:

```bash
python docs/_tools/sdk-reference/generate.py --sdk ../pandaprobe-sdk
python docs/_tools/sdk-reference/generate.py --sdk ../pandaprobe-sdk --check
```

- Edit reviewed introductions and lifecycle notes in `docs/_tools/sdk-reference/content.py`, and field descriptions in `field-notes.json`.
- Edit runnable example fragments in `docs/_tools/sdk-reference/examples/`.
- Regenerate after SDK contract changes; do not hand-edit generated API signatures or field tables.
- `reference/sdk-reference-manifest.json` records each import, symbol, page, field, and method, together with the source revision. `--check` fails when generated content or coverage is stale.
- The reference landing page and `docs.json` navigation are maintained separately. Newly exported symbols must be assigned an appropriate reference area; generation fails for unknown source areas rather than silently omitting them.
- Run `mint validate` and `mint broken-links --check-anchors` from `docs/`, then verify representative examples against the relevant SDK versions. Source extraction checks declarations; behavioral notes and examples still require review.
