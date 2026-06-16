import React, { useEffect, useState } from 'react';
import { motion, AnimatePresence } from 'motion/react';
import { FileText, ScanLine, Brain, Database, CheckCircle2, Sparkles } from 'lucide-react';

interface Props {
  open: boolean;
  fileName?: string;
  done?: boolean;
  onClose?: () => void;
}

const STAGES = [
  { key: 'reading', label: 'Reading PDF document', icon: FileText, color: 'text-indigo-500' },
  { key: 'ocr', label: 'Scanning and extracting text', icon: ScanLine, color: 'text-violet-500' },
  { key: 'ai', label: 'AI analyzing skills & experience', icon: Brain, color: 'text-fuchsia-500' },
  { key: 'index', label: 'Indexing into talent database', icon: Database, color: 'text-emerald-500' },
];

export function CVProcessingOverlay({ open, fileName, done, onClose }: Props) {
  const [stage, setStage] = useState(0);

  useEffect(() => {
    if (!open) { setStage(0); return; }
    if (done) { setStage(STAGES.length); return; }
    const timer = setInterval(() => {
      setStage(s => (s < STAGES.length - 1 ? s + 1 : s));
    }, 1400);
    return () => clearInterval(timer);
  }, [open, done]);

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
            initial={{ scale: 0.9, y: 20 }}
            animate={{ scale: 1, y: 0 }}
            exit={{ scale: 0.95, opacity: 0 }}
            transition={{ type: 'spring', damping: 22 }}
            className="bg-white dark:bg-zinc-900 rounded-3xl shadow-2xl max-w-md w-full overflow-hidden border border-zinc-200 dark:border-zinc-800"
          >
            {/* Animated header */}
            <div className="relative h-40 bg-gradient-to-br from-indigo-600 via-violet-600 to-fuchsia-600 overflow-hidden flex items-center justify-center">
              {/* Floating particles */}
              {[...Array(12)].map((_, i) => (
                <motion.div
                  key={i}
                  className="absolute w-1.5 h-1.5 rounded-full bg-white/40"
                  initial={{ x: Math.random() * 400 - 200, y: 100, opacity: 0 }}
                  animate={{
                    y: -100,
                    opacity: [0, 1, 0],
                    x: Math.random() * 400 - 200,
                  }}
                  transition={{
                    duration: 2 + Math.random() * 2,
                    repeat: Infinity,
                    delay: i * 0.2,
                  }}
                />
              ))}

              <AnimatePresence mode="wait">
                {done ? (
                  <motion.div
                    key="done"
                    initial={{ scale: 0, rotate: -180 }}
                    animate={{ scale: 1, rotate: 0 }}
                    transition={{ type: 'spring', damping: 12 }}
                    className="relative z-10"
                  >
                    <div className="w-24 h-24 rounded-full bg-white/20 backdrop-blur flex items-center justify-center">
                      <CheckCircle2 size={48} className="text-white" />
                    </div>
                  </motion.div>
                ) : (
                  <motion.div
                    key="processing"
                    className="relative z-10"
                    animate={{ rotate: [0, 360] }}
                    transition={{ duration: 8, repeat: Infinity, ease: 'linear' }}
                  >
                    <div className="w-24 h-24 rounded-full border-4 border-white/30 border-t-white flex items-center justify-center">
                      <motion.div
                        animate={{ rotate: [0, -360] }}
                        transition={{ duration: 8, repeat: Infinity, ease: 'linear' }}
                      >
                        <FileText size={36} className="text-white" />
                      </motion.div>
                    </div>
                  </motion.div>
                )}
              </AnimatePresence>
            </div>

            <div className="p-6">
              <h3 className="text-lg font-bold text-center mb-1">
                {done ? 'CV Processed Successfully' : 'Processing CV...'}
              </h3>
              {fileName && (
                <p className="text-xs text-zinc-500 text-center mb-5 truncate">{fileName}</p>
              )}

              {/* Stage list */}
              <div className="space-y-2.5">
                {STAGES.map((s, i) => {
                  const Icon = s.icon;
                  const isActive = i === stage && !done;
                  const isDone = i < stage || done;
                  return (
                    <motion.div
                      key={s.key}
                      initial={{ opacity: 0, x: -10 }}
                      animate={{ opacity: 1, x: 0 }}
                      transition={{ delay: i * 0.1 }}
                      className={`flex items-center gap-3 p-2.5 rounded-xl transition-all ${
                        isActive ? 'bg-indigo-50 dark:bg-indigo-900/20' : ''
                      }`}
                    >
                      <div className={`w-8 h-8 rounded-lg flex items-center justify-center shrink-0 ${
                        isDone ? 'bg-emerald-100 dark:bg-emerald-900/30 text-emerald-600' :
                        isActive ? 'bg-white dark:bg-zinc-800 shadow' : 'bg-zinc-100 dark:bg-zinc-800/50'
                      }`}>
                        {isDone ? (
                          <CheckCircle2 size={16} />
                        ) : isActive ? (
                          <motion.div animate={{ scale: [1, 1.2, 1] }} transition={{ duration: 1, repeat: Infinity }}>
                            <Icon size={16} className={s.color} />
                          </motion.div>
                        ) : (
                          <Icon size={16} className="text-zinc-400" />
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
                    </motion.div>
                  );
                })}
              </div>

              {done && onClose && (
                <motion.button
                  initial={{ opacity: 0, y: 10 }}
                  animate={{ opacity: 1, y: 0 }}
                  onClick={onClose}
                  className="w-full mt-6 bg-gradient-to-r from-indigo-600 to-violet-600 text-white font-bold rounded-xl py-3 flex items-center justify-center gap-2 shadow-lg shadow-indigo-600/20"
                >
                  <Sparkles size={16} /> Done
                </motion.button>
              )}
            </div>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
