"use client";

import { createContext, useContext, type ReactNode } from "react";

type HydrationTimestampContextValue = string | null;

const HydrationTimestampContext =
  createContext<HydrationTimestampContextValue>(null);

type HydrationTimestampProviderProps = {
  initialTimestamp: string;
  children: ReactNode;
};

export const HydrationTimestampProvider = ({
  initialTimestamp,
  children,
}: HydrationTimestampProviderProps) => {
  return (
    <HydrationTimestampContext.Provider value={initialTimestamp}>
      {children}
    </HydrationTimestampContext.Provider>
  );
};

export const useHydrationTimestamp = () =>
  useContext(HydrationTimestampContext);
