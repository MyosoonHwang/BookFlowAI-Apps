import React from 'react';
import ReactDOM from 'react-dom/client';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import Overview from './pages/Overview';
import Pending from './pages/Pending';
import Layout from './Layout';
import './styles.css';

const qc = new QueryClient({ defaultOptions: { queries: { refetchOnWindowFocus: false, staleTime: 5_000 } } });

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <QueryClientProvider client={qc}>
      <BrowserRouter>
        <Routes>
          <Route element={<Layout />}>
            <Route path="/" element={<Navigate to="/overview/1" replace />} />
            <Route path="/overview/:wh" element={<Overview />} />
            <Route path="/pending" element={<Pending />} />
          </Route>
        </Routes>
      </BrowserRouter>
    </QueryClientProvider>
  </React.StrictMode>,
);
