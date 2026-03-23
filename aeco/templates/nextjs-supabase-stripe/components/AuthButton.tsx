import Link from "next/link";
import { createServerClient } from "@/lib/supabase/server";

export async function AuthButton() {
  const supabase = await createServerClient();

  const {
    data: { user },
  } = await supabase.auth.getUser();

  if (user) {
    return (
      <div className="flex items-center gap-3">
        <span className="hidden text-sm text-gray-600 dark:text-gray-400 sm:inline">
          {user.email}
        </span>
        <Link
          href="/dashboard"
          className="rounded-lg bg-black px-3 py-1.5 text-sm font-medium text-white transition hover:bg-gray-800 dark:bg-white dark:text-black dark:hover:bg-gray-200"
        >
          Dashboard
        </Link>
      </div>
    );
  }

  return (
    <Link
      href="/login"
      className="rounded-lg border px-3 py-1.5 text-sm font-medium transition hover:bg-gray-50 dark:hover:bg-gray-900"
    >
      Sign In
    </Link>
  );
}
