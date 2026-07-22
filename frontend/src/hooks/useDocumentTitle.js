import { useEffect } from 'react';

/** Sets document.title for the current page, restores the previous title on unmount. */
export function useDocumentTitle(title) {
  useEffect(() => {
    const previous = document.title;
    document.title = title ? `${title} — ClauseGuard` : 'ClauseGuard';
    return () => {
      document.title = previous;
    };
  }, [title]);
}
