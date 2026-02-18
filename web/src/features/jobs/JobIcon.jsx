import React, { useState } from 'react';
import { Briefcase } from 'lucide-react';
// eslint-disable-next-line no-unused-vars
import { motion, AnimatePresence } from 'framer-motion';
import { useJobs } from './useJobs';
import JobModal from './JobModal';

const JobIcon = () => {
    const { activeJobs } = useJobs();
    const [modalOpen, setModalOpen] = useState(false);
    const activeCount = activeJobs.filter(j => ['pending', 'running'].includes(j.status)).length;
    const hasActive = activeCount > 0;

    return (
        <>
            <button
                onClick={() => setModalOpen(true)}
                className={`relative flex items-center justify-center w-10 h-10 rounded-full bg-surface-dark/80 hover:bg-surface-dark border transition-all hover:shadow-neon focus:outline-none focus-visible:ring-2 focus-visible:ring-primary ${hasActive
                        ? 'border-primary/60 shadow-[0_0_12px_rgba(217,70,219,0.4),0_0_30px_rgba(217,70,219,0.2)]'
                        : 'border-white/10 hover:border-primary/50'
                    }`}
                aria-label="View jobs"
                title="Background Jobs"
            >
                <Briefcase
                    size={18}
                    className={hasActive ? 'text-primary' : 'text-slate-400'}
                />

                {/* Hyperbolic glow ring when jobs are active */}
                {hasActive && (
                    <span className="absolute inset-0 rounded-full animate-ping bg-primary/20" style={{ animationDuration: '1.5s' }} />
                )}

                {/* Badge */}
                <AnimatePresence>
                    {hasActive && (
                        <motion.span
                            initial={{ scale: 0 }}
                            animate={{ scale: 1 }}
                            exit={{ scale: 0 }}
                            className="absolute -top-1 -right-1 flex items-center justify-center w-5 h-5 text-[10px] font-bold text-white bg-primary rounded-full shadow-neon border-2 border-background-dark"
                        >
                            {activeCount}
                        </motion.span>
                    )}
                </AnimatePresence>
            </button>

            <AnimatePresence>
                {modalOpen && <JobModal onClose={() => setModalOpen(false)} />}
            </AnimatePresence>
        </>
    );
};

export default JobIcon;
