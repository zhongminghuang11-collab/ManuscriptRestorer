/* ManuscriptRestorer 1.0 — all manuscript images stay local. */
'use strict';
const $ = id => document.getElementById(id);
const canvas = $('pageCanvas'), ctx = canvas.getContext('2d');
const labels = {replace:'替换', delete:'删除', insert_before:'前插', insert_after:'后插'};
let project = {name:'未命名手稿',version:'1.0',pages:[]};
let pageIndex=0, selected=null, pendingBox=null, dragStart=null;
let picture=null, renderSerial=0, result=null, inkRegions=[];
const past=[], future=[];
const uid=p=>'_'+p+'_'+(typeof crypto!=='undefined'&&crypto.randomUUID?crypto.randomUUID().slice(0,10):Date.now().toString(36)+Math.random().toString(36).slice(2,7));
const current=()=>project.pages[pageIndex]||null;
const tokens=()=>current()?.tokens||[];
const edits=()=>current()?.edits||[];
const sortTokens=()=>[...tokens()].sort((a,b)=>a.line-b.line||a.order-b.order);
const status=(msg, error=false)=>{$('status').textContent=msg;$('status').style.color=error?'#ac3748':'#54708b';};
function button(text, fn, cls=''){const x=document.createElement('button');x.textContent=text;x.className='mini '+cls;x.addEventListener('click',fn);return x;}
function snapshot(){const p=current();if(!p)return;past.push({index:pageIndex,tokens:JSON.stringify(p.tokens),edits:JSON.stringify(p.edits)});if(past.length>30)past.shift();future.length=0;}
function restore(item, other){const p=current();if(!p)return;other.push({index:pageIndex,tokens:JSON.stringify(p.tokens),edits:JSON.stringify(p.edits)});pageIndex=item.index;const pg=current();if(!pg)return;pg.tokens=JSON.parse(item.tokens);pg.edits=JSON.parse(item.edits);selected=null;showPage();}
$('undoBtn').onclick=()=>{if(past.length)restore(past.pop(),future);else status('没有可撤销的页面修改');};
$('redoBtn').onclick=()=>{if(future.length)restore(future.pop(),past);else status('没有可重做的页面修改');};
document.addEventListener('keydown',e=>{if(!(e.ctrlKey||e.metaKey)||e.altKey)return;if(e.key.toLowerCase()==='z'&&!['INPUT','TEXTAREA','SELECT'].includes(document.activeElement.tagName)){e.preventDefault();if(e.shiftKey)$('redoBtn').click();else $('undoBtn').click();}});
async function api(route, data){const response=await fetch(route,{method:'POST',headers:{'Content-Type':'application/json','X-MR-Client':'1'},body:JSON.stringify(data)});const obj=await response.json();if(!response.ok)throw Error(obj.error||'请求失败');return obj;}
async function get(route){const r=await fetch(route);const o=await r.json();if(!r.ok)throw Error(o.error||'无法读取');return o;}
function dataUrl(file){return new Promise((resolve,reject)=>{const reader=new FileReader();reader.onload=()=>resolve(reader.result);reader.onerror=()=>reject(new Error('无法读取文件'));reader.readAsDataURL(file);});}
function download(name,data,mime){const blob=new Blob([data],{type:mime});const url=URL.createObjectURL(blob);const a=document.createElement('a');a.href=url;a.download=name;document.body.appendChild(a);a.click();a.remove();setTimeout(()=>URL.revokeObjectURL(url),5000);}
function shallowProject(){return {pages:project.pages.map(p=>({tokens:p.tokens,edits:p.edits}))};}
function emptyPage(name,image){return {id:uid('page'),name,image,tokens:[],edits:[]};}
function activate(index){if(index<0||index>=project.pages.length)return;pageIndex=index;selected=null;pendingBox=null;inkRegions=[];showPage();}
function showPage(){const p=current();picture=null;if(!p){canvas.width=950;canvas.height=560;$('imgInfo').textContent='尚无图片';render();return;}
  if(p.image){const im=new Image();const key=p.id;im.onload=()=>{if(current()?.id!==key)return;picture=im;canvas.width=im.naturalWidth;canvas.height=im.naturalHeight;$('imgInfo').textContent=`${im.naturalWidth} × ${im.naturalHeight}`;draw();};im.onerror=()=>status('图片读取失败',true);im.src=p.image;}
  else{$('imgInfo').textContent='本页无图片';} render();}
