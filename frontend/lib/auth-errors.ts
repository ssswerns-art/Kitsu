import { AxiosError } from "axios";
import { ROUTES } from "@/constants/routes";
import { getAuthStore } from "@/store/auth-store";

export type ApiError = {
  code: string;
  message: string;
  status?: number;
  details?: unknown;
};

export const normalizeApiError = (error: unknown): ApiError => {
  if (error instanceof AxiosError) {
    const status = error.response?.status;
    const payload = error.response?.data as {
      code?: string;
      message?: string;
      details?: unknown;
    } | undefined;
    const baseMessage =
      typeof payload?.message === "string"
        ? payload.message
        : error.message || "Request failed. Please try again.";
    if (status === 401) {
      return {
        code: payload?.code || "unauthorized",
        message: payload?.message || "Session expired. Please sign in again.",
        details: payload?.details,
        status,
      };
    }
    if (status === 403) {
      return {
        code: payload?.code || "forbidden",
        message: payload?.message || "Access denied.",
        details: payload?.details,
        status,
      };
    }
    if (status && status >= 500) {
      return {
        code: payload?.code || "server_error",
        message:
          payload?.message ||
          "Something went wrong on our side. Please try again.",
        details: payload?.details,
        status,
      };
    }
    if (error.code === "ECONNABORTED") {
      return {
        code: "timeout",
        message: "Request timed out. Please retry.",
        status,
        details: payload?.details,
      };
    }
    return {
      code: payload?.code || "request_failed",
      message: baseMessage,
      status,
      details: payload?.details,
    };
  }
  if (error && typeof error === "object") {
    const candidate = error as ApiError;
    if (
      typeof candidate.code === "string" &&
      typeof candidate.message === "string" &&
      (candidate.status === undefined || typeof candidate.status === "number")
    ) {
      return {
        code: candidate.code,
        message: candidate.message,
        status: candidate.status,
        details: candidate.details,
      };
    }
  }
  return {
    code: "unknown_error",
    message: "Unexpected error occurred.",
  };
};

type AuthFailureState = {
  authFailureHandlers: Set<(redirectTo: string) => void>;
  authFailureCommitted: boolean;
};

const createAuthFailureState = (): AuthFailureState => ({
  authFailureHandlers: new Set<(redirectTo: string) => void>(),
  authFailureCommitted: false,
});

const getIsServer = () => typeof document === "undefined";

let clientAuthFailureState: AuthFailureState | null = null;

const getAuthFailureState = (): AuthFailureState => {
  if (getIsServer()) {
    return createAuthFailureState();
  }
  if (!clientAuthFailureState) {
    clientAuthFailureState = createAuthFailureState();
  }
  return clientAuthFailureState;
};

export const setAuthFailureHandler = (handler: (redirectTo: string) => void) => {
  const state = getAuthFailureState();
  state.authFailureHandlers.add(handler);
  return () => {
    state.authFailureHandlers.delete(handler);
  };
};

const navigateHome = () => {
  if (typeof window === "undefined" || window.location.pathname === ROUTES.HOME) {
    return;
  }
  window.location.replace(ROUTES.HOME);
};

const handleAuthFailure = () => {
  const state = getAuthFailureState();
  if (state.authFailureCommitted) {
    return;
  }
  state.authFailureCommitted = true;
  getAuthStore().getState().clearAuth();
  if (state.authFailureHandlers.size > 0) {
    state.authFailureHandlers.forEach((handler) => handler(ROUTES.HOME));
    return;
  }
  navigateHome();
};

// Always throws a normalized auth error; logout decisions are centralized here.
export const handleAuthError = (error: unknown): never => {
  const normalizedError = normalizeApiError(error);

  if (normalizedError.status === 401) {
    handleAuthFailure();
    throw normalizedError;
  }

  if (normalizedError.status === 403) {
    handleAuthFailure();
    throw normalizedError;
  }

  // Network or unknown auth errors are propagated without logout.
  throw normalizedError;
};
