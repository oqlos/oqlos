import { Routes, Route, Navigate } from "react-router-dom";
import HardwareStatus from "./pages/HardwareStatus";
import HardwareRestart from "./pages/HardwareRestart";
import HardwareRtc from "./pages/HardwareRtc";
import ScenarioFiles from "./pages/ScenarioFiles";
import MotorServices from "./pages/MotorServices";
import Panel from "./pages/Panel";
import ApiDocs from "./pages/ApiDocs";
import HardwareCoilTest from "./pages/HardwareCoilTest";
import HardwareM5Out from "./pages/HardwareM5Out";

// Standalone hardware UI moved out of c2004 connect-scenario. RBAC GuardedRoute
// was an app-shell concern; here routes render directly (SharedNav still reflects
// role from URL config for cosmetic nav).
export default function App() {
  return (
    <Routes>
      <Route path="/" element={<Navigate to="/status" replace />} />
      <Route path="/status" element={<HardwareStatus />} />
      <Route path="/hardware-status" element={<Navigate to="/status" replace />} />
      <Route path="/navigation" element={<Navigate to="/status" replace />} />
      <Route path="/hardware-modbus" element={<HardwareRestart />} />
      <Route path="/hardware-coils" element={<HardwareCoilTest />} />
      <Route path="/hardware-m5-out" element={<HardwareM5Out />} />
      <Route path="/hardware-restart" element={<Navigate to="/hardware-modbus" replace />} />
      <Route path="/hardware-rtc" element={<HardwareRtc />} />
      <Route path="/hardware-demo" element={<Navigate to="/motor-services" replace />} />
      <Route path="/scenario-files" element={<ScenarioFiles />} />
      <Route path="/func-editor" element={<ScenarioFiles />} />
      <Route path="/motor-services" element={<MotorServices />} />
      <Route path="/panel" element={<Panel />} />
      <Route path="/api-docs" element={<ApiDocs />} />
      <Route path="*" element={<Navigate to="/status" replace />} />
    </Routes>
  );
}