function draw(){ctx.clearRect(0,0,canvas.width,canvas.height);
  if(picture?.complete&&picture.naturalWidth){ctx.drawImage(picture,0,0,canvas.width,canvas.height);}
  else{ctx.fillStyle='#f3f7fc';ctx.fillRect(0,0,canvas.width,canvas.height);ctx.fillStyle='#6b809a';ctx.textAlign='center';ctx.font='23px sans-serif';ctx.fillText('导入图片 / PDF 或加载演示',canvas.width/2,canvas.height/2);ctx.textAlign='left';}
  for(const r of inkRegions){const b=r.bbox;ctx.strokeStyle='#f4a45b';ctx.lineWidth=1;ctx.setLineDash([3,4]);ctx.strokeRect(b[0],b[1],b[2]-b[0],b[3]-b[1]);ctx.setLineDash([]);}
  for(const t of tokens()){const b=t.bbox;if(!b)continue;ctx.strokeStyle=t.id===selected?'#e89a20':'#377fd2';ctx.fillStyle=t.id===selected?'rgba(255,170,30,.16)':'rgba(47,121,215,.07)';ctx.lineWidth=t.id===selected?3:2;ctx.fillRect(b[0],b[1],b[2]-b[0],b[3]-b[1]);ctx.strokeRect(b[0],b[1],b[2]-b[0],b[3]-b[1]);}
  for(const e of edits()){const b=e.bbox;if(!b)continue;ctx.strokeStyle=e.status==='confirmed'?'#c42d57':'#eb6c6c';ctx.lineWidth=2;ctx.setLineDash([6,5]);ctx.strokeRect(b[0],b[1],b[2]-b[0],b[3]-b[1]);ctx.setLineDash([]);}
  if(pendingBox){const b=pendingBox;ctx.strokeStyle='#13a183';ctx.fillStyle='rgba(19,161,131,.13)';ctx.lineWidth=3;ctx.fillRect(b[0],b[1],b[2]-b[0],b[3]-b[1]);ctx.strokeRect(b[0],b[1],b[2]-b[0],b[3]-b[1]);}
}
function point(e){const r=canvas.getBoundingClientRect();return [Math.round((e.clientX-r.left)*canvas.width/r.width),Math.round((e.clientY-r.top)*canvas.height/r.height)];}
canvas.addEventListener('pointerdown',e=>{if(!picture)return;canvas.setPointerCapture(e.pointerId);dragStart=point(e);pendingBox=null;});
canvas.addEventListener('pointermove',e=>{if(!dragStart)return;const p=point(e);pendingBox=[Math.min(dragStart[0],p[0]),Math.min(dragStart[1],p[1]),Math.max(dragStart[0],p[0]),Math.max(dragStart[1],p[1])];draw();});
canvas.addEventListener('pointerup',e=>{if(!dragStart)return;const p=point(e),s=dragStart;dragStart=null;
  if(Math.abs(s[0]-p[0])<6&&Math.abs(s[1]-p[1])<6){pendingBox=null;const hit=tokens().filter(t=>t.bbox&&p[0]>=t.bbox[0]&&p[0]<=t.bbox[2]&&p[1]>=t.bbox[1]&&p[1]<=t.bbox[3]);if(hit.length)selected=hit[hit.length-1].id;render();return;}
  pendingBox=[Math.min(s[0],p[0]),Math.min(s[1],p[1]),Math.max(s[0],p[0]),Math.max(s[1],p[1])];draw();});
function refreshTarget(){const el=$('editTarget'),prev=el.value;el.replaceChildren();for(const t of sortTokens()){const o=document.createElement('option');o.value=t.id;o.textContent=`行${t.line} · ${t.text.slice(0,26)}`;el.append(o);}if(selected&&tokens().some(x=>x.id===selected))el.value=selected;else if(tokens().some(x=>x.id===prev))el.value=prev;}
function renderPages(){const box=$('pageTabs');box.replaceChildren();$('pageIndex').textContent=`${project.pages.length? pageIndex+1:0} / ${project.pages.length}`;
 for(let i=0;i<project.pages.length;i++){const p=project.pages[i];const b=button(`${i+1}. ${p.name||'未命名页'} (${p.tokens?.length||0})`,()=>activate(i),'page-tab'+(i===pageIndex?' active':''));b.title=p.name;box.append(b);}
 $('prevPage').disabled=pageIndex===0;$('nextPage').disabled=pageIndex>=project.pages.length-1;$('removePage').disabled=!current();}
