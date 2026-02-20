import { useState, useEffect, useRef, useCallback } from 'react';
import { getAIUsage } from '../../api';

/**
 * Hook providing all-time AI usage tracking via polling.
 * Returns { inputTokens, outputTokens, cost, glowing }.
 * `glowing` is true briefly whenever values update.
 *
 * Polls every 2 seconds for reliable real-time updates on Cloud Run
 * (SSE/EventSource is unreliable on Cloud Run due to HTTP/2 buffering).
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

    // Poll for updates
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
        } catch (err) {
            // Silently ignore polling errors (auth expired, network, etc.)
        }
    }, [triggerGlow]);

    // Initial fetch + polling every 2s
    useEffect(() => {
        fetchUsage();
        intervalRef.current = setInterval(fetchUsage, 2000);

        return () => {
            clearInterval(intervalRef.current);
            clearTimeout(glowTimerRef.current);
        };
    }, [fetchUsage]);

    return { ...usage, glowing };
};
