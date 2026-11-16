'use client';

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useReducer,
  useState,
} from 'react';
import { useTracker } from './tracking-provider';

/**
 * Cart state.
 *
 * Client-side and persisted to localStorage: this is a demo store with no
 * accounts, and keeping the cart on the device avoids inventing a user identity
 * the shopper never gave us. Every mutation emits the matching event, so the
 * funnel is measured from the same action the shopper actually took.
 */

export interface CartLine {
  productId: string;
  title: string;
  price: number;
  quantity: number;
}

interface CartState {
  lines: CartLine[];
}

type CartAction =
  | { type: 'hydrate'; lines: CartLine[] }
  | { type: 'add'; line: CartLine }
  | { type: 'setQuantity'; productId: string; quantity: number }
  | { type: 'remove'; productId: string }
  | { type: 'clear' };

const STORAGE_KEY = 'cartiq.cart';
const MAX_QUANTITY = 99;

function reducer(state: CartState, action: CartAction): CartState {
  switch (action.type) {
    case 'hydrate':
      return { lines: action.lines };
    case 'add': {
      const existing = state.lines.find((l) => l.productId === action.line.productId);
      if (!existing) return { lines: [...state.lines, action.line] };
      return {
        lines: state.lines.map((line) =>
          line.productId === action.line.productId
            ? { ...line, quantity: Math.min(line.quantity + action.line.quantity, MAX_QUANTITY) }
            : line,
        ),
      };
    }
    case 'setQuantity':
      if (action.quantity <= 0) {
        return { lines: state.lines.filter((l) => l.productId !== action.productId) };
      }
      return {
        lines: state.lines.map((line) =>
          line.productId === action.productId
            ? { ...line, quantity: Math.min(action.quantity, MAX_QUANTITY) }
            : line,
        ),
      };
    case 'remove':
      return { lines: state.lines.filter((l) => l.productId !== action.productId) };
    case 'clear':
      return { lines: [] };
  }
}

export interface CartApi {
  lines: CartLine[];
  itemCount: number;
  subtotal: number;
  /** True once localStorage has been read, so the UI can avoid a flash. */
  ready: boolean;
  addItem: (line: CartLine) => void;
  setQuantity: (productId: string, quantity: number) => void;
  removeItem: (productId: string) => void;
  clear: () => void;
}

const CartContext = createContext<CartApi | null>(null);

function readStored(): CartLine[] {
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (!raw) return [];
    const parsed: unknown = JSON.parse(raw);
    if (!Array.isArray(parsed)) return [];
    // Validate rather than trust: a stale or tampered value must not render.
    return parsed.filter(
      (line): line is CartLine =>
        typeof line === 'object' &&
        line !== null &&
        typeof (line as CartLine).productId === 'string' &&
        typeof (line as CartLine).title === 'string' &&
        Number.isFinite((line as CartLine).price) &&
        Number.isInteger((line as CartLine).quantity) &&
        (line as CartLine).quantity > 0,
    );
  } catch {
    return [];
  }
}

export function CartProvider({ children }: { children: React.ReactNode }) {
  const [state, dispatch] = useReducer(reducer, { lines: [] });
  const [ready, setReady] = useState(false);
  const tracker = useTracker();

  useEffect(() => {
    dispatch({ type: 'hydrate', lines: readStored() });
    setReady(true);
  }, []);

  useEffect(() => {
    if (!ready) return;
    try {
      window.localStorage.setItem(STORAGE_KEY, JSON.stringify(state.lines));
    } catch {
      // Out of quota or blocked: the cart still works for this page view.
    }
  }, [state.lines, ready]);

  const addItem = useCallback(
    (line: CartLine) => {
      dispatch({ type: 'add', line });
      tracker.track('add_to_cart', {
        product_id: line.productId,
        price: line.price,
        quantity: line.quantity,
        properties: { title: line.title },
      });
    },
    [tracker],
  );

  const removeItem = useCallback(
    (productId: string) => {
      const line = state.lines.find((l) => l.productId === productId);
      dispatch({ type: 'remove', productId });
      if (line) {
        tracker.track('remove_from_cart', {
          product_id: productId,
          price: line.price,
          quantity: line.quantity,
        });
      }
    },
    [state.lines, tracker],
  );

  const setQuantity = useCallback(
    (productId: string, quantity: number) => {
      const line = state.lines.find((l) => l.productId === productId);
      dispatch({ type: 'setQuantity', productId, quantity });
      if (!line) return;
      // A decrease to zero is a removal, and must be measured as one.
      if (quantity <= 0) {
        tracker.track('remove_from_cart', {
          product_id: productId,
          price: line.price,
          quantity: line.quantity,
        });
      } else if (quantity > line.quantity) {
        tracker.track('add_to_cart', {
          product_id: productId,
          price: line.price,
          quantity: quantity - line.quantity,
          properties: { title: line.title, via: 'quantity_stepper' },
        });
      } else if (quantity < line.quantity) {
        tracker.track('remove_from_cart', {
          product_id: productId,
          price: line.price,
          quantity: line.quantity - quantity,
          properties: { via: 'quantity_stepper' },
        });
      }
    },
    [state.lines, tracker],
  );

  const clear = useCallback(() => dispatch({ type: 'clear' }), []);

  const value = useMemo<CartApi>(() => {
    const itemCount = state.lines.reduce((sum, line) => sum + line.quantity, 0);
    const subtotal = state.lines.reduce((sum, line) => sum + line.price * line.quantity, 0);
    return {
      lines: state.lines,
      itemCount,
      subtotal: Math.round(subtotal * 100) / 100,
      ready,
      addItem,
      setQuantity,
      removeItem,
      clear,
    };
  }, [state.lines, ready, addItem, setQuantity, removeItem, clear]);

  return <CartContext.Provider value={value}>{children}</CartContext.Provider>;
}

export function useCart(): CartApi {
  const context = useContext(CartContext);
  if (!context) throw new Error('useCart must be used inside <CartProvider>');
  return context;
}
