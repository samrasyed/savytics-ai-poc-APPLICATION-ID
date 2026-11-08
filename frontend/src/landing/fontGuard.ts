const FAMILY = "Redaction 50";

// Collects every font face in the document that belongs to Redaction 50.
function displayFaces(): FontFace[] {
  const faces: FontFace[] = [];
  document.fonts.forEach((f) => {
    if (f.family.replace(/"/g, "") === FAMILY) faces.push(f);
  });
  return faces;
}

// Loads the Redaction 50 faces and reports whether at least one loaded, logging an error if none did.
export async function verifyDisplayFont(): Promise<boolean> {
  if (typeof document === "undefined" || !("fonts" in document)) return true;
  const faces = displayFaces();
  await Promise.all(faces.map((f) => f.load().catch(() => null)));
  const ok = faces.length > 0 && faces.some((f) => f.status === "loaded");
  if (!ok) {
    console.error(
      '[Sift] "Redaction 50" did not load. Open DevTools > Network, filter "fonts", and fix the file name or path in fonts.css.',
    );
  }
  return ok;
}

// Reports whether a real Redaction 50 italic face has loaded, so italics are never synthesised.
export function hasDisplayItalic(): boolean {
  if (typeof document === "undefined" || !("fonts" in document)) return false;
  return displayFaces().some((f) => f.style === "italic" && f.status === "loaded");
}
