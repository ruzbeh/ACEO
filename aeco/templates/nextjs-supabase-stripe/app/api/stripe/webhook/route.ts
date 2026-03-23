import { headers } from "next/headers";
import { NextResponse } from "next/server";
import Stripe from "stripe";
import { createClient } from "@supabase/supabase-js";

const stripe = new Stripe(process.env.STRIPE_SECRET_KEY!, {
  apiVersion: "2024-06-20",
});

const supabaseAdmin = createClient(
  process.env.NEXT_PUBLIC_SUPABASE_URL!,
  process.env.SUPABASE_SERVICE_ROLE_KEY!
);

export async function POST(request: Request) {
  const body = await request.text();
  const headersList = await headers();
  const signature = headersList.get("stripe-signature");

  if (!signature) {
    return NextResponse.json(
      { error: "Missing stripe-signature header" },
      { status: 400 }
    );
  }

  let event: Stripe.Event;

  try {
    event = stripe.webhooks.constructEvent(
      body,
      signature,
      process.env.STRIPE_WEBHOOK_SECRET!
    );
  } catch (err) {
    const message = err instanceof Error ? err.message : "Unknown error";
    console.error(`Webhook signature verification failed: ${message}`);
    return NextResponse.json({ error: message }, { status: 400 });
  }

  switch (event.type) {
    case "checkout.session.completed": {
      const session = event.data.object as Stripe.Checkout.Session;

      if (!session.customer || !session.subscription) break;

      const subscription = await stripe.subscriptions.retrieve(
        session.subscription as string
      );

      // Update profile with Stripe customer ID
      await supabaseAdmin
        .from("profiles")
        .update({
          stripe_customer_id: session.customer as string,
          subscription_status: "active",
          updated_at: new Date().toISOString(),
        })
        .eq("id", session.metadata?.user_id);

      // Upsert subscription record
      await supabaseAdmin.from("subscriptions").upsert(
        {
          user_id: session.metadata?.user_id,
          stripe_subscription_id: subscription.id,
          plan: subscription.items.data[0]?.price.id ?? "unknown",
          status: subscription.status,
          current_period_end: new Date(
            subscription.current_period_end * 1000
          ).toISOString(),
        },
        { onConflict: "user_id" }
      );

      break;
    }

    case "customer.subscription.updated":
    case "customer.subscription.deleted": {
      const subscription = event.data.object as Stripe.Subscription;
      const customerId = subscription.customer as string;

      // Find user by stripe_customer_id
      const { data: profile } = await supabaseAdmin
        .from("profiles")
        .select("id")
        .eq("stripe_customer_id", customerId)
        .single();

      if (profile) {
        const status =
          subscription.status === "active" ? "active" : subscription.status;

        await supabaseAdmin
          .from("profiles")
          .update({
            subscription_status: status,
            updated_at: new Date().toISOString(),
          })
          .eq("id", profile.id);

        await supabaseAdmin
          .from("subscriptions")
          .update({
            status: subscription.status,
            plan: subscription.items.data[0]?.price.id ?? "unknown",
            current_period_end: new Date(
              subscription.current_period_end * 1000
            ).toISOString(),
          })
          .eq("user_id", profile.id);
      }

      break;
    }
  }

  return NextResponse.json({ received: true }, { status: 200 });
}
