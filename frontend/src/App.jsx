import { BrowserRouter, Routes, Route, Navigate, useLocation } from 'react-router-dom'
import Layout from './components/Layout'
import Login from './pages/Login'
import OperatorsManagement from './pages/OperatorsManagement'
import SessionSelect from './pages/SessionSelect'
import SessionItems from './pages/SessionItems'
import Picking from './pages/Picking'
import Supervisor from './pages/Supervisor'
import MasterData from './pages/MasterData'
import ShortageReport from './pages/ShortageReport'
import BatchDetail from './pages/BatchDetail'
import OlistOrders from './pages/OlistOrders'
import GemmaDashboard from './pages/GemmaDashboard'
import SeparacaoOlist from './pages/SeparacaoOlist'
import PickingListsHistory from './pages/PickingListsHistory'
import PickingListDetail from './pages/PickingListDetail'
import LandingNVS from './pages/LandingNVS'
import SiteNJS from './pages/SiteNJS'

function AppRoutes() {
  const location = useLocation()
  const backgroundLocation = location.state?.backgroundLocation

  return (
    <>
      {/* Rotas principais — quando há overlay, renderiza o fundo (backgroundLocation) */}
      <Routes location={backgroundLocation || location}>
        <Route path="/" element={<Login />} />
        <Route path="/landing" element={<LandingNVS />} />
        <Route path="/njs" element={<SiteNJS />} />
        <Route element={<Layout />}>
          <Route path="/sessions" element={<SessionSelect />} />
          <Route path="/sessions/:sessionId/items" element={<SessionItems />} />
          <Route path="/picking/:sessionId" element={<Picking />} />
          <Route path="/supervisor" element={<Supervisor />} />
          <Route path="/supervisor/:marketplace/:tab" element={<Supervisor />} />
          <Route path="/supervisor/batch/:batchId" element={<BatchDetail />} />
          <Route path="/olist-orders" element={<GemmaDashboard />} />
          <Route path="/operators" element={<OperatorsManagement />} />
          <Route path="/master-data" element={<MasterData />} />
          <Route path="/separacao" element={<SeparacaoOlist />} />
          <Route path="/separacao/listas" element={<PickingListsHistory />} />
          <Route path="/separacao/listas/:listId" element={<PickingListDetail />} />
          <Route path="/shortage-report" element={<ShortageReport />} />
        </Route>
        <Route path="*" element={<Navigate to="/" />} />
      </Routes>

      {/* Overlay — Picking renderizado como modal sobre o fundo */}
      {backgroundLocation && (
        <Routes>
          <Route path="/picking/:sessionId" element={<Picking />} />
        </Routes>
      )}
    </>
  )
}

export default function App() {
  return (
    <BrowserRouter>
      <AppRoutes />
    </BrowserRouter>
  )
}
