const DATABASE_NAME = "olivar-vision-web";
const DATABASE_VERSION = 1;
const SESSION_STORE = "sessions";

export async function openSessionDatabase(indexedDBFactory = globalThis.indexedDB) {
  if (!indexedDBFactory) throw new Error("IndexedDB no esta disponible en este navegador.");
  return new Promise((resolve, reject) => {
    const request = indexedDBFactory.open(DATABASE_NAME, DATABASE_VERSION);
    request.onupgradeneeded = () => {
      const database = request.result;
      if (!database.objectStoreNames.contains(SESSION_STORE)) {
        const store = database.createObjectStore(SESSION_STORE, { keyPath: "session_id" });
        store.createIndex("created_at", "created_at");
        store.createIndex("repeat_group_id", "repeat_group_id");
      }
    };
    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error ?? new Error("No se pudo abrir IndexedDB."));
  });
}

export async function createStoredSession(database, session) {
  return transactionRequest(database, "readwrite", (store) => store.add(session));
}

export async function updateStoredSession(database, session) {
  const existing = await getStoredSession(database, session.session_id);
  if (!existing) throw new Error("La sesion no existe.");
  if (existing.status === "complete" && JSON.stringify(existing) !== JSON.stringify(session)) {
    throw new Error("Una sesion finalizada no se puede sobrescribir.");
  }
  return transactionRequest(database, "readwrite", (store) => store.put(session));
}

export async function getStoredSession(database, sessionID) {
  return transactionRequest(database, "readonly", (store) => store.get(sessionID));
}

export async function listStoredSessions(database) {
  const sessions = await transactionRequest(database, "readonly", (store) => store.getAll());
  return sessions.sort((left, right) => right.created_at.localeCompare(left.created_at));
}

function transactionRequest(database, mode, operation) {
  return new Promise((resolve, reject) => {
    const transaction = database.transaction(SESSION_STORE, mode);
    const request = operation(transaction.objectStore(SESSION_STORE));
    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error ?? new Error("Fallo de almacenamiento local."));
    transaction.onabort = () => reject(transaction.error ?? new Error("Transaccion cancelada."));
  });
}
