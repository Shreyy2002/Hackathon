import RoleSwitcher from "./components/RoleSwitcher";
import TimelineView from "./components/Timeline/TimelineView";
import { useUserStore } from "./store/userStore";

export default function App() {
  const currentUser = useUserStore((s) => s.currentUser);

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Top navigation bar */}
      <header className="border-b border-gray-200 bg-white px-6 py-3 shadow-sm">
        <div className="mx-auto flex max-w-7xl items-center justify-between">
          <h1 className="text-lg font-semibold text-gray-900">
            Performance Ledger
          </h1>
          <RoleSwitcher />
        </div>
      </header>

      {/* Main content placeholder */}
      <main className="mx-auto max-w-7xl px-6 py-10">
        {currentUser ? (
          <div className="rounded-lg border border-gray-200 bg-white p-6 shadow-sm">
            <p className="text-sm text-gray-600">
              Logged in as{" "}
              <span className="font-medium text-gray-900">
                {currentUser.name}
              </span>{" "}
              <span className="rounded-full bg-blue-100 px-2 py-0.5 text-xs text-blue-700">
                {currentUser.role}
              </span>
            </p>

            {/* Activity Timeline */}
            <div className="mt-6">
              <h2 className="mb-4 text-base font-semibold text-gray-900">
                Activity Timeline
              </h2>
              <TimelineView employeeId={currentUser.id} />
            </div>
          </div>
        ) : (
          <div className="rounded-lg border border-dashed border-gray-300 p-12 text-center">
            <p className="text-sm text-gray-500">
              Select a persona from the top-right dropdown to get started.
            </p>
          </div>
        )}
      </main>
    </div>
  );
}
