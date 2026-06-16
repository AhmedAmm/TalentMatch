import { createBrowserRouter } from "react-router";
import { Layout } from "./components/Layout";
import { Dashboard } from "./pages/Dashboard";
import { ManageUsers } from "./pages/ManageUsers";
import { POProjectDetails } from "./pages/POProjectDetails";
import { EmployeeProfile } from "./pages/EmployeeProfile";
import { RHDashboard } from "./pages/RHDashboard"; // RH Dashboard handles the /cv logic as well
import React from "react";

export const router = createBrowserRouter([
  {
    path: "/",
    Component: Layout,
    children: [
      { index: true, Component: Dashboard },
      { path: "users", Component: ManageUsers },
      { path: "cv", Component: RHDashboard }, // Use RH Dashboard for CV upload link too
      { path: "project/:id", Component: POProjectDetails },
      { path: "employee/:id", Component: EmployeeProfile },
      { path: "*", Component: () => <div className="p-8 text-center">404 Not Found</div> },
    ],
  },
]);
