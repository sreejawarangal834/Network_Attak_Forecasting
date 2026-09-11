import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { SampleProvider } from './context/SampleContext'
import { AnalysisProvider } from './context/AnalysisContext'
import MainLayout from './layouts/MainLayout'

import Dashboard        from './pages/Dashboard'
import AttackForecast   from './pages/AttackForecast'
import AttackStages     from './pages/AttackStages'
import NetworkState     from './pages/NetworkState'
import Explainability   from './pages/Explainability'
import ModelPerformance from './pages/ModelPerformance'
import SystemStatus     from './pages/SystemStatus'
import DatasetUpload    from './pages/DatasetUpload'

export default function App() {
  return (
    <BrowserRouter>
      <AnalysisProvider>
        <SampleProvider>
          <MainLayout>
            <Routes>
              <Route path="/"            element={<Dashboard />} />
              <Route path="/network"     element={<NetworkState />} />
              <Route path="/forecast"    element={<AttackForecast />} />
              <Route path="/stages"      element={<AttackStages />} />
              <Route path="/explain"     element={<Explainability />} />
              <Route path="/performance" element={<ModelPerformance />} />
              <Route path="/system"      element={<SystemStatus />} />
              <Route path="/upload"      element={<DatasetUpload />} />
              {/* Catch-all — redirect unknown routes to dashboard */}
              <Route path="*"            element={<Navigate to="/" replace />} />
            </Routes>
          </MainLayout>
        </SampleProvider>
      </AnalysisProvider>
    </BrowserRouter>
  )
}
