import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
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

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Login />} />
        {/* Usamos o layout agnóstico para as telas que precisam de navegação */}
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
    </BrowserRouter>
  )
}
