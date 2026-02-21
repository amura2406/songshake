import { useState, useEffect, useRef, useCallback } from 'react';
import { getAIUsage } from '../../api';

/**
 * Hook providing all-time AI usage tracking.
 * Returns { inputTokens, outputTokens, cost, glowing, startPolling, stopPolling }.
 *
 * Fetches once on mount. Polling (2s) only runs when explicitly started
 * (e.g. when an enrichment job is active) and stops when told.
 */
export const useAIUsage = () => {
    const [usage, setUsage] = useState({ inputTokens: 0, outputTokens: 0, cost: 0.0 });
    const [glowing, setGlowing] = useState(false);
    const glowTimerRef = useRef(null);
    const intervalRef = useRef(null);

    // Trigger the glow effect when values change
    const triggerGlow = useCallback(() => {
        setGlowing(true);
        clearTimeout(glowTimerRef.current);
        glowTimerRef.current = setTimeout(() => setGlowing(false), 600);
    }, []);

    // Fetch usage data once
    const fetchUsage = useCallback(async () => {
        try {
            const data = await getAIUsage();
            const newUsage = {
                inputTokens: data.input_tokens || 0,
                outputTokens: data.output_tokens || 0,
                cost: data.cost || 0.0,
            };

            setUsage(prev => {
                if (prev.inputTokens !== newUsage.inputTokens || prev.cost !== newUsage.cost) {
                    triggerGlow();
                }
                return newUsage;
            });
        } catch {
            // Silently ignore errors (auth expired, network, etc.)
        }
    }, [triggerGlow]);

    // Start polling — called when a job becomes active
    const startPolling = useCallback(() => {
        if (intervalRef.current) return; // already polling
        fetchUsage(); // immediate fetch
        intervalRef.current = setInterval(fetchUsage, 2000);
    }, [fetchUsage]);

    // Stop polling — called when no more active jobs
    const stopPolling = useCallback(() => {
        if (intervalRef.current) {
            clearInterval(intervalRef.current);
            intervalRef.current = null;
        }
        // One final fetch to get the settled value
        fetchUsage();
    }, [fetchUsage]);

    // Initial fetch only (no polling by default)
    useEffect(() => {
        fetchUsage();

        return () => {
            clearInterval(intervalRef.current);
            clearTimeout(glowTimerRef.current);
        };
    }, [fetchUsage]);

    return { ...usage, glowing, startPolling, stopPolling };
};
