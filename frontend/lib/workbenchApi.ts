import { extractApiErrorMessage } from "@/lib/api-error";

type Api = (path: string, init?: RequestInit) => Promise<Response>;

/** Call a workbench endpoint and return its JSON, or throw the server's error message. */
export async function fetchJson<T = unknown>(api: Api, path: string, fallback: string, init?: RequestInit): Promise<T> {
  const res = await api(path, init);
  const data = (await res.json().catch(() => ({}))) as T;
  if (!res.ok) throw new Error(extractApiErrorMessage(data, fallback));
  return data;
}

/** Fetch a protected file and hand it to the browser as a download. */
export async function downloadFile(api: Api, path: string, filename: string): Promise<void> {
  const res = await api(path);
  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    throw new Error(extractApiErrorMessage(data, "Download failed"));
  }
  const url = URL.createObjectURL(await res.blob());
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  link.click();
  URL.revokeObjectURL(url);
}
