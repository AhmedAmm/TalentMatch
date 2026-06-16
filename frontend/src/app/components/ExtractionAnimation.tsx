import React, { useEffect, useState } from 'react';
import { motion, AnimatePresence } from 'motion/react';
import { FileText, ScanLine, Briefcase, Building2, AlignLeft, Sparkles } from 'lucide-react';

const FIELDS = [
  { key: 'name', label: 'Project Name', icon: Sparkles, color: 'text-indigo-500', sample: 'Atlas Migration' },
  { key: 'client', label: 'Client', icon: Building2, color: 'text-violet-500', sample: 'Acme Corp.' },
  { key: 'desc', label: 'Description', icon: AlignLeft, color: 'text-fuchsia-500', sample: 'Modernize legacy CRM…' },
  { key: 'jobs', label: 'Job Roles', icon: Briefcase, color: 'text-emerald-500', sample: '3 roles detected' },
];

export function ExtractionAnimation() {
  const [foundIdx, setFoundIdx] = useState(-1);

  useEffect(() => {
    const t = setInterval(() => {
      setFoundIdx(i => (i + 1) % (FIELDS.length + 1));
    }, 700);
    return () => clearInterval(t);
  }, []);

  return (
    <div className="relative bg-gradient-to-br from-zinc-50 via-indigo-50/30 to-violet-50/30 dark:from-zinc-900 dark:via-indigo-950/20 dark:to-violet-950/20 rounded-2xl border border-zinc-200 dark:border-zinc-800 p-4 overflow-hidden">
      <div className="flex items-center gap-2 mb-3 text-xs font-bold uppercase tracking-wider text-zinc-500">
        <ScanLine size={14} className="text-indigo-500" />
        Extracting Project Brief
      </div>

      <div className="flex gap-4 items-stretch">
        {/* Animated document */}
        <div className="relative w-20 shrink-0">
          <div className="relative w-16 h-20 mx-auto bg-white dark:bg-zinc-800 rounded-md shadow-md border border-zinc-200 dark:border-zinc-700 overflow-hidden">
            <FileText size={14} className="absolute top-1.5 right-1.5 text-red-400" />
            {[...Array(5)].map((_, i) => (
              <div key={i} className="absolute left-2 right-2 h-0.5 bg-zinc-200 dark:bg-zinc-700 rounded" style={{ top: 8 + i * 5 + 'px' }} />
            ))}
            {/* Scanning beam */}
            <motion.div
              className="absolute left-0 right-0 h-0.5 bg-gradient-to-r from-transparent via-indigo-500 to-transparent shadow-[0_0_8px_rgba(99,102,241,0.8)]"
              animate={{ top: ['0%', '100%', '0%'] }}
              transition={{ duration: 1.6, repeat: Infinity, ease: 'easeInOut' }}
            />
          </div>
        </div>

        {/* Field list — items light up as they're "found" */}
        <div className="flex-1 space-y-1.5 min-w-0">
          {FIELDS.map((f, i) => {
            const Icon = f.icon;
            const isFound = foundIdx >= i;
            const isCurrent = foundIdx === i;
            return (
              <motion.div
                key={f.key}
                initial={false}
                animate={{
                  backgroundColor: isCurrent ? 'rgba(99,102,241,0.08)' : 'rgba(0,0,0,0)',
                }}
                className="flex items-center gap-2 px-2 py-1 rounded-md"
              >
                <Icon size={12} className={isFound ? f.color : 'text-zinc-300'} />
                <span className={`text-xs font-semibold ${isFound ? 'text-zinc-700 dark:text-zinc-300' : 'text-zinc-400'}`}>
                  {f.label}:
                </span>
                <AnimatePresence mode="wait">
                  {isFound && (
                    <motion.span
                      key="val"
                      initial={{ opacity: 0, x: -4 }}
                      animate={{ opacity: 1, x: 0 }}
                      className="text-xs text-zinc-500 truncate font-mono"
                    >
                      {f.sample}
                    </motion.span>
                  )}
                </AnimatePresence>
                {isCurrent && (
                  <motion.span
                    className="ml-auto w-1.5 h-1.5 rounded-full bg-indigo-500 shrink-0"
                    animate={{ opacity: [0.3, 1, 0.3] }}
                    transition={{ duration: 0.8, repeat: Infinity }}
                  />
                )}
              </motion.div>
            );
          })}
        </div>
      </div>
    </div>
  );
}