function renderTokens(){const box=$('tokens');box.replaceChildren();$('tokenCount').textContent=`${tokens().length} 片段`;
 if(!tokens().length){const p=document.createElement('p');p.className='hint';p.textContent='未识别文字：请点击OCR，或在图片上框选并录入。';box.append(p);return;}
 for(const t of sortTokens()){
  const row=document.createElement('div');row.className='entry'+(t.id===selected?' selected':'');
  const ln=document.createElement('span');ln.className='n';ln.textContent=`行${t.line}`;row.append(ln);
  const field=document.createElement('input');field.value=t.text;field.title='校正OCR原文字；不会直接替换为终稿';field.addEventListener('change',()=>{if(!field.value){field.value=t.text;status('文字不能为空',true);return;}if(field.value===t.text)return;snapshot();t.text=field.value;render();});row.append(field);
  const info=document.createElement('span');info.className='conf';info.textContent=t.confidence==null?'人工/无分数':`${Math.round(t.confidence*100)}%`;row.append(info);
  row.append(button('定位',()=>{selected=t.id;pendingBox=null;render();}));
  row.append(button('移前',()=>{snapshot();const s=sortTokens().filter(x=>x.line===t.line);const i=s.findIndex(x=>x.id===t.id);if(i>0){const v=s[i-1].order;s[i-1].order=t.order;t.order=v;}render();}));
  row.append(button('换行号',()=>{const val=prompt('新的行号（从0开始）',String(t.line));if(val===null)return;const n=Number(val);if(!Number.isInteger(n)||n<0){status('行号无效',true);return;}snapshot();t.line=n;t.order=Math.max(0,...tokens().filter(x=>x.line===n).map(x=>x.order+1));render();}));
  row.append(button('删框',()=>{if(edits().some(e=>e.target_id===t.id)){status('该文字框存在修改事件，请先移除修改',true);return;}snapshot();current().tokens=tokens().filter(x=>x.id!==t.id);if(selected===t.id)selected=null;render();},'danger'));
  box.append(row);
 }
}
function renderEdits(){const box=$('edits');box.replaceChildren();$('editCount').textContent=`${edits().length}项`;
 if(!edits().length){const p=document.createElement('p');p.className='hint';p.textContent='未添加修改事件。红笔检测可产生待确认建议。';box.append(p);return;}
 for(const e of edits()){
  const t=tokens().find(x=>x.id===e.target_id);const row=document.createElement('div');row.className='entry'+(e.status!=='confirmed'?' muted':'');
  const span=e.span||([e.op==='replace'||e.op==='delete'?0:e.op==='insert_before'?0:t?.text.length||0,e.op==='replace'||e.op==='delete'?t?.text.length||0:e.op==='insert_before'?0:t?.text.length||0]);
  const matched=(t?.text||'').slice(span[0],span[1]);const info=document.createElement('span');info.className='txt';
  info.textContent=`${labels[e.op]}「${matched||'∅'}」${e.op==='delete'?'':` →「${e.text}」`}`;row.append(info);
  const meta=document.createElement('span');meta.className='meta';meta.textContent=({'confirmed':'已确认','proposed':'待审','rejected':'已拒绝'})[e.status]||e.status;row.append(meta);
  if(e.source==='red-strike-geometry'){const conf=document.createElement('span');conf.className='conf suspect';conf.textContent='几何推断·需人工核对';row.append(conf);}
  if(e.status!=='confirmed')row.append(button('确认',()=>{if(!t){status('文字框不存在',true);return;}const val=prompt('请核实：实际被划掉的原文是什么？（确认前可按取消）',matched);if(val===null)return;if(val!==matched){const pos=t.text.indexOf(val);if(!val||pos<0){status('在该文字框找不到此原文，请先修正OCR结果',true);return;}}let replacement=e.text;
    if(e.op!=='delete'){
      const confirmedText=prompt('请确认图片中的真实替换/插入文字：',e.text);
      if(confirmedText===null)return;
      if(!confirmedText){status('非删除操作的新文字不能为空',true);return;}
      replacement=confirmedText;
    } else if(confirm('这条候选只表示可能有删除线，请检查有无替换字。\n确认删除此原文吗？')===false)return;
    const proposedSpan=val===matched?e.span:[t.text.indexOf(val),t.text.indexOf(val)+val.length];
    const conflict=edits().find(other=>other.id!==e.id&&other.status==='confirmed'&&other.target_id===e.target_id&&['replace','delete'].includes(other.op)&&['replace','delete'].includes(e.op)&&Math.max(other.span?.[0]||0,proposedSpan[0])<Math.min(other.span?.[1]??t.text.length,proposedSpan[1]));
    if(conflict){status('该范围已有已确认的替换/删除，先撤回现有事件再确认建议',true);return;}
    snapshot();e.span=proposedSpan;e.text=replacement;e.status='confirmed';render();}));
  if(e.status==='confirmed')row.append(button('撤回',()=>{snapshot();e.status='proposed';render();}));
  if(e.status==='proposed')row.append(button('拒绝',()=>{snapshot();e.status='rejected';render();}));
  if(e.status==='rejected')row.append(button('重新审核',()=>{snapshot();e.status='proposed';render();}));
  row.append(button('移除',()=>{snapshot();current().edits=edits().filter(a=>a.id!==e.id);render();},'danger'));
  box.append(row);
 }
}
async function renderOutput(){const number=++renderSerial;if(!project.pages.length){result=null;$('original').textContent='—';$('final').textContent='—';$('resultStatus').textContent='等待输入';return;}
 try{const d=await api('/api/reconstruct',shallowProject());if(number!==renderSerial)return;result=d;$('original').textContent=d.original||'（空）';$('final').textContent=d.final||'（空）';$('resultStatus').textContent=`${d.counts.confirmed}已确认 / ${d.counts.pending}待审 / ${d.counts.rejected}已拒绝`;
 }catch(e){if(number!==renderSerial)return;result=null;$('resultStatus').textContent='修改冲突';$('final').textContent='⚠ '+e.message;status('检查修改范围：'+e.message,true);}}
