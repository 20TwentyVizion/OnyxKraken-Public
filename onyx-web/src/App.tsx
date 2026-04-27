import { Routes, Route } from "react-router-dom";
import LandingPage from "./pages/LandingPage";
import EcosystemPage from "./pages/EcosystemPage";
import BotKree8r from "./pages/BotKree8r";
import CardTest from "./pages/CardTest";
import FloatingOnyx from "./components/FloatingOnyx";

export default function App() {
  return (
    <>
      <Routes>
        {/* Grant-focused landing — the main public face for judges + buyers */}
        <Route path="/" element={<LandingPage />} />
        {/* The previous creative-ecosystem landing, preserved */}
        <Route path="/ecosystem" element={<EcosystemPage />} />
        {/* Live face / chat demo */}
        <Route path="/face" element={<BotKree8r />} />
        {/* Legacy paths kept working */}
        <Route path="/create" element={<BotKree8r />} />
        <Route path="/cards" element={<CardTest />} />
      </Routes>
      <FloatingOnyx />
    </>
  );
}
