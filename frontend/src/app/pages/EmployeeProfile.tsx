import React, { useState, useEffect } from 'react';
import { useParams, useNavigate, useSearchParams } from 'react-router';
import { api, Employee, Project } from '../api/apiClient';
import { ArrowLeft, Star, Briefcase, Mail, CheckCircle2, AlertCircle, FileText, Calendar, Building } from 'lucide-react';
import { Radar, RadarChart, PolarGrid, PolarAngleAxis, ResponsiveContainer, BarChart, Bar, XAxis, YAxis, Tooltip as RechartsTooltip, CartesianGrid } from 'recharts';
import { CVGeneratingOverlay } from '../components/CVGeneratingOverlay';

export function EmployeeProfile() {
  const { id } = useParams<{ id: string }>();
  const [searchParams] = useSearchParams();
  const projectId = searchParams.get('projectId');
  
  const navigate = useNavigate();
  const [employee, setEmployee] = useState<Employee | null>(null);
  const [project, setProject] = useState<Project | null>(null);
  const [loading, setLoading] = useState(true);
  const [generating, setGenerating] = useState(false);
  const [generatingName, setGeneratingName] = useState<string | undefined>(undefined);

  useEffect(() => {
    async function loadData() {
      setLoading(true);
      try {
        if (id) {
          const empData = await api.getEmployeeById(id);
          setEmployee(empData);
        }
        if (projectId) {
          const projData = await api.getProjectById(projectId);
          setProject(projData);
        }
      } catch (e: any) {
        console.error(e);
      }
      setLoading(false);
    }
    loadData();
  }, [id, projectId]);

  const handleGenerateCV = async () => {
    if (!employee) return;
    setGenerating(true);
    setGeneratingName(employee.name);
    try {
      const blob = await api.generateCV(employee.id, project?.id, undefined);
      const url = URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = `${employee.name.replace(/ /g, '_')}_${project ? 'Tailored' : 'Standard'}_CV.docx`;
      link.click();
      URL.revokeObjectURL(url);
    } catch (e: any) {
      console.error(e);
      alert(e.message || 'Error generating CV');
    }
    setGenerating(false);
    setGeneratingName(undefined);
  };

  if (loading || !employee) return <div className="animate-pulse">Loading profile...</div>;

  const radarData = [
    { subject: 'Technical', A: employee.stats.technical, fullMark: 100 },
    { subject: 'Communication', A: employee.stats.communication, fullMark: 100 },
    { subject: 'Leadership', A: employee.stats.leadership, fullMark: 100 },
    { subject: 'Problem Solving', A: employee.stats.problemSolving, fullMark: 100 },
    { subject: 'Teamwork', A: employee.stats.teamwork, fullMark: 100 },
  ];

  return (
    <div className="max-w-6xl mx-auto space-y-8 pb-12">
      <CVGeneratingOverlay open={generating} employeeName={generatingName} />
      <div className="flex justify-between items-center mb-4">
        <button onClick={() => navigate(-1)} className="flex items-center gap-2 text-sm font-medium text-zinc-500 hover:text-zinc-900 dark:hover:text-white transition-colors">
          <ArrowLeft size={16} /> Back
        </button>
        {project && (
          <div className="text-sm font-semibold bg-amber-100 dark:bg-amber-900/30 text-amber-700 dark:text-amber-400 px-4 py-1.5 rounded-full flex items-center gap-2">
            <Star size={16} fill="currentColor" /> Evaluating for Project: {project.name}
          </div>
        )}
      </div>

      {/* Header Profile Card */}
      <div className="bg-white dark:bg-zinc-900 rounded-3xl border border-zinc-200 dark:border-zinc-800 p-8 md:p-10 shadow-sm flex flex-col md:flex-row items-center md:items-start gap-8 relative overflow-hidden">
        <div className="absolute top-0 right-0 w-96 h-96 bg-indigo-50 dark:bg-indigo-900/10 rounded-full blur-3xl -mr-20 -mt-20"></div>
        <div className="absolute bottom-0 left-0 w-64 h-64 bg-emerald-50 dark:bg-emerald-900/5 rounded-full blur-3xl -ml-20 -mb-20"></div>
        
        {employee.avatarUrl ? (
          <img src={employee.avatarUrl} alt={employee.name} className="w-40 h-40 rounded-full object-cover ring-4 ring-white dark:ring-zinc-900 shadow-xl z-10" />
        ) : (
          <div className="w-40 h-40 rounded-full bg-indigo-100 dark:bg-indigo-900 text-indigo-700 dark:text-indigo-300 flex items-center justify-center font-bold text-5xl shadow-xl z-10">
            {employee.name.charAt(0)}
          </div>
        )}

        <div className="flex-1 text-center md:text-left z-10 w-full">
          <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 mb-4">
            <div>
              <div className="flex flex-col md:flex-row md:items-center gap-4 mb-2">
                <h1 className="text-4xl md:text-5xl font-black tracking-tight">{employee.name}</h1>
                <span className={`px-3 py-1 rounded-full text-xs font-bold tracking-wider uppercase inline-flex items-center gap-1.5 w-fit mx-auto md:mx-0
                  ${employee.isAvailable ? 'bg-green-100 text-green-700' : 'bg-zinc-200 text-zinc-700'}`}>
                  {employee.isAvailable ? <CheckCircle2 size={14} /> : <AlertCircle size={14} />}
                  {employee.isAvailable ? 'Available' : 'Currently Assigned'}
                </span>
              </div>
              <div className="flex flex-wrap items-center justify-center md:justify-start gap-4 md:gap-6 text-zinc-500 font-medium">
                <span className="flex items-center gap-2"><Mail size={18} /> {employee.email}</span>
                <span className="flex items-center gap-2"><Briefcase size={18} /> {employee.skills.length} Core Skills</span>
              </div>
            </div>
            
            <div className="md:text-right flex flex-col gap-2 shrink-0 w-full md:w-auto">
              <button onClick={handleGenerateCV} disabled={generating}
                className="w-full md:w-auto bg-indigo-600 hover:bg-indigo-700 disabled:bg-indigo-400 text-white font-bold rounded-xl px-6 py-3 transition-colors flex items-center justify-center gap-2 shadow-sm shadow-indigo-600/20">
                {generating ? <span className="animate-pulse">Generating...</span> : <><FileText size={20} /> Generate {project ? 'Tailored' : 'Standard'} CV</>}
              </button>
            </div>
          </div>
          
          <div className="flex flex-wrap justify-center md:justify-start gap-2 mt-6">
            {employee.skills.map(skill => (
              <span key={skill} className="bg-indigo-50 dark:bg-indigo-900/30 text-indigo-700 dark:text-indigo-300 border border-indigo-100 dark:border-indigo-900/50 px-4 py-1.5 rounded-full text-sm font-bold shadow-sm">
                {skill}
              </span>
            ))}
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
        <div className="lg:col-span-2 space-y-8">
          <div className="bg-white dark:bg-zinc-900 rounded-3xl border border-zinc-200 dark:border-zinc-800 p-8 shadow-sm">
            <h2 className="text-xl font-bold mb-4 flex items-center gap-2"><FileText size={22} className="text-indigo-500" /> About Me</h2>
            <p className="text-zinc-700 dark:text-zinc-300 leading-relaxed text-lg">{employee.about}</p>
          </div>

          <div className="bg-white dark:bg-zinc-900 rounded-3xl border border-zinc-200 dark:border-zinc-800 p-8 shadow-sm">
            <h2 className="text-xl font-bold mb-6 flex items-center gap-2"><Briefcase size={22} className="text-indigo-500" /> Professional Experience</h2>
            <div className="space-y-0">
              {employee.experiences.map((exp) => (
                <div key={exp.id} className="relative pl-8 pb-8 before:absolute before:left-[11px] before:top-2 before:bottom-0 before:w-[2px] before:bg-zinc-200 dark:before:bg-zinc-800 last:before:hidden last:pb-0">
                  <div className="absolute left-0 top-1.5 w-6 h-6 bg-white dark:bg-zinc-900 border-4 border-indigo-100 dark:border-indigo-900/50 rounded-full z-10 flex items-center justify-center">
                    <div className="w-2 h-2 bg-indigo-500 rounded-full"></div>
                  </div>
                  <div className="bg-zinc-50 dark:bg-zinc-800/50 rounded-2xl p-6 border border-zinc-100 dark:border-zinc-800 hover:border-indigo-300 dark:hover:border-indigo-700 transition-colors group">
                    <div className="flex flex-col md:flex-row md:justify-between md:items-start gap-2 mb-3">
                      <div>
                        <h3 className="text-lg font-bold group-hover:text-indigo-600 transition-colors">{exp.title}</h3>
                        <p className="text-zinc-600 dark:text-zinc-400 font-medium flex items-center gap-1.5"><Building size={16} /> {exp.company}</p>
                      </div>
                      <span className="text-sm font-bold text-zinc-500 bg-white dark:bg-zinc-800 px-3 py-1 rounded-full flex items-center gap-1.5 shrink-0 border border-zinc-200 dark:border-zinc-700">
                        <Calendar size={14} /> {exp.period}
                      </span>
                    </div>
                    <p className="text-zinc-600 dark:text-zinc-400 text-sm leading-relaxed">{exp.description}</p>
                  </div>
                </div>
              ))}
              {employee.experiences.length === 0 && (
                <div className="text-center py-8 text-zinc-500 italic">No experience data available.</div>
              )}
            </div>
          </div>
        </div>

        <div className="space-y-8">
          <div className="bg-white dark:bg-zinc-900 rounded-3xl border border-zinc-200 dark:border-zinc-800 p-8 shadow-sm flex flex-col items-center">
            <h2 className="text-xl font-bold w-full mb-2 flex items-center gap-2"><Star size={20} className="text-amber-500" /> Competency Radar</h2>
            <div className="w-full h-[280px]">
              <ResponsiveContainer width="100%" height="100%">
                <RadarChart cx="50%" cy="50%" outerRadius="75%" data={radarData}>
                  <PolarGrid stroke="#e4e4e7" strokeDasharray="3 3" />
                  <PolarAngleAxis dataKey="subject" tick={{ fill: '#71717a', fontSize: 11, fontWeight: 600 }} />
                  <Radar name={employee.name} dataKey="A" stroke="#4f46e5" strokeWidth={3} fill="#4f46e5" fillOpacity={0.3} />
                  <RechartsTooltip cursor={{stroke: '#e4e4e7', strokeWidth: 1}} contentStyle={{ borderRadius: '12px', border: 'none', boxShadow: '0 10px 15px -3px rgb(0 0 0 / 0.1)' }} />
                </RadarChart>
              </ResponsiveContainer>
            </div>
          </div>

          <div className="bg-white dark:bg-zinc-900 rounded-3xl border border-zinc-200 dark:border-zinc-800 p-8 shadow-sm flex flex-col items-center">
            <h2 className="text-xl font-bold w-full mb-6 flex items-center gap-2"><Briefcase size={20} className="text-indigo-500" /> Strength Breakdown</h2>
            <div className="w-full h-[280px]">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={radarData} layout="vertical" margin={{ top: 0, right: 30, left: 40, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" horizontal={false} stroke="#e4e4e7" />
                  <XAxis type="number" domain={[0, 100]} hide />
                  <YAxis dataKey="subject" type="category" axisLine={false} tickLine={false} tick={{ fill: '#3f3f46', fontSize: 11, fontWeight: 600 }} width={100} />
                  <RechartsTooltip cursor={{fill: '#f4f4f5'}} contentStyle={{ borderRadius: '12px', border: 'none', boxShadow: '0 10px 15px -3px rgb(0 0 0 / 0.1)' }} />
                  <Bar dataKey="A" fill="#4f46e5" radius={[0, 4, 4, 0]} barSize={20} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
