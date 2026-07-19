import { Routes, Route, Navigate } from "react-router-dom";
import Layout from "./components/Layout.jsx";
import Dashboard from "./pages/Dashboard.jsx";
import CompanyProfile from "./pages/CompanyProfile.jsx";
import CampaignBuilder from "./pages/CampaignBuilder.jsx";
import Leads from "./pages/Leads.jsx";
import Campaigns from "./pages/Campaigns.jsx";
import ReviewQueue from "./pages/ReviewQueue.jsx";
import Compliance from "./pages/Compliance.jsx";
import Mailboxes from "./pages/Mailboxes.jsx";

export default function App() {
  return (
    <Layout>
      <Routes>
        <Route path="/" element={<Dashboard />} />
        <Route path="/company" element={<CompanyProfile />} />
        <Route path="/campaign" element={<CampaignBuilder />} />
        <Route path="/leads" element={<Leads />} />
        <Route path="/campaigns" element={<Campaigns />} />
        <Route path="/review" element={<ReviewQueue />} />
        <Route path="/review/:campaignId" element={<ReviewQueue />} />
        <Route path="/compliance" element={<Compliance />} />
        <Route path="/mailboxes" element={<Mailboxes />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </Layout>
  );
}
