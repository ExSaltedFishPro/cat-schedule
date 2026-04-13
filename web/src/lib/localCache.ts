type CacheEnvelope<T> = {
  savedAt: number;
  data: T;
};

export type CacheReadResult<T> = {
  data: T;
  savedAt: number;
  stale: boolean;
};

function getStorage() {
  if (typeof window === "undefined") {
    return null;
  }
  return window.localStorage;
}

export function readCache<T>(key: string, maxAgeMs: number): CacheReadResult<T> | null {
  const storage = getStorage();
  if (!storage) {
    return null;
  }

  try {
    const raw = storage.getItem(key);
    if (!raw) {
      return null;
    }
    const parsed = JSON.parse(raw) as CacheEnvelope<T>;
    if (!parsed || typeof parsed.savedAt !== "number" || parsed.data === undefined) {
      storage.removeItem(key);
      return null;
    }
    return {
      data: parsed.data,
      savedAt: parsed.savedAt,
      stale: Date.now() - parsed.savedAt > maxAgeMs
    };
  } catch {
    storage.removeItem(key);
    return null;
  }
}

export function writeCache<T>(key: string, data: T): void {
  const storage = getStorage();
  if (!storage) {
    return;
  }

  try {
    const envelope: CacheEnvelope<T> = {
      savedAt: Date.now(),
      data
    };
    storage.setItem(key, JSON.stringify(envelope));
  } catch {
    // 忽略本地存储失败，不影响主流程
  }
}

export function removeCache(key: string): void {
  const storage = getStorage();
  if (!storage) {
    return;
  }

  try {
    storage.removeItem(key);
  } catch {
    // 忽略本地存储失败
  }
}
