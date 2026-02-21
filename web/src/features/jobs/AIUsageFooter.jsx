import React, { useEffect, useRef } from 'react';
import { Sparkles } from 'lucide-react';
import { useAIUsage } from './useAIUsage';
import { useJobs } from './useJobs';

const AIUsageFooter = () => {
    const { inputTokens, cost, glowing, startPolling, stopPolling } = useAIUsage();
    const { activeJobs } = useJobs();
    const wasPollingRef = useRef(false);

    // Start/stop AI usage polling based on active jobs
    useEffect(() => {
        const hasActive = activeJobs.some(j => ['pending', 'running'].includes(j.status));
        if (hasActive && !wasPollingRef.current) {
            wasPollingRef.current = true;
            startPolling();
        } else if (!hasActive && wasPollingRef.current) {
            wasPollingRef.current = false;
            stopPolling();
        }
    }, [activeJobs, startPolling, stopPolling]);

    return (
        <div
            className="ai-usage-footer"
            style={{
                position: 'relative',
                overflow: 'hidden',
                display: 'flex',
                alignItems: 'center',
                gap: '0.5rem',
                padding: '0.5rem 0.75rem',
                borderRadius: '0.5rem',
                background: 'rgba(15, 15, 25, 0.6)',
                border: `1px solid ${glowing ? 'rgba(139, 92, 246, 0.3)' : 'rgba(255,255,255,0.05)'}`,
                fontSize: '0.75rem',
                transition: 'border-color 0.3s ease',
            }}
        >
            {/* Shine sweep overlay */}
            {glowing && (
                <span
                    style={{
                        position: 'absolute',
                        inset: 0,
                        background: 'linear-gradient(90deg, transparent 0%, rgba(139,92,246,0.15) 40%, rgba(255,255,255,0.18) 50%, rgba(139,92,246,0.15) 60%, transparent 100%)',
                        animation: 'shineSweep 0.6s ease-out forwards',
                        pointerEvents: 'none',
                        borderRadius: 'inherit',
                    }}
                />
            )}

            <Sparkles
                size={14}
                style={{
                    color: glowing ? '#8b5cf6' : '#64748b',
                    transition: 'color 0.3s ease',
                    animation: glowing ? 'pulse 1s ease-in-out' : 'none',
                }}
            />
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', color: '#94a3b8' }}>
                <span>
                    <span
                        style={{
                            fontFamily: 'monospace',
                            fontWeight: 600,
                            color: glowing ? '#8b5cf6' : '#fff',
                            transition: 'color 0.3s ease',
                        }}
                    >
                        {inputTokens.toLocaleString()}
                    </span>
                    {' tokens'}
                </span>
                <span style={{ color: 'rgba(255,255,255,0.1)' }}>|</span>
                <span>
                    {'$'}
                    <span
                        style={{
                            fontFamily: 'monospace',
                            fontWeight: 600,
                            color: glowing ? '#8b5cf6' : '#fff',
                            transition: 'color 0.3s ease',
                        }}
                    >
                        {cost.toFixed(5)}
                    </span>
                </span>
            </div>

            <style>{`
                @keyframes shineSweep {
                    0% { transform: translateX(-100%); }
                    100% { transform: translateX(100%); }
                }
                @keyframes pulse {
                    0%, 100% { opacity: 1; }
                    50% { opacity: 0.6; }
                }
            `}</style>
        </div>
    );
};

export default AIUsageFooter;
