'use strict';
let state=null, currentView='review', limit=15, renderId='', busy=false;
let onlyNew=true,preferenceLoaded=false;
let feedbackContext=null,feedbackDraft=null;
const $=id=>document.getElementById(id);
const esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const safe=v=>{try{const u=new URL(v);return ['http:','https:'].includes(u.protocol)?esc(u.href):'#';}catch{return '#';}};
const date=(value,withTime=false)=>value?new Intl.DateTimeFormat('zh-CN',{timeZone:'Europe/Berlin',month:'2-digit',day:'2-digit',...(withTime?{hour:'2-digit',minute:'2-digit',hour12:false}:{})}).format(new Date(value)):'未知';
const isoDay=v=>new Intl.DateTimeFormat('sv-SE',{timeZone:'Europe/Berlin',year:'numeric',month:'2-digit',day:'2-digit'}).format(new Date(v));
const labels={review:'待人工筛查',excluded:'已排除'};
const notes={review:'所有候选合并在此；自动核验状态和缺口分别标在卡片内。请核对原文后决定是否申请。',excluded:'保留排除原因，便于核对筛选是否符合你的要求。'};
const group=j=>j.display_group||(j.classification==='excluded'?'excluded':'review');

function card(j,number){
  const stamp=j.posted?(j.posted.slice(0,10)+(j.date_precision==='day'?' · 仅日期':'')):'发布时间待确认';
  const employment=j.fulltime_confirmed?'已找到 Vollzeit 依据':j.employment?.includes('PART_TIME')?'标注 Teilzeit':'工时待确认';
  const reasons=(j.reasons||[]).slice(0,4);
  const topMatches=(j.matches||[]).slice(0,2);
  return `<article class="job-card"><div class="job-topline"><span><b class="job-number">#${j.number||number}</b><span class="company">${esc(j.company||'公司待确认')}</span></span><span class="status ${group(j)}">${labels[group(j)]}</span></div>
    <h3><button class="title-link" data-external-url="${safe(j.url)}">${esc(j.title)}</button></h3>
    <div class="meta"><strong>${esc(j.location||'地点待确认')}</strong><span>${esc(j.role_type)}</span><span>${employment}</span><span>${esc(j.salary)}</span></div>
    ${topMatches.length?`<div class="match">${topMatches.map(m=>`<p>${esc(m.reason)}</p>`).join('')}</div>`:''}
    <p class="privacy-note">${esc(j.verification_label||'请人工核对证据')}</p>${reasons.length?`<ul class="reasons">${reasons.map(r=>`<li>· ${esc(r)}</li>`).join('')}</ul>`:''}
    <div class="job-keywords">实际命中 ${j.search_terms?.map(k=>`<span>${esc(k)}</span>`).join('')||'未记录'}</div>
    <div class="meta"><span>发布 ${esc(stamp)}</span>${j.portal_posted&&j.portal_posted!==j.posted?`<span>门户日期 ${esc(j.portal_posted.slice(0,10))}</span>`:''}</div>
    <div class="job-bottom"><span class="source-name">${esc(j.source)} · 核验于 ${date(j.checked_at,true)}</span><span>${j.classification!=='excluded'?`<button class="feedback-btn" data-feedback="${esc(j.key)}">不适合我</button>`:''}<button class="details-btn" data-evidence="${esc(j.key)}" aria-expanded="false">查看依据与原文 ＋</button></span></div>
    <div class="evidence" id="evidence-${esc(j.key)}" hidden><dl>${(j.evidence||[]).map(e=>`<dt>${esc(e.label)}</dt><dd>${esc(e.text)}</dd>`).join('')}${(j.matches||[]).map(e=>`<dt>${esc(e.label)} · 职位原文</dt><dd>${esc(e.evidence)}</dd>`).join('')}</dl>
    <div class="source-links"><button data-external-url="${safe(j.url)}">来源详情 ↗</button>${j.apply_url?`<button data-external-url="${safe(j.apply_url)}">${j.apply_status==='verified'?'已核验的申请入口':'申请入口 · 状态待确认'} ↗</button>`:''}</div>
    ${(j.sources||[]).length>1?`<p>合并来源：${j.sources.map(s=>`<button class="inline-link" data-external-url="${safe(s.url)}">${esc(s.name)}</button>`).join('、')}</p>`:''}
    <details><summary>读取到的岗位正文</summary><div class="raw">${esc(j.description)}</div></details></div></article>`;
}

