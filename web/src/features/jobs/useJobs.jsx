import React, { createContext, useContext, useState, useEffect, useRef, useCallback } from 'react';
import { createJob as apiCreateJob, getJobs, cancelJob as apiCancelJob, getJobStreamUrl } from '../../api';

const JobsContext = createContext(null);

export const useJobs = () => {
    const ctx = useContext(JobsContext);
    if (!ctx) throw new Error('useJobs must be used within JobsProvider');
    return ctx;
};

export const JobsProvider = ({ user, children }) => {
    const [activeJobs, setActiveJobs] = useState([]);
    const [jobHistory, setJobHistory] = useState([]);
    const [jobsByPlaylistId, setJobsByPlaylistId] = useState({});
    const eventSourcesRef = useRef({});
    const pollRef = useRef(null);

    // Build playlist→job lookup whenever activeJobs change
    useEffect(() => {
        const map = {};
        for (const job of activeJobs) {
            if (job.playlist_id) {
                map[job.playlist_id] = job;
            }
        }
        setJobsByPlaylistId(map);
    }, [activeJobs]);

    const fetchJobs = useCallback(async () => {
        try {
            const data = await getJobs();
            if (data.active) {
                setActiveJobs(data.active);
            }
            if (data.history) {
                setJobHistory(data.history);
            }
        } catch (err) {
            console.error('Failed to fetch jobs', err);
        }
    }, []);

    // Connect SSE for each active job
    const connectSSE = useCallback((jobId) => {
        // Avoid duplicate connections
        if (eventSourcesRef.current[jobId]) return;

        const url = getJobStreamUrl(jobId);
        const es = new EventSource(url);
        eventSourcesRef.current[jobId] = es;

        es.onmessage = (event) => {
            try {
                const data = JSON.parse(event.data);
                setActiveJobs(prev => {
                    const idx = prev.findIndex(j => j.id === jobId);
                    if (idx === -1) return [...prev, data];
                    const updated = [...prev];
                    updated[idx] = { ...updated[idx], ...data };
                    return updated;
                });

                // If terminal, close and refresh
                if (['completed', 'error', 'cancelled'].includes(data.status)) {
                    es.close();
                    delete eventSourcesRef.current[jobId];
                    // Refresh to move job from active to history
                    setTimeout(fetchJobs, 500);
                }
            } catch (e) {
                console.error('SSE parse error', e);
            }
        };

        es.onerror = () => {
            es.close();
            delete eventSourcesRef.current[jobId];
        };
    }, [fetchJobs]);

    // Poll and connect SSE
    useEffect(() => {
        if (!user) return;

        fetchJobs();

        pollRef.current = setInterval(fetchJobs, 10000);
        return () => {
            clearInterval(pollRef.current);
            // Close all SSE connections
            Object.values(eventSourcesRef.current).forEach(es => es.close());
            eventSourcesRef.current = {};
        };
    }, [user, fetchJobs]);

    // Connect SSE for newly discovered active jobs
    useEffect(() => {
        for (const job of activeJobs) {
            if (['pending', 'running'].includes(job.status)) {
                connectSSE(job.id);
            }
        }
    }, [activeJobs, connectSSE]);

    const createJob = async (playlistId, wipe = false, playlistName = '') => {
        const job = await apiCreateJob(playlistId, null, wipe, playlistName);
        setActiveJobs(prev => [...prev, job]);
        connectSSE(job.id);
        return job;
    };

    const cancelJobById = async (jobId) => {
        try {
            await apiCancelJob(jobId);
            // Close SSE for this job so it doesn't overwrite our state
            if (eventSourcesRef.current[jobId]) {
                eventSourcesRef.current[jobId].close();
                delete eventSourcesRef.current[jobId];
            }
            // Update state optimistically
            setActiveJobs(prev =>
                prev.map(j => j.id === jobId ? { ...j, status: 'cancelled', message: 'Cancelling…' } : j)
            );
            // Refresh from server to get actual state
            setTimeout(fetchJobs, 1000);
        } catch (err) {
            console.error('Failed to cancel job', err);
            // Refresh to get actual state from server
            fetchJobs();
        }
    };

    return (
        <JobsContext.Provider value={{
            activeJobs,
            jobHistory,
            jobsByPlaylistId,
            createJob,
            cancelJob: cancelJobById,
            fetchJobs,
        }}>
            {children}
        </JobsContext.Provider>
    );
};
