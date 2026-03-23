"""Auth tools — generate Supabase auth boilerplate files in a workspace."""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from aeco.config import settings

logger = logging.getLogger(__name__)


def _resolve(relative_path: str, workspace_path: str | None = None) -> Path:
    ws = Path(workspace_path or settings.workspace_path).expanduser().resolve()
    target = (ws / relative_path).resolve()
    if not str(target).startswith(str(ws)):
        raise ValueError("Path escapes workspace directory")
    return target


async def auth_setup_supabase(workspace_path: str | None = None) -> dict[str, Any]:
    """Configure Supabase auth files in a Next.js project.

    Writes lib/supabase/client.ts, lib/supabase/server.ts, and middleware.ts.
    """
    files_written: list[str] = []

    # Client helper
    client_path = _resolve("lib/supabase/client.ts", workspace_path)
    client_path.parent.mkdir(parents=True, exist_ok=True)
    client_path.write_text(
        '''"use client";\n\nimport { createBrowserClient } from "@supabase/ssr";\n\nexport function createClient() {\n  return createBrowserClient(\n    process.env.NEXT_PUBLIC_SUPABASE_URL!,\n    process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!\n  );\n}\n''',
        encoding="utf-8",
    )
    files_written.append("lib/supabase/client.ts")

    # Server helper
    server_path = _resolve("lib/supabase/server.ts", workspace_path)
    server_path.parent.mkdir(parents=True, exist_ok=True)
    server_path.write_text(
        '''import { createServerClient } from "@supabase/ssr";\nimport { cookies } from "next/headers";\n\nexport async function createClient() {\n  const cookieStore = await cookies();\n  return createServerClient(\n    process.env.NEXT_PUBLIC_SUPABASE_URL!,\n    process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!,\n    {\n      cookies: {\n        getAll() {\n          return cookieStore.getAll();\n        },\n        setAll(cookiesToSet) {\n          try {\n            cookiesToSet.forEach(({ name, value, options }) =>\n              cookieStore.set(name, value, options)\n            );\n          } catch {\n            // Server component — can\'t set cookies\n          }\n        },\n      },\n    }\n  );\n}\n''',
        encoding="utf-8",
    )
    files_written.append("lib/supabase/server.ts")

    logger.info(f"Supabase auth setup: wrote {files_written}")
    return {
        "status": "ok",
        "files_written": files_written,
        "note": "Ensure NEXT_PUBLIC_SUPABASE_URL and NEXT_PUBLIC_SUPABASE_ANON_KEY are set in .env.local",
    }


async def auth_add_provider(
    provider: str = "google",
    workspace_path: str | None = None,
) -> dict[str, Any]:
    """Add an OAuth provider component to the project.

    Args:
        provider: OAuth provider name (google, github, apple)
    """
    provider_lower = provider.lower()
    provider_title = provider.capitalize()

    component_path = _resolve(f"components/{provider_title}OAuthButton.tsx", workspace_path)
    component_path.parent.mkdir(parents=True, exist_ok=True)
    component_path.write_text(
        f'''"use client";\n\nimport {{ createClient }} from "@/lib/supabase/client";\n\nexport default function {provider_title}OAuthButton() {{\n  const handleLogin = async () => {{\n    const supabase = createClient();\n    await supabase.auth.signInWithOAuth({{\n      provider: "{provider_lower}",\n      options: {{\n        redirectTo: `${{window.location.origin}}/auth/callback`,\n      }},\n    }});\n  }};\n\n  return (\n    <button\n      onClick={{handleLogin}}\n      className="w-full flex items-center justify-center gap-2 rounded-lg border border-gray-300 bg-white px-4 py-2.5 text-sm font-medium text-gray-700 hover:bg-gray-50 transition"\n    >\n      Continue with {provider_title}\n    </button>\n  );\n}}\n''',
        encoding="utf-8",
    )

    logger.info(f"Added {provider_title} OAuth button component")
    return {
        "status": "ok",
        "provider": provider_lower,
        "files_written": [f"components/{provider_title}OAuthButton.tsx"],
        "note": f"Configure {provider_title} OAuth in your Supabase dashboard under Authentication > Providers",
    }


async def auth_generate_middleware(workspace_path: str | None = None) -> dict[str, Any]:
    """Generate Next.js middleware for Supabase auth session refresh and route protection."""
    middleware_path = _resolve("middleware.ts", workspace_path)
    middleware_path.parent.mkdir(parents=True, exist_ok=True)
    middleware_path.write_text(
        '''import { createServerClient } from "@supabase/ssr";\nimport { NextResponse, type NextRequest } from "next/server";\n\nexport async function middleware(request: NextRequest) {\n  let supabaseResponse = NextResponse.next({ request });\n\n  const supabase = createServerClient(\n    process.env.NEXT_PUBLIC_SUPABASE_URL!,\n    process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!,\n    {\n      cookies: {\n        getAll() {\n          return request.cookies.getAll();\n        },\n        setAll(cookiesToSet) {\n          cookiesToSet.forEach(({ name, value, options }) =>\n            request.cookies.set(name, value)\n          );\n          supabaseResponse = NextResponse.next({ request });\n          cookiesToSet.forEach(({ name, value, options }) =>\n            supabaseResponse.cookies.set(name, value, options)\n          );\n        },\n      },\n    }\n  );\n\n  const {\n    data: { user },\n  } = await supabase.auth.getUser();\n\n  // Protect dashboard routes\n  if (!user && request.nextUrl.pathname.startsWith("/dashboard")) {\n    const url = request.nextUrl.clone();\n    url.pathname = "/login";\n    return NextResponse.redirect(url);\n  }\n\n  return supabaseResponse;\n}\n\nexport const config = {\n  matcher: [\n    "/((?!_next/static|_next/image|favicon.ico|.*\\\\.(?:svg|png|jpg|jpeg|gif|webp)$).*)",\n  ],\n};\n''',
        encoding="utf-8",
    )

    logger.info("Generated auth middleware")
    return {
        "status": "ok",
        "files_written": ["middleware.ts"],
        "protected_routes": ["/dashboard"],
    }
