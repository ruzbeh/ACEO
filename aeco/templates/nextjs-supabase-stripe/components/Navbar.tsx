import Link from "next/link";
import { AuthButton } from "./AuthButton";

export function Navbar() {
  return (
    <header className="sticky top-0 z-50 w-full border-b bg-white/80 backdrop-blur-sm dark:bg-[#0a0a0a]/80">
      <nav className="mx-auto flex h-14 max-w-5xl items-center justify-between px-4">
        <Link href="/" className="text-lg font-bold">
          {"{{PROJECT_NAME}}"}
        </Link>
        <AuthButton />
      </nav>
    </header>
  );
}
