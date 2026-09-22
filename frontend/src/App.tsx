import { Navigate, Route, Routes } from "react-router-dom";

import Layout from "./components/Layout";
import AgentSkills from "./pages/AgentSkills";
import CompetitionInfo from "./pages/CompetitionInfo";
import DataIngestion from "./pages/DataIngestion";
import ResponseBuilder from "./pages/ResponseBuilder";
import StatusReport from "./pages/StatusReport";

export default function App() {
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route index element={<Navigate to="/builder" replace />} />
        <Route path="/builder" element={<ResponseBuilder />} />
        <Route path="/ingestion" element={<DataIngestion />} />
        <Route path="/status" element={<StatusReport />} />
        <Route path="/info" element={<CompetitionInfo />} />
        <Route path="/skills" element={<AgentSkills />} />
      </Route>
    </Routes>
  );
}
