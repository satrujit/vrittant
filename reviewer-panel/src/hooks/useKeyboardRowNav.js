import { useCallback, useRef, useState } from 'react';

const TYPING_TAGS = new Set(['INPUT', 'TEXTAREA', 'SELECT']);

export function useKeyboardRowNav({ rowCount, onOpen, onCycleStatus }) {
  const [focusedIndex, setFocusedIndexState] = useState(-1);
  const focusedRef = useRef(-1);

  const setFocusedIndex = useCallback((next) => {
    if (typeof next === 'function') {
      setFocusedIndexState((prev) => {
        const v = next(prev);
        focusedRef.current = v;
        return v;
      });
    } else {
      focusedRef.current = next;
      setFocusedIndexState(next);
    }
  }, []);

  const handleKeyDown = useCallback((e) => {
    const tag = e.target?.tagName;
    if (TYPING_TAGS.has(tag) || e.target?.isContentEditable) return;

    const down   = e.key === 'ArrowDown' || e.key === 'j';
    const up     = e.key === 'ArrowUp'   || e.key === 'k';
    const open   = e.key === 'Enter';
    const cycle  = e.key === 's' || e.key === 'S';
    const escape = e.key === 'Escape';

    if (!(down || up || open || cycle || escape)) return;
    e.preventDefault();

    if (down) {
      setFocusedIndex((i) => Math.min(rowCount - 1, i + 1 < 0 ? 0 : i + 1));
      return;
    }
    if (up) {
      setFocusedIndex((i) => Math.max(0, i - 1));
      return;
    }
    if (escape) {
      setFocusedIndex(-1);
      return;
    }
    const current = focusedRef.current;
    if (open && current >= 0) {
      onOpen?.(current);
      return;
    }
    if (cycle && current >= 0) {
      onCycleStatus?.(current);
    }
  }, [rowCount, onOpen, onCycleStatus, setFocusedIndex]);

  return { focusedIndex, setFocusedIndex, handleKeyDown };
}