function render(){renderPages();refreshTarget();renderTokens();renderEdits();draw();renderOutput();
 const v=current()?.visionReview,details=$('visionDetails');details.hidden=!v;
 if(v)$('visionSummary').textContent=JSON.stringify({modelTranscription:v.transcription_lines,uncertain:v.uncertain,unmatched:v.unmatched},null,2);
}
async function handleImages(files){if(!files.length)return;const accepted=[...files].filter(f=>['image/png','image/jpeg','image/webp'].includes(f.type));if(accepted.length!==files.length){status('只支持PNG、JPEG、WebP图片',true);return;}
 if(project.pages.length+accepted.length>30){status('单项目最多30页',true);return;}
 for(const f of accepted){if(f.size>16*1024*1024){status(`${f.name}超过16MB`,true);return;}}
 for(const f of accepted){const image=await dataUrl(f);project.pages.push(emptyPage(f.name,image));}
 project.name=$('projectName').value||'未命名手稿';activate(project.pages.length-accepted.length);status(`已导入${accepted.length}张图片；选择当前页后运行OCR或手动核对。`);}
$('upload').onchange=async e=>{try{await handleImages(e.target.files);}catch(e){status(e.message,true);}e.target.value='';};
$('uploadPdf').onchange=async e=>{const f=e.target.files?.[0];if(!f)return;try{if(f.size>20*1024*1024)throw Error('PDF超过20MB');status('正在在本机渲染PDF页面…');const d=await api('/api/pdf',{data:(await dataUrl(f)).split(',',2)[1]});if(project.pages.length+d.pages.length>30)throw Error('导入后超过30页上限');const start=project.pages.length;for(const p of d.pages)project.pages.push(emptyPage(`${f.name} · ${p.name}`,p.image));activate(start);status(`已导入PDF的${d.pages.length}页，接下来可逐页运行本地OCR。`);}catch(err){status('PDF导入失败：'+err.message,true);}e.target.value='';};
$('demoBtn').onclick=async()=>{if(project.pages.length&&!confirm('载入演示会替换当前工作区，确定吗？'))return;try{project=await get('/api/demo');$('projectName').value=project.name;past.length=0;future.length=0;activate(0);status('演示已载入：可以查看人工确认修改、撤回、导出。');}catch(e){status(e.message,true);}};
$('prevPage').onclick=()=>activate(pageIndex-1);$('nextPage').onclick=()=>activate(pageIndex+1);
$('removePage').onclick=()=>{if(!current())return;if(!confirm('删除本页及其所有标注？此操作不能撤销。'))return;project.pages.splice(pageIndex,1);past.length=0;future.length=0;pageIndex=Math.min(pageIndex,Math.max(0,project.pages.length-1));showPage();};
$('ocrBtn').onclick=async()=>{const p=current();if(!p?.image){status('请先导入当前页图片',true);return;}if(p.tokens.length&&!confirm('重新OCR会清空当前页所有文字框及修改记录。建议先保存项目。是否继续？'))return;
 const roi=$('ocrRegion').checked?pendingBox:null;if($('ocrRegion').checked&&!roi){status('请先在图片上拖动框选OCR区域',true);return;}
 const btn=$('ocrBtn');btn.disabled=true;status('正在运行本地OCR，请查看进度…');try{const id=p.id;const d=await api('/api/ocr',{image:p.image,engine:$('ocrEngine').value,roi,remove_red:$('removeRed').checked});if(current()?.id!==id){status('已切换页面，OCR结果未覆盖其他页面');return;}snapshot();p.tokens=d.tokens;p.edits=[];selected=null;pendingBox=null;render();status(`已使用${d.engine}识别${p.tokens.length}个文字片段。OCR不等于原文正确，请逐字核对。`);}catch(err){status('OCR失败：'+err.message,true);}finally{btn.disabled=false;}};
