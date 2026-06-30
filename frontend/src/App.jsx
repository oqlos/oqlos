import { Routes, Route, Navigate } from "react-router-dom";
import HardwareStatus from "./pages/HardwareStatus";
import HardwareDemo from "./pages/HardwareDemo";
import HardwareRestart from "./pages/HardwareRestart";
import MapEditor from "./pages/MapEditor";
import ScenarioFiles from "./pages/ScenarioFiles";

// Standalone hardware UI moved out of c2004 connect-scenario. RBAC GuardedRoute
// was an app-shell concern; here routes render directly (SharedNav still reflects
// role from URL config for cosmetic nav).
export default function App() {
  return (
    <Routes>
      <Route path="/" element={<Navigate to="/hardware-status" replace />} />
      <Route path="/hardware-status" element={<HardwareStatus />} />
      <Route path="/hardware-restart" element={<HardwareRestart />} />
      <Route path="/hardware-demo" element={<HardwareDemo />} />
      <Route path="/map-editor" element={<MapEditor />} />
      <Route path="/scenario-files" element={<ScenarioFiles />} />
      <Route path="/func-editor" element={<ScenarioFiles />} />
      <Route path="*" element={<Navigate to="/hardware-status" replace />} />
    </Routes>
  );
}
