import React, { useEffect, useMemo, useState } from "react";
import {
  Activity, ArrowDownToLine, ArrowUpRight, Bell, BriefcaseBusiness, Check,
  ChevronDown, CircleHelp, Clock3, FileText, Filter, LayoutDashboard,
  ListChecks, LoaderCircle, Menu, MoreHorizontal, Plus, Search, Settings,
  ShieldCheck, Sparkles, UploadCloud, Users, X, Zap
} from "lucide-react";

const API = (import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8000").replace(/\/$/, "");
const JOBS = [
  { id: "JOB-AI-001", title: "AI Engineer", dept: "Engineering", location: "Remote / Hybrid" },
  { id: "JOB-PY-002", title: "Python Developer", dept: "Engineering", location: "Kochi, India" },
  { id: "JOB-DA-003", title: "Data Analyst", dept: "Data", location: "Kochi, India" },
  { id: "JOB-FE-004", title: "Frontend Developer", dept: "Engineering", location: "Remote" },
  { id: "JOB-NLP-005", title: "NLP Engineer", dept: "AI Research", location: "Hybrid" }
];
const initialCandidates = [];
function mapCandidate(row) {
  const role = row.job_title || row.job_id || "Unassigned";
  const score = row.overall_score ?? null;
  return {
    id: row.candidate_id,
    name: row.name || row.candidate_id,
    role,
    score,
    status: score !== null ? (score >= 75 ? "Shortlisted" : score >= 50 ? "Review" : "Not shortlisted") : "New",
    skills: row.skills || [],
    source: "Resume upload",
    date: row.created_at ? new Date(row.created_at).toLocaleDateString() : "—",
    resumeId: row.resume_id,
    jobId: row.job_id,
    filename: row.filename,
  };
}

function Badge({children,tone="blue"}) { return <span className={`badge ${tone}`}>{children}</span>; }
function Stat({label,value,delta,icon:Icon,tone}) { return <div className="stat-card"><div className="stat-top"><span>{label}</span><span className={`stat-icon ${tone}`}><Icon size={18}/></span></div><div className="stat-value">{value}</div><div className="stat-foot"><span className="positive">{delta}</span><span>vs. last 30 days</span></div></div>; }
function initials(name="Candidate"){return name.split(" ").map(x=>x[0]).slice(0,2).join("").toUpperCase();}
async function api(path, options={}) {
  const res = await fetch(`${API}${path}`, options);
  const data = await res.json().catch(()=>({}));
  if(!res.ok) throw new Error(data?.error?.message || data?.detail?.message || data?.detail || `Request failed (${res.status})`);
  return data;
}
const sleep = ms => new Promise(r=>setTimeout(r,ms));
async function waitTask(taskId, onUpdate) {
  for(let i=0;i<45;i++){
    const task=await api(`/api/v1/tasks/${taskId}`);
    onUpdate?.(task);
    if(task.status==="completed") return task;
    if(task.status==="failed") throw new Error(task.error?.message || "Background task failed.");
    await sleep(700);
  }
  throw new Error("Task is taking longer than expected. Check task status in the API.");
}
export default function App(){
  const [page,setPage]=useState("Overview");
  const [candidates,setCandidates]=useState(initialCandidates);
  const [jobs,setJobs]=useState([]);
  const [selectedJob,setSelectedJob]=useState("");
  const [apiOnline,setApiOnline]=useState(false);
  const [search,setSearch]=useState("");
  const [notice,setNotice]=useState("");
  const [error,setError]=useState("");
  const [busy,setBusy]=useState(false);
  const [showUpload,setShowUpload]=useState(false);
  const [showScore,setShowScore]=useState(false);
  const [showShortlist,setShowShortlist]=useState(false);
  const [showJobForm,setShowJobForm]=useState(false);
  const [jobForm,setJobForm]=useState({title:"",description:"",job_id:"",file:null});
  const [uploadForm,setUploadForm]=useState({candidate_id:"CAND-021",file:null,job_id:""});
  const [scoreForm,setScoreForm]=useState({candidate_id:"",job_id:""});
  const [shortlistForm,setShortlistForm]=useState({job_id:"",top_n:5,shortlist_threshold:75,review_threshold:50});
  const [ranking,setRanking]=useState(null);
  const [taskLog,setTaskLog]=useState([]);
  const [loadingCandidates,setLoadingCandidates]=useState(false);
  async function refreshCandidates() {
    setLoadingCandidates(true);
    try {
      const data = await api("/api/v1/candidates");
      setCandidates((data.candidates || []).map(mapCandidate));
    } catch (e) {
      setError(`Could not load candidate records: ${e.message}`);
    } finally { setLoadingCandidates(false); }
  }
  useEffect(()=>{
    let active=true;
    const check=()=>api("/health").then(()=>{if(active){setApiOnline(true);refreshCandidates();api("/api/v1/jobs").then(d=>{if(active){setJobs(d.jobs||[]);if(d.jobs?.length){setSelectedJob(v=>v||d.jobs[0].job_id);setUploadForm(v=>({...v,job_id:v.job_id||d.jobs[0].job_id}));setShortlistForm(v=>({...v,job_id:v.job_id||d.jobs[0].job_id}));}}}).catch(()=>{});}}).catch(()=>{if(active)setApiOnline(false);});
    check();
    const t=setInterval(()=>api("/health").then(()=>{if(active)setApiOnline(true);}).catch(()=>{if(active)setApiOnline(false);}),15000);
    return ()=>{active=false;clearInterval(t);};
  },[]);
  const filtered=useMemo(()=>candidates.filter(c=>(`${c.name} ${c.id} ${c.role}`).toLowerCase().includes(search.toLowerCase())),[candidates,search]);
  const addLog=(label,task)=>setTaskLog(v=>[{label,task,status:"completed",time:new Date().toLocaleTimeString()},...v].slice(0,6));
  const flash=(msg)=>{setNotice(msg);setError("");setTimeout(()=>setNotice(""),5000);};
  const fail=(e)=>{setError(e.message || String(e));setNotice("");};
  async function uploadResume(e){
    e.preventDefault(); if(!uploadForm.file){fail(new Error("Choose a PDF or DOCX resume first."));return;}
    if(!uploadForm.job_id){fail(new Error("Save and select a job description before uploading a resume."));return;}
    setBusy(true);setError("");
    try{
      const fd=new FormData();fd.append("file",uploadForm.file);fd.append("candidate_id",uploadForm.candidate_id);fd.append("job_id",uploadForm.job_id);
      const result=await api("/api/v1/resumes",{method:"POST",body:fd});
      flash(`Resume uploaded. Task ${result.task_id} is processing.`);
      setTaskLog(v=>[{label:`Resume upload · ${uploadForm.candidate_id}`,task:result.task_id,status:"queued",time:new Date().toLocaleTimeString()},...v]);
      const done=await waitTask(result.task_id);
      const profile=done.result?.parsed_profile || {};
      await refreshCandidates();
      addLog("Resume parsed · "+uploadForm.candidate_id,result.task_id);
      flash(done.result?.score ? `Resume parsed and automatically scored: ${Number(done.result.score.overall_score).toFixed(1)} / 100.` : `Resume parsed. ${profile.skills?.length || 0} skills extracted. Add/select a saved job description to generate its ATS score.`);
      setShowUpload(false);setUploadForm(v=>({...v,candidate_id:`CAND-${String(Date.now()).slice(-3)}`,file:null}));
    }catch(e){fail(e);}finally{setBusy(false);}
  }
  async function scoreCandidate(e){
    e.preventDefault();setBusy(true);setError("");
    try{
      const body={job_id:scoreForm.job_id};
      const queued=await api(`/api/v1/candidates/${encodeURIComponent(scoreForm.candidate_id)}/score`,{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(body)});
      setTaskLog(v=>[{label:`Score candidate · ${scoreForm.candidate_id}`,task:queued.task_id,status:"queued",time:new Date().toLocaleTimeString()},...v]);
      const done=await waitTask(queued.task_id);const score=done.result?.overall_score ?? done.result?.score ?? null;
      await refreshCandidates();
      addLog("Candidate scored · "+scoreForm.candidate_id,queued.task_id);
      flash(`Scoring complete for ${scoreForm.candidate_id}.`);setShowScore(false);
    }catch(e){fail(e);}finally{setBusy(false);}
  }
  async function runShortlist(e){
    e.preventDefault();setBusy(true);setError("");
    try{
      const eligible=candidates.filter(c=>c.score!==null && c.score!==undefined);
      if(!eligible.length)throw new Error("Score at least one candidate before creating a ranking.");
      const body={candidates:eligible.map(c=>({candidate_id:c.id,overall_score:Number(c.score)})),top_n:Number(shortlistForm.top_n),shortlist_threshold:Number(shortlistForm.shortlist_threshold),review_threshold:Number(shortlistForm.review_threshold)};
      const queued=await api(`/api/v1/jobs/${encodeURIComponent(shortlistForm.job_id)}/shortlist`,{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(body)});
      const done=await waitTask(queued.task_id);
      const result=await api(`/api/v1/jobs/${encodeURIComponent(shortlistForm.job_id)}/rankings`);
      setRanking(result);await refreshCandidates();
      addLog("Candidate ranking generated · "+shortlistForm.job_id,queued.task_id);
      flash(`Ranking generated for ${result.count} candidates.`);setShowShortlist(false);setPage("Candidates");
    }catch(e){fail(e);}finally{setBusy(false);}
  }
  const scored=candidates.filter(c=>c.score!==null&&c.score!==undefined);
  const shortlisted=candidates.filter(c=>c.status==="Shortlisted").length;
  const nav=[["Overview",LayoutDashboard],["Candidates",Users],["Jobs",BriefcaseBusiness],["Evaluations",Activity]];
  return <div className="app-shell">
    <aside className="sidebar">
      <div className="brand"><div className="brand-mark"><Zap size={19} fill="currentColor"/></div><div><b>zecpath</b><small>RECRUITER WORKSPACE</small></div></div>
      <div className="workspace-label">WORKSPACE</div>
      <nav>{nav.map(([name,Icon])=><button key={name} className={`nav-item ${page===name?"active":""}`} onClick={()=>setPage(name)}><Icon size={18}/><span>{name}</span>{name==="Candidates"&&<em>{candidates.length}</em>}</button>)}</nav>
      <div className="sidebar-bottom"><div className="help-card"><div className="help-icon"><CircleHelp size={17}/></div><b>Need a hand?</b><p>Review API connection and demo workflow.</p><a href="http://127.0.0.1:8000/docs" target="_blank" rel="noreferrer">Open API docs <ArrowUpRight size={13}/></a></div><button className="nav-item"><Settings size={18}/>Settings</button><div className="profile"><div className="avatar dark">Z</div><div><b>Zecpath Admin</b><small>Workspace admin</small></div><MoreHorizontal size={18}/></div></div>
    </aside>
    <main className="main">
      <header className="topbar"><div className="crumb">Workspace <span>/</span> <b>{page}</b></div><div className="top-actions"><div className={`api-status ${apiOnline?"online":"offline"}`}><i/>{apiOnline?"API connected":"API offline"}</div><button className="icon-button" title="Notifications"><Bell size={18}/></button><div className="avatar">ZA</div></div></header>
      <div className="content">
        <div className="page-heading"><div><div className="eyebrow">HIRING INTELLIGENCE</div><h1>{page==="Overview"?"Good morning, Admin":page}</h1><p>{page==="Overview"?"Here's what's happening across your hiring pipeline.":page==="Candidates"?"Review candidate profiles, scores and shortlist status.":page==="Jobs"?"Manage demo roles and choose a job for ATS evaluation.":"Track parsing, scoring and ranking activity."}</p></div><div className="heading-actions"><button className="btn secondary" onClick={()=>setShowScore(true)}><Sparkles size={16}/> Score candidate</button><button className="btn primary" onClick={()=>setShowUpload(true)}><Plus size={17}/> Upload resume</button></div></div>
        {notice&&<div className="alert success"><Check size={16}/>{notice}<button onClick={()=>setNotice("")}><X size={15}/></button></div>}
        {error&&<div className="alert error"><X size={16}/>{error}<button onClick={()=>setError("")}><X size={15}/></button></div>}
        {!apiOnline&&<div className="alert warning"><CircleHelp size={17}/>Backend API is not reachable. Start FastAPI at <code>127.0.0.1:8000</code>. The dashboard preview remains available, but API actions need a live backend.</div>}
        {page==="Overview"&&<>
          <div className="stat-grid"><Stat label="Total candidates" value={candidates.length} delta="Parsed resume records" icon={Users} tone="purple"/><Stat label="Active jobs" value={jobs.length} delta="Configured in frontend demo" icon={BriefcaseBusiness} tone="blue"/><Stat label="Scored candidates" value={scored.length} delta="Component score inputs" icon={Activity} tone="teal"/><Stat label="Shortlisted" value={shortlisted} delta="Human review required" icon={ListChecks} tone="orange"/></div>
          <div className="two-col"><section className="panel pipeline-panel"><div className="panel-head"><div><h3>Hiring pipeline</h3><p>Candidate status across the demo workspace</p></div><Badge tone="green">Live workspace</Badge></div><div className="pipeline"><div><span className="pipe-num">{candidates.length}</span><span className="pipe-label">All candidates</span><div className="pipe-bar"><i style={{width:"100%"}}/></div></div><div><span className="pipe-num">{scored.length}</span><span className="pipe-label">Scored</span><div className="pipe-bar"><i style={{width:`${candidates.length?scored.length/candidates.length*100:0}%`}}/></div></div><div><span className="pipe-num">{shortlisted}</span><span className="pipe-label">Shortlisted</span><div className="pipe-bar"><i style={{width:`${candidates.length?shortlisted/candidates.length*100:0}%`}}/></div></div></div><div className="panel-foot"><ShieldCheck size={16}/> AI scores support recruiter review; final hiring decisions remain human-led.</div></section>
          <section className="panel jobs-panel"><div className="panel-head"><div><h3>Open positions</h3><p>Choose a job to work with</p></div><button className="text-btn" onClick={()=>setPage("Jobs")}>View all <ArrowUpRight size={14}/></button></div>{jobs.slice(0,4).map(j=><button className={`job-row ${selectedJob===j.job_id?"selected":""}`} key={j.job_id} onClick={()=>setSelectedJob(j.job_id)}><div className="job-symbol"><BriefcaseBusiness size={16}/></div><div className="job-info"><b>{j.title}</b><small>{j.job_id}</small></div><ChevronDown size={15}/></button>)}</section></div>
          <CandidateTable candidates={candidates.slice(0,5)} onAll={()=>setPage("Candidates")} onScore={(c)=>{setScoreForm({candidate_id:c.id,job_id:c.jobId||selectedJob});setShowScore(true);}}/>
          <div className="bottom-grid"><ActivityPanel taskLog={taskLog}/><div className="panel quick-panel"><div className="panel-head"><div><h3>Quick actions</h3><p>Continue your ATS demo</p></div><Zap size={18} className="muted"/></div><button onClick={()=>setShowUpload(true)}><UploadCloud size={17}/> Upload candidate resume <ArrowUpRight size={14}/></button><button onClick={()=>setShowScore(true)}><Sparkles size={17}/> Calculate ATS score <ArrowUpRight size={14}/></button><button onClick={()=>setShowShortlist(true)}><ListChecks size={17}/> Generate job ranking <ArrowUpRight size={14}/></button></div></div>
        </>}
        {page==="Candidates"&&<><div className="toolbar"><div className="searchbox"><Search size={16}/><input value={search} onChange={e=>setSearch(e.target.value)} placeholder="Search candidates or IDs..."/></div><div className="toolbar-right"><select value={selectedJob} onChange={e=>setSelectedJob(e.target.value)}>{jobs.map(j=><option value={j.job_id} key={j.job_id}>{j.title}</option>)}</select><button className="btn secondary small" onClick={refreshCandidates} disabled={loadingCandidates}><Activity size={15}/> {loadingCandidates?"Refreshing…":"Refresh"}</button><button className="btn secondary small" onClick={()=>setShowShortlist(true)}><Filter size={15}/> Rank & shortlist</button></div></div><CandidateTable candidates={filtered} onScore={(c)=>{setScoreForm({candidate_id:c.id,job_id:c.jobId||selectedJob});setShowScore(true);}} full/></>}
        {page==="Jobs"&&<><div className="toolbar"><p>Saved job descriptions used to score candidate resumes.</p><button className="btn primary" onClick={()=>setShowJobForm(true)}><Plus size={16}/> Add job description</button></div><div className="job-grid">{jobs.map(j=><div className="panel job-card" key={j.job_id}><div className="job-symbol large"><BriefcaseBusiness size={20}/></div><Badge tone="blue">JD parsed and saved</Badge><h3>{j.title}</h3><p>{j.description?.slice(0,180) || "Job description saved"}</p><small>{j.job_id}</small><button className="btn secondary small" onClick={()=>{setSelectedJob(j.job_id);setUploadForm(v=>({...v,job_id:j.job_id}));setShortlistForm(v=>({...v,job_id:j.job_id}));setPage("Candidates");}}>View candidates <ArrowUpRight size={14}/></button></div>)}{!jobs.length&&<div className="empty">No job descriptions yet. Add one to start automatic ATS scoring.</div>}</div></>}
        {page==="Evaluations"&&<><div className="stat-grid"><Stat label="Latest local test run" value="100/100" delta="Reported by project owner" icon={ShieldCheck} tone="teal"/><Stat label="Day 17 F1 score" value="0.80" delta="8 synthetic labelled pairs" icon={Activity} tone="blue"/><Stat label="Day 18 benchmark" value="20/20" delta="Local extraction benchmark" icon={Clock3} tone="purple"/><Stat label="Fairness group audit" value="Pending" delta="No group statistics recorded" icon={ShieldCheck} tone="orange"/></div><div className="panel evaluation-note"><h3>Evaluation caveats</h3><ul><li>Day 17 precision, recall and F1 were measured on only 8 synthetic labelled pairs.</li><li>Day 20 demo scoring used skill overlap only; all 100 candidate–job results were marked partial.</li><li>Group-level fairness statistics were not available in the supplied report.</li><li>The latest 100 passing tests were reported by the project owner and were not rerun by this frontend.</li></ul><p>Do not interpret ATS scores as hiring probabilities. Human review is required.</p></div></>}
        <footer className="footer">© 2026 Zecpath AI <span>Recruiter decision-support prototype · Day 20 demo</span></footer>
      </div>
    </main>
    {showJobForm&&<Modal title="Add job description" subtitle="Define the role or upload a JD to parse and save it for automatic candidate scoring." onClose={()=>setShowJobForm(false)}><form onSubmit={async e=>{e.preventDefault();setBusy(true);setError("");try{let created;if(jobForm.file){const fd=new FormData();fd.append("file",jobForm.file);fd.append("title",jobForm.title);if(jobForm.job_id)fd.append("job_id",jobForm.job_id);created=await api("/api/v1/jobs/upload",{method:"POST",body:fd});}else{created=await api("/api/v1/jobs",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({job_id:jobForm.job_id||null,title:jobForm.title,description:jobForm.description})});}const data=await api("/api/v1/jobs");setJobs(data.jobs||[]);setSelectedJob(created.job_id);setUploadForm(v=>({...v,job_id:created.job_id}));setShortlistForm(v=>({...v,job_id:created.job_id}));setJobForm({title:"",description:"",job_id:"",file:null});setShowJobForm(false);flash(`Job description saved: ${created.title}`);}catch(err){fail(err);}finally{setBusy(false);}}}><label>Job title<input required value={jobForm.title} onChange={e=>setJobForm(v=>({...v,title:e.target.value}))} placeholder="AI Engineer"/></label><label>Job ID (optional)<input value={jobForm.job_id} onChange={e=>setJobForm(v=>({...v,job_id:e.target.value}))} placeholder="JOB-AI-001"/></label><label className="dropzone"><FileText size={24}/><b>{jobForm.file?.name||"Upload JD file (optional)"}</b><span>TXT, PDF or DOCX · Or paste the description below</span><input type="file" accept=".txt,.pdf,.docx" onChange={e=>setJobForm(v=>({...v,file:e.target.files?.[0]||null}))}/></label><label>Full job description<textarea rows={7} value={jobForm.description} onChange={e=>setJobForm(v=>({...v,description:e.target.value}))} placeholder="Required when no file is uploaded. Paste responsibilities, skills, experience and education requirements…" required={!jobForm.file} minLength={jobForm.file?0:30}/></label><ModalActions busy={busy} onCancel={()=>setShowJobForm(false)} action="Parse & save job"/></form></Modal>}
    {showUpload&&<Modal title="Upload candidate resume" subtitle="Submit a PDF or DOCX file to the Zecpath API." onClose={()=>setShowUpload(false)}><form onSubmit={uploadResume}><label>Candidate ID<input required value={uploadForm.candidate_id} onChange={e=>setUploadForm(v=>({...v,candidate_id:e.target.value}))}/></label><label>Job position<select value={uploadForm.job_id} onChange={e=>setUploadForm(v=>({...v,job_id:e.target.value}))}>{jobs.map(j=><option key={j.job_id} value={j.job_id}>{j.title} ({j.job_id})</option>)}</select></label><label className="dropzone"><UploadCloud size={26}/><b>{uploadForm.file?.name || "Choose resume file"}</b><span>PDF or DOCX · Maximum 10 MB</span><input type="file" accept=".pdf,.docx" required onChange={e=>setUploadForm(v=>({...v,file:e.target.files?.[0]||null}))}/></label><ModalActions busy={busy} onCancel={()=>setShowUpload(false)} action="Upload & parse"/></form></Modal>}
    {showScore&&<Modal title="Calculate ATS score" subtitle="Generate a fresh score from the candidate resume and selected saved job description." onClose={()=>setShowScore(false)}><form onSubmit={scoreCandidate}><label>Candidate ID<input required value={scoreForm.candidate_id} onChange={e=>setScoreForm(v=>({...v,candidate_id:e.target.value}))}/></label><label>Job position<select value={scoreForm.job_id} onChange={e=>setScoreForm(v=>({...v,job_id:e.target.value,role:jobs.find(j=>j.job_id===e.target.value)?.title||""}))}>{jobs.map(j=><option value={j.job_id} key={j.job_id}>{j.title}</option>)}</select></label><p className="form-hint">Scores are calculated automatically using the existing skill, experience, education, semantic matching and weighted ATS engines.</p><ModalActions busy={busy} onCancel={()=>setShowScore(false)} action="Calculate score"/></form></Modal>}
    {showShortlist&&<Modal title="Rank & shortlist candidates" subtitle="Send scored candidates to the existing ranking and shortlist API." onClose={()=>setShowShortlist(false)}><form onSubmit={runShortlist}><label>Job position<select value={shortlistForm.job_id} onChange={e=>setShortlistForm(v=>({...v,job_id:e.target.value}))}>{jobs.map(j=><option value={j.job_id} key={j.job_id}>{j.title}</option>)}</select></label><div className="score-fields"><label>Top candidates<input type="number" min="1" max="1000" value={shortlistForm.top_n} onChange={e=>setShortlistForm(v=>({...v,top_n:e.target.value}))}/></label><label>Shortlist threshold<input type="number" min="0" max="100" value={shortlistForm.shortlist_threshold} onChange={e=>setShortlistForm(v=>({...v,shortlist_threshold:e.target.value}))}/></label><label>Review threshold<input type="number" min="0" max="100" value={shortlistForm.review_threshold} onChange={e=>setShortlistForm(v=>({...v,review_threshold:e.target.value}))}/></label></div><p className="form-hint">{scored.length} candidate(s) currently have a score. Only scored candidates are sent.</p><ModalActions busy={busy} onCancel={()=>setShowShortlist(false)} action="Generate ranking"/></form></Modal>}
  </div>;
}
function CandidateTable({candidates,onAll,onScore,full=false}){
  return <section className="panel table-panel"><div className="panel-head"><div><h3>{full?"All candidates":"Recent candidates"}</h3><p>{full?"Candidate records loaded from parsed resumes":"Latest candidate activity and ATS status"}</p></div>{!full&&<button className="text-btn" onClick={onAll}>View all <ArrowUpRight size={14}/></button>}</div><div className="table-wrap"><table><thead><tr><th>Candidate</th><th>Applied role</th><th>Skills</th><th>ATS score</th><th>Status</th><th></th></tr></thead><tbody>{candidates.map(c=><tr key={c.id}><td><div className="candidate-cell"><div className="avatar candidate-avatar">{initials(c.name)}</div><div><b>{c.name}</b><small>{c.id}</small></div></div></td><td>{c.role}</td><td><div className="skill-list">{(c.skills||[]).slice(0,3).map(s=><span key={s}>{s}</span>)}</div></td><td>{c.score===null||c.score===undefined?<span className="muted">Not scored</span>:<div className="score-cell"><b>{Number(c.score).toFixed(1)}</b><div className="mini-track"><i style={{width:`${Math.max(0,Math.min(100,c.score))}%`}}/></div></div>}</td><td><Badge tone={c.status==="Shortlisted"?"green":c.status==="Review"?"amber":c.status==="New"?"blue":"gray"}>{c.status}</Badge></td><td><button className="row-action" title="Score candidate" onClick={()=>onScore(c)}><Sparkles size={15}/></button></td></tr>)}</tbody></table>{!candidates.length&&<div className="empty">No parsed candidate records yet. Upload a PDF or DOCX resume to begin.</div>}</div></section>
}
function ActivityPanel({taskLog}){return <section className="panel activity-panel"><div className="panel-head"><div><h3>Recent activity</h3><p>API tasks from this session</p></div><Activity size={18} className="muted"/></div>{taskLog.length?taskLog.map((t,i)=><div className="activity-row" key={i}><span className="activity-dot"><Check size={12}/></span><div><b>{t.label}</b><small>{t.task} · {t.time}</small></div><Badge tone="green">{t.status}</Badge></div>):<div className="empty compact">No API tasks yet. Upload a resume to begin.</div>}</section>}
function Modal({title,subtitle,onClose,children}){return <div className="modal-backdrop" onMouseDown={e=>{if(e.target===e.currentTarget)onClose();}}><div className="modal"><div className="modal-head"><div><h2>{title}</h2><p>{subtitle}</p></div><button className="icon-button" onClick={onClose}><X size={18}/></button></div>{children}</div></div>}
function ModalActions({busy,onCancel,action}){return <div className="modal-actions"><button type="button" className="btn secondary" onClick={onCancel} disabled={busy}>Cancel</button><button type="submit" className="btn primary" disabled={busy}>{busy?<><LoaderCircle className="spin" size={16}/> Processing…</>:action}</button></div>}