$('strikeBtn').onclick=async()=>{const p=current();if(!p?.image||!p.tokens.length){status('请先识别或录入当前页文字',true);return;}const btn=$('strikeBtn');btn.disabled=true;
 try{const d=await api('/api/marks',{image:p.image,tokens:p.tokens});snapshot();inkRegions=d.ink_regions;let added=0;for(const e of d.proposals){if(edits().some(x=>x.target_id===e.target_id&&x.span?.join(',')===e.span.join(',')&&x.op==='delete'))continue;p.edits.push(e);added++;}render();status(`找到${added}项候选划除，全部标记为待审。红笔区域数量：${inkRegions.length}。`);}catch(e){status(e.message,true);}finally{btn.disabled=false;}};
$('visionBtn').onclick=async()=>{const p=current();if(!p?.image){status('请先导入图片',true);return;}
 const btn=$('visionBtn');btn.disabled=true;status('正调用本机Ollama视觉模型；大模型初次启动可能需要较长时间。');
 try{const d=await api('/api/vision',{image:p.image,tokens:p.tokens,model:$('visionModel').value.trim()});snapshot();
 for(const item of d.proposals){if(!p.edits.some(e=>e.target_id===item.target_id&&e.op===item.op&&JSON.stringify(e.span)===JSON.stringify(item.span)))p.edits.push(item);}
 // Preserve model evidence even when OCR anchors cannot be matched.
 p.visionReview={transcription_lines:d.transcription_lines,uncertain:d.uncertain,unmatched:d.unmatched};
 render();let msg=`视觉模型提出${d.proposals.length}条待审核修改，${d.unmatched.length}条因无法定位未采用；`;
 if(d.uncertain.length)msg+=`模型还标记${d.uncertain.length}处不确定。`;
 status(msg);alert('视觉模型分析完成。待审建议在右侧「修改事件」里。\n\n无法定位/不确定项目：\n'+JSON.stringify({unmatched:d.unmatched,uncertain:d.uncertain,transcription:d.transcription_lines},null,2).slice(0,1800));
 }catch(e){status('本地视觉模型失败：'+e.message,true);}finally{btn.disabled=false;}};
