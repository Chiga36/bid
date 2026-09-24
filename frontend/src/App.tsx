import { Route, Routes } from "react-router-dom";

import Layout from "./components/Layout";
import AgentOverview from "./pages/AgentOverview";
import CompetitionInfo from "./pages/CompetitionInfo";
import DataIngestion from "./pages/DataIngestion";
import Home from "./pages/Home";
import ResponseBuilder from "./pages/ResponseBuilder";
import StatusReport from "./pages/StatusReport";

export default function App() {
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route index element={<Home />} />
        <Route path="/builder" element={<ResponseBuilder />} />
        <Route path="/ingestion" element={<DataIngestion />} />
        <Route path="/status" element={<StatusReport />} />
        <Route path="/info" element={<CompetitionInfo />} />
        <Route path="/skills" element={<AgentOverview />} />
      </Route>
    </Routes>
  );
}