function showJobs(){
  const all=state?.snapshot?.jobs||[],jobs=all.filter(j=>!onlyNew||j.is_new!==false);
  $('delta-note').textContent=`本轮共 ${all.length} 个岗位，其中 ${all.filter(j=>j.is_new!==false).length} 个此前未出现；${all.filter(j=>j.is_new===false).length} 个已出现。${onlyNew?'当前只看新增。':'当前展示本轮全部。'}去重范围：本机采集历史。`;
  for(const key of Object.keys(labels))$(`n-${key}`).textContent=jobs.filter(j=>group(j)===key).length;
  document.querySelectorAll('.tab').forEach(b=>{b.classList.toggle('active',b.dataset.view===currentView);b.setAttribute('aria-pressed',String(b.dataset.view===currentView));});
  $('view-note').textContent=notes[currentView];
  const list=jobs.filter(j=>group(j)===currentView);
  if(!list.length){
    const isScanning=state?.latest_attempt?.status==='running';
    const title=!state?.snapshot?(isScanning?'正在采集首批真实岗位':'先设置需求，再开始搜索'):`本批暂无${labels[currentView]}记录`;
    const body='可取消“只显示此前没出现过的岗位”查看本轮全部，或调整关键词和搜索设置。来源状态及读取缺口记录在右侧和下方。';
    $('jobs').innerHTML=`<div class="empty"><div class="empty-mark">◎</div><h3>${title}</h3><p>${body}</p></div>`;
  }else $('jobs').innerHTML=list.slice(0,limit).map((job,index)=>card(job,index+1)).join('')+(list.length>limit?`<button class="load-more" id="more">再显示 ${Math.min(15,list.length-limit)} 条 · 共 ${list.length} 条</button>`:'');
}

function showHeader(){
  const snap=state.snapshot,attempt=state.latest_attempt,today=isoDay(state.now);
  const hour=Number(new Intl.DateTimeFormat('en-GB',{timeZone:'Europe/Berlin',hour:'2-digit',hourCycle:'h23'}).format(new Date(state.now)));
  const scanning=attempt?.status==='running';
  $('refresh').disabled=scanning||busy;
  $('refresh').innerHTML=`<span class="refresh-icon">↻</span> ${scanning?'正在抓取与核验…':'抓取截至现在的近24小时新岗'}`;
  $('progress').hidden=!scanning;
  if(scanning){$('progress-label').textContent=attempt.progress||'正在扫描';$('progress-count').textContent=attempt.total?`${attempt.completed} / ${attempt.total}`:'';$('progress-bar').value=attempt.total?attempt.completed/attempt.total*100:2;}
  let heading='尚无岗位批次',note='首次采集完成后显示真实结果。',notice='';
  if(snap){
    const day=snap.edition_date;
    if(state.mode==='manual'){
      heading='手动抓取的最新岗位';note=`近24小时窗口截至 ${date(snap.stats?.window_end||snap.started,true)} · 采集完成于 ${date(snap.finished,true)}`;
    }else if(state.mode==='initial'){
      heading='首次采集的岗位';note=`实际采集于 ${date(snap.finished,true)}，没有可回溯的昨日批次。`;
      notice='这是安装后的首次采集，不是昨天的历史数据。今后按德国工作日 18:00 保存并切换批次。';
    }else if(day===today){heading='今天的岗位';note=`${day} 批次 · 完成于 ${date(snap.finished,true)} · 检查此前24小时的新发布职位`;}
    else{
      const yesterday=new Date(`${today}T12:00:00Z`);yesterday.setUTCDate(yesterday.getUTCDate()-1);
      heading=day===yesterday.toISOString().slice(0,10)?'这是昨天的岗位':`${day} 的岗位`;
      note=`${hour<18?'尚未到今天18:00，':'今日批次尚未完成，'}展示最近的工作日扫描结果 · ${date(snap.finished,true)}`;
      if(state.stale)notice=`期望批次为 ${state.target_date}，当前仍显示 ${day} 的结果。旧数据不会被标成今天。`;
    }
    if(snap.status==='partial')notice+=(notice?' ':'')+'本轮部分来源或详情读取失败，已标明覆盖缺口。';
  }
  if(attempt?.status==='failed')notice='最近一次扫描失败。'+(snap?'继续保留上次已完成结果。':'目前没有可用岗位批次。')+' 请查看检索记录，联网后重试。';
  $('headline').textContent=heading;$('date-note').textContent=note;
  $('edition-tag').textContent=`${today} · 德国时间 ${new Intl.DateTimeFormat('en-GB',{timeZone:'Europe/Berlin',hour:'2-digit',minute:'2-digit',hour12:false}).format(new Date(state.now))}`;
  $('notice').hidden=!notice;$('notice').textContent=notice;$('notice').classList.toggle('error',attempt?.status==='failed');
  $('schedule-note').textContent=state.schedule?.installed?'已启用本机计划任务。周一至周五，德国时间 18:00 开始扫描。':'自动扫描未启用；可手动抓取，或按使用说明安装本机计划任务。';
  $('quit-app').hidden=!state.desktop_packaged;
  $('desktop-controls').hidden=!state.desktop_packaged;
  $('enable-schedule').disabled=false;
  $('enable-schedule').textContent=state.schedule?.installed?'更新自动扫描位置':'启用自动扫描';
  $('disable-schedule').disabled=!state.schedule?.installed;
  $('profile-summary').textContent=state.profile.themes.length?state.profile.themes.join(' · '):'按搜索关键词查找；不按优先方向排除';
  $('last-check').textContent=snap?`最后成功采集：${date(snap.finished,true)}`:'还没有成功采集记录';
}

