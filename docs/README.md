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

```
docs/
├── docs.json                        # Mintlify configuration (theme, navigation, branding)
├── assets/
│   ├── logo/                        # Brand logos and favicons
│   ├── images/                      # Screenshots and diagrams
│   ├── PandProbe.png                # Banner image (dark bg)
│   └── PandProbe-1.png              # Banner image with mascot
├── get-started/                     # Getting started guides
├── tracing/
│   ├── wrappers/                    # LLM provider wrappers (OpenAI, Anthropic, Gemini)
│   ├── integrations/                # Agent framework integrations
│   ├── manual/                      # Manual instrumentation (decorators, context managers)
│   └── configuration/               # Env vars, project config, troubleshooting
├── evaluation/                      # Evaluation framework (placeholders)
├── api-reference/                   # REST API reference (placeholder)
└── changelog/                       # Release notes (placeholder)
```

## Configuration

All site configuration lives in `docs.json`. Key settings:

| Setting | Description |
|---|---|
| `theme` | Mintlify theme (`linden`) |
| `colors` | Brand colors (primary: `#10B981`) |
| `background.color.dark` | Dark mode background (`#18191b`) |
| `logo` | Logo images for light/dark mode |
| `navigation` | Full sidebar and tab structure |

See the [Mintlify docs.json reference](https://mintlify.com/docs/organize/settings-reference) for all options.

## Writing Content

- All pages are `.mdx` files with YAML frontmatter (`title`, `description`, `icon`)
- Use [Mintlify components](https://mintlify.com/docs/content/components) for rich content: `<CodeGroup>`, `<Tabs>`, `<Note>`, `<Warning>`, `<Tip>`, `<Steps>`, `<Card>`, `<CardGroup>`, `<Accordion>`
- Cross-reference pages with absolute paths (e.g., `/tracing/concepts`)
- Add new pages to the `navigation` section in `docs.json`

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
4. Verify it renders correctly with `mint dev`

## Deployment

Mintlify handles deployment automatically when connected to a GitHub repository. Push changes to the configured branch and the site updates within minutes.

For manual deployment or CI/CD integration, see the [Mintlify deployment docs](https://mintlify.com/docs/quickstart#deployment).

## Useful Commands

| Command | Description |
|---|---|
| `mint dev` | Start local dev server on port 3000 |
| `mint dev --port 3001` | Start on a custom port |
| `mint broken-links` | Check for broken internal links |
