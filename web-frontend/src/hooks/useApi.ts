import { useEffect, useReducer, useRef } from "react";

type State<T> =
  | { status: "idle"; data: undefined; error: null }
  | { status: "loading"; data: undefined; error: null }
  | { status: "success"; data: T; error: null }
  | { status: "error"; data: undefined; error: string };

type Action<T> =
  | { type: "LOADING" }
  | { type: "SUCCESS"; data: T }
  | { type: "ERROR"; error: string };

function reducer<T>(state: State<T>, action: Action<T>): State<T> {
  switch (action.type) {
    case "LOADING": return { status: "loading", data: undefined, error: null };
    case "SUCCESS": return { status: "success", data: action.data, error: null };
    case "ERROR":   return { status: "error", data: undefined, error: action.error };
    default: return state;
  }
}

/**
 * Generic data-fetching hook.
 * Re-fetches when any value in `deps` changes.
 *
 * @example
 * const { data, status, error, refetch } = useApi(() => inventoryApi.listProducts(), []);
 */
export function useApi<T>(
  fetcher: () => Promise<T>,
  deps: React.DependencyList = []
) {
  const [state, dispatch] = useReducer(reducer as React.Reducer<State<T>, Action<T>>, {
    status: "idle",
    data: undefined,
    error: null,
  });
  const fetcherRef = useRef(fetcher);
  fetcherRef.current = fetcher;

  const run = () => {
    dispatch({ type: "LOADING" });
    fetcherRef.current()
      .then((data) => dispatch({ type: "SUCCESS", data }))
      .catch((err: unknown) => {
        const msg =
          err instanceof Error ? err.message : "Unknown error";
        dispatch({ type: "ERROR", error: msg });
      });
  };

  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(run, deps);

  return { ...state, refetch: run };
}
