import React, { useEffect, useState } from 'react';
import { motion, AnimatePresence } from 'motion/react';
import { User, Briefcase, Sparkles } from 'lucide-react';

interface Props {
  /** Number of candidate nodes (left side) */
  candidates?: number;
  /** Job titles (right side) */
  jobs?: string[];
  /** Whether to keep cycling. Set to false when done. */
  active?: boolean;
}

/**
 * Animated bipartite-matching visualization. Lines flicker between candidate
 * dots and job dots, with scores popping in to simulate the algorithm.
 */
export function BipartiteMatching({ candidates = 6, jobs = ['Frontend', 'Backend', 'Design'], active = true }: Props) {
  const [tick, setTick] = useState(0);
  const [edges, setEdges] = useState<{ from: number; to: number; score: number; id: number }[]>([]);

  useEffect(() => {
    if (!active) return;
    const interval = setInterval(() => {
      setTick(t => t + 1);
      setEdges(prev => {
        const next = [...prev];
        // Add random edge
        const from = Math.floor(Math.random() * candidates);
        const to = Math.floor(Math.random() * jobs.length);
        const score = Math.floor(Math.random() * 60 + 40);
        next.push({ from, to, score, id: Date.now() + Math.random() });
        // Cap to last 10 edges
        return next.slice(-10);
      });
    }, 400);
    return () => clearInterval(interval);
  }, [active, candidates, jobs.length]);

  const width = 360;
  const height = 180;
  const leftX = 50;
  const rightX = width - 70;

  const candidateY = (i: number) => 30 + i * ((height - 60) / Math.max(candidates - 1, 1));
  const jobY = (i: number) => 30 + i * ((height - 60) / Math.max(jobs.length - 1, 1));

  return (
    <div className="relative bg-gradient-to-br from-zinc-50 via-indigo-50/30 to-violet-50/30 dark:from-zinc-900 dark:via-indigo-950/20 dark:to-violet-950/20 rounded-2xl border border-zinc-200 dark:border-zinc-800 overflow-hidden">
      {/* Background grid */}
      <div className="absolute inset-0 opacity-[0.04]" style={{
        backgroundImage: 'radial-gradient(circle, currentColor 1px, transparent 1px)',
        backgroundSize: '20px 20px'
      }} />

      {/* Header */}
      <div className="relative px-5 pt-4 pb-2 flex items-center gap-2 text-xs font-bold uppercase tracking-wider text-zinc-500">
        <Sparkles size={14} className="text-amber-500" />
        Bipartite Matching Algorithm
        <motion.span
          className="ml-auto flex items-center gap-1.5 text-indigo-600 normal-case tracking-normal"
          animate={{ opacity: [0.5, 1, 0.5] }}
          transition={{ duration: 1.5, repeat: Infinity }}
        >
          <span className="w-1.5 h-1.5 rounded-full bg-indigo-500" />
          Computing optimal pairing...
        </motion.span>
      </div>

      <svg viewBox={`0 0 ${width} ${height}`} className="w-full h-auto block max-h-48 mx-auto">
        {/* Column labels */}
        <text x={leftX} y={18} textAnchor="middle" className="fill-zinc-400" fontSize="10" fontWeight="bold">CANDIDATES</text>
        <text x={rightX} y={18} textAnchor="middle" className="fill-zinc-400" fontSize="10" fontWeight="bold">POSITIONS</text>

        {/* Edges */}
        <AnimatePresence>
          {edges.map(edge => {
            const y1 = candidateY(edge.from);
            const y2 = jobY(edge.to);
            const strong = edge.score >= 75;
            return (
              <motion.line
                key={edge.id}
                initial={{ pathLength: 0, opacity: 0 }}
                animate={{ pathLength: 1, opacity: strong ? 0.8 : 0.3 }}
                exit={{ opacity: 0 }}
                transition={{ duration: 0.5 }}
                x1={leftX} y1={y1} x2={rightX} y2={y2}
                stroke={strong ? '#6366f1' : '#a78bfa'}
                strokeWidth={strong ? 2 : 1}
                strokeDasharray={strong ? '0' : '4 4'}
              />
            );
          })}
        </AnimatePresence>

        {/* Score bubbles on strong edges */}
        <AnimatePresence>
          {edges.filter(e => e.score >= 75).slice(-3).map(edge => {
            const y1 = candidateY(edge.from);
            const y2 = jobY(edge.to);
            const mx = (leftX + rightX) / 2;
            const my = (y1 + y2) / 2;
            return (
              <motion.g
                key={`bubble-${edge.id}`}
                initial={{ scale: 0, opacity: 0 }}
                animate={{ scale: 1, opacity: 1 }}
                exit={{ scale: 0, opacity: 0 }}
                transition={{ type: 'spring', damping: 12 }}
              >
                <rect x={mx - 18} y={my - 9} width={36} height={18} rx={9} fill="#10b981" />
                <text x={mx} y={my + 4} textAnchor="middle" fill="white" fontSize="10" fontWeight="bold">
                  {edge.score}%
                </text>
              </motion.g>
            );
          })}
        </AnimatePresence>

        {/* Candidate nodes */}
        {Array.from({ length: candidates }).map((_, i) => (
          <motion.circle
            key={`c-${i}`}
            cx={leftX} cy={candidateY(i)} r={10}
            fill="#fff"
            stroke="#6366f1"
            strokeWidth={2}
            animate={{
              scale: edges.some(e => e.from === i && e.id === edges[edges.length - 1]?.id) ? [1, 1.4, 1] : 1,
            }}
            transition={{ duration: 0.5 }}
          />
        ))}

        {/* Job nodes */}
        {jobs.map((job, i) => (
          <g key={`j-${i}`}>
            <motion.circle
              cx={rightX} cy={jobY(i)} r={12}
              fill="#fff"
              stroke="#8b5cf6"
              strokeWidth={2}
              animate={{
                scale: edges.some(e => e.to === i && e.id === edges[edges.length - 1]?.id) ? [1, 1.4, 1] : 1,
              }}
              transition={{ duration: 0.5 }}
            />
            <text
              x={rightX + 22} y={jobY(i) + 4}
              fontSize="10" fontWeight="600"
              className="fill-zinc-600 dark:fill-zinc-400"
            >
              {job.length > 14 ? job.slice(0, 12) + '…' : job}
            </text>
          </g>
        ))}
      </svg>

      {/* Footer counter */}
      <div className="relative px-5 pb-4 pt-1 flex items-center justify-between text-xs text-zinc-500">
        <span className="flex items-center gap-1.5"><User size={12} /> {candidates} candidates evaluated</span>
        <span className="font-mono">Iter #{tick}</span>
        <span className="flex items-center gap-1.5"><Briefcase size={12} /> {jobs.length} positions</span>
      </div>
    </div>
  );
}
