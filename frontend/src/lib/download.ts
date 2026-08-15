/**
 * Utilities for downloading generated game files.
 */

/**
 * Download a single file as a text file.
 */
export function downloadFile(path: string, content: string) {
  const filename = path.split("/").pop() ?? path;
  const blob = new Blob([content], { type: "text/plain;charset=utf-8" });
  const url = URL.createObjectURL(blob);

  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}

/**
 * Download all files as a .zip archive.
 * Uses JSZip-compatible manual zip creation (no dependency needed for small files).
 */
export async function downloadAllAsZip(files: Record<string, string>) {
  // Dynamically import JSZip — it's lightweight and handles paths correctly
  // Since we don't have JSZip installed, use a manual Blob-based approach
  const zip = await buildZipBlob(files);
  const url = URL.createObjectURL(zip);

  const a = document.createElement("a");
  a.href = url;
  a.download = "game.zip";
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}

/**
 * Build a ZIP file from a flat path→content map.
 * Minimal ZIP implementation (no compression, store-only) — works for text files.
 */
async function buildZipBlob(files: Record<string, string>): Promise<Blob> {
  const entries: { path: string; data: Uint8Array }[] = [];
  const encoder = new TextEncoder();

  for (const [path, content] of Object.entries(files)) {
    entries.push({ path, data: encoder.encode(content) });
  }

  const parts: Uint8Array[] = [];
  const centralDir: Uint8Array[] = [];
  let offset = 0;

  for (const entry of entries) {
    const pathBytes = encoder.encode(entry.path);

    // Local file header
    const header = new Uint8Array(30 + pathBytes.length);
    const view = new DataView(header.buffer);
    view.setUint32(0, 0x04034b50, true); // signature
    view.setUint16(4, 20, true); // version needed
    view.setUint16(6, 0, true); // flags
    view.setUint16(8, 0, true); // compression (store)
    view.setUint16(10, 0, true); // mod time
    view.setUint16(12, 0, true); // mod date
    view.setUint32(14, crc32(entry.data), true); // crc32
    view.setUint32(18, entry.data.length, true); // compressed size
    view.setUint32(22, entry.data.length, true); // uncompressed size
    view.setUint16(26, pathBytes.length, true); // filename length
    view.setUint16(28, 0, true); // extra field length
    header.set(pathBytes, 30);

    // Central directory entry
    const cdEntry = new Uint8Array(46 + pathBytes.length);
    const cdView = new DataView(cdEntry.buffer);
    cdView.setUint32(0, 0x02014b50, true); // signature
    cdView.setUint16(4, 20, true); // version made by
    cdView.setUint16(6, 20, true); // version needed
    cdView.setUint16(8, 0, true); // flags
    cdView.setUint16(10, 0, true); // compression
    cdView.setUint16(12, 0, true); // mod time
    cdView.setUint16(14, 0, true); // mod date
    cdView.setUint32(16, crc32(entry.data), true); // crc32
    cdView.setUint32(20, entry.data.length, true); // compressed size
    cdView.setUint32(24, entry.data.length, true); // uncompressed size
    cdView.setUint16(28, pathBytes.length, true); // filename length
    cdView.setUint16(30, 0, true); // extra field length
    cdView.setUint16(32, 0, true); // comment length
    cdView.setUint16(34, 0, true); // disk number
    cdView.setUint16(36, 0, true); // internal attrs
    cdView.setUint32(38, 0, true); // external attrs
    cdView.setUint32(42, offset, true); // relative offset
    cdEntry.set(pathBytes, 46);

    parts.push(header);
    parts.push(entry.data);
    centralDir.push(cdEntry);

    offset += header.length + entry.data.length;
  }

  const centralDirOffset = offset;
  let centralDirSize = 0;
  for (const cd of centralDir) {
    parts.push(cd);
    centralDirSize += cd.length;
  }

  // End of central directory
  const eocd = new Uint8Array(22);
  const eocdView = new DataView(eocd.buffer);
  eocdView.setUint32(0, 0x06054b50, true); // signature
  eocdView.setUint16(4, 0, true); // disk number
  eocdView.setUint16(6, 0, true); // disk with CD
  eocdView.setUint16(8, entries.length, true); // entries on disk
  eocdView.setUint16(10, entries.length, true); // total entries
  eocdView.setUint32(12, centralDirSize, true); // CD size
  eocdView.setUint32(16, centralDirOffset, true); // CD offset
  eocdView.setUint16(20, 0, true); // comment length
  parts.push(eocd);

  return new Blob(parts as BlobPart[], { type: "application/zip" });
}

/**
 * CRC32 implementation for ZIP file creation.
 */
function crc32(data: Uint8Array): number {
  let crc = 0xffffffff;
  for (let i = 0; i < data.length; i++) {
    crc ^= data[i];
    for (let j = 0; j < 8; j++) {
      crc = (crc >>> 1) ^ (crc & 1 ? 0xedb88320 : 0);
    }
  }
  return (crc ^ 0xffffffff) >>> 0;
}
