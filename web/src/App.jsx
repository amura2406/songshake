import React, { useEffect, useState } from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import { checkAuth } from './api';
import Login from './components/Login';
import Dashboard from './components/Dashboard';
import Enrichment from './components/Enrichment';
import Results from './components/Results';

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
    return <div className="min-h-screen bg-neutral-900 flex items-center justify-center text-white">Loading...</div>;
  }

  return isAuthenticated ? children : <Navigate to="/login" />;
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
