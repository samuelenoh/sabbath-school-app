/* Accessible themed calendar; native date inputs remain the form's source of truth. */
(()=>{
 'use strict';
 const months=Array.from({length:12},(_,m)=>new Intl.DateTimeFormat('en-GB',{month:'long',timeZone:'UTC'}).format(new Date(Date.UTC(2026,m,1))));
 const utc=(y,m,d)=>{const value=new Date(0);value.setUTCFullYear(y,m,d);value.setUTCHours(0,0,0,0);return value};
 const key=d=>`${String(d.getUTCFullYear()).padStart(4,'0')}-${String(d.getUTCMonth()+1).padStart(2,'0')}-${String(d.getUTCDate()).padStart(2,'0')}`;
 const parse=s=>/^\d{4}-\d{2}-\d{2}$/.test(s)?utc(...s.split('-').map((v,i)=>Number(v)-(i===1?1:0))):null;
 const pretty=d=>new Intl.DateTimeFormat('en-GB',{weekday:'long',day:'numeric',month:'long',year:'numeric',timeZone:'UTC'}).format(d);
 const icon='<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" aria-hidden="true"><rect x="3" y="5" width="18" height="16" rx="3"/><path d="M7 2v6m10-6v6M3 11h18m-12 4h2m3 0h2m-7 3h2"/></svg>';
 let host,trigger,cursor,view,minimum,maximum;
 const calendar=document.createElement('dialog');calendar.id='date-picker';calendar.className='date-picker';calendar.setAttribute('aria-labelledby','calendar-title');calendar.setAttribute('aria-describedby','calendar-help');document.body.append(calendar);
 const allowed=d=>d.getUTCFullYear()>=1&&d.getUTCFullYear()<=9999&&(!minimum||d>=minimum)&&(!maximum||d<=maximum);
 const clamp=d=>minimum&&d<minimum?new Date(minimum):maximum&&d>maximum?new Date(maximum):d;
 function setDate(value){
  const input=host;calendar.close();if(!input?.isConnected)return;
  input.value=value;input.dispatchEvent(new Event('input',{bubbles:true}));input.dispatchEvent(new Event('change',{bubbles:true}));queueMicrotask(()=>{if(!input.isConnected&&input.id)document.getElementById(input.id)?.focus()});
 }
 function moveMonth(delta){
  const next=utc(view.getUTCFullYear(),view.getUTCMonth()+delta,1);
  if(next.getUTCFullYear()<1||next.getUTCFullYear()>9999)return;
  view=next;cursor=clamp(utc(view.getUTCFullYear(),view.getUTCMonth(),Math.min(cursor.getUTCDate(),utc(view.getUTCFullYear(),view.getUTCMonth()+1,0).getUTCDate())));draw();
 }
 function draw(){
  const y=view.getUTCFullYear(),m=view.getUTCMonth(),first=utc(y,m,1),last=utc(y,m+1,0),today=key(new Date()),selected=host.value;
  const previous=utc(y,m,0),next=utc(y,m+1,1);
  calendar.innerHTML='<header class="calendar-header"><div><p class="eyebrow">CHOOSE A DATE</p><h2 id="calendar-title"></h2></div><button type="button" class="calendar-close" aria-label="Close calendar">×</button></header><div class="calendar-navigation"><button type="button" class="calendar-prev" aria-label="Previous month">‹</button><div class="calendar-period"><label><span class="screen-reader">Month</span><select class="calendar-month" aria-label="Month"></select></label><label><span class="screen-reader">Year</span><input class="calendar-year" aria-label="Year" type="number" min="1" max="9999" inputmode="numeric"></label></div><button type="button" class="calendar-next" aria-label="Next month">›</button></div><p class="calendar-announcement screen-reader" aria-live="polite"></p><p class="calendar-year-error field-error" role="alert"></p><table class="calendar-grid" role="grid" aria-label="Choose a day"><thead><tr>'+['Sun','Mon','Tue','Wed','Thu','Fri','Sat'].map((d,i)=>`<th scope="col"><abbr title="${['Sunday','Monday','Tuesday','Wednesday','Thursday','Friday','Saturday'][i]}">${d}</abbr></th>`).join('')+'</tr></thead><tbody></tbody></table><div class="calendar-selection" aria-live="polite"></div><footer class="calendar-footer"><button type="button" class="calendar-clear">Clear date</button><button type="button" class="primary calendar-today">Today</button></footer><p id="calendar-help" class="calendar-help">Use arrow keys to move between days. Enter selects a date. Escape closes.</p>';
  const caption=host.dataset.fieldCaption||host.getAttribute('aria-label')||'date';calendar.querySelector('#calendar-title').textContent='Choose '+({From:'start date',To:'end date',Birthday:'birthday',Date:'date','Date joined':'join date'}[caption]||caption);
  calendar.querySelector('.calendar-announcement').textContent=months[m]+' '+y;
  const month=calendar.querySelector('.calendar-month');months.forEach((name,i)=>{const option=new Option(name,String(i));option.disabled=!!((minimum&&utc(y,i+1,0)<minimum)||(maximum&&utc(y,i,1)>maximum));month.add(option)});month.value=String(m);
  const year=calendar.querySelector('.calendar-year');year.value=y;
  month.onchange=()=>{view=utc(y,Number(month.value),1);cursor=clamp(utc(y,Number(month.value),1));draw();calendar.querySelector('.calendar-month').focus()};
  year.onchange=()=>{
   const value=Number(year.value);if(!Number.isInteger(value)||value<1||value>9999){year.setAttribute('aria-invalid','true');calendar.querySelector('.calendar-year-error').textContent='Enter a year from 1 to 9999.';return}
   cursor=clamp(utc(value,m,Math.min(cursor.getUTCDate(),utc(value,m+1,0).getUTCDate())));view=utc(cursor.getUTCFullYear(),cursor.getUTCMonth(),1);draw();calendar.querySelector('.calendar-year').focus();
  };
  const prev=calendar.querySelector('.calendar-prev'),nextButton=calendar.querySelector('.calendar-next');
  prev.disabled=previous.getUTCFullYear()<1||!!(minimum&&previous<minimum);nextButton.disabled=next.getUTCFullYear()>9999||!!(maximum&&next>maximum);
  prev.onclick=()=>{moveMonth(-1);const button=calendar.querySelector('.calendar-prev');(button.disabled?calendar.querySelector('.calendar-month'):button).focus()};nextButton.onclick=()=>{moveMonth(1);const button=calendar.querySelector('.calendar-next');(button.disabled?calendar.querySelector('.calendar-month'):button).focus()};
  const body=calendar.querySelector('tbody');let row;
  for(let index=0;index<Math.ceil((first.getUTCDay()+last.getUTCDate())/7)*7;index++){
   if(index%7===0){row=document.createElement('tr');body.append(row)}
   const cell=document.createElement('td');row.append(cell);const day=index-first.getUTCDay()+1;
   if(day<1||day>last.getUTCDate()){cell.setAttribute('aria-hidden','true');continue}
   const date=utc(y,m,day),value=key(date),button=document.createElement('button');button.type='button';button.className='calendar-day';button.textContent=day;button.dataset.date=value;button.setAttribute('aria-label',pretty(date));button.disabled=!allowed(date);button.tabIndex=value===key(cursor)?0:-1;
   cell.setAttribute('role','gridcell');cell.setAttribute('aria-selected',String(value===selected));
   if(value===selected)button.classList.add('selected');if(value===today){button.classList.add('is-today');button.setAttribute('aria-current','date')}
   button.onclick=()=>setDate(value);cell.append(button);
  }
  calendar.querySelector('.calendar-selection').textContent=selected?'Selected · '+pretty(parse(selected)):'Select a day above';
  calendar.querySelector('.calendar-today').disabled=!allowed(parse(today));calendar.querySelector('.calendar-today').onclick=()=>setDate(today);
  calendar.querySelector('.calendar-clear').onclick=()=>setDate('');calendar.querySelector('.calendar-close').onclick=()=>calendar.close();
 }
 function focusDay(){calendar.querySelector(`[data-date="${key(cursor)}"]`)?.focus()}
 calendar.addEventListener('keydown',event=>{
  if(!event.target.matches('.calendar-day'))return;
  const shifts={ArrowLeft:-1,ArrowRight:1,ArrowUp:-7,ArrowDown:7};let date;
  if(event.key in shifts)date=utc(cursor.getUTCFullYear(),cursor.getUTCMonth(),cursor.getUTCDate()+shifts[event.key]);
  else if(event.key==='Home')date=utc(cursor.getUTCFullYear(),cursor.getUTCMonth(),cursor.getUTCDate()-cursor.getUTCDay());
  else if(event.key==='End')date=utc(cursor.getUTCFullYear(),cursor.getUTCMonth(),cursor.getUTCDate()+6-cursor.getUTCDay());
  else if(['PageUp','PageDown'].includes(event.key)){const m=cursor.getUTCMonth()+(event.key==='PageUp'?-1:1)*(event.shiftKey?12:1);date=utc(cursor.getUTCFullYear(),m,Math.min(cursor.getUTCDate(),utc(cursor.getUTCFullYear(),m+1,0).getUTCDate()))}
  if(!date)return;event.preventDefault();date=clamp(date);if(!allowed(date))return;cursor=date;view=utc(date.getUTCFullYear(),date.getUTCMonth(),1);draw();focusDay();
 });
 calendar.addEventListener('close',()=>{trigger?.setAttribute('aria-expanded','false');if(trigger?.isConnected)trigger.focus()});
 calendar.addEventListener('click',event=>{if(event.target===calendar){const r=calendar.getBoundingClientRect();if(event.clientX<r.left||event.clientX>r.right||event.clientY<r.top||event.clientY>r.bottom)calendar.close()}});
 function enhance(){
  document.querySelectorAll('input[type="date"]').forEach(input=>{
   if(input.closest('.date-field'))return;
   const wrapper=document.createElement('span');wrapper.className='date-field';input.before(wrapper);wrapper.append(input);
   const button=document.createElement('button');button.type='button';button.className='date-trigger';button.innerHTML=icon;button.setAttribute('aria-label','Choose date: '+(input.dataset.fieldCaption||input.getAttribute('aria-label')||input.name||'date'));button.setAttribute('aria-haspopup','dialog');button.setAttribute('aria-controls','date-picker');button.setAttribute('aria-expanded','false');button.disabled=input.disabled||input.readOnly;wrapper.append(button);
   button.onclick=event=>{
    event.preventDefault();if(input.disabled||input.readOnly)return;
    host=input;trigger=button;minimum=parse(input.min);maximum=parse(input.max);cursor=clamp(parse(input.value)||parse(key(new Date())));view=utc(cursor.getUTCFullYear(),cursor.getUTCMonth(),1);draw();calendar.showModal();button.setAttribute('aria-expanded','true');focusDay();
   };
  });
 }
 new MutationObserver(()=>{if(calendar.open&&!host?.isConnected)calendar.close();enhance()}).observe(document.getElementById('app'),{childList:true,subtree:true});
 new MutationObserver(enhance).observe(document.getElementById('dialog-content'),{childList:true,subtree:true});enhance();
})();
