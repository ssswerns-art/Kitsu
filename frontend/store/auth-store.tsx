import {
  createContext,
  type ReactNode,
  useContext,
  useEffect,
  useRef,
  useState,
} from "react";
import { useStore } from "zustand";
import { type StoreApi, createStore } from "zustand/vanilla";
import { createJSONStorage, persist } from "zustand/middleware";

export type IAuth = {
  id?: string;
  avatar?: string;
  email?: string;
  username?: string;
  collectionId?: string;
  collectionName?: string;
  autoSkip?: boolean;
  accessToken: string;
  refreshToken: string;
};

export interface IAuthStore {
  auth: IAuth | null;
  setAuth: (state: IAuth) => void;
  clearAuth: () => void;
  isRefreshing: boolean;
  setIsRefreshing: (val: boolean) => void;
}

type AuthState = Pick<IAuthStore, "auth" | "isRefreshing">;
type AuthStoreApi = StoreApi<IAuthStore> & {
  persist?: {
    hasHydrated: () => boolean;
    onFinishHydration: (callback: () => void) => () => void;
  };
};

const defaultState: AuthState = {
  auth: null,
  isRefreshing: false,
};

const resolveStorage = () => {
  if (typeof document !== "undefined" && "localStorage" in globalThis) {
    return globalThis.localStorage;
  }
  return {
    getItem: (key: string) => {
      void key;
      return null;
    },
    setItem: (key: string, value: string) => {
      void key;
      void value;
      return undefined;
    },
    removeItem: (key: string) => {
      void key;
      return undefined;
    },
  };
};

const createAuthStore = (initState: AuthState = defaultState) => {
  const store = createStore<IAuthStore>()(
    persist(
      (set) => ({
        ...defaultState,
        ...initState,
        setAuth: (state: IAuth) => set({ auth: state }),
        clearAuth: () => set({ auth: null }),
        setIsRefreshing: (val: boolean) => set({ isRefreshing: val }),
      }),
      {
        name: "auth",
        partialize: (state) => ({
          auth: state.auth,
        }),
        version: 0,
        storage: createJSONStorage(() => resolveStorage()),
      },
    ),
  ) as AuthStoreApi;

  return store;
};

let clientStore: AuthStoreApi | null = null;

const getIsServer = () => typeof document === "undefined";

export const getAuthStore = (initState?: AuthState) => {
  if (getIsServer()) {
    return createAuthStore({ ...defaultState, ...initState });
  }
  if (!clientStore) {
    clientStore = createAuthStore({ ...defaultState, ...initState });
  } else if (initState) {
    clientStore.setState(
      {
        ...clientStore.getState(),
        ...initState,
      },
      true,
    );
  }
  return clientStore;
};

const AuthStoreContext = createContext<AuthStoreApi | null>(null);

export const AuthStoreProvider = ({
  children,
  initialState,
}: {
  children: ReactNode;
  initialState?: AuthState;
}) => {
  const storeRef = useRef<AuthStoreApi>();
  if (!storeRef.current) {
    storeRef.current = getAuthStore(initialState);
  }
  return (
    <AuthStoreContext.Provider value={storeRef.current}>
      {children}
    </AuthStoreContext.Provider>
  );
};

const useAuthStoreApi = () => {
  const store = useContext(AuthStoreContext);
  if (!store) {
    throw new Error("AuthStoreProvider is missing in the component tree.");
  }
  return store;
};

export const useAuthSelector = <T,>(selector: (state: IAuthStore) => T) => {
  const store = useAuthStoreApi();
  return useStore(store, selector);
};

export const useAuthHydrated = () => {
  const store = useAuthStoreApi();
  const [hydrated, setHydrated] = useState(
    store.persist?.hasHydrated?.() ?? false,
  );

  useEffect(() => {
    if (hydrated) return;
    const unsub = store.persist?.onFinishHydration?.(() => setHydrated(true));
    return () => unsub?.();
  }, [store, hydrated]);

  return hydrated;
};
