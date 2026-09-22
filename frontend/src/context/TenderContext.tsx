import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from "react";

import { listTenders } from "../api/tenders";
import type { Tender } from "../api/types";

interface TenderContextValue {
  tenders: Tender[];
  selectedTenderId: number | null;
  selectedTender: Tender | null;
  selectTender: (id: number) => void;
  refreshTenders: () => Promise<void>;
}

const TenderContext = createContext<TenderContextValue | undefined>(undefined);

const STORAGE_KEY = "bid-co-author:selected-tender-id";

export function TenderProvider({ children }: { children: ReactNode }) {
  const [tenders, setTenders] = useState<Tender[]>([]);
  const [selectedTenderId, setSelectedTenderId] = useState<number | null>(() => {
    const stored = localStorage.getItem(STORAGE_KEY);
    return stored ? Number(stored) : null;
  });

  const refreshTenders = useCallback(async () => {
    const result = await listTenders();
    setTenders(result);
    // If nothing is selected yet (or the selection no longer exists), default to the first tender.
    setSelectedTenderId((current) => {
      if (current !== null && result.some((t) => t.id === current)) {
        return current;
      }
      return result.length > 0 ? result[0].id : null;
    });
  }, []);

  useEffect(() => {
    refreshTenders().catch(() => {
      // The API may not be reachable yet (backend not started) — the layout surfaces a clear
      // "no tenders" / connection state instead of crashing the app.
    });
  }, [refreshTenders]);

  useEffect(() => {
    if (selectedTenderId !== null) {
      localStorage.setItem(STORAGE_KEY, String(selectedTenderId));
    }
  }, [selectedTenderId]);

  const selectedTender = tenders.find((t) => t.id === selectedTenderId) ?? null;

  return (
    <TenderContext.Provider
      value={{
        tenders,
        selectedTenderId,
        selectedTender,
        selectTender: setSelectedTenderId,
        refreshTenders,
      }}
    >
      {children}
    </TenderContext.Provider>
  );
}

export function useTender() {
  const context = useContext(TenderContext);
  if (!context) {
    throw new Error("useTender must be used within a TenderProvider");
  }
  return context;
}
