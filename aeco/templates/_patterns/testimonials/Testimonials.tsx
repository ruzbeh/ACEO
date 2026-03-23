import React from "react";

interface Testimonial {
  name: string;
  role: string;
  avatar: string;
  quote: string;
}

const testimonials: Testimonial[] = [
  {
    name: "Sarah Chen",
    role: "Head of Product, Acme Inc.",
    avatar: "https://api.dicebear.com/7.x/avataaars/svg?seed=sarah",
    quote:
      "This product completely transformed our workflow. We shipped features 3x faster within the first month.",
  },
  {
    name: "Marcus Rivera",
    role: "CTO, Launchpad Studios",
    avatar: "https://api.dicebear.com/7.x/avataaars/svg?seed=marcus",
    quote:
      "The best tool we have adopted this year. Our team loves the simplicity and the results speak for themselves.",
  },
  {
    name: "Emily Tanaka",
    role: "Founder, Nimbus AI",
    avatar: "https://api.dicebear.com/7.x/avataaars/svg?seed=emily",
    quote:
      "We evaluated a dozen alternatives and nothing came close. The support team is exceptional too.",
  },
];

export default function Testimonials() {
  return (
    <section className="py-20 px-4 bg-white">
      <div className="max-w-6xl mx-auto">
        <h2 className="text-3xl font-bold text-center text-gray-900 mb-4">
          Loved by teams everywhere
        </h2>
        <p className="text-center text-gray-600 mb-12 max-w-2xl mx-auto">
          See what our customers have to say about their experience.
        </p>

        <div className="grid md:grid-cols-3 gap-8">
          {testimonials.map((t) => (
            <div
              key={t.name}
              className="rounded-2xl bg-white border border-gray-100 p-8 shadow-md hover:shadow-lg transition-shadow"
            >
              {/* Quote icon */}
              <svg
                className="h-8 w-8 text-indigo-200 mb-4"
                fill="currentColor"
                viewBox="0 0 24 24"
              >
                <path d="M4.583 17.321C3.553 16.227 3 15 3 13.011c0-3.5 2.457-6.637 6.03-8.188l.893 1.378c-3.335 1.804-3.987 4.145-4.247 5.621.537-.278 1.24-.375 1.929-.311 1.804.167 3.226 1.648 3.226 3.489a3.5 3.5 0 01-3.5 3.5 3.871 3.871 0 01-2.748-1.179zm10 0C13.553 16.227 13 15 13 13.011c0-3.5 2.457-6.637 6.03-8.188l.893 1.378c-3.335 1.804-3.987 4.145-4.247 5.621.537-.278 1.24-.375 1.929-.311 1.804.167 3.226 1.648 3.226 3.489a3.5 3.5 0 01-3.5 3.5 3.871 3.871 0 01-2.748-1.179z" />
              </svg>

              <p className="text-gray-700 leading-relaxed mb-6">{t.quote}</p>

              <div className="flex items-center gap-3">
                <img
                  src={t.avatar}
                  alt={t.name}
                  className="h-10 w-10 rounded-full bg-gray-100"
                />
                <div>
                  <p className="text-sm font-semibold text-gray-900">
                    {t.name}
                  </p>
                  <p className="text-xs text-gray-500">{t.role}</p>
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
