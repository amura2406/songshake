import { useState, useEffect, useRef, useCallback } from 'react';
import { getAIUsage, getAIUsageStreamUrl } from '../../api';

/**
 * Hook providing all-time AI usage tracking via SSE.
 * Returns { inputTokens, outputTokens, cost, glowing }.
 * `glowing` is true briefly whenever values update.
 */
export const useAIUsage = () => {
    const [usage, setUsage] = useState({ inputTokens: 0, outputTokens: 0, cost: 0.0 });
    const [glowing, setGlowing] = useState(false);
    const glowTimerRef = useRef(null);
    const esRef = useRef(null);
    const reconnectTimerRef = useRef(null);

    // Trigger the glow effect when values change
    const triggerGlow = useCallback(() => {
        setGlowing(true);
        clearTimeout(glowTimerRef.current);
        glowTimerRef.current = setTimeout(() => setGlowing(false), 600);
    }, []);

    // Initial fetch
    useEffect(() => {
        const fetchInitial = async () => {
            try {
                const data = await getAIUsage();
                setUsage({
                    inputTokens: data.input_tokens || 0,
                    outputTokens: data.output_tokens || 0,
                    cost: data.cost || 0.0,
                });
            } catch (err) {
                console.error('Failed to fetch AI usage', err);
            }
        };
        fetchInitial();
    }, []);

    // SSE stream with automatic reconnection
    useEffect(() => {
        let closed = false;

        const connect = () => {
            if (closed) return;

            const url = getAIUsageStreamUrl();
            const es = new EventSource(url);
            esRef.current = es;

            es.onmessage = (event) => {
                try {
                    const data = JSON.parse(event.data);
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
                } catch (e) {
                    console.error('AI usage SSE parse error', e);
                }
            };

            es.onerror = () => {
                es.close();
                esRef.current = null;
                // Reconnect after a delay instead of giving up permanently
                if (!closed) {
                    reconnectTimerRef.current = setTimeout(connect, 3000);
                }
            };
        };

        connect();

        return () => {
            closed = true;
            esRef.current?.close();
            clearTimeout(reconnectTimerRef.current);
            clearTimeout(glowTimerRef.current);
        };
    }, [triggerGlow]);

    return { ...usage, glowing };
};
