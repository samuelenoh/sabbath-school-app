/* Display publisher-hosted readings without copying or storing lesson bodies. */
function mountStudyReader(lesson,target){
 if(!lesson.available)return;
 const valid=value=>{try{const u=new URL(value);return u.protocol==='https:'&&u.hostname==='absg.sspmadventist.org'&&/^\/en\/\d{4}-0[1-4]\/\d{2}(?:\/0[1-7])?$/.test(u.pathname)}catch{return false}};
 if(!valid(lesson.weekly_url)||!valid(lesson.daily_url))return;
 const introduction=lesson.weekly_url+'/01';
 const section=document.createElement('section');section.className='study-reader';section.setAttribute('aria-label','Read the published lesson');
 section.innerHTML='<header class="study-reader-head"><div><h3>Read the lesson here</h3><p>The weekly introduction includes the memory text. Switch to today for the daily study.</p></div><a class="study-fullpage" target="_blank" rel="noopener noreferrer">Open full page ↗</a></header><div class="study-reader-tabs" role="tablist" aria-label="Study section"><button type="button" id="study-intro-tab" role="tab" aria-selected="true" aria-controls="study-reader-panel">Lesson & memory text</button><button type="button" id="study-today-tab" role="tab" aria-selected="false" aria-controls="study-reader-panel" tabindex="-1">Today’s study</button></div><div id="study-reader-panel" role="tabpanel" aria-labelledby="study-intro-tab" class="study-reader-panel"><div class="study-reader-status" role="status"><span class="loader-spinner" aria-hidden="true"></span> Opening the official study…</div><iframe class="study-reader-frame" title="Official lesson and memory text" referrerpolicy="no-referrer" sandbox="allow-scripts allow-same-origin allow-popups" loading="eager"></iframe></div><p class="note study-reader-foot">The reading is displayed directly from the General Conference’s official website. Scroll inside the reader to continue. If it is unavailable, use Open full page.</p>';
 target.append(section);
 const frame=section.querySelector('iframe'),status=section.querySelector('.study-reader-status'),link=section.querySelector('a'),tabs=[...section.querySelectorAll('[role="tab"]')],panel=section.querySelector('[role="tabpanel"]');
 let timer;
 function select(index){
  const source=index?lesson.daily_url:introduction;
  tabs.forEach((tab,i)=>{tab.setAttribute('aria-selected',String(i===index));tab.tabIndex=i===index?0:-1});panel.setAttribute('aria-labelledby',tabs[index].id);
  frame.title=index?'Official daily Sabbath School study':'Official lesson and memory text';link.href=source;status.hidden=false;status.innerHTML='<span class="loader-spinner" aria-hidden="true"></span> Opening the official study…';panel.setAttribute('aria-busy','true');
  clearTimeout(timer);timer=setTimeout(()=>{if(!section.isConnected)return;status.textContent='The publisher is taking longer to respond. You can use Open full page above.';panel.removeAttribute('aria-busy')},20000);
  frame.src=source;
 }
 frame.onload=()=>{clearTimeout(timer);status.hidden=true;panel.removeAttribute('aria-busy')};
 tabs.forEach((tab,index)=>{tab.onclick=()=>select(index);tab.onkeydown=event=>{if(!['ArrowLeft','ArrowRight','Home','End'].includes(event.key))return;event.preventDefault();const next=event.key==='Home'?0:event.key==='End'?1:1-index;tabs[next].focus();select(next)}});
 select(0);
}
