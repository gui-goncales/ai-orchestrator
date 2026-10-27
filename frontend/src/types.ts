export type Task = {
  conversation_id?: string;
  id: string;
  conversation_history?: {objective:string;result:string}[];
  project_id: string;
  objective: string;
  provider: string;
  status: string;
  result: string;
  usage: Record<string, number>;
  error: string | null;
  created_at: string;
  updated_at: string;
  workflow?: string;
  routing?: { reason?: string; category?: string };
  context_metrics?: {
    prompt_characters?: number;
    duplicates_removed?: string[];
    references_omitted?: string[];
    constraints_preserved?: boolean;
  };
  validation?: { status?: string };
  quality?: string;
};

export type Revision = {
  task_id: string;
  parent_id: string;
  source_review_id: string;
  status: string;
  after_review_id?: string;
  changes: { added?: string[]; modified?: string[]; removed?: string[] };
  validation: { passed?: boolean };
  created_at: string;
};

export type Data = {
  projects: { id: string; name: string; path: string }[];
  tasks: Task[];
  providers: {
    id: string;
    state: string;
    auth?: string;
    installed: boolean;
    name?: string;
    session_ready?: boolean;
    automatic_routing?: boolean;
    config?: Record<string, string>;
  }[];
  events: { id: number; task_id: string | null; kind: string; payload: any; time: string }[];
  checkpoints: { id: number; task_id: string; payload: any; time: string }[];
  artifacts?: {
    task_id: string;
    path: string;
    manifest: {
      passed: boolean;
      preview_url: string;
      scope: string;
      files: { path: string; bytes: number }[];
    };
  }[];
  revisions?: Revision[];
  visual_reviews?: {
    suggestions?: {
      id: string;
      priority: string;
      capture: string;
      evidence: string;
      proposal: string;
      criterion: string;
    }[];
    task_id: string;
    parent_id: string;
    report: string;
    capture: {
      images?: { name: string; label: string }[];
      captured_at?: string;
      scope?: string;
      page_errors?: string[];
    };
  }[];
  task_steps?: { task_id: string; stage: string; output: string; time: string }[];
  memory: { id: string; project_id: string; content: string; time: string; kind?: string }[];
};

export type ChatFolder = {
  id: string;
  name: string;
  projectId?: string; // specific project or 'all'
  createdAt: string;
  collapsed?: boolean;
  color?: string;
};