function showSources(){
  const failed=state.latest_attempt?.status==='failed';
  const snap=failed?state.latest_attempt:state.snapshot,queries=snap?.queries||[],stats=snap?.stats||{};
  $('audit-title').textContent=failed?'最新失败批次的检索记录（岗位保留上次结果）':'查看本轮检索记录';
  $('keywords').innerHTML=state.keywords.map(k=>`<div class="keyword-row"><label><input type="checkbox" data-keyword-toggle="${k.id}" ${k.enabled?'checked':''}> <span>${esc(k.term)}</span></label><span><button data-keyword-edit="${k.id}">编辑</button><button data-keyword-delete="${k.id}">删除</button></span></div>`).join('');
  $('query-label').textContent=queries.length?`${queries.length} 次读取`:'计划使用的关键词';
  $('source-count').textContent=snap?`${stats.source_ok||0} / ${stats.source_total||state.sources.length} 可读取`:'尚未实测';
  $('source-list').innerHTML=state.sources.map(s=>{
    const q=queries.filter(q=>q.source===s.name),good=q.filter(x=>x.status==='ok'),failed=q.filter(x=>x.status!=='ok');
    const cls=!q.length?'waiting':failed.length?'error':'';
    const label=!q.length?'待扫描':!good.length?'读取失败':failed.length?'部分失败':'已读取';
    return `<div class="source-row"><div><button class="inline-link" data-external-url="${safe(s.base)}">${esc(s.name)}</button>${s.region?`<small>${esc(s.region)}</small>`:''}</div><span class="source-state ${cls}" title="${esc(failed[0]?.error||'')}">${s.enabled?label:'已停用'}</span></div>`;
  }).join('');
  $('coverage-note').textContent=snap?`实际读取 ${stats.detail_count||0} 个详情，合并 ${stats.dedup_count||0} 个重复项。每个关键词最多 ${stats.pages_per_query||2} 页、每个来源最多 ${stats.detail_limit_per_source||35} 个近期候选；${stats.limited_queries||0} 次查询仍有后续页。全国覆盖不代表穷尽全网。`:'关键词和来源仅为计划清单，完成扫描后才会标注为“已读取”。';
  $('audit-count').textContent=queries.length?`${queries.length} 次读取 · ${stats.detail_errors?.length||0} 个详情失败`:'关键词 · 查询链接 · 读取状态';
  let rows=queries.map(q=>`<tr><td>${esc(q.source)}</td><td><button class="inline-link" data-external-url="${safe(q.url)}">${esc(q.keyword)}</button><br>第 ${q.page||'—'} 页</td><td>${q.status==='ok'?`${q.count} 条${q.limited?' · 有后续页':''}`:`<span class="audit-error">${esc(q.error||'未读取')}</span>`}</td><td>${date(q.at,true)}</td></tr>`).join('');
  for(const err of stats.detail_errors||[])rows+=`<tr><td>${esc(err.source)}</td><td><button class="inline-link" data-external-url="${safe(err.url)}">${esc(err.title)}</button></td><td class="audit-error">${esc(err.error)}</td><td>详情读取失败</td></tr>`;
  $('audit-content').innerHTML=(stats.error?`<p class="audit-error">${esc(stats.error)}</p>`:'')+(rows?`<table><thead><tr><th>来源</th><th>实际搜索词 / 岗位</th><th>读取结果</th><th>德国时间</th></tr></thead><tbody>${rows}</tbody></table>`:'<p>没有可显示的查询记录。</p>');
}

