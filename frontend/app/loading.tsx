/**
 * Loading Component - Pure Visual Skeleton
 * ==========================================
 * 
 * ARCHITECTURAL INVARIANTS:
 * 
 * 1. ZERO LOGIC
 *    - This component has NO business logic
 *    - This component has NO data awareness
 *    - This component is ONLY presentation layer
 * 
 * 2. ZERO DATA KNOWLEDGE
 *    - Does not know what data is loading
 *    - Does not know from where data is coming
 *    - Does not know why loading is happening
 * 
 * 3. SUSPENSE BOUNDARY
 *    - This is triggered by Suspense boundaries
 *    - Suspense controls when this is shown
 *    - This component does not control loading state
 * 
 * 4. NO IMPORTS
 *    - No query imports
 *    - No adapter imports
 *    - No API imports
 *    - Only UI primitives (Image, React)
 */

import React from "react";
import Image from "next/image";
import { assertRenderMode } from "@/lib/render-mode";

/**
 * Pure visual loading skeleton
 * 
 * CONTRACT:
 * - No props (no data awareness)
 * - No state (Suspense controls visibility)
 * - No effects (no side effects during loading)
 * - No logic (pure presentation)
 */
const Loading = () => {
  // Declare render mode - client component
  const RENDER_MODE = "client" as const;
  assertRenderMode(RENDER_MODE);
  
  return (
    <div className="h-screen w-screen flex items-center justify-center">
      <div className="h-[10.25rem] w-auto">
        <Image
          src="/loader.gif"
          height={100}
          width={100}
          unoptimized
          priority
          alt="loader"
          className="h-full w-full object-cover"
          suppressHydrationWarning
        />
      </div>
    </div>
  );
};

export default Loading;
