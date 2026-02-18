import React, { useEffect, useState } from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import { checkAuth } from './api';
import Login from './features/auth/Login';
import Dashboard from './features/enrichment/Dashboard';
import Enrichment from './features/enrichment/Enrichment';
import Results from './features/songs/Results';
import Layout from './components/layout/Layout';

const PrivateRoute = ({ children }) => {
  const [isAuthenticated, setIsAuthenticated] = useState(null);

  useEffect(() => {
    const verify = async () => {
      const auth = await checkAuth();
      setIsAuthenticated(auth);
    };
    verify();
  }, []);

  if (isAuthenticated === null) {
    return <div className="min-h-screen bg-background-dark flex items-center justify-center text-white">Loading...</div>;
  }

  return isAuthenticated ? <Layout>{children}</Layout> : <Navigate to="/login" />;
};

function App() {
  return (
    <Router>
      <Routes>
        <Route path="/login" element={<Login />} />
        <Route
          path="/"
          element={
            <PrivateRoute>
              <Dashboard />
            </PrivateRoute>
          }
        />
        <Route
          path="/enrichment/:playlistId"
          element={
            <PrivateRoute>
              <Enrichment />
            </PrivateRoute>
          }
        />
        <Route
          path="/results"
          element={
            <PrivateRoute>
              <Results />
            </PrivateRoute>
          }
        />
      </Routes>
    </Router>
  );
}

export default App;
