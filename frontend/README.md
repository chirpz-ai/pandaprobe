This is a [Next.js](https://nextjs.org) project bootstrapped with [`create-next-app`](https://nextjs.org/docs/app/api-reference/cli/create-next-app).

## Getting Started

First, run the development server:

```bash
npm run dev
# or
yarn dev
# or
pnpm dev
# or
bun dev
```

Open [http://localhost:3000](http://localhost:3000) with your browser to see the result.

You can start editing the page by modifying `app/page.tsx`. The page auto-updates as you edit the file.

This project uses [`next/font`](https://nextjs.org/docs/app/building-your-application/optimizing/fonts) to automatically optimize and load [Geist](https://vercel.com/font), a new font family for Vercel.

## Dashboard typography

Font sizes and their default line heights live in [`src/styles/typography.css`](src/styles/typography.css). Use its Tailwind classes instead of arbitrary sizes or inline numeric font sizes:

- `text-caption` — 11px, the minimum for regular UI text, including card headings, labels, tabs and metadata.
- `text-xs` — 12px for dense content and code; `text-sm` — 14px for body copy and controls.
- `text-base`, `text-lg`, `text-xl`, `text-2xl` — 16px, 18px, 20px and 24px. `text-6xl` is reserved for the 404 display.
- `text-compact` — 10px, used only for timeline ticks, span-kind tags and the development-mode badge.

Sizes use rem units so they respect browser font preferences. Components requiring inline styles can reference the same variables, e.g. `fontSize: "var(--text-xs)"`. If adding a custom size name, also register it in `src/lib/utils/cn.ts` so class overrides merge as font sizes rather than colors.

## Learn More

To learn more about Next.js, take a look at the following resources:

- [Next.js Documentation](https://nextjs.org/docs) - learn about Next.js features and API.
- [Learn Next.js](https://nextjs.org/learn) - an interactive Next.js tutorial.

You can check out [the Next.js GitHub repository](https://github.com/vercel/next.js) - your feedback and contributions are welcome!

## Deploy on Vercel

The easiest way to deploy your Next.js app is to use the [Vercel Platform](https://vercel.com/new?utm_medium=default-template&filter=next.js&utm_source=create-next-app&utm_campaign=create-next-app-readme) from the creators of Next.js.

Check out our [Next.js deployment documentation](https://nextjs.org/docs/app/building-your-application/deploying) for more details.
