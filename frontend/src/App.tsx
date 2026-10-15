import { Route, Routes } from "react-router-dom";
import Sidebar from "./components/Sidebar";
import Cockpit from "./pages/Cockpit";
import AgentsPage from "./pages/AgentsPage";
import AgentChat from "./pages/AgentChat";
import Goals from "./pages/Goals";
import Categories from "./pages/Categories";
import Documents from "./pages/Documents";
import Integrations from "./pages/Integrations";

export default function App() {
  return (
    <div className="app-shell">
      <Sidebar />
      <main className="main-content">
        <Routes>
          <Route path="/" element={<Cockpit />} />
          <Route path="/agenten" element={<AgentsPage />} />
          <Route path="/agenten/:agentId" element={<AgentChat />} />
          <Route path="/ziele" element={<Goals />} />
          <Route path="/kategorien" element={<Categories />} />
          <Route path="/dokumente" element={<Documents />} />
          <Route path="/integrationen" element={<Integrations />} />
        </Routes>
      </main>
    </div>
  );
}
