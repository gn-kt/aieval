export interface User {
  id: number;
  username: string;
  email: string;
  api_key: string;
  is_active: boolean;
}

export interface LoginResponse {
  access_token: string;
  token_type: string;
}

export interface TaskCreateResponse {
  task_id: string;
  status: string;
  rate_limit_remaining: number | null;
}

export interface TaskStatusResponse {
  task_id: string;
  status: string;
  result: string | RAGResult | null;
}

export interface RAGResult {
  answer: string;
  sources: SourceItem[];
}

export interface SourceItem {
  file: string;
  chunk: number;
  score: number;
}

export interface TaskListItem {
  task_id: string;
  question: string;
  status: string;
  created_at: string | null;
}

export interface PaginatedTasks {
  items: TaskListItem[];
  total: number;
  page: number;
  size: number;
  pages: number;
}

export interface ApiError {
  error: {
    code: string;
    message: string;
    details: { field: string; reason: string }[] | null;
  };
}

export interface Stats {
  active_ws: number;
  task_count: number;
  user_count: number;
}

export interface ChatMessage {
  role: 'user' | 'assistant';
  content: string;
  sources?: SourceItem[];
}

export interface SessionResponse {
  session_id: string;
  messages: ChatMessage[];
}

export interface DimensionScore {
  name: string;
  name_en: string;
  weight: number;
  score: number;
  max_score: number;
  evidence: string[];
}

export interface EvaluationResult {
  scores: Record<string, DimensionScore>;
  weighted_total: number;
  overall_summary: string;
  top_strengths: string[];
  top_weaknesses: string[];
  suggestions: { dimension: string; issue: string; fix: string; priority: string }[];
  directions: string[];
  veto: { triggered: boolean; reason: string };
  raw_llm_output?: string;
}

export interface ProjectMeta {
  full_name: string;
  description: string;
  stars: number;
  forks: number;
  open_issues: number;
  language: string;
  topics: string[];
  license_name: string;
  created_at: string;
  updated_at: string;
  commit_days_active_90d: number;
  last_commit_at: string;
  issue_stats: Record<string, number>;
}

export interface CompetitorMeta {
  full_name: string;
  description: string;
  stars: number;
  forks: number;
  commit_days_active_90d: number;
  last_commit_at: string;
}

export interface EvaluateResult {
  evaluation: EvaluationResult;
  project_meta: ProjectMeta;
  competitors_meta: CompetitorMeta[];
  report_markdown: string;
}