function showSettings(){
  const p=state.profile;
  const expansion=state.expansion||{enabled:true,status:'pending',added:[]};
  $('auto-expand').checked=expansion.enabled;
  const summary=!expansion.enabled?'自动扩展已停用':expansion.status==='complete'?`首轮扩展已完成：新增 ${expansion.added.length} 个词，下次扫描使用。`:'首轮扩展等待至少两份候选 JD；当前按你启用的词搜索。';
  $('expansion-summary').textContent=summary;
  $('expansion-details').innerHTML=`<p>${esc(summary)}</p>`+expansion.added.map(k=>`<p><strong>${esc(k.term)}</strong><br>${esc(k.reason)}<br><small>原文依据：${esc(k.evidence)}<br>批次：${esc(expansion.run_id)} · 岗位标识：${k.job_keys.map(esc).join('、')}</small></p>`).join('');
  $('role-regular').checked=p.role_types.includes('regular');
  $('profile-fulltime').checked=p.fulltime_required;
  $('role-internship').checked=p.role_types.includes('internship');
  $('role-werkstudent').checked=p.role_types.includes('werkstudent_fulltime');
  $('profile-relocation').checked=p.relocation;
  $('profile-themes').value=p.themes.join(', ');
  $('profile-exclusions').value=p.exclusions.join(', ');
  $('profile-notes').value=p.notes||'';
  $('source-settings').innerHTML=state.sources.map(s=>{const t=s.last_test;const tested=t?(t.status==='supported'?`测试通过 · ${t.result_count} 个搜索结果${t.detail_parsed?' · 详情可读':''}`:t.message):'尚未单独测试';return `<div class="setting-row"><span><strong>${esc(s.name)}</strong><small>${esc(tested)}</small></span><span><button type="button" data-source-test="${esc(s.id)}">测试</button><input aria-label="启用 ${esc(s.name)}" type="checkbox" data-source-toggle="${esc(s.id)}" ${s.enabled?'checked':''}></span></div>`;}).join('');
  $('openai-status').textContent=state.openai?.configured?'OpenAI 已连接；密钥保存在 Windows 凭据保险库。':'尚未保存 OpenAI API Key。';
  $('delete-openai-key').hidden=!state.openai?.configured;
  $('cv-status').innerHTML=state.cv?`<p><strong>${esc(state.cv.original_name)}</strong><br>已在本机提取 ${state.cv.chars} 个字符。</p>`:'<p>尚未上传简历。</p>';
  $('delete-cv').hidden=!state.cv;$('analyze-cv').disabled=!(state.cv&&state.openai?.configured);
  $('learned-rule-settings').innerHTML=state.learned_rules.length?state.learned_rules.map(r=>`<div class="rule-row"><label><input type="checkbox" data-rule-toggle="${esc(r.id)}" ${r.enabled?'checked':''}> <span><strong>${esc(r.title)}</strong><small>${esc(r.rule.explanation)}</small></span></label><button data-rule-delete="${esc(r.id)}">删除</button></div>`).join(''):'<p>还没有学习规则。</p>';
}

async function load(){
  try{
    const response=await fetch('/api/state');if(!response.ok)throw new Error('本机服务暂不可用');
    state=await response.json();showHeader();
    if(!preferenceLoaded){onlyNew=state.display?.only_new!==false;$('only-new').checked=onlyNew;preferenceLoaded=true;}
    $('confirm-display').textContent=state.display?.confirmed?'保存显示规则':'确认此显示规则';
    const id=(state.snapshot?.id||'none')+'-'+(state.latest_attempt?.id||'none')+'-'+(state.latest_attempt?.status||'none')+'-'+JSON.stringify([state.keywords,state.sources,state.profile,state.expansion,state.learned_rules,state.cv,state.openai]);
    if(id!==renderId){renderId=id;showJobs();showSources();showSettings();}
  }catch(error){$('notice').hidden=false;$('notice').classList.add('error');$('notice').textContent='连接本机应用失败。请重新打开“德国岗位雷达”，已有数据仍保存在本机。';}
}

