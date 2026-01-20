"use client";

import { useEffect } from "react";
import Link from "next/link";
import { ROUTES } from "@/constants/routes";
import { Button } from "@/components/ui/button";
import {
  getErrorHandlingStrategy,
  logErrorByPolicy,
  getUserFriendlyErrorMessage,
} from "@/lib/error-boundary-policy";
import { assertRenderMode } from "@/lib/render-mode";

export default function GlobalError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  // Declare render mode - client component
  const RENDER_MODE = "client" as const;
  assertRenderMode(RENDER_MODE);
  
  useEffect(() => {
    // Use error handling policy to determine logging strategy
    const strategy = getErrorHandlingStrategy(error);
    logErrorByPolicy(error, strategy);
  }, [error]);

  // Get user-friendly error message from policy
  const errorMessage = getUserFriendlyErrorMessage(error);

  return (
    <html>
      <body className="min-h-screen bg-[#0b0b0f] text-white">
        <div className="flex min-h-screen flex-col items-center justify-center gap-4 px-6 text-center">
          <h2 className="text-2xl font-semibold">Something went wrong</h2>
          <p className="max-w-md text-sm text-slate-300">
            {errorMessage}
          </p>
          <div className="flex gap-3">
            <Button onClick={reset}>Try again</Button>
            <Button variant="secondary" asChild>
              <Link href={ROUTES.HOME}>Go home</Link>
            </Button>
          </div>
        </div>
      </body>
    </html>
  );
}
