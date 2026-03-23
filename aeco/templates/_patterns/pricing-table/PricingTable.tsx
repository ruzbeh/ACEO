import React from "react";

interface PlanFeature {
  text: string;
  included: boolean;
}

interface Plan {
  name: string;
  price: string;
  period: string;
  description: string;
  features: PlanFeature[];
  popular?: boolean;
  priceId: string;
}

const plans: Plan[] = [
  {
    name: "{{PLAN_1_NAME}}",
    price: "{{PLAN_1_PRICE}}",
    period: "/month",
    description: "Perfect for getting started",
    priceId: "", // Set your Stripe Price ID
    features: [
      { text: "Up to 1,000 requests", included: true },
      { text: "Basic analytics", included: true },
      { text: "Email support", included: true },
      { text: "Custom branding", included: false },
      { text: "Priority support", included: false },
    ],
  },
  {
    name: "{{PLAN_2_NAME}}",
    price: "{{PLAN_2_PRICE}}",
    period: "/month",
    description: "Best for growing teams",
    popular: true,
    priceId: "", // Set your Stripe Price ID
    features: [
      { text: "Up to 10,000 requests", included: true },
      { text: "Advanced analytics", included: true },
      { text: "Priority email support", included: true },
      { text: "Custom branding", included: true },
      { text: "Priority support", included: false },
    ],
  },
  {
    name: "{{PLAN_3_NAME}}",
    price: "{{PLAN_3_PRICE}}",
    period: "/month",
    description: "For large-scale operations",
    priceId: "", // Set your Stripe Price ID
    features: [
      { text: "Unlimited requests", included: true },
      { text: "Full analytics suite", included: true },
      { text: "Dedicated support", included: true },
      { text: "Custom branding", included: true },
      { text: "Priority support", included: true },
    ],
  },
];

async function handleCheckout(priceId: string) {
  const res = await fetch("/api/checkout", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ priceId }),
  });
  const { url } = await res.json();
  if (url) window.location.href = url;
}

export default function PricingTable() {
  return (
    <section className="py-20 px-4 bg-gray-50">
      <div className="max-w-6xl mx-auto">
        <h2 className="text-3xl font-bold text-center text-gray-900 mb-4">
          Simple, transparent pricing
        </h2>
        <p className="text-center text-gray-600 mb-12 max-w-2xl mx-auto">
          Choose the plan that fits your needs. Upgrade or downgrade at any time.
        </p>

        <div className="grid md:grid-cols-3 gap-8">
          {plans.map((plan) => (
            <div
              key={plan.name}
              className={`relative rounded-2xl bg-white p-8 shadow-sm border-2 transition-shadow hover:shadow-lg ${
                plan.popular
                  ? "border-indigo-600 shadow-md"
                  : "border-gray-200"
              }`}
            >
              {plan.popular && (
                <span className="absolute -top-3 left-1/2 -translate-x-1/2 rounded-full bg-indigo-600 px-4 py-1 text-xs font-semibold text-white">
                  Most Popular
                </span>
              )}

              <h3 className="text-lg font-semibold text-gray-900">
                {plan.name}
              </h3>
              <p className="mt-1 text-sm text-gray-500">{plan.description}</p>

              <div className="mt-6 flex items-baseline gap-1">
                <span className="text-4xl font-bold text-gray-900">
                  ${plan.price}
                </span>
                <span className="text-sm text-gray-500">{plan.period}</span>
              </div>

              <ul className="mt-8 space-y-3">
                {plan.features.map((feature) => (
                  <li key={feature.text} className="flex items-center gap-3">
                    {feature.included ? (
                      <svg
                        className="h-5 w-5 text-indigo-600 shrink-0"
                        fill="none"
                        viewBox="0 0 24 24"
                        strokeWidth={2}
                        stroke="currentColor"
                      >
                        <path
                          strokeLinecap="round"
                          strokeLinejoin="round"
                          d="M4.5 12.75l6 6 9-13.5"
                        />
                      </svg>
                    ) : (
                      <svg
                        className="h-5 w-5 text-gray-300 shrink-0"
                        fill="none"
                        viewBox="0 0 24 24"
                        strokeWidth={2}
                        stroke="currentColor"
                      >
                        <path
                          strokeLinecap="round"
                          strokeLinejoin="round"
                          d="M6 18L18 6M6 6l12 12"
                        />
                      </svg>
                    )}
                    <span
                      className={
                        feature.included ? "text-gray-700" : "text-gray-400"
                      }
                    >
                      {feature.text}
                    </span>
                  </li>
                ))}
              </ul>

              <button
                onClick={() => handleCheckout(plan.priceId)}
                className={`mt-8 w-full rounded-lg py-3 px-4 text-sm font-semibold transition-colors ${
                  plan.popular
                    ? "bg-indigo-600 text-white hover:bg-indigo-700"
                    : "bg-gray-100 text-gray-900 hover:bg-gray-200"
                }`}
              >
                Get started
              </button>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
