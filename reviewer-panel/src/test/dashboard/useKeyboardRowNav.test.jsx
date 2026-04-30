import { describe, it, expect, vi } from 'vitest';
import { renderHook, act } from '@testing-library/react';
import { useKeyboardRowNav } from '../../hooks/useKeyboardRowNav';

const mkEvent = (key) => ({ key, preventDefault: vi.fn(), target: { tagName: 'BODY' } });

describe('useKeyboardRowNav', () => {
  it('starts with no focused row', () => {
    const { result } = renderHook(() => useKeyboardRowNav({ rowCount: 5 }));
    expect(result.current.focusedIndex).toBe(-1);
  });

  it('ArrowDown moves focus down and clamps at last row', () => {
    const { result } = renderHook(() => useKeyboardRowNav({ rowCount: 3 }));
    act(() => result.current.handleKeyDown(mkEvent('ArrowDown')));
    expect(result.current.focusedIndex).toBe(0);
    act(() => result.current.handleKeyDown(mkEvent('ArrowDown')));
    act(() => result.current.handleKeyDown(mkEvent('ArrowDown')));
    act(() => result.current.handleKeyDown(mkEvent('ArrowDown')));
    expect(result.current.focusedIndex).toBe(2);
  });

  it('j and k mirror arrow keys', () => {
    const { result } = renderHook(() => useKeyboardRowNav({ rowCount: 3 }));
    act(() => result.current.handleKeyDown(mkEvent('j')));
    expect(result.current.focusedIndex).toBe(0);
    act(() => result.current.handleKeyDown(mkEvent('j')));
    expect(result.current.focusedIndex).toBe(1);
    act(() => result.current.handleKeyDown(mkEvent('k')));
    expect(result.current.focusedIndex).toBe(0);
  });

  it('Enter calls onOpen with the focused index', () => {
    const onOpen = vi.fn();
    const { result } = renderHook(() => useKeyboardRowNav({ rowCount: 3, onOpen }));
    act(() => result.current.handleKeyDown(mkEvent('ArrowDown')));
    act(() => result.current.handleKeyDown(mkEvent('Enter')));
    expect(onOpen).toHaveBeenCalledWith(0);
  });

  it('S calls onCycleStatus with the focused index', () => {
    const onCycleStatus = vi.fn();
    const { result } = renderHook(() => useKeyboardRowNav({ rowCount: 3, onCycleStatus }));
    act(() => result.current.handleKeyDown(mkEvent('ArrowDown')));
    act(() => result.current.handleKeyDown(mkEvent('s')));
    expect(onCycleStatus).toHaveBeenCalledWith(0);
  });

  it('ignores keys when typing in an input', () => {
    const onOpen = vi.fn();
    const { result } = renderHook(() => useKeyboardRowNav({ rowCount: 3, onOpen }));
    const e = { key: 'Enter', preventDefault: vi.fn(), target: { tagName: 'INPUT' } };
    act(() => result.current.handleKeyDown(e));
    expect(onOpen).not.toHaveBeenCalled();
  });

  it('Escape clears the focused row', () => {
    const { result } = renderHook(() => useKeyboardRowNav({ rowCount: 3 }));
    act(() => result.current.handleKeyDown(mkEvent('ArrowDown')));
    act(() => result.current.handleKeyDown(mkEvent('ArrowDown')));
    expect(result.current.focusedIndex).toBe(1);
    act(() => result.current.handleKeyDown(mkEvent('Escape')));
    expect(result.current.focusedIndex).toBe(-1);
  });

  it('clamps focusedIndex when rowCount shrinks', () => {
    const { result, rerender } = renderHook(({ rowCount }) => useKeyboardRowNav({ rowCount }), {
      initialProps: { rowCount: 5 },
    });
    act(() => result.current.handleKeyDown(mkEvent('ArrowDown')));
    act(() => result.current.handleKeyDown(mkEvent('ArrowDown')));
    act(() => result.current.handleKeyDown(mkEvent('ArrowDown')));
    expect(result.current.focusedIndex).toBe(2);
    rerender({ rowCount: 2 });
    expect(result.current.focusedIndex).toBe(1);
    rerender({ rowCount: 0 });
    expect(result.current.focusedIndex).toBe(-1);
  });
});
