import { useNavigate } from "react-router-dom";
import type { AnalysisRecord } from "../api/types";
import AnalyzeForm from "../components/AnalyzeForm";

// Shows the analyze form and opens the result page once an analysis is created.
export default function NewAnalysisPage({ onCreated }: { onCreated: (record: AnalysisRecord) => void }) {
  const navigate = useNavigate();

  // Adds the new record to history and navigates to its page.
  function handleCreated(record: AnalysisRecord) {
    onCreated(record);
    navigate(`/analyses/${record.id}`, { state: { record } });
  }

  return <AnalyzeForm onCreated={handleCreated} />;
}
