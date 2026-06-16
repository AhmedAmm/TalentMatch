import React, { useState } from 'react';
import { Eye, EyeOff, Lock, Mail, ArrowRight } from 'lucide-react';
import { useAuth } from '../context/AuthContext';
import { useNavigate } from 'react-router';

export function LoginPage() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setLoading(true);
    const result = await login(email, password);
    setLoading(false);
    if (result.success) {
      navigate('/');
    } else {
      setError(result.error || 'Login failed.');
    }
  };

  return (
    <div className="min-h-screen flex">
      {/* Left: Branding Panel */}
      <div className="hidden lg:flex lg:w-[480px] xl:w-[540px] relative overflow-hidden bg-gradient-to-br from-indigo-600 via-violet-600 to-purple-700 flex-col justify-between p-12 text-white">
        <div className="absolute inset-0 opacity-10">
          <div className="absolute top-[-20%] right-[-20%] w-[600px] h-[600px] rounded-full bg-white/20 blur-3xl" />
          <div className="absolute bottom-[-10%] left-[-10%] w-[400px] h-[400px] rounded-full bg-white/10 blur-3xl" />
        </div>
        <div className="relative z-10">
          <div className="flex items-center gap-3 mb-16">
            <div className="w-11 h-11 rounded-xl bg-white/20 backdrop-blur-sm flex items-center justify-center text-white font-black text-xl border border-white/10">D</div>
            <span className="text-2xl font-black tracking-tight">Diapo</span>
          </div>
          <h1 className="text-4xl xl:text-5xl font-black tracking-tight leading-[1.1] mb-6">
            Smart Talent<br />Matching Platform
          </h1>
          <p className="text-lg text-white/70 leading-relaxed max-w-sm">
            AI-powered candidate matching, project management, and tailored CV generation — all in one place.
          </p>
        </div>
        <div className="relative z-10 flex flex-col gap-4">
          <div className="flex items-center gap-3 text-sm text-white/60">
            <div className="w-8 h-8 rounded-full bg-white/10 flex items-center justify-center text-xs">✦</div>
            Intelligent job-to-candidate matching
          </div>
          <div className="flex items-center gap-3 text-sm text-white/60">
            <div className="w-8 h-8 rounded-full bg-white/10 flex items-center justify-center text-xs">✦</div>
            Automated CV parsing & generation
          </div>
          <div className="flex items-center gap-3 text-sm text-white/60">
            <div className="w-8 h-8 rounded-full bg-white/10 flex items-center justify-center text-xs">✦</div>
            Role-based access for Admin, PO & HR
          </div>
        </div>
      </div>

      {/* Right: Login Form */}
      <div className="flex-1 flex items-center justify-center bg-zinc-50 dark:bg-zinc-950 p-6 sm:p-12">
        <div className="w-full max-w-md">
          {/* Mobile logo */}
          <div className="flex items-center gap-3 mb-10 lg:hidden">
            <div className="w-10 h-10 rounded-xl bg-indigo-600 flex items-center justify-center text-white font-black text-lg">D</div>
            <span className="text-xl font-black tracking-tight text-zinc-900 dark:text-white">Diapo</span>
          </div>

          <div className="mb-8">
            <h2 className="text-3xl font-black tracking-tight text-zinc-900 dark:text-white mb-2">Welcome back</h2>
            <p className="text-zinc-500">Sign in to your account to continue.</p>
          </div>

          <form onSubmit={handleSubmit} className="space-y-5">
            <div>
              <label className="block text-sm font-semibold text-zinc-700 dark:text-zinc-300 mb-2">Email</label>
              <div className="relative">
                <Mail size={18} className="absolute left-3.5 top-1/2 -translate-y-1/2 text-zinc-400" />
                <input
                  type="email"
                  required
                  placeholder="you@diapo.com"
                  value={email}
                  onChange={e => setEmail(e.target.value)}
                  className="w-full bg-white dark:bg-zinc-900 border border-zinc-200 dark:border-zinc-800 rounded-xl pl-11 pr-4 py-3 text-sm focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 outline-none transition-all shadow-sm"
                />
              </div>
            </div>

            <div>
              <label className="block text-sm font-semibold text-zinc-700 dark:text-zinc-300 mb-2">Password</label>
              <div className="relative">
                <Lock size={18} className="absolute left-3.5 top-1/2 -translate-y-1/2 text-zinc-400" />
                <input
                  type={showPassword ? 'text' : 'password'}
                  required
                  placeholder="••••••••"
                  value={password}
                  onChange={e => setPassword(e.target.value)}
                  className="w-full bg-white dark:bg-zinc-900 border border-zinc-200 dark:border-zinc-800 rounded-xl pl-11 pr-12 py-3 text-sm focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 outline-none transition-all shadow-sm"
                />
                <button
                  type="button"
                  onClick={() => setShowPassword(!showPassword)}
                  className="absolute right-3.5 top-1/2 -translate-y-1/2 text-zinc-400 hover:text-zinc-600 dark:hover:text-zinc-300 transition-colors"
                >
                  {showPassword ? <EyeOff size={18} /> : <Eye size={18} />}
                </button>
              </div>
            </div>

            {error && (
              <div className="bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 text-red-700 dark:text-red-400 rounded-xl px-4 py-3 text-sm font-medium">
                {error}
              </div>
            )}

            <button
              type="submit"
              disabled={loading}
              className="w-full bg-indigo-600 hover:bg-indigo-700 disabled:opacity-60 text-white font-bold rounded-xl px-6 py-3.5 transition-all flex items-center justify-center gap-2 shadow-lg shadow-indigo-600/20 hover:shadow-indigo-600/30"
            >
              {loading ? (
                <span className="animate-pulse">Signing in...</span>
              ) : (
                <>Sign In <ArrowRight size={18} /></>
              )}
            </button>
          </form>

          {/* Quick access hint */}
          <div className="mt-8 pt-6 border-t border-zinc-200 dark:border-zinc-800">
            <p className="text-xs text-zinc-400 text-center">
              Contact your administrator if you don't have an account.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}