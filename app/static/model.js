export const EMOTIONS = [
  {key:'happy',icon:'😊',label:'开心',color:'#D39522'},
  {key:'neutral',icon:'😐',label:'平静',color:'#627A96'},
  {key:'sad',icon:'😢',label:'低落',color:'#5084C9'},
  {key:'surprised',icon:'😮',label:'惊讶',color:'#9273C0'},
  {key:'angry',icon:'😠',label:'生气',color:'#CB6565'},
  {key:'fearful',icon:'😨',label:'紧张',color:'#5D9A95'},
  {key:'disgusted',icon:'😣',label:'反感',color:'#8A9762'},
];
export const ROLES = {student:'学生',teacher:'教师',admin:'管理员'};
export const state = {user:null,page:'home',sessions:[],courses:[],users:[],sessionId:'',emotion:'',filters:{},history:{items:[],total:0,page:1,page_size:20},statistics:null,selectedSession:null,authMode:'login'};

export async function api(path, options={}) {
  const headers = new Headers(options.headers || {});
  if (options.method && !['GET','HEAD'].includes(options.method)) headers.set('X-Requested-With','EmojiApp');
  if (options.body && !(options.body instanceof FormData)) {
    headers.set('Content-Type','application/json');
    options.body = JSON.stringify(options.body);
  }
  const response=await fetch(path,{credentials:'same-origin',...options,headers});
  const content=response.headers.get('content-type') || '';
  const data=content.includes('json') ? await response.json() : await response.text();
  if (!response.ok) {
    const error=new Error(typeof data==='object' ? data.message || '操作未完成，请稍后重试' : '操作未完成，请稍后重试');
    error.status=response.status; throw error;
  }
  return data;
}
export function params(filters={}) {
  const q = new URLSearchParams();
  for (const [k,v] of Object.entries(filters)) if(v!=='' && v!==null && v!==undefined) q.set(k,v);
  return q.toString();
}
export function currentSession(){return state.sessions.find(s=>String(s.id)===String(state.sessionId));}
export function sessionActive(s){return s && Date.parse(s.start_at)<=Date.now() && Date.parse(s.end_at)>=Date.now();}
