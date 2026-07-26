import { useCallback, useEffect, useState } from 'react';

type AsyncState<T> =
  | { status: 'loading'; data: null; error: null }
  | { status: 'success'; data: T; error: null }
  | { status: 'error'; data: null; error: Error };

export function useAsync<T>(load: (signal: AbortSignal) => Promise<T>) {
  const [attempt, setAttempt] = useState(0);
  const [state, setState] = useState<AsyncState<T>>({
    status: 'loading',
    data: null,
    error: null,
  });

  useEffect(() => {
    const controller = new AbortController();
    setState({ status: 'loading', data: null, error: null });
    load(controller.signal).then(
      (data) => {
        if (!controller.signal.aborted) setState({ status: 'success', data, error: null });
      },
      (caught: unknown) => {
        if (!controller.signal.aborted) {
          setState({
            status: 'error',
            data: null,
            error: caught instanceof Error ? caught : new Error('Something went wrong'),
          });
        }
      },
    );
    return () => controller.abort();
  }, [load, attempt]);

  const retry = useCallback(() => setAttempt((value) => value + 1), []);
  return { ...state, retry };
}
