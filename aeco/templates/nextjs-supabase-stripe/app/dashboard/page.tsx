import { redirect } from "next/navigation";
import { createServerClient } from "@/lib/supabase/server";
import { SignOutButton } from "./sign-out-button";

export default async function DashboardPage() {
  const supabase = await createServerClient();

  const {
    data: { user },
  } = await supabase.auth.getUser();

  if (!user) {
    redirect("/login");
  }

  return (
    <div className="mx-auto max-w-4xl px-4 py-12">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Welcome back</h1>
          <p className="mt-1 text-sm text-gray-500">{user.email}</p>
        </div>
        <SignOutButton />
      </div>

      <div className="mt-8 grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
        <div className="rounded-xl border p-6">
          <h3 className="font-semibold">Subscription</h3>
          <p className="mt-1 text-sm text-gray-500">Free plan</p>
          <button className="mt-4 rounded-lg bg-black px-4 py-2 text-sm font-medium text-white transition hover:bg-gray-800 dark:bg-white dark:text-black dark:hover:bg-gray-200">
            Upgrade
          </button>
        </div>

        <div className="rounded-xl border p-6">
          <h3 className="font-semibold">Usage</h3>
          <p className="mt-1 text-sm text-gray-500">
            Track your usage and limits here.
          </p>
        </div>

        <div className="rounded-xl border p-6">
          <h3 className="font-semibold">Settings</h3>
          <p className="mt-1 text-sm text-gray-500">
            Manage your account and preferences.
          </p>
        </div>
      </div>
    </div>
  );
}
