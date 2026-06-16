import React, { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router';
import { api, Project, Match, Candidate } from '../api/apiClient';
import {
  CheckCircle2, XCircle, Clock, Search, ArrowLeft, Star, FileText,
  AlertCircle, RefreshCw, Briefcase, ChevronDown, ChevronUp, Sparkles,
  Loader2, ThumbsUp, ThumbsDown, Zap, Users
} from 'lucide-react';
import clsx from 'clsx';
import { CVGeneratingOverlay } from '../components/CVGeneratingOverlay';

export function POProjectDetails() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();

  const [project, setProject] = useState<Project | null>(null);
  const [matches, setMatches] = useState<Match[]>([]);
  const [loading, setLoading] = useState(true);
  /** Tracks per-match pending actions for inline feedback (no full-page reload). */
  const [pendingMatchIds, setPendingMatchIds] = useState<Set<string>>(new Set());
  const [generatingCV, setGeneratingCV] = useState<{ name: string } | null>(null);
  const markPending = (id: string, on: boolean) => {
    setPendingMatchIds(prev => {
      const next = new Set(prev);
      if (on) next.add(id); else next.delete(id);
      return next;
    });
  };

  // Candidate search state — keyed by "jobId::slotIndex"
  const [swapSlotKey, setSwapSlotKey] = useState<string | null>(null);
  const [candidates, setCandidates] = useState<Candidate[]>([]);
  const [candidatesLoading, setCandidatesLoading] = useState(false);
  const [swapSearch, setSwapSearch] = useState('');

  // Explanation state
  const [expandedExplanation, setExpandedExplanation] = useState<string | null>(null);
  const [explanationLoading, setExplanationLoading] = useState<string | null>(null);
  const [explanations, setExplanations] = useState<Record<string, string>>({});

  useEffect(() => { loadData(); }, [id]);

  // ── Single composite load — 1 API call instead of 3 ──────────────────
  const loadData = async () => {
    if (!id) return;
    setLoading(true);
    try {
      const { project: proj, matches: m } = await api.getProjectDetails(id);
      setProject(proj);
      setMatches(m);
      // Pre-load explanations from matches
      const existing: Record<string, string> = {};
      m.forEach(match => { if (match.explanation) existing[match.id] = match.explanation; });
      setExplanations(prev => ({ ...prev, ...existing }));
    } catch (e: any) {
      console.error(e);
      if (e.status === 404) navigate('/');
    }
    setLoading(false);
  };

  /** Update local matches from action response, or silently re-fetch without spinner */
  const applyMatches = async (updatedMatches: Match[] | null) => {
    if (updatedMatches) {
      setMatches(updatedMatches);
      const existing: Record<string, string> = {};
      updatedMatches.forEach(m => { if (m.explanation) existing[m.id] = m.explanation; });
      setExplanations(prev => ({ ...prev, ...existing }));
    } else if (id) {
      // Silent re-fetch — keep page UI mounted, no full-screen loader
      try {
        const { project: proj, matches: m } = await api.getProjectDetails(id);
        setProject(proj);
        setMatches(m);
      } catch (e) { console.error(e); }
    }
  };

  const handleUpdateStatus = async (status: Project['status']) => {
    if (!project) return;
    try {
      const updated = await api.updateProjectStatus(project.id, status);
      setProject(updated);
    } catch (e: any) {
      alert(e.message);
    }
  };

  const handleAccept = async (matchId: string) => {
    markPending(matchId, true);
    try {
      const updatedMatches = await api.acceptMatch(matchId);
      await applyMatches(updatedMatches);
    } catch (e: any) {
      alert(e.message);
    } finally {
      markPending(matchId, false);
    }
  };

  const handleReject = async (matchId: string) => {
    markPending(matchId, true);
    try {
      const result = await api.rejectMatch(matchId);
      if (result.matches) {
        await applyMatches(result.matches);
        return;
      }
      if (result.suggestion) {
        const suggestionId = result.suggestion.id || result.suggestion.matchId;
        if (!suggestionId) {
          const match = matches.find(m => m.id === matchId);
          if (match && project) {
            const empId = result.suggestion.employeeId || result.suggestion.employee_id;
            if (empId) {
              const assignResult = await api.manualAssign(project.id, match.jobId, empId);
              if (assignResult.matches) { await applyMatches(assignResult.matches); return; }
            }
          }
        }
      }
      await applyMatches(null);
    } catch (e: any) {
      alert(e.message);
    } finally {
      markPending(matchId, false);
    }
  };

  const handleUnassign = async (matchId: string) => {
    if (!confirm('Unassign this employee? The system will suggest a replacement.')) return;
    markPending(matchId, true);
    try {
      const updatedMatches = await api.unassignMatch(matchId);
      await applyMatches(updatedMatches);
    } catch (e: any) {
      alert(e.message);
    } finally {
      markPending(matchId, false);
    }
  };

  const handleGenerateCV = async (employeeId: string, jobId: string) => {
    if (!project) return;
    const emp = matches.find(m => m.employeeId === employeeId)?.employee;
    setGeneratingCV({ name: emp?.name || 'Employee' });
    try {
      const blob = await api.generateCV(employeeId, project.id, jobId);
      const url = URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = `${(emp?.name || 'Employee').replace(/ /g, '_')}_Tailored_CV.docx`;
      link.click();
      URL.revokeObjectURL(url);
    } catch (e: any) {
      alert(e.message || 'Error generating CV');
    } finally {
      setGeneratingCV(null);
    }
  };

  const handleOpenCandidateSearch = async (jobId: string, slotIndex: number) => {
    if (!project) return;
    const key = `${jobId}::${slotIndex}`;
    if (swapSlotKey === key) { setSwapSlotKey(null); return; }
    setSwapSlotKey(key);
    setCandidatesLoading(true);
    setCandidates([]);
    setSwapSearch('');
    try {
      const results = await api.searchCandidates(project.id, jobId);
      setCandidates(results);
    } catch (e: any) {
      console.error('Failed to search candidates:', e);
      setCandidates([]);
    }
    setCandidatesLoading(false);
  };

  const handleManualAssign = async (jobId: string, employeeId: string, oldMatchId?: string) => {
    if (!project) return;
    if (oldMatchId) markPending(oldMatchId, true);
    try {
      const result = await api.manualAssign(project.id, jobId, employeeId, oldMatchId);
      setSwapSlotKey(null);
      setSwapSearch('');
      setCandidates([]);
      await applyMatches(result.matches);
    } catch (e: any) {
      alert(e.message);
    } finally {
      if (oldMatchId) markPending(oldMatchId, false);
    }
  };

  const handleLoadExplanation = async (matchId: string, jobId: string, employeeId: string) => {
    if (!project) return;
    if (expandedExplanation === matchId) { setExpandedExplanation(null); return; }
    setExpandedExplanation(matchId);
    if (explanations[matchId]) return;
    setExplanationLoading(matchId);
    try {
      const text = await api.explainCandidateFit(project.id, jobId, employeeId);
      setExplanations(prev => ({ ...prev, [matchId]: text }));
    } catch {
      setExplanations(prev => ({ ...prev, [matchId]: 'Could not load explanation.' }));
    }
    setExplanationLoading(null);
  };

  if (loading || !project) return <div className="animate-pulse p-8">Loading project details...</div>;

  const totalSlots = project.jobs.reduce((sum, j) => sum + j.headcount, 0);
  const totalAccepted = matches.filter(m => m.status === 'ACCEPTED').length;

  // ── Helpers ──────────────────────────────────────────────────────────────

  const renderScoreBadge = (score: number) => {
    const color = score >= 80 ? 'text-green-700 bg-green-100 dark:bg-green-900/40 dark:text-green-400'
      : score >= 60 ? 'text-amber-700 bg-amber-100 dark:bg-amber-900/40 dark:text-amber-400'
      : 'text-red-700 bg-red-100 dark:bg-red-900/40 dark:text-red-400';
    return (
      <div className={clsx('flex items-center gap-1 px-3 py-1 rounded-full text-sm font-black shadow-sm', color)}>
        <Star size={16} fill="currentColor" />
        {Math.round(score)}%
      </div>
    );
  };

  const getJobSlots = (jobId: string, headcount: number) => {
    const jobMatches = matches.filter(m => m.jobId === jobId);
    const accepted = jobMatches.filter(m => m.status === 'ACCEPTED');
    const pending = jobMatches.filter(m => m.status === 'PENDING').sort((a, b) => b.scorePercentage - a.scorePercentage);
    const slots: (Match | null)[] = [];
    const usedIds = new Set<string>();
    for (const m of accepted) { if (slots.length < headcount) { slots.push(m); usedIds.add(m.id); } }
    for (const m of pending) { if (slots.length >= headcount) break; if (!usedIds.has(m.id)) { slots.push(m); usedIds.add(m.id); } }
    while (slots.length < headcount) slots.push(null);
    return slots;
  };

  // ── Candidate Search Panel ────────────────────────────────────────────

  const renderCandidateSearch = (jobId: string, slotIndex: number, currentMatchId?: string) => {
    const key = `${jobId}::${slotIndex}`;
    if (swapSlotKey !== key) return null;

    const filteredCandidates = candidates.filter(c =>
      c.name.toLowerCase().includes(swapSearch.toLowerCase()) ||
      c.employee_id.toLowerCase().includes(swapSearch.toLowerCase())
    );

    return (
      <div className="mt-4 bg-zinc-50 dark:bg-zinc-800/80 rounded-xl border border-zinc-200 dark:border-zinc-700 p-4 shadow-inner">
        <div className="flex items-center justify-between mb-3">
          <h4 className="text-sm font-black flex items-center gap-2 text-zinc-800 dark:text-zinc-200">
            <Zap size={16} className="text-indigo-500" /> Smart Candidate Search
          </h4>
          <button onClick={() => setSwapSlotKey(null)} className="text-zinc-400 hover:text-zinc-600 dark:hover:text-zinc-300">
            <XCircle size={18} />
          </button>
        </div>
        <div className="relative mb-3">
          <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-zinc-400" />
          <input type="text" placeholder="Filter candidates..." value={swapSearch} onChange={e => setSwapSearch(e.target.value)}
            className="w-full bg-white dark:bg-zinc-900 border border-zinc-300 dark:border-zinc-600 rounded-lg pl-9 pr-3 py-2 text-sm focus:ring-2 focus:ring-indigo-500 outline-none" />
        </div>

        {candidatesLoading ? (
          <div className="flex items-center justify-center py-8 gap-2 text-zinc-500">
            <Loader2 size={20} className="animate-spin" /> Searching candidates...
          </div>
        ) : (
          <div className="max-h-80 overflow-y-auto space-y-2 pr-1">
            {filteredCandidates.map(candidate => {
              const isAssigned = matches.some(m => m.employeeId === candidate.employee_id && (m.status === 'ACCEPTED' || m.status === 'PENDING'));
              return (
                <div key={candidate.employee_id}
                  onClick={() => !isAssigned && handleManualAssign(jobId, candidate.employee_id, currentMatchId)}
                  className={clsx("p-3 rounded-lg border transition-colors",
                    isAssigned ? "opacity-50 grayscale cursor-not-allowed bg-zinc-100 dark:bg-zinc-900/50 border-zinc-200 dark:border-zinc-700"
                      : "cursor-pointer hover:border-indigo-400 hover:bg-white dark:hover:bg-zinc-800 bg-white dark:bg-zinc-800 border-zinc-200 dark:border-zinc-700"
                  )}>
                  <div className="flex justify-between items-center mb-2">
                    <div className="flex items-center gap-3">
                      <div className="w-8 h-8 rounded-full bg-indigo-100 dark:bg-indigo-900 text-indigo-700 dark:text-indigo-300 flex items-center justify-center font-black text-xs">
                        {candidate.name.charAt(0)}
                      </div>
                      <div>
                        <h5 className="font-black text-sm leading-tight">{candidate.name}</h5>
                        <p className="text-xs text-zinc-500">{candidate.employee_id}</p>
                      </div>
                    </div>
                    <div className="flex items-center gap-2">
                      {isAssigned && <span className="text-xs text-amber-600 font-black">In project</span>}
                      {renderScoreBadge(candidate.score_percentage || Math.round(candidate.matching_score * 100))}
                    </div>
                  </div>
                  {(candidate.matched_skills?.length > 0 || candidate.missing_skills?.length > 0) && (
                    <div className="mt-2 flex flex-wrap gap-1.5">
                      {candidate.matched_skills?.slice(0, 5).map((s, i) => (
                        <span key={`m-${i}`} className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-green-50 dark:bg-green-900/20 text-green-700 dark:text-green-400 text-xs font-bold">
                          <ThumbsUp size={10} /> {typeof s === 'string' ? s : s.skill}
                        </span>
                      ))}
                      {candidate.missing_skills?.slice(0, 3).map((s, i) => (
                        <span key={`x-${i}`} className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-red-50 dark:bg-red-900/20 text-red-600 dark:text-red-400 text-xs font-bold">
                          <ThumbsDown size={10} /> {typeof s === 'string' ? s : s.skill}
                        </span>
                      ))}
                    </div>
                  )}
                  {candidate.explanation && (
                    <p className="mt-2 text-xs text-zinc-500 dark:text-zinc-400 italic line-clamp-2">{candidate.explanation}</p>
                  )}
                </div>
              );
            })}
            {filteredCandidates.length === 0 && (
              <div className="text-center py-4 text-zinc-500 text-sm">No candidates found.</div>
            )}
          </div>
        )}
      </div>
    );
  };

  // ── Employee Card ─────────────────────────────────────────────────────

  const renderEmployeeCard = (match: Match, job: { id: string; title: string }, slotIndex: number) => {
    const emp = match.employee;
    if (!emp) return null;
    const isPending = match.status === 'PENDING';
    const isAccepted = match.status === 'ACCEPTED';
    const isExpanded = expandedExplanation === match.id;
    const explanationText = explanations[match.id] || match.explanation || '';
    const isBusy = pendingMatchIds.has(match.id);

    return (
      <div
        className={clsx("rounded-2xl border p-5 shadow-sm flex flex-col gap-4 relative overflow-hidden",
        isAccepted ? "bg-green-50/50 dark:bg-green-900/10 border-green-200 dark:border-green-900/50" : "bg-white dark:bg-zinc-900 border-zinc-200 dark:border-zinc-800"
      )}>
        {isBusy && (
          <div className="absolute inset-0 bg-white/70 dark:bg-zinc-900/70 backdrop-blur-sm z-20 flex items-center justify-center rounded-2xl">
            <div className="flex items-center gap-2 px-4 py-2 bg-white dark:bg-zinc-800 rounded-full shadow-lg border border-zinc-200 dark:border-zinc-700">
              <Loader2 size={16} className="animate-spin text-indigo-600" />
              <span className="text-xs font-bold text-zinc-700 dark:text-zinc-200">Updating...</span>
            </div>
          </div>
        )}
        {isAccepted && (
          <div className="absolute top-0 right-0 bg-green-500 text-white text-xs font-black px-3 py-1 rounded-bl-lg flex items-center gap-1 shadow-sm">
            <CheckCircle2 size={14} /> ASSIGNED
          </div>
        )}
        <div className="flex justify-between items-start pt-2">
          <div className="flex items-center gap-4 cursor-pointer group" onClick={() => navigate(`/employee/${emp.id}`)}>
            {emp.avatarUrl ? (
              <img src={emp.avatarUrl} alt={emp.name} className="w-14 h-14 rounded-full object-cover group-hover:ring-4 ring-indigo-100 dark:ring-indigo-900/50 transition-all shadow-sm" />
            ) : (
              <div className="w-14 h-14 rounded-full bg-indigo-100 dark:bg-indigo-900 text-indigo-700 dark:text-indigo-300 flex items-center justify-center font-black text-xl group-hover:ring-4 ring-indigo-50 dark:ring-indigo-900/30 transition-all shadow-sm">
                {emp.name.charAt(0)}
              </div>
            )}
            <div>
              <h3 className="text-lg font-black group-hover:text-indigo-600 transition-colors">{emp.name}</h3>
              <p className="text-sm text-zinc-500 mb-1">{emp.email}</p>
            </div>
          </div>
          <div className="flex flex-col items-end gap-2">
            {renderScoreBadge(match.scorePercentage)}
          </div>
        </div>

        {/* Explanation Section */}
        <div className="bg-zinc-50 dark:bg-zinc-800/50 rounded-xl border border-zinc-100 dark:border-zinc-800/80 overflow-hidden">
          <button
            onClick={() => handleLoadExplanation(match.id, match.jobId, match.employeeId)}
            className="w-full p-4 flex items-center justify-between hover:bg-zinc-100/50 dark:hover:bg-zinc-700/30 transition-colors"
          >
            <h4 className="text-xs font-black text-zinc-500 uppercase tracking-wider flex items-center gap-1.5">
              <Sparkles size={14} className="text-amber-500" /> AI Explainability Report
            </h4>
            {explanationLoading === match.id ? (
              <Loader2 size={16} className="animate-spin text-zinc-400" />
            ) : (
              isExpanded ? <ChevronUp size={16} className="text-zinc-400" /> : <ChevronDown size={16} className="text-zinc-400" />
            )}
          </button>
          {isExpanded && (
            <div className="px-4 pb-4 border-t border-zinc-100 dark:border-zinc-800/80">
              {explanationLoading === match.id ? (
                <div className="flex items-center gap-2 py-3 text-sm text-zinc-500">
                  <Loader2 size={16} className="animate-spin" /> Generating explanation...
                </div>
              ) : explanationText ? (
                <div className="pt-3 text-sm text-zinc-700 dark:text-zinc-300 leading-relaxed whitespace-pre-wrap">
                  {explanationText}
                </div>
              ) : (
                <p className="pt-3 text-sm text-zinc-400 italic">No explanation available.</p>
              )}
            </div>
          )}
        </div>

        {match.matchReason && !isExpanded && (
          <p className="text-sm text-zinc-500 italic px-1">"{match.matchReason}"</p>
        )}

        <div className="flex flex-wrap gap-2 mt-2">
          {isPending && (
            <>
              <button disabled={isBusy} onClick={() => handleAccept(match.id)} className="flex-1 min-w-[120px] disabled:opacity-50 bg-green-600 hover:bg-green-700 text-white font-black rounded-xl px-4 py-2.5 transition-colors flex items-center justify-center gap-2 shadow-sm">
                <CheckCircle2 size={18} /> Accept
              </button>
              <button onClick={() => handleReject(match.id)} className="flex-1 min-w-[120px] bg-red-100 hover:bg-red-200 dark:bg-red-900/30 dark:hover:bg-red-900/50 text-red-700 dark:text-red-400 font-black rounded-xl px-4 py-2.5 transition-colors flex items-center justify-center gap-2" title="Reject and auto-suggest next candidate">
                <XCircle size={18} /> Reject (Next)
              </button>
              <button onClick={() => handleOpenCandidateSearch(job.id, slotIndex)} className="flex-none bg-zinc-100 hover:bg-zinc-200 dark:bg-zinc-800 dark:hover:bg-zinc-700 text-zinc-700 dark:text-zinc-300 font-black rounded-xl px-4 py-2.5 transition-colors flex items-center justify-center gap-2">
                <RefreshCw size={18} /> Swap
              </button>
            </>
          )}
          {isAccepted && (
            <button onClick={() => handleUnassign(match.id)} className="flex-1 bg-red-50 hover:bg-red-100 dark:bg-red-900/20 dark:hover:bg-red-900/40 text-red-600 dark:text-red-400 font-black rounded-xl px-4 py-2.5 transition-colors flex items-center justify-center gap-2">
              <XCircle size={18} /> Unassign
            </button>
          )}
          <button onClick={() => handleGenerateCV(match.employeeId, job.id)}
            className={clsx("flex-none font-black rounded-xl px-4 py-2.5 transition-colors flex items-center justify-center gap-2 shadow-sm",
              isAccepted ? "bg-indigo-600 hover:bg-indigo-700 text-white flex-1" : "bg-indigo-50 hover:bg-indigo-100 dark:bg-indigo-900/30 dark:hover:bg-indigo-900/50 text-indigo-700 dark:text-indigo-400"
            )}>
            <FileText size={18} /> Tailored CV
          </button>
        </div>
      </div>
    );
  };

  // ── Empty Slot ────────────────────────────────────────────────────────

  const renderEmptySlot = (job: { id: string; title: string }, slotIndex: number) => (
    <div className="border-2 border-dashed border-zinc-300 dark:border-zinc-700 rounded-2xl p-6 text-center bg-zinc-50/50 dark:bg-zinc-800/20">
      <div className="w-12 h-12 rounded-full bg-zinc-200 dark:bg-zinc-700 flex items-center justify-center mx-auto mb-3">
        <AlertCircle size={24} className="text-zinc-400" />
      </div>
      <h4 className="font-black text-zinc-600 dark:text-zinc-400 mb-1">Position {slotIndex + 1} — Open</h4>
      <p className="text-sm text-zinc-500 mb-4">No candidate assigned yet.</p>
      <button onClick={() => handleOpenCandidateSearch(job.id, slotIndex)}
        className="bg-white dark:bg-zinc-800 border border-zinc-300 dark:border-zinc-600 hover:bg-zinc-50 dark:hover:bg-zinc-700 font-black rounded-lg px-6 py-2 transition-colors inline-flex items-center gap-2 text-sm shadow-sm">
        <Search size={16} /> Search Candidates
      </button>
      <div className="text-left mt-4">{renderCandidateSearch(job.id, slotIndex)}</div>
    </div>
  );

  // ── Main Render ───────────────────────────────────────────────────────

  return (
    <div className="space-y-8 max-w-5xl mx-auto pb-12">
      <CVGeneratingOverlay open={!!generatingCV} employeeName={generatingCV?.name} />
      {/* Project Header */}
      <div className="flex flex-col md:flex-row md:justify-between md:items-start gap-4 bg-white dark:bg-zinc-900 p-6 rounded-2xl border border-zinc-200 dark:border-zinc-800 shadow-sm">
        <div>
          <button onClick={() => navigate('/')} className="flex items-center gap-2 text-sm font-black text-zinc-500 hover:text-zinc-900 dark:hover:text-white transition-colors mb-4">
            <ArrowLeft size={16} /> Back to Dashboard
          </button>
          <h1 className="text-3xl font-black tracking-tight mb-2">{project.name}</h1>
          <p className="text-zinc-500 font-medium flex items-center gap-2">
            <Briefcase size={18} /> {project.client}
            <span className="text-zinc-300 dark:text-zinc-700">&bull;</span>
            <span className={clsx("px-2.5 py-0.5 rounded-full text-xs font-black uppercase",
              project.status === 'IN_PROGRESS' ? 'bg-blue-100 text-blue-700' :
              project.status === 'FINISHED' ? 'bg-green-100 text-green-700' : 'bg-red-100 text-red-700'
            )}>{project.status.replace('_', ' ')}</span>
          </p>
        </div>
        <div className="flex gap-3 shrink-0">
          {project.status === 'IN_PROGRESS' && (
            <>
              <button onClick={() => handleUpdateStatus('FINISHED')} className="bg-green-100 hover:bg-green-200 text-green-700 dark:bg-green-900/30 dark:hover:bg-green-900/50 dark:text-green-400 font-black rounded-xl px-4 py-2.5 transition-colors flex items-center gap-2">
                <CheckCircle2 size={18} /> Mark Finished
              </button>
              <button onClick={() => handleUpdateStatus('CANCELED')} className="bg-red-100 hover:bg-red-200 text-red-700 dark:bg-red-900/30 dark:hover:bg-red-900/50 dark:text-red-400 font-black rounded-xl px-4 py-2.5 transition-colors flex items-center gap-2">
                <XCircle size={18} /> Mark Canceled
              </button>
            </>
          )}
          {project.status !== 'IN_PROGRESS' && (
            <button onClick={() => handleUpdateStatus('IN_PROGRESS')} className="bg-indigo-100 hover:bg-indigo-200 text-indigo-700 dark:bg-indigo-900/30 dark:hover:bg-indigo-900/50 dark:text-indigo-400 font-black rounded-xl px-4 py-2.5 transition-colors flex items-center gap-2">
              <RefreshCw size={18} /> Reopen Project
            </button>
          )}
        </div>
      </div>

      {/* Team Summary */}
      <div className="flex items-center gap-4 text-sm">
        <h2 className="text-2xl font-black flex items-center gap-2">Required Team</h2>
        <span className="bg-indigo-100 dark:bg-indigo-900 text-indigo-600 dark:text-indigo-400 px-2.5 py-0.5 rounded-full text-sm font-black">
          {project.jobs.length} Roles
        </span>
        <span className="bg-zinc-100 dark:bg-zinc-800 text-zinc-600 dark:text-zinc-400 px-2.5 py-0.5 rounded-full text-sm font-black flex items-center gap-1">
          <Users size={14} /> {totalAccepted}/{totalSlots} Positions Filled
        </span>
      </div>

      {/* Jobs with multi-slot layout */}
      <div className="space-y-6">
        {project.jobs.map(job => {
          const slots = getJobSlots(job.id, job.headcount);
          const filledCount = slots.filter(s => s?.status === 'ACCEPTED').length;

          return (
            <div key={job.id} className="bg-white dark:bg-zinc-900 border border-zinc-200 dark:border-zinc-800 rounded-2xl p-6 shadow-sm">
              <div className="flex items-center justify-between mb-6 pb-4 border-b border-zinc-100 dark:border-zinc-800">
                <h3 className="text-xl font-black flex items-center gap-3">
                  <span className="w-10 h-10 rounded-full bg-zinc-100 dark:bg-zinc-800 flex items-center justify-center text-zinc-500">
                    <Briefcase size={20} />
                  </span>
                  {job.title}
                </h3>
                <div className="flex items-center gap-3">
                  <span className="px-3 py-1 bg-zinc-100 dark:bg-zinc-800 text-zinc-600 dark:text-zinc-400 rounded-full text-xs font-black flex items-center gap-1.5">
                    <Users size={14} />
                    {job.headcount} {job.headcount === 1 ? 'Position' : 'Positions'}
                  </span>
                  {filledCount === job.headcount ? (
                    <span className="px-3 py-1 bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400 rounded-full text-xs font-black uppercase tracking-widest flex items-center gap-1">
                      <CheckCircle2 size={14} /> All Filled
                    </span>
                  ) : filledCount > 0 ? (
                    <span className="px-3 py-1 bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400 rounded-full text-xs font-black uppercase tracking-widest flex items-center gap-1">
                      <Clock size={14} /> {filledCount}/{job.headcount} Filled
                    </span>
                  ) : (
                    <span className="px-3 py-1 bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-400 rounded-full text-xs font-black uppercase tracking-widest flex items-center gap-1">
                      <Clock size={14} /> Hiring
                    </span>
                  )}
                </div>
              </div>

              <div className={clsx(
                "grid gap-4",
                job.headcount === 1 ? "grid-cols-1" :
                job.headcount === 2 ? "grid-cols-1 lg:grid-cols-2" :
                "grid-cols-1 lg:grid-cols-2 xl:grid-cols-3"
              )}>
                {slots.map((slotMatch, slotIdx) => (
                  <div key={`${job.id}-slot-${slotIdx}`}>
                    {job.headcount > 1 && (
                      <div className="flex items-center gap-2 mb-2">
                        <span className="w-6 h-6 rounded-full bg-indigo-50 dark:bg-indigo-900/20 text-indigo-600 dark:text-indigo-400 flex items-center justify-center text-xs font-black">
                          {slotIdx + 1}
                        </span>
                        <span className="text-xs font-black text-zinc-400 uppercase tracking-wider">
                          Position {slotIdx + 1}
                        </span>
                      </div>
                    )}

                    {slotMatch ? (
                      <>
                        {slotMatch.status === 'PENDING' && (
                          <h4 className="text-xs font-black text-zinc-500 uppercase tracking-widest mb-2 flex items-center gap-2">
                            <Star size={14} className="text-amber-500" /> System Suggestion
                          </h4>
                        )}
                        {renderEmployeeCard(slotMatch, job, slotIdx)}
                        {slotMatch.status === 'PENDING' && renderCandidateSearch(job.id, slotIdx, slotMatch.id)}
                      </>
                    ) : (
                      renderEmptySlot(job, slotIdx)
                    )}
                  </div>
                ))}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}