import { useState, useEffect, useRef } from 'react';
import TopBar from '../components/TopBar';
import client from '../api/client';
import type { TaskCreateResponse, EvaluateResult, ProjectMeta } from '../types';

const PRESETS = [
  { label: 'Flask (72k)', url: 'https://github.com/pallets/flask', desc: 'Python Web 微框架' },
  { label: 'FastAPI (87k)', url: 'https://github.com/fastapi/fastapi', desc: '现代 Python Web 框架' },
  { label: 'petite-vue (9.7k)', url: 'https://github.com/vuejs/petite-vue', desc: 'Vue 轻量子集' },
  { label: 'Vizro (3.8k)', url: 'https://github.com/mckinsey/vizro', desc: '低代码仪表盘框架' },
];

type Mode = 'github' | 'text' | 'file';
type ChatMsg = { role: 'user' | 'assistant'; content: string };
type EvalRecord = { id: number; repo: string; url: string; score: number; summary: string; positioning: number; differentiation: number; moat: number; engineering: number; sustainability: number; strengths: string; weaknesses: string; evaluated_at: string };

const API = import.meta.env.DEV ? 'http://127.0.0.1:8000' : '';

const SCORE_GRADES = ['较差', '一般', '优秀'];
const DIM_NAMES = ['定位', '差异化', '护城河', '工程健康度', '可持续性'];
const DIM_KEYS = ['positioning', 'differentiation', 'moat', 'engineering', 'sustainability'];
const DIM_DESC = ['目标用户和场景是否清晰', '与竞品相比的独特价值', '防御能力和市场壁垒', '代码质量和迭代频率', '长期维护和社区活跃度'];