$('addTokenBtn').onclick=()=>{const p=current(),txt=$('newText').value.trim(),line=Number($('newLine').value);if(!p||!pendingBox){status('请先有图片并在图片上框选',true);return;}if(!txt||!Number.isInteger(line)||line<0){status('请输入原始文字与有效行号',true);return;}snapshot();p.tokens.push({id:uid('manual'),text:txt,bbox:pendingBox,line,order:Math.max(0,...p.tokens.filter(t=>t.line===line).map(t=>t.order+1)),source:'manual'});selected=p.tokens[p.tokens.length-1].id;pendingBox=null;$('newText').value='';render();status('已录入一个原文片段。');};
$('splitBtn').onclick=()=>{const t=tokens().find(x=>x.id===selected),needle=$('splitNeedle').value;if(!t){status('先选中文字框',true);return;}if(!needle){status('请填写要拆出的文字',true);return;}if(edits().some(e=>e.target_id===t.id)){status('这个框存在修改事件，请先移除该事件再拆分',true);return;}
 const idx=t.text.indexOf(needle);if(idx<0||needle===t.text){status('输入的文字必须是该框中的真子串',true);return;}
 snapshot();const parts=[t.text.slice(0,idx),needle,t.text.slice(idx+needle.length)].filter(Boolean),old=tokens().indexOf(t);let consumed=0;
 const resultParts=parts.map(s=>{let box=null;if(t.bbox){const [x1,y1,x2,y2]=t.bbox,w=x2-x1,total=t.text.length;let a=x1+Math.round(w*consumed/total),b=x1+Math.round(w*(consumed+s.length)/total);box=[a,y1,Math.max(a+1,b),y2];}consumed+=s.length;return {...t,id:uid('split'),text:s,bbox:box,source:'estimated-split'};});
 const later=tokens().filter(x=>x.line===t.line&&x.order>t.order);later.forEach(x=>x.order+=resultParts.length-1);resultParts.forEach((x,i)=>x.order=t.order+i);
 current().tokens.splice(old,1,...resultParts);selected=resultParts.find(x=>x.text===needle)?.id||resultParts[0].id;$('splitNeedle').value='';render();status('拆分成功；框坐标为按长度估算，请核实。');};
$('editOp').onchange=()=>{$('editText').disabled=$('editOp').value==='delete';if($('editOp').value==='delete')$('editText').value='';};
$('addEditBtn').onclick=()=>{const p=current();if(!p)return;const op=$('editOp').value,txt=$('editText').value,tid=$('editTarget').value,t=tokens().find(x=>x.id===tid);if(!t){status('先选择修改目标框',true);return;}if(op!=='delete'&&!txt){status('请填写新文字',true);return;}
 const needle=$('editNeedle').value, idx=needle?t.text.indexOf(needle):0;
 if(idx<0){status('当前OCR原文中找不到该子串，先校正OCR文本',true);return;}
 const start=idx,end=idx+(needle?needle.length:t.text.length);
 const span=['replace','delete'].includes(op)?[start,end]:op==='insert_before'?[start,start]:[end,end];
 snapshot();p.edits.push({id:uid('edit'),op,target_id:tid,text:op==='delete'?'':txt,span,status:'confirmed',source:'manual',...(pendingBox?{bbox:pendingBox}:{})});
 pendingBox=null;$('editText').value='';$('editNeedle').value='';render();status('已记录修改；若修改区域冲突，右侧会显示错误，撤销或撤回即可。');};
