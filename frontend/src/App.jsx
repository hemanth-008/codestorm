import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { FleetProvider } from './context/FleetProvider';
import Shell from './components/Shell';
import FleetOverview from './pages/FleetOverview';
import RobotDetail from './pages/RobotDetail';
import Attacks from './pages/Attacks';
import Scorecard from './pages/Scorecard';
import Sandbox from './pages/Sandbox';
import Monitor from './pages/Monitor';
import Login from './pages/Login';

export default function App() {
  return (
    <FleetProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/" element={<Shell />}>
            <Route index element={<FleetOverview />} />
            <Route path="robot/:id" element={<RobotDetail />} />
            <Route path="attacks" element={<Attacks />} />
            <Route path="scorecard" element={<Scorecard />} />
            <Route path="sandbox" element={<Sandbox />} />
            <Route path="monitor" element={<Monitor />} />
            <Route path="login" element={<Login />} />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Route>
        </Routes>
      </BrowserRouter>
    </FleetProvider>
  );
}
