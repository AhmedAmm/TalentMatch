import React from 'react';
import { useAuth } from '../context/AuthContext';
import { AdminDashboard } from './AdminDashboard';
import { PODashboard } from './PODashboard';
import { RHDashboard } from './RHDashboard';

export function Dashboard() {
  const { user } = useAuth();

  if (!user) return null;

  switch (user.role) {
    case 'ADMIN':
      return <AdminDashboard />;
    case 'PO':
      return <PODashboard />;
    case 'RH':
      return <RHDashboard />;
    default:
      return <div>Unknown role</div>;
  }
}
