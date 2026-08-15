/**
 * Local storage fallback for project persistence.
 * Used when the backend DB is not configured.
 */

export interface LocalProject {
  id: string;
  prompt: string;
  status: "running" | "done" | "error";
  created_at: string;
  files: Record<string, string>;
}

const STORAGE_KEY = "higenbot_projects";

export function getLocalProjects(): LocalProject[] {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return [];
    return JSON.parse(raw);
  } catch {
    return [];
  }
}

export function saveLocalProject(project: LocalProject) {
  const projects = getLocalProjects();
  const existing = projects.findIndex((p) => p.id === project.id);
  if (existing >= 0) {
    projects[existing] = project;
  } else {
    projects.unshift(project);
  }
  localStorage.setItem(STORAGE_KEY, JSON.stringify(projects));
}

export function getLocalProject(id: string): LocalProject | null {
  const projects = getLocalProjects();
  return projects.find((p) => p.id === id) ?? null;
}
