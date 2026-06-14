// db.js — IndexedDB wrapper for meetings, transcripts, and audio blobs.
// Used by background (via dynamic import) and dashboard.

const DB_NAME = "echo-db";
const DB_VERSION = 1;

function openDB() {
  return new Promise((resolve, reject) => {
    const req = indexedDB.open(DB_NAME, DB_VERSION);
    req.onupgradeneeded = (e) => {
      const db = e.target.result;
      if (!db.objectStoreNames.contains("meetings")) {
        const s = db.createObjectStore("meetings", { keyPath: "id" });
        s.createIndex("startedAt", "startedAt");
        s.createIndex("status", "status");
      }
      if (!db.objectStoreNames.contains("audio")) {
        db.createObjectStore("audio", { keyPath: "id" }); // id === meeting id
      }
    };
    req.onsuccess = () => resolve(req.result);
    req.onerror = () => reject(req.error);
  });
}

function tx(db, store, mode) {
  return db.transaction(store, mode).objectStore(store);
}

export async function createMeeting(meeting) {
  const db = await openDB();
  return new Promise((resolve, reject) => {
    const r = tx(db, "meetings", "readwrite").put(meeting);
    r.onsuccess = () => resolve(meeting);
    r.onerror = () => reject(r.error);
  });
}

export async function updateMeeting(id, patch) {
  const db = await openDB();
  return new Promise((resolve, reject) => {
    const store = tx(db, "meetings", "readwrite");
    const g = store.get(id);
    g.onsuccess = () => {
      const m = g.result;
      if (!m) return reject(new Error("meeting not found: " + id));
      Object.assign(m, patch);
      const p = store.put(m);
      p.onsuccess = () => resolve(m);
      p.onerror = () => reject(p.error);
    };
    g.onerror = () => reject(g.error);
  });
}

// Append a transcript segment {speaker, text, ts, isFinal} to a meeting.
export async function appendSegment(id, segment) {
  const db = await openDB();
  return new Promise((resolve, reject) => {
    const store = tx(db, "meetings", "readwrite");
    const g = store.get(id);
    g.onsuccess = () => {
      const m = g.result;
      if (!m) return reject(new Error("meeting not found: " + id));
      m.segments = m.segments || [];
      m.segments.push(segment);
      const p = store.put(m);
      p.onsuccess = () => resolve(m);
      p.onerror = () => reject(p.error);
    };
    g.onerror = () => reject(g.error);
  });
}

export async function getMeeting(id) {
  const db = await openDB();
  return new Promise((resolve, reject) => {
    const r = tx(db, "meetings", "readonly").get(id);
    r.onsuccess = () => resolve(r.result);
    r.onerror = () => reject(r.error);
  });
}

export async function listMeetings() {
  const db = await openDB();
  return new Promise((resolve, reject) => {
    const out = [];
    const idx = tx(db, "meetings", "readonly").index("startedAt");
    idx.openCursor(null, "prev").onsuccess = (e) => {
      const c = e.target.result;
      if (c) { out.push(c.value); c.continue(); }
      else resolve(out);
    };
  });
}

export async function deleteMeeting(id) {
  const db = await openDB();
  await new Promise((res, rej) => {
    const r = tx(db, "meetings", "readwrite").delete(id);
    r.onsuccess = res; r.onerror = () => rej(r.error);
  });
  await new Promise((res, rej) => {
    const r = tx(db, "audio", "readwrite").delete(id);
    r.onsuccess = res; r.onerror = () => rej(r.error);
  });
}

export async function saveAudio(id, blob) {
  const db = await openDB();
  return new Promise((resolve, reject) => {
    const r = tx(db, "audio", "readwrite").put({ id, blob });
    r.onsuccess = () => resolve(true);
    r.onerror = () => reject(r.error);
  });
}

export async function getAudio(id) {
  const db = await openDB();
  return new Promise((resolve, reject) => {
    const r = tx(db, "audio", "readonly").get(id);
    r.onsuccess = () => resolve(r.result ? r.result.blob : null);
    r.onerror = () => reject(r.error);
  });
}