$('refresh').addEventListener('click',async()=>{
  if(!state||busy)return;busy=true;showHeader();
  try{const r=await fetch('/api/scan',{method:'POST',headers:{'X-Radar-Token':state.token}});if(!r.ok)throw new Error('无法启动扫描');await new Promise(resolve=>setTimeout(resolve,500));await load();}
  catch(e){$('notice').hidden=false;$('notice').textContent=e.message;}finally{busy=false;showHeader();}
});
document.addEventListener('click',e=>{
  const external=e.target.closest('[data-external-url]');
  if(external){e.preventDefault();post('/api/open-external',{url:external.dataset.externalUrl}).catch(error=>toast(error.message));return;}
  const tab=e.target.closest('[data-view],[data-switch]');
  if(tab){currentView=tab.dataset.view||tab.dataset.switch;limit=15;showJobs();return;}
  const button=e.target.closest('[data-evidence]');
  if(button){const panel=$('evidence-'+button.dataset.evidence);panel.hidden=!panel.hidden;button.setAttribute('aria-expanded',String(!panel.hidden));button.textContent=panel.hidden?'查看依据与原文 ＋':'收起核验依据 −';return;}
  const edit=e.target.closest('[data-keyword-edit]');
  if(edit){const item=state.keywords.find(k=>k.id===Number(edit.dataset.keywordEdit));const term=prompt('编辑搜索关键词',item.term);if(term&&term.trim()!==item.term)post('/api/keywords/update',{id:item.id,term:term.trim(),enabled:item.enabled}).then(()=>{renderId='';return load();}).catch(error=>toast(error.message));return;}
  const del=e.target.closest('[data-keyword-delete]');
  if(del){const item=state.keywords.find(k=>k.id===Number(del.dataset.keywordDelete));if(confirm(`删除关键词“${item.term}”？`))post('/api/keywords/delete',{id:item.id}).then(()=>{renderId='';return load();}).catch(error=>toast(error.message));return;}
  const feedback=e.target.closest('[data-feedback]');
  if(feedback){const job=state.snapshot.jobs.find(j=>j.key===feedback.dataset.feedback);feedbackContext={scan_id:state.snapshot.id,job_key:job.key,job};feedbackDraft=null;$('feedback-job').textContent=`${job.company} · ${job.title}`;$('feedback-note').value='';$('feedback-preview').hidden=true;$('feedback-preview').innerHTML='';$('accept-feedback').disabled=true;$('feedback-dialog').showModal();return;}
  const ruleDelete=e.target.closest('[data-rule-delete]');
  if(ruleDelete){if(confirm('删除这条 AI 学习规则？'))post('/api/rules/delete',{id:ruleDelete.dataset.ruleDelete}).then(()=>{renderId='';return load();}).catch(error=>toast(error.message));return;}
  const sourceTest=e.target.closest('[data-source-test]');
  if(sourceTest){sourceTest.disabled=true;sourceTest.textContent='测试中…';post('/api/sources/test',{id:sourceTest.dataset.sourceTest}).then(result=>{renderId='';toast(result.test.message);return load();}).catch(error=>toast(error.message)).finally(()=>{sourceTest.disabled=false;sourceTest.textContent='测试';});return;}
  if(e.target.id==='more'){limit+=15;showJobs();}
});

