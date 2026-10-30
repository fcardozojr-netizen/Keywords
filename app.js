let results = [];
const $ = (id) => document.getElementById(id);
function money(v){return v ? v.toLocaleString('pt-BR',{style:'currency',currency:'BRL'}) : '—'}
function number(v){return Number(v||0).toLocaleString('pt-BR')}
async function api(path, options={}) {
  const res = await fetch(path,{credentials:'same-origin',headers:{'Content-Type':'application/json',...(options.headers||{})},...options});
  let data={}; try{data=await res.json()}catch{}
  if(!res.ok) throw new Error(data.detail||'Ocorreu um erro.');
  return data;
}
function showApp(){ $('login-screen').classList.add('hidden'); $('app').classList.remove('hidden'); }
function showLogin(){ $('app').classList.add('hidden'); $('login-screen').classList.remove('hidden'); }
async function boot(){try{const me=await api('/api/me');if(me.authenticated)showApp()}catch{}}
$('login-form').addEventListener('submit',async e=>{e.preventDefault();$('login-error').textContent='';try{await api('/api/login',{method:'POST',body:JSON.stringify({password:$('password').value})});showApp()}catch(err){$('login-error').textContent=err.message}});
$('logout').addEventListener('click',async()=>{try{await api('/api/logout',{method:'POST'})}finally{showLogin()}});
$('generate').addEventListener('click',async()=>{
 const keywords=$('seeds').value.split('\n').map(x=>x.trim()).filter(Boolean), url=$('url').value.trim();
 if(!keywords.length&&!url){$('message').textContent='Informe palavras-chave ou uma URL.';$('message').className='message error';return}
 $('generate').disabled=true;$('generate').textContent='Consultando Google Ads...';$('message').textContent='Buscando ideias e métricas históricas. Isso pode levar alguns segundos.';$('message').className='message';
 try{
  const data=await api('/api/keywords',{method:'POST',body:JSON.stringify({keywords,url:url||null,location_id:$('location').value,language_id:$('language').value,limit:Number($('limit').value),include_average_cpc:$('cpc').checked})});
  results=data.keywords||[];render();$('message').textContent=`Pesquisa concluída: ${data.count} ideias retornadas pelo Google Ads.`;$('message').className='message';
 }catch(err){$('message').textContent=err.message;$('message').className='message error'}
 finally{$('generate').disabled=false;$('generate').textContent='✦ Gerar palavras-chave'}
});
function render(){
 const total=results.length, volume=results.reduce((a,x)=>a+x.avg_monthly_searches,0), low=results.filter(x=>x.competition==='LOW').length, withCpc=results.filter(x=>x.average_cpc>0);
 $('stat-total').textContent=number(total);$('stat-volume').textContent=number(volume);$('stat-low').textContent=number(low);$('stat-cpc').textContent=withCpc.length?money(withCpc.reduce((a,x)=>a+x.average_cpc,0)/withCpc.length):'—';
 $('analyze').disabled=!total;$('export').disabled=!total;drawTable();
}
function drawTable(){
 const q=$('filter').value.toLowerCase(), comp=$('competition-filter').value, sort=$('sort').value;
 let rows=results.filter(x=>x.keyword.toLowerCase().includes(q)&&(!comp||x.competition===comp));
 rows.sort((a,b)=>sort==='cpc'?b.average_cpc-a.average_cpc:sort==='alpha'?a.keyword.localeCompare(b.keyword):b.avg_monthly_searches-a.avg_monthly_searches);
 $('row-count').textContent=`Exibindo ${rows.length} de ${results.length} palavras-chave`;
 $('table-body').innerHTML=rows.length?rows.map(x=>`<tr><td>${esc(x.keyword)}</td><td>${number(x.avg_monthly_searches)}</td><td><span class="competition ${x.competition}">${x.competition||'—'}</span></td><td>${x.competition_index||'—'}</td><td>${money(x.average_cpc)}</td><td>${money(x.low_top_of_page_bid)} – ${money(x.high_top_of_page_bid)}</td></tr>`).join(''):'<tr><td colspan="6" class="empty">Nenhuma palavra-chave corresponde aos filtros.</td></tr>';
}
function esc(s){return String(s).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]))}
$('filter').addEventListener('input',drawTable);$('competition-filter').addEventListener('change',drawTable);$('sort').addEventListener('change',drawTable);
$('analyze').addEventListener('click',async()=>{
 try{const data=await api('/api/analyze',{method:'POST',body:JSON.stringify({keywords:results.map(x=>x.keyword)})});
  const host=$('analysis-content');host.innerHTML='';
  Object.entries(data.groups).forEach(([name,items])=>{const div=document.createElement('div');div.className='analysis-card';const h=document.createElement('h3');h.textContent=`${name} (${items.length})`;const p=document.createElement('p');p.textContent=items.slice(0,25).join(' • ');div.append(h,p);host.append(div)});
  if(data.negative_keyword_ideas.length){const div=document.createElement('div');div.className='analysis-card';div.innerHTML='<h3>Ideias de palavras negativas</h3>';const p=document.createElement('p');p.textContent=data.negative_keyword_ideas.join(' • ');div.append(p);host.append(div)}
  $('analysis-panel').classList.remove('hidden');$('analysis-panel').scrollIntoView({behavior:'smooth'});
 }catch(err){$('message').textContent=err.message}
});
$('export').addEventListener('click',async()=>{
 try{const res=await fetch('/api/export.csv',{method:'POST',credentials:'same-origin',headers:{'Content-Type':'application/json'},body:JSON.stringify({keywords:results.map(x=>x.keyword)})});if(!res.ok)throw new Error('Falha ao exportar');const blob=await res.blob(),a=document.createElement('a');a.href=URL.createObjectURL(blob);a.download='keyword-master-odonto-master.csv';a.click();URL.revokeObjectURL(a.href)}catch(e){$('message').textContent=e.message}
});
boot();