export default function EvaluatorPage() {
  const [mode, setMode] = useState<Mode>('github');
  const [repoUrl, setRepoUrl] = useState('');
  const [description, setDescription] = useState('');
  const [textInput, setTextInput] = useState('');
  const [files, setFiles] = useState<File[]>([]);
  const [waiting, setWaiting] = useState(false);
  const [error, setError] = useState('');
  const [report, setReport] = useState<EvaluateResult | null>(null);
  const [evalRepoUrl, setEvalRepoUrl] = useState('');
  const [chatMsgs, setChatMsgs] = useState<ChatMsg[]>([]);
  const [chatInput, setChatInput] = useState('');
  const [chatLoading, setChatLoading] = useState(false);
  const [history, setHistory] = useState<EvalRecord[]>([]);
  const [showHistory, setShowHistory] = useState(false);
  const chatEndRef = useRef<HTMLDivElement>(null);

  const loadHistory = () => {
    fetch(`${API}/evaluator/history`).then(r => r.json()).then(d => setHistory(d.evaluations || [])).catch(() => {});
  };

  useEffect(() => { loadHistory(); }, [report]);
  useEffect(() => { chatEndRef.current?.scrollIntoView({ behavior: 'smooth' }); }, [chatMsgs]);

  const clearAllHistory = async () => {
    if (!window.confirm('确定要清除全部历史评测记录吗？')) return;
    try { await fetch(`${API}/evaluator/history`, { method: 'DELETE' }); loadHistory(); } catch {}
  };

  const deleteHistory = async (id: number, e: React.MouseEvent) => {
    e.stopPropagation();
    if (!window.confirm('确定删除这条记录？')) return;
    try { await fetch(`${API}/evaluator/history/${id}`, { method: 'DELETE' }); loadHistory(); } catch {}
  };

  const handleFiles = (e: React.ChangeEvent<HTMLInputElement>) => {
    const selected = Array.from(e.target.files || []).filter(f => /\.(md|txt|py|js|ts|json|yml|yaml|toml|cfg|ini)$/i.test(f.name));
    setFiles(selected);
  };

  const readFiles = (): Promise<string> => {
    return Promise.all(files.map(f => f.text().then(t => `### ${f.name}\n\`\`\`\n${t.slice(0, 3000)}\n\`\`\``)))
      .then(parts => parts.join('\n\n'));
  };

  const selectPreset = (p: typeof PRESETS[0]) => {
    setRepoUrl(p.url); setDescription(p.desc); setReport(null); setError(''); setChatMsgs([]);
  };

  const handleSubmit = async () => {
    if (waiting) return;
    if (mode === 'github' && !repoUrl.trim()) { setError('请输入仓库地址'); return; }
    if (mode === 'text' && !textInput.trim()) { setError('请输入产品描述'); return; }
    if (mode === 'file' && files.length === 0) { setError('请选择文件'); return; }
    setError(''); setReport(null); setChatMsgs([]); setWaiting(true);
    try {
      if (mode === 'file') {
        const content = await readFiles();
        if (!content) { setError('请选择文件'); setWaiting(false); return; }
        const res = await client.post<TaskCreateResponse>('/evaluator/analyze-text', { description: content, n_competitors: 3 });
        setEvalRepoUrl('file://' + Date.now()); pollForResult(res.data.task_id);
      } else if (mode === 'text') {
        const txt = textInput.trim();
        const res = await client.post<TaskCreateResponse>('/evaluator/analyze-text', { description: txt, n_competitors: 3 });
        setEvalRepoUrl('text://' + Date.now()); pollForResult(res.data.task_id);
      } else {
        const url = repoUrl.trim();
        const res = await client.post<TaskCreateResponse>('/evaluator/analyze', { repo_url: url, description: description.trim() || null, n_competitors: 5 });
        setEvalRepoUrl(url); pollForResult(res.data.task_id);
      }
    } catch (err: any) { setError(err.response?.data?.detail || '提交失败'); setWaiting(false); }
  };

  const pollForResult = async (tid: string) => {
    let attempts = 0;
    const check = async () => {
      attempts++;
      try {
        const res = await fetch(`${API}/result/${tid}?t=${Date.now()}`);
        const data = await res.json();
        if (data.status === 'done' || data.status === 'SUCCESS') {
          if (data.result?.evaluation) { setReport(data.result); setWaiting(false); return; }
          setError('评测结果为空'); setWaiting(false); return;
        }
        if (data.status === 'failed' || data.status === 'FAILURE') { setError('评测失败'); setWaiting(false); return; }
      } catch {}
      // 150 次 × 2s = 300s，对齐后端任务 time_limit（text 180s / github 300s），避免长任务被前端提前判超时
      if (attempts >= 150) { setError('评测超时'); setWaiting(false); return; }
      setTimeout(check, 2000);
    };
    check();
  };

  const sendChat = async () => {
    const q = chatInput.trim(); if (!q || chatLoading) return;
    const newMsgs: ChatMsg[] = [...chatMsgs, { role: 'user', content: q }];
    setChatMsgs(newMsgs); setChatInput(''); setChatLoading(true);
    try {
      const res = await client.post('/advisor/ask', {
        repo_url: evalRepoUrl, question: q,
        history: chatMsgs,
        eval_data: report?.evaluation || null,
      });
      setChatMsgs([...newMsgs, { role: 'assistant', content: res.data.answer }]);
    } catch {
      setChatMsgs([...newMsgs, { role: 'assistant', content: '抱歉，回答出错，请重试' }]);
    }
    setChatLoading(false);
  };

  return (
    <div style={{ maxWidth: 960, margin: '0 auto', paddingBottom: 40 }}>
      <TopBar />
      <h2 style={{ marginTop: 0, marginBottom: 4 }}>产品竞争力评测</h2>
      <p style={{ color: '#999', fontSize: 13, margin: '0 0 16px 0' }}>输入 GitHub 仓库地址、产品描述或上传项目文件，AI 自动分析竞争力</p>

      {/* 模式切换 */}
      <div style={s.modeBar}>
        <button style={mode === 'github' ? s.modeActive : s.modeInactive} onClick={() => setMode('github')}>GitHub 仓库</button>
        <button style={mode === 'text' ? s.modeActive : s.modeInactive} onClick={() => setMode('text')}>文字描述</button>
        <button style={mode === 'file' ? s.modeActive : s.modeInactive} onClick={() => setMode('file')}>上传文件夹</button>
      </div>

      {/* GitHub 模式 */}
      {mode === 'github' && (
        <>
          <div style={{ fontSize: 11, color: '#aaa', marginBottom: 8 }}>示例项目（点击自动填入）</div>
          <div style={s.presets}>
            {PRESETS.map(p => (
              <button key={p.url} style={repoUrl === p.url ? s.presetActive : s.presetInactive} onClick={() => selectPreset(p)} disabled={waiting}>{p.label}</button>
            ))}
          </div>
          <div style={s.form}>
            <div style={s.field}>
              <label style={s.label}>仓库地址 *</label>
              <input style={s.input} placeholder="https://github.com/用户名/仓库名" value={repoUrl} onChange={e => setRepoUrl(e.target.value)} onKeyDown={e => e.key === 'Enter' && handleSubmit()} disabled={waiting} />
            </div>
            <div style={s.field}>
              <label style={s.label}>项目描述（可选）</label>
              <input style={s.input} placeholder="一句话描述这个项目..." value={description} onChange={e => setDescription(e.target.value)} disabled={waiting} />
            </div>
          </div>
        </>
      )}

      {/* 文字描述模式 */}
      {mode === 'text' && (
        <div style={s.form}>
          <div style={s.field}>
            <label style={s.label}>产品描述 *</label>
            <textarea style={{ ...s.input, minHeight: 120, resize: 'vertical' }} placeholder="描述你的产品：它是做什么的、面向谁、与竞品有什么不同..." value={textInput} onChange={e => setTextInput(e.target.value)} disabled={waiting} />
          </div>
        </div>
      )}

      {/* 上传文件模式 */}
      {mode === 'file' && (
        <div style={s.form}>
          <div style={s.field}>
            <label style={s.label}>上传项目文件夹</label>
            <input type="file" {...{ webkitdirectory: '', directory: '' } as any} onChange={handleFiles} disabled={waiting} style={{ fontSize: 13 }} />
          </div>
          {files.length > 0 && (
            <div style={{ fontSize: 12, color: '#666', marginBottom: 8 }}>
              已选择 {files.length} 个文件：{files.map(f => f.name).join('、')}
            </div>
          )}
        </div>
      )}

      <button style={{ ...s.btn, opacity: waiting ? 0.7 : 1, marginBottom: 16 }} onClick={handleSubmit} disabled={waiting || (mode === 'github' ? !repoUrl.trim() : mode === 'text' ? !textInput.trim() : files.length === 0)}>
        {waiting ? '评测中...' : '开始评测'}
      </button>

      {waiting && (
        <div role="status" aria-live="polite" style={s.waiting}>
          <div style={s.waitSpinner}>
            <div className="af-spin" style={s.waitRingOuter}>
              <div className="af-spin-reverse" style={s.waitRingMid}>
                <div className="af-pulse" style={s.waitDot} />
              </div>
            </div>
          </div>
          <span>正在评测，大约需要 30-90 秒...</span>
        </div>
      )}
      {error && <div style={s.error}>{error}</div>}

      {/* 历史记录 */}
      {history.length > 0 && (
        <div style={{ marginBottom: 16 }}>
          <button style={s.toggleLink} onClick={() => setShowHistory(!showHistory)}>{showHistory ? '收起' : '展开'} 历史记录 ({history.length})</button>
          {showHistory && (
            <div style={s.historyBox}>
              <div style={{ display: 'flex', justifyContent: 'flex-end', marginBottom: 4 }}>
                <button style={s.clearBtn} onClick={clearAllHistory}>全部清除</button>
              </div>
              {history.map(ev => (
                <div key={ev.id} style={s.historyItem}>
                  <span style={{ fontWeight: 600, fontSize: 13, flex: 1 }}>{ev.repo}</span>
                  <Bar pct={Math.round((ev.score / 2) * 100)} />
                  <button style={s.deleteBtn} onClick={(e) => deleteHistory(ev.id, e)} title="删除">×</button>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* 评测结果 */}
      {report && (
        <>
          <ScoreCard evaluation={report.evaluation} />
          <ProjectInfo meta={report.project_meta} />
          {report.competitors_meta?.length > 0 && (
            <div style={s.card}>
              <div style={{ fontWeight: 600, fontSize: 13, marginBottom: 6 }}>竞品</div>
              <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
                {report.competitors_meta.map((c: any) => <span key={c.full_name} style={{ background: '#f0f0f5', padding: '2px 8px', borderRadius: 10, fontSize: 11, color: '#555' }}>{c.full_name}</span>)}
              </div>
            </div>
          )}
          <Suggestions data={report.evaluation.suggestions} />
          <Directions data={report.evaluation.directions} />

          {/* 持续对话 */}
          <div style={{ ...s.card, marginTop: 12 }}>
            <div style={{ fontWeight: 600, fontSize: 14, marginBottom: 10 }}>追问评测结果</div>
            <div style={{ maxHeight: 300, overflow: 'auto', marginBottom: 10 }}>
              {chatMsgs.length === 0 && <div style={{ color: '#ccc', fontSize: 12, textAlign: 'center', padding: 20 }}>在这里追问，AI 会结合评测数据回答</div>}
              {chatMsgs.map((m, i) => (
                <div key={i} style={{ marginBottom: 8, textAlign: m.role === 'user' ? 'right' : 'left' }}>
                  <div style={{
                    display: 'inline-block', maxWidth: '80%', padding: '8px 12px', borderRadius: 8,
                    background: m.role === 'user' ? '#1a1a2e' : '#f4f4f8',
                    color: m.role === 'user' ? '#fff' : '#333',
                    fontSize: 13, lineHeight: 1.5, whiteSpace: 'pre-wrap', wordBreak: 'break-word',
                  }}>{m.content}</div>
                </div>
              ))}
              {chatLoading && <div style={{ color: '#999', fontSize: 12 }}>思考中...</div>}
              <div ref={chatEndRef} />
            </div>
            <div style={{ display: 'flex', gap: 8 }}>
              <input style={{ flex: 1, ...s.chatInput }} placeholder="例如：为什么护城河得分低？怎么改进？" value={chatInput} onChange={e => setChatInput(e.target.value)} onKeyDown={e => e.key === 'Enter' && sendChat()} />
              <button style={s.chatBtn} onClick={sendChat} disabled={chatLoading}>发送</button>
            </div>
          </div>
        </>
      )}
    </div>
  );
}

function Bar({ pct }: { pct: number }) {
  const c = pct >= 80 ? '#2e7d32' : pct >= 50 ? '#e67e22' : '#c62828';
  return <div style={{ display: 'flex', alignItems: 'center', gap: 4, width: 80 }}><div style={{ flex: 1, height: 5, background: '#eee', borderRadius: 3, overflow: 'hidden' }}><div style={{ width: `${pct}%`, height: '100%', background: c, borderRadius: 3 }} /></div><span style={{ fontSize: 11, color: c, fontWeight: 600 }}>{pct}%</span></div>;
}

function ScoreCard({ evaluation }: { evaluation: EvaluateResult['evaluation'] }) {
  if (!evaluation) return null;
  const pct = Math.round((evaluation.weighted_total / 2) * 100);
  const sc = evaluation.weighted_total >= 1.5 ? '#2e7d32' : evaluation.weighted_total >= 1.0 ? '#e67e22' : '#c62828';
  const sbg = evaluation.weighted_total >= 1.5 ? '#e8f5e9' : evaluation.weighted_total >= 1.0 ? '#fff3e0' : '#ffebee';
  const grade = evaluation.weighted_total >= 1.5 ? '有竞争力' : evaluation.weighted_total >= 1.0 ? '一般水平' : '需要改进';

  return (
    <div style={s.card}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 10 }}>
        <span style={{ fontSize: 13, color: '#666' }}>综合得分</span>
        <span style={{ fontSize: 28, fontWeight: 700, color: sc }}>{pct}%</span>
        <span style={{ background: sbg, color: sc, padding: '2px 10px', borderRadius: 10, fontSize: 12, fontWeight: 600 }}>{grade}</span>
      </div>
      <div style={{ display: 'flex', gap: 6 }}>
        {DIM_KEYS.map((key, i) => {
          const dim = evaluation.scores[key];
          if (!dim) return null;
          const dpct = Math.round((dim.score / 2) * 100);
          const dc = dim.score === 0 ? '#c62828' : dim.score === 1 ? '#e67e22' : '#2e7d32';
          const dbg = dim.score === 0 ? '#ffebee' : dim.score === 1 ? '#fff3e0' : '#e8f5e9';
          return (
            <div key={key} style={{ flex: 1, textAlign: 'center', padding: '8px 4px', borderRadius: 6, background: dbg }} title={DIM_DESC[i]}>
              <div style={{ fontSize: 10, color: '#888', marginBottom: 2 }}>{DIM_NAMES[i]}</div>
              <div style={{ fontSize: 18, fontWeight: 700, color: dc }}>{dpct}%</div>
              <div style={{ fontSize: 10, color: dc, marginTop: 2 }}>{SCORE_GRADES[dim.score]}</div>
            </div>
          );
        })}
      </div>
      {evaluation.overall_summary && <div style={{ fontSize: 12, color: '#666', marginTop: 10, lineHeight: 1.6 }}>{evaluation.overall_summary}</div>}
      {evaluation.top_strengths?.length > 0 && (
        <div style={{ fontSize: 12, marginTop: 8, padding: 8, background: '#f1f8f1', borderRadius: 4 }}>
          <span style={{ color: '#2e7d32', fontWeight: 600 }}>优势：</span>{evaluation.top_strengths.map((x: string) => DIM_NAMES[DIM_KEYS.indexOf(x)] || x).filter(Boolean).join('、')}
        </div>
      )}
      {evaluation.top_weaknesses?.length > 0 && (
        <div style={{ fontSize: 12, marginTop: 4, padding: 8, background: '#fef5f5', borderRadius: 4 }}>
          <span style={{ color: '#c62828', fontWeight: 600 }}>短板：</span>{evaluation.top_weaknesses.map((x: string) => DIM_NAMES[DIM_KEYS.indexOf(x)] || x).filter(Boolean).join('、')}
        </div>
      )}
    </div>
  );
}

function ProjectInfo({ meta }: { meta: ProjectMeta }) {
  if (!meta?.full_name || meta.full_name === 'Custom Project') return null;
  return (
    <div style={s.card}>
      <div style={{ fontWeight: 600, fontSize: 14, marginBottom: 2 }}>{meta.full_name}</div>
      {meta.description && <div style={{ color: '#666', fontSize: 12, marginBottom: 4 }}>{meta.description}</div>}
      <div style={{ display: 'flex', gap: 16, fontSize: 12, color: '#888' }}>
        {meta.stars > 0 && <span>Stars <strong>{meta.stars.toLocaleString()}</strong></span>}
        {meta.language && <span>语言 <strong>{meta.language}</strong></span>}
        {meta.license_name && <span>许可 <strong>{meta.license_name}</strong></span>}
      </div>
    </div>
  );
}

function Suggestions({ data }: { data: any[] }) {
  if (!data?.length) return null;
  return (
    <div style={s.card}>
      <div style={{ fontWeight: 600, fontSize: 13, marginBottom: 8 }}>优化建议</div>
      {data.map((s: any, i: number) => (
        <div key={i} style={{ display: 'flex', gap: 8, padding: '6px 0', borderBottom: i < data.length - 1 ? '1px solid #f0f0f0' : 'none', fontSize: 12, lineHeight: 1.6 }}>
          <span style={{ background: s.priority === '高' ? '#ffebee' : s.priority === '中' ? '#fff3e0' : '#e8f5e9', color: s.priority === '高' ? '#c62828' : s.priority === '中' ? '#e67e22' : '#2e7d32', padding: '0 6px', borderRadius: 4, fontSize: 11, fontWeight: 600, flexShrink: 0, alignSelf: 'flex-start' }}>{s.priority || '—'}</span>
          <span><strong>{s.dimension || '—'}</strong>：{s.fix || '—'}</span>
        </div>
      ))}
    </div>
  );
}

function Directions({ data }: { data: string[] }) {
  if (!data?.length) return null;
  return (
    <div style={s.card}>
      <div style={{ fontWeight: 600, fontSize: 13, marginBottom: 6 }}>发展方向</div>
      {data.map((d: string, i: number) => <div key={i} style={{ fontSize: 12, color: '#555', padding: '4px 0', lineHeight: 1.5 }}>{i + 1}. {d}</div>)}
    </div>
  );
}

const s: Record<string, React.CSSProperties> = {
  card: { background: '#fff', padding: 16, borderRadius: 8, boxShadow: '0 1px 3px rgba(0,0,0,0.06)', marginBottom: 8 },
  modeBar: { display: 'flex', gap: 8, marginBottom: 14 },
  modeActive: { padding: '6px 16px', background: '#1a1a2e', color: '#fff', border: 'none', borderRadius: 6, fontSize: 13, cursor: 'pointer', fontWeight: 600 },
  modeInactive: { padding: '6px 16px', background: '#f5f5f5', color: '#666', border: '1px solid #ddd', borderRadius: 6, fontSize: 13, cursor: 'pointer' },
  presets: { display: 'flex', gap: 8, flexWrap: 'wrap', marginBottom: 10 },
  presetActive: { padding: '6px 14px', border: '2px solid #1a1a2e', borderRadius: 16, fontSize: 12, cursor: 'pointer', background: '#1a1a2e', color: '#fff', fontWeight: 600 },
  presetInactive: { padding: '6px 14px', border: '1px solid #ddd', borderRadius: 16, fontSize: 12, cursor: 'pointer', background: '#fff', color: '#333' },
  form: { background: '#fff', padding: 16, borderRadius: 8, boxShadow: '0 1px 3px rgba(0,0,0,0.06)', marginBottom: 10 },
  field: { marginBottom: 10 },
  label: { display: 'block', fontSize: 13, fontWeight: 600, marginBottom: 4, color: '#333' },
  input: { width: '100%', padding: '8px 12px', border: '1px solid #ddd', borderRadius: 6, fontSize: 14, outline: 'none', boxSizing: 'border-box' },
  btn: { width: '100%', padding: '10px', background: '#1a1a2e', color: '#fff', border: 'none', borderRadius: 6, fontSize: 14, cursor: 'pointer', fontWeight: 600 },
  waiting: { display: 'flex', alignItems: 'center', gap: 12, padding: '12px 16px', background: '#fff', border: '1px solid #e8e8f0', borderRadius: 8, marginBottom: 12, color: '#666', fontSize: 13, boxShadow: '0 1px 3px rgba(0,0,0,0.04)' },
  waitSpinner: { display: 'flex', alignItems: 'center', justifyContent: 'center', width: 44, height: 44, flexShrink: 0 },
  waitRingOuter: { width: 40, height: 40, borderRadius: '50%', border: '3px solid #e8e8f0', borderTopColor: '#1a1a2e', display: 'flex', alignItems: 'center', justifyContent: 'center' },
  waitRingMid: { width: 26, height: 26, borderRadius: '50%', border: '2px solid #dcdce8', borderBottomColor: '#6366f1', display: 'flex', alignItems: 'center', justifyContent: 'center' },
  waitDot: { width: 8, height: 8, borderRadius: '50%', background: '#1a1a2e' },
  error: { background: '#fff0f0', color: '#c00', padding: '12px 16px', borderRadius: 6, fontSize: 13, marginBottom: 12 },
  toggleLink: { background: 'none', border: 'none', color: '#666', fontSize: 13, cursor: 'pointer', padding: '2px 0', fontWeight: 600 },
  historyBox: { marginTop: 8, display: 'flex', flexDirection: 'column', gap: 2, maxHeight: 300, overflow: 'auto', background: '#fff', padding: 8, borderRadius: 6, border: '1px solid #eee' },
  historyItem: { display: 'flex', alignItems: 'center', gap: 8, padding: '6px 4px', borderBottom: '1px solid #f5f5f5' },
  deleteBtn: { background: 'none', border: 'none', color: '#c62828', fontSize: 16, cursor: 'pointer', padding: '0 4px', fontWeight: 700, lineHeight: 1 },
  clearBtn: { background: 'none', border: '1px solid #c62828', color: '#c62828', fontSize: 11, cursor: 'pointer', padding: '2px 8px', borderRadius: 4 },
  chatInput: { padding: '8px 12px', border: '1px solid #ddd', borderRadius: 6, fontSize: 13, outline: 'none' },
  chatBtn: { padding: '8px 18px', background: '#1a1a2e', color: '#fff', border: 'none', borderRadius: 6, fontSize: 13, cursor: 'pointer', fontWeight: 600 },
};
