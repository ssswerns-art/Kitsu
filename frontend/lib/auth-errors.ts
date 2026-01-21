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
    
    // Backend contract: all API errors have { error: { code, message, details } }
    const errorEnvelope = error.response?.data as {
      error?: {
        code: string;
        message: string;
        details?: unknown;
      };
    } | undefined;
    
    // If backend returned canonical error format, use it
    if (errorEnvelope?.error) {
      return {
        code: errorEnvelope.error.code,
        message: errorEnvelope.error.message,
        status,
        details: errorEnvelope.error.details,
      };
    }
    
    // Network-level errors (timeouts, connection failures)
    // These are NOT backend errors - they're Axios/network errors
    if (error.code === "ECONNABORTED") {
      return {
        code: "network_timeout",
        message: "Request timed out. Please retry.",
        status,
      };
    }
    
    if (!error.response) {
      // No response = network error
      return {
        code: "network_error",
        message: error.message || "Network error. Please check your connection.",
        status,
      };
    }
    
    // If we reach here, backend violated the contract
    // This should never happen after FIX-02A
    return {
      code: "malformed_error",
      message: "Server returned malformed error response.",
      status,
    };
  }
  
  // Already normalized ApiError
  if (error && typeof error === "object") {
    const candidate = error as ApiError;
    if (
      typeof candidate.code === "string" &&
      typeof candidate.message === "string"
    ) {
      return candidate;
    }
  }
  
  // Unexpected error type
  return {
    code: "unexpected_error",
    message: String(error) || "Unexpected error occurred.",
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

  // Backend contract: use error.code to determine auth failures
  // AUTH_ERROR = 401 (expired/invalid token)
  // PERMISSION_DENIED = 403 (revoked token or insufficient permissions)
  if (normalizedError.code === "AUTH_ERROR") {
    handleAuthFailure();
    throw normalizedError;
  }

  if (normalizedError.code === "PERMISSION_DENIED") {
    handleAuthFailure();
    throw normalizedError;
  }

  // Network or unknown auth errors are propagated without logout.
  throw normalizedError;
};
