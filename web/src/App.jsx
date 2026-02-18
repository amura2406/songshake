import React, { useEffect, useState } from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import { checkAuth, getCurrentUser } from './api';
import Login from './features/auth/Login';
import Dashboard from './features/enrichment/Dashboard';
import Results from './features/songs/Results';
import Layout from './components/layout/Layout';
import { JobsProvider } from './features/jobs/useJobs';

const PrivateRoute = ({ children }) => {
  const [isAuthenticated, setIsAuthenticated] = useState(null);
  const [user, setUser] = useState(null);

  useEffect(() => {
    const verify = async () => {
      const auth = await checkAuth();
      setIsAuthenticated(auth);
      if (auth) {
        try {
          const u = await getCurrentUser();
          setUser(u);
        } catch (e) {
          console.error('Failed to get user', e);
        }
      }
    };
    verify();
  }, []);

  if (isAuthenticated === null) {
    return <div className="min-h-screen bg-background-dark flex items-center justify-center text-white">Loading...</div>;
  }

  return isAuthenticated ? (
    <JobsProvider user={user}>
      <Layout>{children}</Layout>
    </JobsProvider>
  ) : (
    <Navigate to="/login" />
  );
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
