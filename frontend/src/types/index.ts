export interface TaskCreateResponse {
  task_id: string;
  status: string;
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
