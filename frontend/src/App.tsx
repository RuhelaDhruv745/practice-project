import { NavLink, Outlet, Route, Routes } from "react-router";

import { AuditPage } from "./pages/AuditPage";
import { CustomerDetailPage } from "./pages/CustomerDetailPage";
import { CustomersPage } from "./pages/CustomersPage";
import { DashboardPage } from "./pages/DashboardPage";
import { ReviewDetailPage } from "./pages/ReviewDetailPage";
import { ReviewQueuePage } from "./pages/ReviewQueuePage";

const NAV = [
  { to: "/", label: "Dashboard" },
  { to: "/customers", label: "Customers" },
  { to: "/reviews", label: "Review queue" },
  { to: "/audit", label: "Audit log" },
];

function Layout() {
  return (
    <div className="min-h-screen">
      <header className="border-b border-slate-200 bg-white">
        <div className="mx-auto flex max-w-6xl items-center gap-6 px-4 py-3">
          <span className="font-semibold text-slate-900">Loyalty Reviewer</span>
          <nav className="flex gap-4 text-sm">
            {NAV.map((item) => (
              <NavLink
                key={item.to}
                to={item.to}
                end={item.to === "/"}
                className={({ isActive }) =>
                  isActive ? "font-semibold text-indigo-700" : "text-slate-600 hover:text-slate-900"
                }
              >
                {item.label}
              </NavLink>
            ))}
          </nav>
          <span className="ml-auto text-xs text-slate-500">
            Mock outbox only. Nothing is sent without approval.
          </span>
        </div>
      </header>
      <main className="mx-auto max-w-6xl space-y-4 px-4 py-6">
        <Outlet />
      </main>
    </div>
  );
}

export function AppRoutes() {
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route index element={<DashboardPage />} />
        <Route path="customers" element={<CustomersPage />} />
        <Route path="customers/:customerId" element={<CustomerDetailPage />} />
        <Route path="reviews" element={<ReviewQueuePage />} />
        <Route path="reviews/:reviewId" element={<ReviewDetailPage />} />
        <Route path="audit" element={<AuditPage />} />
        <Route path="*" element={<p>Page not found.</p>} />
      </Route>
    </Routes>
  );
}
