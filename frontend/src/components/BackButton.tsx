import { ArrowLeft } from "lucide-react";
import { useLocation, useNavigate } from "react-router-dom";

const LANDING_URL = "/";

// Goes back one step inside the app; on the first app page it falls back to the new-analysis page,
// and from there to the landing page, so it never leaves the site or loops back to login.
export default function BackButton() {
  const navigate = useNavigate();
  const location = useLocation();

  // Picks the right destination for this point in the app's history.
  function goBack() {
    if (location.key !== "default") navigate(-1);
    else if (location.pathname !== "/") navigate("/");
    else window.location.assign(LANDING_URL);
  }

  return (
    <button type="button" className="btn btn-ghost back-btn" onClick={goBack}>
      <ArrowLeft size={16} strokeWidth={1.75} aria-hidden="true" />
      Back
    </button>
  );
}
