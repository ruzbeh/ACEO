import Stripe from "stripe";

const stripe = new Stripe(process.env.STRIPE_SECRET_KEY!, {
  apiVersion: "2024-04-10",
});

/**
 * Find an existing Stripe customer by email or create a new one.
 * Stores the Supabase user ID as metadata for cross-referencing.
 */
export async function getOrCreateCustomer(
  email: string,
  supabaseUserId: string
): Promise<Stripe.Customer> {
  const existing = await stripe.customers.list({ email, limit: 1 });

  if (existing.data.length > 0) {
    return existing.data[0];
  }

  return stripe.customers.create({
    email,
    metadata: { supabase_user_id: supabaseUserId },
  });
}

/**
 * Create a Stripe Checkout session for a subscription.
 * Redirects to success/cancel URLs after payment.
 */
export async function createCheckoutSession(
  customerId: string,
  priceId: string,
  origin: string
): Promise<Stripe.Checkout.Session> {
  return stripe.checkout.sessions.create({
    customer: customerId,
    mode: "subscription",
    line_items: [{ price: priceId, quantity: 1 }],
    success_url: `${origin}/dashboard/billing?session_id={CHECKOUT_SESSION_ID}`,
    cancel_url: `${origin}/pricing`,
    allow_promotion_codes: true,
  });
}
