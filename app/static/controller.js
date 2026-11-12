import {api,state,params,currentSession,sessionActive} from './model.js';
import * as V from './view.js';

const app=document.querySelector('#app'),modal=document.querySelector('#modal');
let renderVersion=0,toastTimer,ws,wsTimer,cameraStream,cameraTimer,cameraGeneration=0,localVideoUrl;

function toast(message){const node=document.querySelector('#toast');node.textContent=message;node.hidden=false;clearTimeout(toastTimer);toastTimer=setTimeout(()=>node.hidden=true,4500);}
function formError(form,error){const node=form.querySelector('.form-error');if(node){node.textContent=error.message||String(error);node.hidden=false;node.scrollIntoView({block:'nearest'});}else toast(error.message||String(error));}
async function formAction(form,action){const button=form.querySelector('[type=submit]');if(button?.disabled)return;const label=button?.textContent;if(button){button.disabled=true;button.textContent='正在保存…';}const error=form.querySelector('.form-error');if(error)error.hidden=true;try{await action();}catch(e){formError(form,e);}finally{if(button?.isConnected){button.disabled=false;button.textContent=label;}}}
function closeModal(){modal.close();modal.innerHTML='';}
function openModal(content){modal.innerHTML=content;modal.showModal();}
function queryFilters(){const {fromLocal,toLocal,...f}=state.filters;return f;}
function ensureSession(){if(!state.sessions.some(s=>String(s.id)===String(state.sessionId)))state.sessionId=String(state.sessions.find(sessionActive)?.id||state.sessions[0]?.id||'');}
async function basics(){const calls=[api('/api/sessions'),api('/api/courses')];if(state.user.role==='admin')calls.push(api('/api/admin/users'));const [sessions,courses,users]=await Promise.all(calls);state.sessions=sessions;state.courses=courses;if(users)state.users=users;ensureSession();}
function disconnect(){clearTimeout(wsTimer);if(ws){const old=ws;ws=null;old.close();}}
function stopCamera(){cameraGeneration++;clearTimeout(cameraTimer);if(cameraStream)cameraStream.getTracks().forEach(t=>t.stop());cameraStream=null;const video=document.querySelector('#camera-video');if(video){video.pause();video.srcObject=null;video.removeAttribute('src');video.controls=false;}if(localVideoUrl)URL.revokeObjectURL(localVideoUrl);localVideoUrl=null;const preview=document.querySelector('#camera-preview');if(preview)preview.hidden=true;const source=document.querySelector('#sampling-source');if(source)source.hidden=true;const start=document.querySelector('#camera-start'),stop=document.querySelector('#camera-stop'),label=document.querySelector('#local-video-label');if(start){start.hidden=false;start.disabled=false;}if(label)label.hidden=false;if(stop)stop.hidden=true;}
function auth(){stopCamera();disconnect();state.user=null;app.innerHTML=V.authView();document.title='课间晴雨 · 课堂表情管理';}
function pageContent(html){const node=document.querySelector('#page-content');if(node)node.innerHTML=html;}
async function navigate(page=state.page,{refreshBasics=true}={}){
 const allowed=['home','history','stats','settings',...(state.user?.role==='admin'?['sessions','users','audit']:[])];if(!allowed.includes(page))page='home';
 stopCamera();disconnect();state.page=page;state.emotion='';const token=++renderVersion;app.innerHTML=V.shell();pageContent(V.loading());
 try{
  if(refreshBasics)await basics();if(token!==renderVersion)return;
  if(page==='home'){
   if(state.user.role==='student')state.history=await api('/api/emoji/history?'+params({page:1,page_size:5}));
   else state.statistics=await api('/api/emoji/statistics?'+params(state.sessionId?{session_id:state.sessionId}:{}));
  }else if(page==='history')state.history=await api('/api/emoji/history?'+params({...queryFilters(),page:state.history.page||1,page_size:20}));
  else if(page==='stats')state.statistics=await api('/api/emoji/statistics?'+params(queryFilters()));
  else if(page==='audit'){const rows=await api('/api/admin/audit');if(token!==renderVersion)return;pageContent(V.auditPage(rows));return;}
  if(token!==renderVersion)return;
  const views={home:state.user.role==='student'?V.studentHome:V.dashboard,history:V.historyPage,stats:V.statsPage,sessions:V.sessionsPage,users:V.usersPage,settings:V.settingsPage};
  pageContent(views[page]());if(page==='home'&&state.user.role!=='student'&&state.sessionId)connectDashboard();
 }catch(e){if(token!==renderVersion)return;if(e.status===401){auth();toast('请重新登录');}else pageContent(V.errorView(e.message));}
}
function connectDashboard(){
 if(!state.user||state.user.role==='student'||state.page!=='home'||!state.sessionId)return;
 const generation=renderVersion;const socket=new WebSocket(`${location.protocol==='https:'?'wss':'ws'}://${location.host}/ws/dashboard?sessionId=${encodeURIComponent(state.sessionId)}`);ws=socket;
 const status=(text,live)=>{const node=document.querySelector('#connection-status');if(node)node.innerHTML=`<span class="status-dot ${live?'live':''}"></span>${V.esc(text)}`;};
 socket.onopen=()=>{if(generation===renderVersion)status('实时更新中',true);};
 socket.onmessage=e=>{if(generation!==renderVersion)return;try{const message=JSON.parse(e.data);if(message.type==='statistics'&&message.data){state.statistics=message.data;const node=document.querySelector('#dashboard-data');if(node)node.innerHTML=V.statisticsView(message.data);}}catch{status('等待下一次更新',false);}};
 socket.onclose=e=>{if(ws!==socket||generation!==renderVersion)return;status('连接已断开，正在重连',false);if([1008,4401,4403].includes(e.code)){status('课堂连接不可用，请刷新页面',false);return;}wsTimer=setTimeout(connectDashboard,3500);};socket.onerror=()=>status('正在恢复连接',false);
}
async function startCamera(file=null){
 stopCamera();
 const start=document.querySelector('#camera-start'),error=document.querySelector('#camera-error');if(error)error.hidden=true;
 if(!sessionActive(currentSession())){error.textContent='课堂进行中可以开启画面采样。';error.hidden=false;return;}
 if(!file&&!navigator.mediaDevices?.getUserMedia){error.textContent='当前浏览器无法打开摄像头，请使用本机地址或 HTTPS 访问。';error.hidden=false;return;}
 start.disabled=true;const generation=++cameraGeneration;
 try{
  const config=await api('/api/ai/config');if(generation!==cameraGeneration)return;const video=document.querySelector('#camera-video');
  if(file){if(!file.type.startsWith('video/'))throw new Error('请选择浏览器支持的视频文件。');localVideoUrl=URL.createObjectURL(file);video.src=localVideoUrl;video.controls=true;}
  else {const stream=await navigator.mediaDevices.getUserMedia({video:{width:{ideal:960},height:{ideal:540}},audio:false});if(generation!==cameraGeneration){stream.getTracks().forEach(t=>t.stop());return;}cameraStream=stream;video.srcObject=stream;}
  await video.play();if(generation!==cameraGeneration)return;document.querySelector('#camera-preview').hidden=false;start.hidden=true;document.querySelector('#local-video-label').hidden=true;document.querySelector('#camera-stop').hidden=false;
  const source=document.querySelector('#sampling-source');source.textContent=file?`本地视频采样：${file.name}`:'摄像头实时采样';source.hidden=false;
  const canvas=document.createElement('canvas');const interval=Math.max(1,Number(config.sample_seconds)||3)*1000;
  const sample=async()=>{
   if(generation!==cameraGeneration||(!cameraStream&&!localVideoUrl))return;
   try{
    if(!sessionActive(currentSession())){stopCamera();toast('课堂已结束，画面采样已停止');return;}
    if(file&&video.ended){stopCamera();toast('视频播放完成，采样已停止');return;}
    if(video.paused||video.readyState<2){cameraTimer=setTimeout(sample,500);return;}
    canvas.width=Math.min(960,video.videoWidth||640);canvas.height=Math.round((video.videoHeight||480)/(video.videoWidth||640)*canvas.width);canvas.getContext('2d').drawImage(video,0,0,canvas.width,canvas.height);
    const blob=await new Promise(resolve=>canvas.toBlob(resolve,'image/jpeg',0.85));if(!blob)throw new Error('没有读取到画面，请检查摄像头。');
    const form=new FormData();form.append('file',blob,'frame.jpg');const result=await api('/api/ai/frame?session_id='+encodeURIComponent(state.sessionId),{method:'POST',body:form});
    if(generation!==cameraGeneration)return;
    document.querySelector('#camera-status').textContent=`${V.tm(new Date().toISOString())} · 已检测 ${Number(result.detected)||0} 张人脸`;
    document.querySelector('#camera-result').textContent=result.detected?`本次保存 ${Number(result.accepted)||0} 条反馈${result.rejected?`，${result.rejected} 条低于阈值`:''}。`:'当前画面未检测到人脸，请调整位置或光线。';
    const summary=document.querySelector('#sampling-last-result');summary.textContent=`最近一次采样：${V.tm(new Date().toISOString())}，检测到 ${Number(result.detected)||0} 张人脸，保存 ${Number(result.accepted)||0} 条反馈。${file?' 来源：'+file.name:''}`;summary.hidden=false;
   }catch(e){if(generation!==cameraGeneration)return;document.querySelector('#camera-status').textContent='本次采样未完成';document.querySelector('#camera-result').textContent=e.message;}
   if(generation===cameraGeneration)cameraTimer=setTimeout(sample,interval);
  };
  await sample();
 }catch(e){stopCamera();if(error){error.textContent=e.name==='NotAllowedError'?'请允许使用摄像头，然后重新开启。':e.name==='NotFoundError'?'没有找到摄像头，请连接设备后重试。':e.message;error.hidden=false;}}
 finally{if(start.isConnected)start.disabled=false;}
}
document.addEventListener('click',async event=>{
 const target=event.target.closest('button');if(!target||target.disabled)return;
 try{
  if(target.dataset.page){if(state.page!==target.dataset.page){state.history.page=1;state.filters={};}await navigate(target.dataset.page);return;}
  if(target.id==='show-login'||target.id==='show-register'){state.authMode=target.id==='show-login'?'login':'register';auth();return;}
  if(target.id==='logout'){await api('/api/auth/logout',{method:'POST'});auth();return;}
  if(target.id==='retry-page'){await navigate();return;}
  if(target.dataset.emoji){state.emotion=target.dataset.emoji;document.querySelectorAll('[data-emoji]').forEach(b=>{b.classList.toggle('selected',b===target);b.setAttribute('aria-pressed',String(b===target));});document.querySelector('#send-emoji').disabled=false;document.querySelector('#selection-hint').textContent=`已选择${V.emotion(state.emotion).label}`;return;}
  if(target.id==='page-prev'||target.id==='page-next'){state.history.page+=target.id==='page-next'?1:-1;await navigate('history',{refreshBasics:false});return;}
  if(target.id==='reset-filters'){state.filters={};state.history.page=1;await navigate(state.page,{refreshBasics:false});return;}
  if(target.id==='new-course'){openModal(V.courseForm());return;}
  if(target.id==='new-session'){openModal(V.sessionForm());return;}
  if(target.dataset.editSession){const s=state.sessions.find(s=>s.id===Number(target.dataset.editSession));state.selectedSession=s;openModal(V.sessionForm(s));return;}
  if(target.dataset.schedule){target.disabled=true;const s=state.sessions.find(s=>s.id===Number(target.dataset.schedule));state.selectedSession=s;const users=await api(`/api/admin/sessions/${s.id}/schedule`);openModal(V.scheduleForm(s,users.map(u=>u.id)));return;}
  if(target.id==='modal-close'||target.hasAttribute('data-close-modal')){closeModal();return;}
  if(target.dataset.userToggle){target.disabled=true;await api(`/api/admin/users/${target.dataset.userToggle}`,{method:'PUT',body:{active:target.dataset.active==='true'}});await navigate('users');toast('账号状态已更新');return;}
  if(target.id==='export-csv'){
   target.disabled=true;const response=await fetch('/api/admin/emoji/export?'+params(queryFilters()),{credentials:'same-origin'});if(!response.ok){const e=await response.json();throw new Error(e.message||'导出未完成');}const url=URL.createObjectURL(await response.blob());const a=document.createElement('a');a.href=url;a.download='课堂表情记录.csv';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);toast('表情记录已导出');return;
  }
  if(target.id==='camera-start'){await startCamera();return;}
  if(target.id==='camera-stop'){stopCamera();toast('画面采样已停止');return;}
 }catch(e){toast(e.message);}
 finally{if(target.isConnected&&!target.dataset.emoji&&target.id!=='send-emoji')target.disabled=false;}
});
document.addEventListener('change',async event=>{
 const el=event.target;
 if(el.id==='register-role'){const field=document.querySelector('#invite-field');field.hidden=el.value==='student';field.querySelector('input').required=el.value!=='student';}
 if(el.id==='session-select'){state.sessionId=el.value;await navigate('home',{refreshBasics:false});}
 if(el.id==='local-video-file'&&el.files?.[0]){await startCamera(el.files[0]);el.value='';}
 if(el.id==='select-all-students')modal.querySelectorAll('[name=user_ids]').forEach(c=>c.checked=el.checked);
});
document.addEventListener('submit',event=>{
 const form=event.target;if(!(form instanceof HTMLFormElement))return;event.preventDefault();
 formAction(form,async()=>{
  const data=Object.fromEntries(new FormData(form));
  if(form.id==='login-form'){const result=await api('/api/auth/login',{method:'POST',body:data});state.user=result.user;state.page='home';state.filters={};state.history.page=1;await navigate('home');return;}
  if(form.id==='register-form'){await api('/api/auth/register',{method:'POST',body:data});state.authMode='login';auth();document.querySelector('[name=username]').value=data.username;toast('账号已创建，请登录');return;}
  if(form.id==='emoji-form'){if(!state.emotion)throw new Error('请先选择一个表情。');await api('/api/emoji',{method:'POST',body:{session_id:Number(state.sessionId),emoji:state.emotion}});await navigate('home',{refreshBasics:false});toast('表情已发送');return;}
  if(form.id==='filters-form'){
   const f={...data,fromLocal:data.from,toLocal:data.to};if(data.from)f.from=new Date(data.from).toISOString();if(data.to)f.to=new Date(data.to).toISOString();if(f.from&&f.to&&f.from>=f.to)throw new Error('结束时间需要晚于开始时间。');state.filters=f;state.history.page=1;await navigate(state.page,{refreshBasics:false});return;
  }
  if(form.id==='course-form'){await api('/api/admin/courses',{method:'POST',body:{name:data.name,teacher_id:Number(data.teacher_id)}});closeModal();await navigate('sessions');toast('课程已创建');return;}
  if(form.id==='session-form'){
   const body={...data,course_id:Number(data.course_id),start_at:new Date(data.start_at).toISOString(),end_at:new Date(data.end_at).toISOString()};if(body.end_at<=body.start_at)throw new Error('结束时间需要晚于开始时间。');const id=form.dataset.id;if(id)body.version=state.selectedSession.version;await api(id?`/api/admin/sessions/${id}`:'/api/admin/sessions',{method:id?'PUT':'POST',body});closeModal();await navigate('sessions');toast(id?'课堂已更新':'课堂已安排');return;
  }
  if(form.id==='schedule-form'){const user_ids=new FormData(form).getAll('user_ids').map(Number);await api(`/api/admin/sessions/${form.dataset.id}/schedule`,{method:'POST',body:{user_ids,version:state.selectedSession.version}});closeModal();await navigate('sessions');toast('课堂名单已保存');return;}
  if(form.id==='password-form'){if(data.new_password!==data.confirm_password)throw new Error('两次输入的新密码不一致。');await api('/api/auth/password',{method:'PUT',body:{old_password:data.old_password,new_password:data.new_password}});state.authMode='login';auth();toast('密码已修改，请重新登录');return;}
 });
});
modal.addEventListener('click',event=>{if(event.target===modal){const r=modal.getBoundingClientRect();if(event.clientX<r.left||event.clientX>r.right||event.clientY<r.top||event.clientY>r.bottom)closeModal();}});
window.addEventListener('beforeunload',()=>{stopCamera();disconnect();});
document.addEventListener('visibilitychange',()=>{if(document.hidden&&(cameraStream||localVideoUrl)){stopCamera();toast('页面已离开，画面采样已停止');}});
document.addEventListener('keydown',event=>{if(event.target.id==='local-video-label'&&['Enter',' '].includes(event.key)){event.preventDefault();document.querySelector('#local-video-file').click();}});
async function boot(){try{state.user=await api('/api/users/me');await navigate('home');}catch{auth();}}
boot();
