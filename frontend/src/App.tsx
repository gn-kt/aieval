import { BrowserRouter, Routes, Route } from 'react-router-dom';
import EvaluatorPage from './pages/EvaluatorPage';

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="*" element={<EvaluatorPage />} />
      </Routes>
    </BrowserRouter>
  );
}
