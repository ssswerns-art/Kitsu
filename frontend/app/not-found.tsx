import Link from "next/link";
import { ROUTES } from "@/constants/routes";
import { Button } from "@/components/ui/button";
import { assertRenderMode } from "@/lib/render-mode";

/**
 * Pure visual not found page
 * 
 * CONTRACT:
 * - No props (no data awareness)
 * - No state (static page)
 * - No effects (no side effects)
 * - No logic (pure presentation)
 */
export default function NotFound() {
  // Declare render mode - server component
  const RENDER_MODE = "server" as const;
  assertRenderMode(RENDER_MODE);
  
  return (
    <div className="min-h-screen bg-[#0b0b0f] text-white">
      <div className="flex min-h-screen flex-col items-center justify-center gap-4 px-6 text-center">
        <h1 className="text-6xl font-bold">404</h1>
        <h2 className="text-2xl font-semibold">Page Not Found</h2>
        <p className="max-w-md text-sm text-slate-300">
          The page you are looking for does not exist or has been moved.
        </p>
        <Button asChild>
          <Link href={ROUTES.HOME}>Return Home</Link>
        </Button>
      </div>
    </div>
  );
}
