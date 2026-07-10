// Base protocol types. A consumer defines its message union by extending these:
//
//   type Msg = SnapshotMsg<MySnapshot> | ErrorMsg | { type: "my_custom"; ... };
//
// and hands `Net<Msg>` a handlers map keyed by `type` — fully typed per message kind.

export type BaseMsg = { type: string };

export type SnapshotMsg<S> = { type: "snapshot"; data: S };
export type ErrorMsg = { type: "error"; msg: string };

/** Handlers map for a discriminated message union: one optional callback per `type`. */
export type Handlers<M extends BaseMsg> = {
  [K in M["type"]]?: (m: Extract<M, { type: K }>) => void;
};

// --- demokit.gpu wire schemas (for consumers exposing a GPU-occupancy panel) ---

export interface GpuProc {
  pid: string;
  user: string; // owner (resolved via ps — a co-tenant's job is named, not just numbered)
  cmd: string; // full argv (truncate in the UI)
  mem: number | null; // MiB this process holds (null if nvidia-smi reported N/A)
}

export interface GpuInfo {
  index: string; // nvidia-smi index (what a force-pick targets)
  name: string; // short name, e.g. "RTX A6000"
  full_name: string;
  uuid: string;
  mem_used: number | null; // MiB
  mem_total: number | null; // MiB
  is_eligible: boolean; // may the polite auto-picker take it?
  procs: GpuProc[]; // empty = idle
}
