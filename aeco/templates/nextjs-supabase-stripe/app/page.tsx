import Link from "next/link";

const features = [
  {
    title: "Authentication",
    description:
      "Secure email and social login powered by Supabase Auth with session management.",
  },
  {
    title: "Payments",
    description:
      "Stripe integration with checkout sessions, webhooks, and subscription management.",
  },
  {
    title: "Database",
    description:
      "PostgreSQL database with row-level security, migrations, and real-time capabilities.",
  },
];

export default function HomePage() {
  return (
    <div className="flex flex-col items-center">
      {/* Hero */}
      <section className="flex flex-col items-center justify-center gap-6 px-4 py-24 text-center sm:py-32">
        <h1 className="text-4xl font-bold tracking-tight sm:text-6xl">
          {"{{PROJECT_NAME}}"}
        </h1>
        <p className="max-w-2xl text-lg text-gray-600 dark:text-gray-400">
          The fastest way to launch your SaaS. Built with Next.js, Supabase, and
          Stripe so you can focus on what matters.
        </p>
        <Link
          href="/login"
          className="rounded-lg bg-black px-6 py-3 text-sm font-medium text-white transition hover:bg-gray-800 dark:bg-white dark:text-black dark:hover:bg-gray-200"
        >
          Get Started
        </Link>
      </section>

      {/* Features */}
      <section className="w-full max-w-5xl px-4 pb-24">
        <div className="grid gap-8 sm:grid-cols-3">
          {features.map((feature) => (
            <div
              key={feature.title}
              className="rounded-xl border p-6 transition hover:shadow-md"
            >
              <h3 className="mb-2 text-lg font-semibold">{feature.title}</h3>
              <p className="text-sm text-gray-600 dark:text-gray-400">
                {feature.description}
              </p>
            </div>
          ))}
        </div>
      </section>

      {/* Footer */}
      <footer className="w-full border-t py-8 text-center text-sm text-gray-500">
        &copy; {new Date().getFullYear()} {"{{PROJECT_NAME}}"}. All rights
        reserved.
      </footer>
    </div>
  );
}
