"use client";

import { useState } from "react";

interface PricingTier {
  name: string;
  price: string;
  priceId: string | null;
  description: string;
  features: string[];
  cta: string;
  highlighted?: boolean;
}

const tiers: PricingTier[] = [
  {
    name: "Free",
    price: "$0",
    priceId: null,
    description: "Get started with the basics",
    features: [
      "Up to 5 projects",
      "Basic analytics",
      "Community support",
      "1 GB storage",
    ],
    cta: "Get Started",
  },
  {
    name: "Pro",
    price: "$9.99",
    priceId: process.env.NEXT_PUBLIC_STRIPE_PRO_PRICE_ID ?? "",
    description: "Everything you need to grow",
    features: [
      "Unlimited projects",
      "Advanced analytics",
      "Priority support",
      "10 GB storage",
      "Custom domain",
    ],
    cta: "Upgrade to Pro",
    highlighted: true,
  },
  {
    name: "Enterprise",
    price: "$29.99",
    priceId: process.env.NEXT_PUBLIC_STRIPE_ENTERPRISE_PRICE_ID ?? "",
    description: "For teams and organizations",
    features: [
      "Everything in Pro",
      "Unlimited storage",
      "Dedicated support",
      "SSO & SAML",
      "Custom integrations",
      "SLA guarantee",
    ],
    cta: "Contact Sales",
  },
];

export function PricingTable() {
  const [loading, setLoading] = useState<string | null>(null);

  const handleCheckout = async (priceId: string | null, tierName: string) => {
    if (!priceId) return;

    setLoading(tierName);
    try {
      const res = await fetch("/api/stripe/checkout", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ priceId }),
      });

      const data = await res.json();
      if (data.url) {
        window.location.href = data.url;
      }
    } catch (err) {
      console.error("Checkout error:", err);
    } finally {
      setLoading(null);
    }
  };

  return (
    <div className="mx-auto grid max-w-5xl gap-8 py-12 md:grid-cols-3">
      {tiers.map((tier) => (
        <div
          key={tier.name}
          className={`relative flex flex-col rounded-2xl border p-8 shadow-sm ${
            tier.highlighted
              ? "border-blue-500 ring-2 ring-blue-500"
              : "border-gray-200"
          }`}
        >
          {tier.highlighted && (
            <span className="absolute -top-3 left-1/2 -translate-x-1/2 rounded-full bg-blue-500 px-4 py-1 text-xs font-semibold text-white">
              Most Popular
            </span>
          )}

          <h3 className="text-lg font-semibold text-gray-900">{tier.name}</h3>
          <p className="mt-1 text-sm text-gray-500">{tier.description}</p>

          <div className="mt-6">
            <span className="text-4xl font-bold text-gray-900">{tier.price}</span>
            {tier.price !== "$0" && (
              <span className="text-sm text-gray-500">/month</span>
            )}
          </div>

          <ul className="mt-8 flex-1 space-y-3">
            {tier.features.map((feature) => (
              <li key={feature} className="flex items-start gap-3 text-sm text-gray-600">
                <svg
                  className="mt-0.5 h-4 w-4 flex-shrink-0 text-blue-500"
                  fill="none"
                  viewBox="0 0 24 24"
                  strokeWidth={2}
                  stroke="currentColor"
                >
                  <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
                </svg>
                {feature}
              </li>
            ))}
          </ul>

          <button
            onClick={() => handleCheckout(tier.priceId, tier.name)}
            disabled={loading === tier.name || !tier.priceId}
            className={`mt-8 w-full rounded-lg px-4 py-3 text-sm font-semibold transition-colors ${
              tier.highlighted
                ? "bg-blue-500 text-white hover:bg-blue-600"
                : "bg-gray-100 text-gray-900 hover:bg-gray-200"
            } disabled:cursor-not-allowed disabled:opacity-60`}
          >
            {loading === tier.name ? "Redirecting..." : tier.cta}
          </button>
        </div>
      ))}
    </div>
  );
}
