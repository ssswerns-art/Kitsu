import axios, {
  AxiosError,
  AxiosHeaders,
  InternalAxiosRequestConfig,
  type AxiosInstance,
} from "axios";
import { env } from "next-runtime-env";
import {
  handleAuthError,
  normalizeApiError,
  setAuthFailureHandler,
} from "./auth-errors";
import { getAuthStore } from "@/store/auth-store";

const envBaseUrl =
  (env("NEXT_PUBLIC_API_BASE_URL") || env("NEXT_PUBLIC_API_URL") || "").trim();

const fallbackBaseUrl = "http://localhost:8000";

if (!envBaseUrl) {
  // eslint-disable-next-line no-console
  console.warn(
    "NEXT_PUBLIC_API_BASE_URL is not set; falling back to http://localhost:8000",
  );
}

const baseURL = envBaseUrl || fallbackBaseUrl;

type RefreshTokensResponse = { accessToken: string; refreshToken: string };

type RetriableRequestConfig = InternalAxiosRequestConfig & { _retry?: boolean };

export const createApiClient = (): AxiosInstance => {
  const apiClient = axios.create({
    baseURL,
    timeout: 10000,
  });

  const refreshClient = axios.create({
    baseURL,
    timeout: 10000,
  });

  let refreshPromise: Promise<RefreshTokensResponse> | null = null;

  const refreshTokens = (
    refreshToken: string,
    authStore = getAuthStore(),
  ) => {
    if (!refreshPromise) {
      refreshPromise = refreshClient
        .post("/auth/refresh", {
          refresh_token: refreshToken,
        })
        .then((refreshResponse) => {
          const tokens = refreshResponse.data as {
            access_token?: string;
            refresh_token?: string;
          };
          const accessToken = tokens.access_token;
          const newRefreshToken = tokens.refresh_token;

          if (!accessToken) {
            throw new Error("Missing access token in refresh response");
          }

          if (!newRefreshToken) {
            throw new Error("Missing refresh token in refresh response");
          }

          const currentAuth = authStore.getState().auth;
          authStore.getState().setAuth({
            ...(currentAuth ?? {}),
            accessToken,
            refreshToken: newRefreshToken,
          });

          return { accessToken, refreshToken: newRefreshToken };
        })
        .finally(() => {
          refreshPromise = null;
        });
    }

    return refreshPromise;
  };

  apiClient.interceptors.request.use((config: InternalAxiosRequestConfig) => {
    const token = getAuthStore().getState().auth?.accessToken;
    if (token) {
      // eslint-disable-next-line no-param-reassign
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  });

  apiClient.interceptors.response.use(
    (response) => response,
    async (error: AxiosError) => {
      const config = error.config as RetriableRequestConfig | undefined;
      const isRefreshRequest = config?.url?.includes("/auth/refresh");

      // Normalize the error to extract the backend error code
      const normalizedError = normalizeApiError(error);

      // Backend contract: use error.code to determine action
      // PERMISSION_DENIED (403) means token is revoked - logout immediately
      if (normalizedError.code === "PERMISSION_DENIED") {
        return handleAuthError(error);
      }

      // AUTH_ERROR (401) means token expired - try refresh once
      if (normalizedError.code === "AUTH_ERROR" && config && !config._retry && !isRefreshRequest) {
        const authStore = getAuthStore();
        const refreshToken = authStore.getState().auth?.refreshToken;

        if (!refreshToken) {
          return handleAuthError(error);
        }

        config._retry = true;
        try {
          const tokens = await refreshTokens(refreshToken, authStore);
          const accessToken = tokens.accessToken;

          const headers =
            config.headers instanceof AxiosHeaders
              ? config.headers
              : new AxiosHeaders(config.headers ?? undefined);

          headers.set("Authorization", `Bearer ${accessToken}`);
          config.headers = headers;
          return apiClient(config);
        } catch (refreshError) {
          const normalizedRefreshError =
            refreshError instanceof AxiosError
              ? normalizeApiError(refreshError)
              : refreshError;
          return handleAuthError(normalizedRefreshError);
        }
      }

      return handleAuthError(error);
    },
  );

  return apiClient;
};

let clientApi: AxiosInstance | null = null;

export const getClientApi = (): AxiosInstance => {
  if (!clientApi) {
    clientApi = createApiClient();
  }
  return clientApi;
};

export const getServerApi = (): AxiosInstance => createApiClient();

const isBrowser = typeof window !== "undefined";

export const api = (isBrowser ? getClientApi() : undefined) as AxiosInstance;

export { setAuthFailureHandler };
