import { getStoredToken, BACKEND_URL } from "./api";
import { toast } from "sonner";

/**
 * Authenticated PDF download — uses fetch with Bearer header so token-protected
 * /api endpoints work from anywhere in the UI. Browsers don't pass localStorage
 * tokens on plain <a href> clicks, which is why those return 401 — use this
 * helper instead of a raw anchor for any /api/...pdf link.
 *
 * Pass `inline=true` to open the PDF in a new tab via blob URL; default is
 * to trigger a save dialog with the supplied filename.
 */
export async function authedDownload(path, {
  filename,
  inline = false,
  onError,
} = {}) {
  const token = getStoredToken();
  if (!token) {
    toast.error("You're signed out — please sign in again.");
    return null;
  }
  const url = path.startsWith("http") ? path : `${BACKEND_URL}${path}`;
  try {
    const res = await fetch(url, {
      headers: { Authorization: `Bearer ${token}` },
    });
    if (!res.ok) {
      const txt = await res.text().catch(() => "");
      throw new Error(`HTTP ${res.status}${txt ? ` · ${txt.slice(0, 120)}` : ""}`);
    }
    const blob = await res.blob();
    const objectUrl = URL.createObjectURL(blob);
    if (inline) {
      window.open(objectUrl, "_blank");
      // revoke later — give the new tab a chance to load
      setTimeout(() => URL.revokeObjectURL(objectUrl), 60_000);
      return objectUrl;
    }
    const inferredName =
      filename ||
      res.headers.get("content-disposition")?.match(/filename="([^"]+)"/)?.[1] ||
      "download.pdf";
    const a = document.createElement("a");
    a.href = objectUrl;
    a.download = inferredName;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    setTimeout(() => URL.revokeObjectURL(objectUrl), 5_000);
    return objectUrl;
  } catch (e) {
    const msg = e?.message || "Download failed";
    if (onError) onError(e);
    else toast.error(msg);
    return null;
  }
}
