import SharedNav from "../components/SharedNav";

export default function HardwareStatus() {
  const search = typeof window !== "undefined" ? window.location.search : "";
  let origin = "";
  try {
    if (window.parent && window.parent.location.origin && window.parent !== window) {
      origin = window.parent.location.origin;
    }
  } catch (e) {
    // Ignore cross-origin errors
  }
  
  const iframeUrl = `${origin}/hardware-status${search}`;

  return (
    <div className="dashboard">
      <SharedNav />
      <div className="dash-content" style={{ padding: 0, overflow: "hidden" }}>
        <iframe
          src={iframeUrl}
          style={{ width: "100%", height: "100%", border: "none", display: "block" }}
          title="Hardware Status"
        />
      </div>
    </div>
  );
}