$('saveProject').onclick=async()=>{if(!project.pages.length){status('先导入图片或演示',true);return;}try{project.name=$('projectName').value.trim()||'未命名手稿';const d=await api('/api/project/save',project);project.id=d.project.id;project.updated_at=d.project.updated_at;project.created_at||=d.project.updated_at;status(`已保存 ${project.name}（${project.pages.length}页）到程序的本地data/projects文件夹。`);}catch(e){status('保存失败：'+e.message,true);}};
$('loadProject').onclick=async()=>{try{const d=await get('/api/projects');const box=$('savedProjects');box.replaceChildren();if(!d.projects.length){const p=document.createElement('p');p.textContent='目前没有本地保存的项目。';box.append(p);}for(const item of d.projects){const row=document.createElement('div');row.className='entry';const lbl=document.createElement('span');lbl.className='txt';lbl.textContent=`${item.name} · ${item.pages}页 · ${item.updated_at}`;row.append(lbl);row.append(button('打开',async()=>{if(project.pages.length&&!confirm('打开项目会替换工作区未保存的内容。继续？'))return;try{project=await get('/api/project/'+item.id);$('projectName').value=project.name;past.length=0;future.length=0;activate(0);$('projectsDialog').close();status('已打开本地项目。');}catch(e){status(e.message,true);}}));row.append(button('删除',async()=>{if(!confirm('永久删除这个本地项目？'))return;try{await api('/api/project/delete',{id:item.id});row.remove();status('项目已删除。');}catch(e){status(e.message,true);}},'danger'));box.append(row);} $('projectsDialog').showModal();}catch(e){status(e.message,true);}};
$('closeDialog').onclick=()=>$('projectsDialog').close();
$('exportProject').onclick=()=>{if(!project.pages.length){status('没有可导出的页面',true);return;}project.name=$('projectName').value||'未命名手稿';download('手稿项目完整备份.json',JSON.stringify(project,null,2),'application/json;charset=utf-8');};
$('importProject').onchange=async e=>{try{const f=e.target.files?.[0];if(!f)return;if(f.size>44*1024*1024)throw Error('项目文件超过44MB');let obj=JSON.parse(await f.text());if(!obj.pages&&Array.isArray(obj.tokens))obj={name:'从旧版导入',version:'1.0',pages:[{id:uid('page'),name:'第1页',image:obj.image||null,tokens:obj.tokens,edits:obj.edits}]};
 await api('/api/reconstruct',{pages:obj.pages?.map(p=>({tokens:p.tokens,edits:p.edits}))});if(project.pages.length&&!confirm('导入项目会替换当前工作区，确定吗？'))return;project=obj;$('projectName').value=obj.name||'未命名手稿';past.length=0;future.length=0;activate(0);status('项目导入成功。');}catch(err){status('导入失败：'+err.message,true);}e.target.value='';};
$('saveOriginal').onclick=()=>{if(result)download('原稿全文.txt',result.original,'text/plain;charset=utf-8');};
$('saveFinal').onclick=()=>{if(result)download('终稿全文.txt',result.final,'text/plain;charset=utf-8');};
$('saveRecords').onclick=()=>{if(result)download('修改轨迹.json',JSON.stringify({operations:result.operations,pages:result.pages.map((p,i)=>({page:i+1,pending:p.pending,rejected:p.rejected}))},null,2),'application/json;charset=utf-8');};
$('saveReport').onclick=()=>{if(!result)return;const low=project.pages.flatMap((p,i)=>p.tokens.filter(t=>typeof t.confidence==='number'&&t.confidence<.65).map(t=>`第${i+1}页：${t.text}（OCR置信度${Math.round(t.confidence*100)}%）`));
 const visionNotes=project.pages.flatMap((p,i)=>p.visionReview?[`第${i+1}页：未定位${p.visionReview.unmatched?.length||0}项，存疑${p.visionReview.uncertain?.length||0}项`]:[]);
 const lines=[`项目：${project.name}` , `页面数量：${project.pages.length}`,`确认修改：${result.counts.confirmed}`,`待确认：${result.counts.pending}`,`拒绝候选：${result.counts.rejected}`,`OCR低置信度文字框：${low.length}`,'','低置信度文字框：',...(low.length?low:['无（可能未运行OCR，不能视为准确）']), '', '视觉模型未定位和存疑：',...visionNotes,'', '说明：仅检测有限的红色横线，复杂笔迹未得到全自动解释；人工逐字核对必不可少。'];
 download('核对质量报告.txt',lines.join('\n'),'text/plain;charset=utf-8');};
(async()=>{try{const h=await get('/api/health');$('engineStatus').textContent=`本地环境：Tesseract ${h.tesseract?'就绪':'未安装'} · PaddleOCR ${h.paddle?'就绪':'未安装'} · PDF ${h.pdf?'可用':'需依赖'}`;}catch(e){$('engineStatus').textContent='无法连接后端服务';}render();})();
