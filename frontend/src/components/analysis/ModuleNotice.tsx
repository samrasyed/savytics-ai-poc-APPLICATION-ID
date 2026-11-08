import type { ModuleState } from "../../api/types";

// Explains when an intelligence check failed or has not been run for this analysis.
export default function ModuleNotice({ state }: { state: ModuleState | undefined }) {
  if (state === "ok") return null;
  const message =
    state === "failed"
      ? "This check could not be completed. Use “Re-run checks” at the top of the page to try again."
      : "This check has not been run for this analysis yet. Use “Re-run checks” at the top of the page.";
  return <p className="notice small">{message}</p>;
}
