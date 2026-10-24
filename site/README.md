# Clinic Voice landing page

A responsive Next.js App Router marketing page with TypeScript and Tailwind CSS. The call preview is an interactive, simulated transcript; it does not access a microphone or connect to the Python receptionist.

## Run locally

Use Node.js 20.9 or newer.

```bash
cd site
cp .env.example .env.local
npm install
npm run dev
```

Open http://localhost:3000.

## Contact address

Set `NEXT_PUBLIC_CONTACT_EMAIL` in `.env.local` to the address that should receive pilot inquiries. All CTAs open the visitor's email application with a prefilled subject and message; no email is sent automatically.

The fallback, `hello@example.com`, is a deliberately non-operational demo placeholder. The footer displays a notice while that fallback is in use. Replace it before publishing. `NEXT_PUBLIC_*` values are public and embedded at build time, so do not put credentials in this variable and rebuild after changing it.

## Production build

```bash
npm install
npm run build
npm run start
```

`npm run typecheck` also runs TypeScript independently. The package lock pins the resolved dependency tree. Fonts use the operating system's serif and sans-serif families, so building and rendering do not require fetching remote fonts or images.

## Deploy to Vercel

1. Import the repository into Vercel when you are ready to publish.
2. Set **Root Directory** to `site`; use the detected **Next.js** framework preset.
3. Add `NEXT_PUBLIC_CONTACT_EMAIL` to the project environment variables.
4. Use the default `npm run build` build command and deploy.

The landing page deploys separately from the Python bot. It makes no claim that the preview is a live telephone connection. Use synthetic data when demonstrating the backend, and review the root README's privacy and HIPAA guidance before a real clinic pilot.

Built using the official [Next.js App Router setup](https://nextjs.org/docs/app/getting-started/installation) and [Tailwind CSS Next.js integration](https://tailwindcss.com/docs/installation/framework-guides/nextjs).
