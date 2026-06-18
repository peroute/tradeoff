import { BrowserRouter, Routes, Route } from 'react-router-dom'
import IntakePage from './pages/IntakePage'
import LoadingPage from './pages/LoadingPage'
import DashboardPage from './pages/DashboardPage'

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<IntakePage />} />
        <Route path="/loading" element={<LoadingPage />} />
        <Route path="/dashboard" element={<DashboardPage />} />
      </Routes>
    </BrowserRouter>
  )
}
