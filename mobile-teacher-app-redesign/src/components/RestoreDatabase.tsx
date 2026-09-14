import { useEffect, useRef, useState } from "react";
import { Upload } from "lucide-react";
import { store } from "../lib/store";
import { Btn, ConfirmSheet, Field, Select, Sheet, useToast } from "./ui";

type Capabilities = { android: boolean; picker_available?: boolean };
type RestoreTarget = { kind: "native" } | { kind: "named"; name: string } | { kind: "file"; file: File };
type Backup = { name: string };

export default function RestoreDatabase() {
  const toast = useToast();
  const [capabilities, setCapabilities] = useState<Capabilities | null>(null);
  const [checking, setChecking] = useState(true);
  const [target, setTarget] = useState<RestoreTarget | null>(null);
  const [busy, setBusy] = useState(false);
  const locked = useRef(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [backups, setBackups] = useState<Backup[]>([]);
  const [listOpen, setListOpen] = useState(false);
  const [listLoading, setListLoading] = useState(false);
  const listing = useRef(false);
  const [backupName, setBackupName] = useState("");

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const response = await fetch("/api/restore/pick/diag");
        const data = await response.json();
        if (!response.ok || typeof data?.android !== "boolean") throw new Error("Invalid capability response");
        if (!cancelled) {
          setCapabilities(data);
          if (data.android && !data.picker_available) {
            setMessage("The native file picker is unavailable. Choose a saved backup instead.");
          }
        }
      } catch (_) {
        if (!cancelled) setError("Could not check the file picker. Choose a saved backup, or select a file on desktop.");
      } finally {
        if (!cancelled) setChecking(false);
      }
    })();
    return () => { cancelled = true; };
  }, []);

  const choose = (next: RestoreTarget) => {
    if (locked.current || listing.current) return;
    setError("");
    setMessage("");
    setTarget(next);
  };

  const cancel = () => {
    if (locked.current) return;
    setTarget(null);
    setMessage("Restore cancelled. The database was not replaced.");
  };

  const loadBackups = async () => {
    if (locked.current || listing.current) return;
    listing.current = true;
    setListLoading(true);
    setListOpen(true);
    setBackupName("");
    setBackups([]);
    setError("");
    setMessage("");
    try {
      const response = await fetch("/api/backup/list");
      const data = await response.json();
      if (!response.ok || !Array.isArray(data?.backups) ||
          !data.backups.every((item: Backup) => item && typeof item.name === "string")) {
        throw new Error(data?.error || "Could not load saved backups.");
      }
      setBackups(data.backups);
      if (!data.backups.length) setMessage("No saved backups were found. Save a database copy first, then refresh the list.");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not load saved backups.");
    } finally {
      listing.current = false;
      setListLoading(false);
    }
  };

  const restore = async () => {
    if (!target || locked.current || listing.current) return;
    const selected = target;
    locked.current = true;
    setBusy(true);
    setTarget(null);
    setListOpen(false);
    setError("");
    setMessage("Saving pending attendance before restore...");
    let reloading = false;
    try {
      // Drain old-database writes before the picker can replace the database.
      await store.flushAttendance();
      setMessage(selected.kind === "native"
        ? "Choose a database in the system picker, or cancel there. Keep the app open."
        : "Restoring the database. Keep the app open...");
      let url = "/api/restore/pick";
      const options: RequestInit = { method: "POST" };
      if (selected.kind === "file") {
        url = "/api/restore";
        const body = new FormData();
        body.append("file", selected.file);
        options.body = body;
      } else if (selected.kind === "named") {
        url = "/api/restore/named";
        options.headers = { "Content-Type": "application/json" };
        options.body = JSON.stringify({ name: selected.name });
      }
      const response = await fetch(url, options);
      const data = await response.json().catch(() => null);
      if (selected.kind === "native" && (data?.cancelled === true ||
          data?.error === "Выбор файла отменён")) {
        setMessage("File selection cancelled. The database was not replaced.");
        return;
      }
      if (!response.ok || data?.ok !== true) {
        throw new Error(data?.error || `Restore did not complete (HTTP ${response.status}).`);
      }
      const success = "Database restored. A safe recovery copy was created.";
      toast(success);
      // Keep the success notice across the immediate full-state reload.
      try { sessionStorage.setItem("th-restore-success", "1"); } catch (_) {}
      reloading = true;
      window.location.reload();
    } catch (e) {
      setMessage("");
      setError(e instanceof Error ? e.message : "Restore failed. Check the connection before retrying.");
    } finally {
      if (!reloading) {
        locked.current = false;
        setBusy(false);
      }
    }
  };

  const feedback = <>
    {message && <p role="status" className="text-[12px] text-muted leading-snug">{message}</p>}
    {error && <p role="alert" className="text-[12px] text-danger leading-snug">{error}</p>}
  </>;

  return <>
    {checking || capabilities?.android ? (
      <Btn type="button" variant="outline" icon={Upload}
        disabled={checking || busy || listLoading || !capabilities?.picker_available}
        onClick={() => choose({ kind: "native" })}>
        {checking ? "Checking file picker..." : "Restore database"}
      </Btn>
    ) : (
      <label htmlFor="restore-database-file"
        className="restore-file-label pressable relative inline-flex items-center justify-center gap-2 font-semibold select-none h-11 px-4 text-[14px] rounded-xl bg-surface text-ink border border-linestrong cursor-pointer active:bg-surface2">
        <Upload size={17} strokeWidth={2.2} />
        Restore database from file
        <input id="restore-database-file" type="file" accept="application/x-sqlite3,.db"
          className="restore-file-input" disabled={busy || listLoading}
          onCancel={() => setMessage("File selection cancelled. The database was not replaced.")}
          onChange={(event) => {
            const file = event.currentTarget.files?.[0];
            event.currentTarget.value = "";
            if (file) choose({ kind: "file", file });
          }} />
      </label>
    )}
    <Btn type="button" variant="outline" disabled={busy || listLoading} onClick={loadBackups}>
      Restore from saved backup
    </Btn>
    {!listOpen && !busy && feedback}
    <p className="text-[11.5px] text-faint leading-snug mt-1">
      Restoring replaces the current SQLite database. A safe recovery copy is created before replacement.
    </p>
    <Sheet open={listOpen} title="Saved backups" onClose={() => setListOpen(false)}>
      <div className="flex flex-col gap-3">
        {listLoading && <p role="status">Loading saved backups...</p>}
        {feedback}
        {backups.length > 0 && <Field label="Choose a backup">
          <Select value={backupName} disabled={listLoading || busy}
            onChange={(event) => setBackupName(event.target.value)}>
            <option value="">Select a backup</option>
            {backups.map((backup) => <option key={backup.name} value={backup.name}>{backup.name}</option>)}
          </Select>
        </Field>}
        <Btn type="button" disabled={!backupName || listLoading || busy} onClick={() => {
          if (!backups.some((backup) => backup.name === backupName)) return;
          choose({ kind: "named", name: backupName });
          setListOpen(false);
        }}>Continue</Btn>
        <Btn type="button" variant="muted" disabled={listLoading || busy} onClick={loadBackups}>Refresh list</Btn>
      </div>
    </Sheet>
    <ConfirmSheet open={target !== null} onClose={cancel} title="Restore database?"
      body={target?.kind === "native"
        ? "The file you choose next will immediately replace the current database. A safe recovery copy will be created first. Continue to the system picker?"
        : `Replace the current database with ${target?.kind === "file" ? target.file.name : target?.kind === "named" ? target.name : "the selected backup"}? A safe recovery copy will be created first.`}
      confirmLabel={target?.kind === "native" ? "Choose and restore" : "Replace database"}
      danger onConfirm={restore} />
    <Sheet open={busy} onClose={() => {}} title="Restoring database">
      <div aria-busy="true">{feedback}</div>
    </Sheet>
  </>;
}
