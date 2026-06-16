import React, { useEffect, useState } from 'react';
import { motion, AnimatePresence } from 'motion/react';
import { FileText, Wand2, Sparkles, Download } from 'lucide-react';

interface Props {
  open: boolean;
  employeeName?: string;
}

const STAGES = [
  { label: 'Analyzing job requirements', icon: Wand2 },
  { label: 'Tailoring experience & skills', icon: Sparkles },
  { label: 'Composing the document', icon: FileText },
  { label: 'Preparing download', icon: Download },
];

export function CVGeneratingOverlay({ open, employeeName }: Props) {
  const [stage, setStage] = useState(0);

  useEffect(() => {
    if (!open) { setStage(0); return; }
    const t = setInterval(() => {
      setStage(s => (s < STAGES.length - 1 ? s + 1 : s));
    }, 1500);
    return () => clearInterval(t);
  }, [open]);

  return (
    <AnimatePresence>
      {open && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          className="fixed inset-0 z-50 flex items-center justify-center bg-zinc-950/60 backdrop-blur-md p-4"
        >
          <motion.div
            initial={{ scale: 0.95, y: 12 }}
            animate={{ scale: 1, y: 0 }}
            exit={{ scale: 0.95, opacity: 0 }}
            className="bg-white dark:bg-zinc-900 rounded-2xl shadow-2xl max-w-sm w-full overflow-hidden border border-zinc-200 dark:border-zinc-800"
          >
            <div className="relative h-32 bg-gradient-to-br from-indigo-600 via-violet-600 to-fuchsia-600 flex items-center justify-center overflow-hidden">
              {[...Array(8)].map((_, i) => (
                <motion.div
                  key={i}
                  className="absolute w-1 h-1 rounded-full bg-white/50"
                  initial={{ x: Math.random() * 300 - 150, y: 80 }}
                  animate={{ y: -80, opacity: [0, 1, 0] }}
                  transition={{ duration: 2, repeat: Infinity, delay: i * 0.25 }}
                />
              ))}
              <motion.div
                className="relative z-10 w-20 h-20 rounded-2xl bg-white/15 backdrop-blur flex items-center justify-center"
                animate={{ rotate: [0, 6, -6, 0] }}
                transition={{ duration: 2.5, repeat: Infinity, ease: 'easeInOut' }}
              >
                <FileText size={36} className="text-white" />
                <motion.div
                  className="absolute -top-2 -right-2 w-8 h-8 rounded-full bg-amber-400 flex items-center justify-center shadow-lg"
                  animate={{ scale: [1, 1.15, 1], rotate: [0, 12, 0] }}
                  transition={{ duration: 1.6, repeat: Infinity }}
                >
                  <Sparkles size={16} className="text-white" />
                </motion.div>
              </motion.div>
            </div>

            <div className="p-5">
              <h3 className="font-bold text-center mb-1">Generating Tailored CV</h3>
              <p className="text-xs text-zinc-500 text-center mb-4 truncate">
                {employeeName ? `for ${employeeName}` : 'Please wait...'}
              </p>

              <div className="space-y-2">
                {STAGES.map((s, i) => {
                  const Icon = s.icon;
                  const isDone = i < stage;
                  const isActive = i === stage;
                  return (
                    <div
                      key={s.label}
                      className={`flex items-center gap-2.5 p-2 rounded-lg ${isActive ? 'bg-indigo-50 dark:bg-indigo-900/20' : ''}`}
                    >
                      <div className={`w-7 h-7 rounded-md flex items-center justify-center shrink-0 ${
                        isDone ? 'bg-emerald-100 dark:bg-emerald-900/30 text-emerald-600' :
                        isActive ? 'bg-white dark:bg-zinc-800 shadow text-indigo-500' : 'bg-zinc-100 dark:bg-zinc-800/50 text-zinc-400'
                      }`}>
                        {isActive ? (
                          <motion.div animate={{ scale: [1, 1.15, 1] }} transition={{ duration: 1, repeat: Infinity }}>
                            <Icon size={14} />
                          </motion.div>
                        ) : (
                          <Icon size={14} />
                        )}
                      </div>
                      <span className={`text-sm flex-1 ${
                        isDone ? 'text-zinc-400 line-through' :
                        isActive ? 'font-semibold text-zinc-900 dark:text-zinc-100' : 'text-zinc-500'
                      }`}>
                        {s.label}
                      </span>
                      {isActive && (
                        <motion.div
                          className="w-1.5 h-1.5 rounded-full bg-indigo-500"
                          animate={{ opacity: [0.3, 1, 0.3] }}
                          transition={{ duration: 1, repeat: Infinity }}
                        />
                      )}
                    </div>
                  );
                })}
              </div>

              <p className="text-[11px] text-center text-zinc-400 italic mt-4">
                This may take a few moments...
              </p>
            </div>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