function toast(message){$('toast').textContent=message;$('toast').hidden=false;setTimeout(()=>{$('toast').hidden=true;},7000);}
async function post(path,data){const r=await fetch(path,{method:'POST',headers:{'Content-Type':'application/json','X-Radar-Token':state.token},body:JSON.stringify(data)});const result=await r.json();if(!r.ok)throw new Error(result.error||'操作失败');return result;}
$('only-new').addEventListener('change',()=>{onlyNew=$('only-new').checked;limit=15;showJobs();});
$('confirm-display').addEventListener('click',async()=>{try{await post('/api/display',{only_new:onlyNew});toast(onlyNew?'已确认：默认只显示此前未出现的岗位':'已确认：默认显示本轮全部岗位');await load();}catch(e){toast(e.message);}});
$('export-csv').addEventListener('click',async()=>{const button=$('export-csv');button.disabled=true;try{const r=await fetch('/api/export.csv',{method:'POST',headers:{'Content-Type':'application/json','X-Radar-Token':state.token},body:JSON.stringify({})});if(!r.ok){const value=await r.json();throw new Error(value.error||'导出失败');}const blob=await r.blob(),link=document.createElement('a');link.href=URL.createObjectURL(blob);link.download=`德国岗位-全部-${state.snapshot?.id||isoDay(state.now)}.csv`;document.body.appendChild(link);link.click();link.remove();URL.revokeObjectURL(link.href);toast('本轮两个列表全部导出，包含已出现岗位；CSV 标注为只作为建议');}catch(error){toast(error.message);}finally{button.disabled=false;}});
$('auto-expand').addEventListener('change',async e=>{try{await post('/api/expansion',{enabled:e.target.checked});renderId='';await load();toast('首轮扩展开关已保存');}catch(error){e.target.checked=!e.target.checked;toast(error.message);}});
$('open-settings').addEventListener('click',()=>{$('settings-dialog').showModal();});
$('close-settings').addEventListener('click',()=>{$('settings-dialog').close();});
$('keyword-form').addEventListener('submit',async e=>{e.preventDefault();const input=$('new-keyword');try{await post('/api/keywords',{term:input.value,enabled:true});input.value='';renderId='';await load();toast('关键词已添加，下次扫描生效');}catch(error){toast(error.message);}});
$('profile-form').addEventListener('submit',async e=>{e.preventDefault();const role_types=[];if($('role-regular').checked)role_types.push('regular');if($('role-internship').checked)role_types.push('internship');if($('role-werkstudent').checked)role_types.push('werkstudent_fulltime');const split=id=>$(id).value.split(/[,，]/).map(x=>x.trim()).filter(Boolean);try{await post('/api/profile',{role_types,fulltime_required:$('profile-fulltime').checked,locations:['Deutschland'],relocation:$('profile-relocation').checked,themes:split('profile-themes'),exclusions:split('profile-exclusions'),notes:$('profile-notes').value});renderId='';await load();toast('求职目标已保存；请同步调整关键词中的 Praktikum 或 Intern 限定');}catch(error){toast(error.message);}});
$('custom-source-form').addEventListener('submit',async e=>{e.preventDefault();const button=e.target.querySelector('button');button.disabled=true;button.textContent='正在实际读取…';$('custom-source-result').textContent='正在测试搜索页和岗位详情。';try{const source=await post('/api/sources/custom',{name:$('custom-source-name').value,url:$('custom-source-url').value});e.target.reset();$('custom-source-result').textContent=`已添加 ${source.name}，下次扫描生效。`;renderId='';await load();}catch(error){$('custom-source-result').textContent=error.message;toast(error.message);}finally{button.disabled=false;button.textContent='测试并添加网址';}});
$('openai-form').addEventListener('submit',async e=>{e.preventDefault();const input=$('openai-key');try{await post('/api/openai/credential',{api_key:input.value});input.value='';renderId='';await load();toast('OpenAI 凭据已安全保存');}catch(error){toast(error.message);}});
$('delete-openai-key').addEventListener('click',async()=>{if(!confirm('删除 Windows 凭据保险库中的 OpenAI API Key？'))return;try{await post('/api/openai/delete',{});renderId='';await load();toast('OpenAI 凭据已删除');}catch(error){toast(error.message);}});
$('cv-upload-form').addEventListener('submit',async e=>{e.preventDefault();const file=$('cv-file').files[0];if(!file)return;const form=new FormData();form.append('file',file);try{const r=await fetch('/api/cv',{method:'POST',headers:{'X-Radar-Token':state.token},body:form});const result=await r.json();if(!r.ok)throw new Error(result.error||'上传失败');$('cv-file').value='';renderId='';await load();toast(`已在本机读取 ${result.chars} 个字符`);}catch(error){toast(error.message);}});
$('delete-cv').addEventListener('click',async()=>{if(!confirm('删除本机保存的简历和提取文字？'))return;try{await post('/api/cv/delete',{});$('ai-draft').innerHTML='';renderId='';await load();toast('本机简历已删除');}catch(error){toast(error.message);}});
$('analyze-cv').addEventListener('click',async()=>{const button=$('analyze-cv');button.disabled=true;button.textContent='AI 正在分析…';try{const draft=await post('/api/cv/analyze',{});$('ai-draft').innerHTML=`<h4>AI 建议的搜索词</h4><form id="apply-ai-keywords">${draft.keywords.map((k,i)=>`<label><input type="checkbox" name="keyword" value="${esc(k)}" checked> ${esc(k)}</label>`).join('')}<h4>简历已证明</h4><p>${draft.demonstrated_capabilities.map(esc).join('、')||'无'}</p><h4>加入前需要确认</h4><p>${draft.needs_confirmation.map(esc).join('、')||'无'}</p><button class="primary">加入选中的关键词</button></form>`;}catch(error){toast(error.message);}finally{button.disabled=false;button.textContent='用 AI 分析并生成关键词';}});
document.addEventListener('submit',async e=>{if(e.target.id!=='apply-ai-keywords')return;e.preventDefault();const keywords=[...e.target.querySelectorAll('input[name=keyword]:checked')].map(x=>x.value);try{const result=await post('/api/cv/apply-keywords',{keywords});renderId='';await load();toast(result.message);}catch(error){toast(error.message);}});
$('close-feedback').addEventListener('click',()=>$('feedback-dialog').close());
$('cancel-feedback').addEventListener('click',()=>$('feedback-dialog').close());
$('feedback-form').addEventListener('submit',async e=>{e.preventDefault();if(!feedbackContext)return;const button=$('analyze-feedback');button.disabled=true;button.textContent='AI 正在分析…';try{feedbackDraft=await post('/api/feedback/analyze',{scan_id:feedbackContext.scan_id,job_key:feedbackContext.job_key,category:$('feedback-category').value,note:$('feedback-note').value});const r=feedbackDraft.rule;$('feedback-preview').innerHTML=`<h3>AI 对这次反馈的理解</h3><p><strong>${esc(r.title)}</strong></p><p>${esc(r.explanation)}</p><p>作用范围：${r.scope.map(esc).join('、')||'全部'}<br>不适合信号：${r.negative_any.map(esc).join('、')||'无'}<br>出现这些内容则保留：${r.keep_if_any.map(esc).join('、')||'无'}<br><strong>硬排除（优先于保留条件）：${r.hard_exclude_any.map(esc).join('、')||'无'}</strong></p><p class="privacy-note">本次发送岗位内容、你的原因、求职目标和现有规则，不发送简历文字。确认后才会保存并影响类似岗位。</p>`;$('feedback-preview').hidden=false;$('accept-feedback').disabled=false;}catch(error){toast(error.message);}finally{button.disabled=false;button.textContent='让 AI 分析这次反馈';}});
$('accept-feedback').addEventListener('click',async()=>{if(!feedbackDraft)return;const button=$('accept-feedback');button.disabled=true;try{const result=await post('/api/feedback/accept',feedbackDraft);$('feedback-dialog').close();feedbackDraft=null;renderId='';await load();toast(result.message);}catch(error){toast(error.message);button.disabled=false;}});
document.addEventListener('change',async e=>{
  const kid=e.target.dataset.keywordToggle;
  if(kid){const item=state.keywords.find(k=>k.id===Number(kid));try{await post('/api/keywords/update',{id:item.id,term:item.term,enabled:e.target.checked});renderId='';await load();}catch(error){e.target.checked=!e.target.checked;toast(error.message);}return;}
  const sid=e.target.dataset.sourceToggle;
  if(sid){try{await post('/api/sources/toggle',{id:sid,enabled:e.target.checked});renderId='';await load();}catch(error){e.target.checked=!e.target.checked;toast(error.message);}}
  const rid=e.target.dataset.ruleToggle;
  if(rid){const item=state.learned_rules.find(r=>r.id===rid);try{await post('/api/rules/update',{id:rid,rule:item.rule,enabled:e.target.checked});renderId='';await load();}catch(error){e.target.checked=!e.target.checked;toast(error.message);}}
});
for(const [id,enabled] of [['enable-schedule',true],['disable-schedule',false]]){
  $(id).addEventListener('click',async()=>{const button=$(id);button.disabled=true;try{const result=await post('/api/desktop/schedule',{enabled});renderId='';await load();toast(result.message);}catch(error){toast(error.message);button.disabled=false;}});
}
$('quit-app').addEventListener('click',async()=>{if(!confirm('退出本机应用？已启用的18点计划任务仍会运行。'))return;try{const result=await post('/api/desktop/quit',{});clearInterval(pollTimer);$('headline').textContent='应用已退出';$('date-note').textContent='可关闭这个页面；下次双击 EXE 即可重新打开。';toast(result.message);}catch(error){toast(error.message);}});
load();const pollTimer=setInterval(load,5000);
