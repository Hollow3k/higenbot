import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useAuth } from "../providers/AuthProvider";
import { apiFetch } from "../lib/api";

interface Project {
  id: string;
  prompt: string;
  status: string;
  created_at: string;
}

export default function ProjectsPage() {
  const { session, signOut } = useAuth();
  const navigate = useNavigate();
  const [projects, setProjects] = useState<Project[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function fetchProjects() {
      try {
        const res = await apiFetch("/api/projects/");
        if (res.ok) {
          const data = await res.json();
          setProjects(data.projects ?? []);
        }
      } catch {
        // silently fail
      } finally {
        setLoading(false);
      }
    }
    fetchProjects();
  }, []);

  const handleSignOut = async () => {
    await signOut();
    navigate("/");
  };

  return (
    <div className="min-h-screen bg-zinc-950 text-zinc-100 font-inter">
      {/* Header */}
      <header className="flex items-center justify-between border-b border-zinc-800 px-6 py-3">
        <Link to="/" className="font-bm-hanna text-xl text-zinc-100">
          Higenbot
        </Link>
        <div className="flex items-center gap-4">
          <span className="text-xs text-zinc-600">{session?.user?.email}</span>
          <button
            onClick={handleSignOut}
            className="text-xs text-zinc-500 hover:text-zinc-200 transition-colors"
          >
            Sign out
          </button>
        </div>
      </header>

      {/* Content */}
      <main className="max-w-2xl mx-auto px-6 py-10">
        <div className="flex items-center justify-between mb-6">
          <h2 className="text-lg font-medium">Your projects</h2>
          <Link
            to="/studio"
            className="rounded-lg bg-white text-zinc-900 px-4 py-2 text-xs font-medium hover:opacity-90 transition-opacity"
          >
            + New game
          </Link>
        </div>

        {loading ? (
          <p className="text-sm text-zinc-500">Loading...</p>
        ) : projects.length === 0 ? (
          <div className="text-center py-16 border border-dashed border-zinc-800 rounded-xl">
            <p className="text-zinc-500 text-sm">No projects yet</p>
            <p className="text-zinc-600 text-xs mt-1">
              Click "+ New game" to create your first project
            </p>
          </div>
        ) : (
          <div className="space-y-2">
            {projects.map((project) => (
              <Link
                key={project.id}
                to={`/studio/${project.id}`}
                className="flex items-center justify-between p-4 rounded-lg border border-zinc-800 hover:border-zinc-700 hover:bg-zinc-900/50 transition-colors"
              >
                <div className="space-y-1 min-w-0 flex-1">
                  <p className="text-sm text-zinc-200 truncate">
                    {project.prompt}
                  </p>
                  <p className="text-[11px] text-zinc-600">
                    {new Date(project.created_at).toLocaleDateString("en-US", {
                      month: "short",
                      day: "numeric",
                      year: "numeric",
                    })}
                  </p>
                </div>
                <span
                  className={`shrink-0 ml-4 text-[10px] uppercase tracking-wider px-2 py-0.5 rounded ${
                    project.status === "done"
                      ? "bg-emerald-900/30 text-emerald-400"
                      : project.status === "error"
                        ? "bg-red-900/30 text-red-400"
                        : project.status === "running"
                          ? "bg-amber-900/30 text-amber-400"
                          : "bg-zinc-800 text-zinc-500"
                  }`}
                >
                  {project.status}
                </span>
              </Link>
            ))}
          </div>
        )}
      </main>
    </div>
  );
}
