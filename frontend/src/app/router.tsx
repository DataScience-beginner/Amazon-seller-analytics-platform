import { useCallback, useSyncExternalStore, type MouseEvent, type ReactNode } from 'react';

const routeEvent = 'selleros:navigate';

function subscribe(callback: () => void) {
  window.addEventListener('popstate', callback);
  window.addEventListener(routeEvent, callback);
  return () => {
    window.removeEventListener('popstate', callback);
    window.removeEventListener(routeEvent, callback);
  };
}

function snapshot() {
  return `${window.location.pathname}${window.location.search}`;
}

export function navigate(to: string, options: { replace?: boolean } = {}) {
  const current = snapshot();
  if (current === to) return;
  window.history[options.replace ? 'replaceState' : 'pushState']({}, '', to);
  window.dispatchEvent(new Event(routeEvent));
  window.scrollTo?.({ top: 0 });
}

export function useLocation() {
  const value = useSyncExternalStore(subscribe, snapshot, () => '/');
  const [pathname, search = ''] = value.split('?');
  return {
    pathname,
    search: search ? `?${search}` : '',
    searchParams: new URLSearchParams(search),
  };
}

export function useNavigate() {
  return useCallback((to: string, options?: { replace?: boolean }) => navigate(to, options), []);
}

export function Link({
  to,
  children,
  className,
  'aria-current': ariaCurrent,
}: {
  to: string;
  children: ReactNode;
  className?: string;
  'aria-current'?: 'page';
}) {
  function follow(event: MouseEvent<HTMLAnchorElement>) {
    if (
      event.defaultPrevented ||
      event.button !== 0 ||
      event.metaKey ||
      event.ctrlKey ||
      event.shiftKey ||
      event.altKey
    ) {
      return;
    }
    event.preventDefault();
    navigate(to);
  }

  return (
    <a href={to} onClick={follow} className={className} aria-current={ariaCurrent}>
      {children}
    </a>
  );
}
