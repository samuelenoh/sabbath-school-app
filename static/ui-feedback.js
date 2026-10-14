'use strict';
// Shared feedback enhances every module without changing its permissions or data rules.
const feedbackEscape=value=>String(value).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
let feedbackId=0,activeRequests=0,lastSubmitButton=null;
function feedbackError(target,message,title='We couldn’t complete this action'){
 if(!target)return;
 target.innerHTML=`<span class="error-icon" aria-hidden="true">!</span><span class="error-body"><strong>${feedbackEscape(title)}</strong><span>${feedbackEscape(message)}</span></span>`;
 target.dataset.feedbackMessage=target.textContent;
 target.dataset.feedbackType=title==='Please check your entries'?'validation':'request';
 target.setAttribute('role','alert');
 if(target.closest('form'))target.scrollIntoView({block:'nearest'});
}
function fieldCaption(control){
 if(control.dataset.fieldCaption)return control.dataset.fieldCaption;
 const label=control.labels?.[0];
 if(!label)return control.getAttribute('aria-label')||control.name.replaceAll('_',' ')||'This field';
 const copy=label.cloneNode(true);copy.querySelectorAll('input,select,textarea,.note,.required-mark,.field-error').forEach(e=>e.remove());
 return copy.textContent.trim();
}
function validationMessage(control){
 const name=fieldCaption(control),v=control.validity;
 if(v.valueMissing)return control.tagName==='SELECT'?`Choose ${name.toLowerCase()}.`:`Enter ${name.toLowerCase()}.`;
 if(v.typeMismatch)return control.type==='email'?'Enter an email address, for example name@example.com.':'Enter a complete web address, for example https://example.com.';
 if(v.rangeUnderflow)return `${name} must be at least ${control.min}.`;
 if(v.rangeOverflow)return `${name} must be ${control.max} or less.`;
 if(v.tooShort)return `${name} needs at least ${control.minLength} characters.`;
 if(v.tooLong)return `${name} must be ${control.maxLength} characters or fewer.`;
 if(v.stepMismatch)return control.step==='0.01'?'Enter an amount with no more than two decimal places.':`Enter a valid increment of ${control.step||'1'} for ${name.toLowerCase()}.`;
 if(v.badInput)return `Enter a number for ${name.toLowerCase()}.`;
 if(v.patternMismatch)return control.name==='phone'?'Use international format, for example +233201234567.':control.name==='resource_url'?'Use a secure web address beginning with https://.':`Check the format of ${name.toLowerCase()}.`;
 return `Check ${name.toLowerCase()} and try again.`;
}
function clearFieldError(control){
 control.removeAttribute('aria-invalid');
 const id=control.dataset.errorId;if(!id)return;
 document.getElementById(id)?.remove();
 const ids=(control.getAttribute('aria-describedby')||'').split(' ').filter(v=>v&&v!==id);
 if(ids.length)control.setAttribute('aria-describedby',ids.join(' '));else control.removeAttribute('aria-describedby');
 delete control.dataset.errorId;
}
function enhanceFeedback(){
 document.querySelectorAll('form').forEach(form=>{form.noValidate=true;if(form.querySelector('[required]')&&!form.querySelector('.form-guidance')){const note=document.createElement('p');note.className='note form-guidance';note.textContent='Fields marked Required must be completed.';form.prepend(note)}const card=form.querySelector('.error');if(card&&form.firstElementChild!==card)form.prepend(card)});
 document.querySelectorAll('input,select,textarea').forEach(control=>{
  const label=control.labels?.[0];
  if(!control.dataset.fieldCaption){control.dataset.fieldCaption=fieldCaption(control);if(label&&!control.hasAttribute('aria-label'))control.setAttribute('aria-label',control.dataset.fieldCaption)}
  if(control.required&&label&&!label.querySelector('.required-mark')){
   const mark=document.createElement('span');mark.className='required-mark';mark.textContent='Required';mark.setAttribute('aria-hidden','true');label.insertBefore(mark,control);
   control.setAttribute('aria-required','true');
  }
  if(control.name==='phone'&&!control.hasAttribute('pattern'))control.pattern='\\+[1-9][0-9]{7,14}';
  if(control.name==='resource_url'&&!control.hasAttribute('pattern'))control.pattern='https://.*';
 });
 document.querySelectorAll('.error').forEach(target=>{
  if(target.textContent.trim()&&target.dataset.feedbackMessage!==target.textContent)feedbackError(target,target.textContent.trim());
 });
}
document.addEventListener('submit',event=>{
 const form=event.target;if(!(form instanceof HTMLFormElement))return;
 enhanceFeedback();
 const controls=[...form.elements].filter(e=>e.willValidate);
 controls.forEach(clearFieldError);
 const invalid=controls.filter(e=>!e.validity.valid);
 const card=form.querySelector('.error');if(card){card.replaceChildren();delete card.dataset.feedbackMessage}
 if(invalid.length){
  event.preventDefault();event.stopImmediatePropagation();
  invalid.forEach(control=>{
   const id=`field-error-${++feedbackId}`,hint=document.createElement('span');hint.id=id;hint.className='field-error';hint.textContent=validationMessage(control);
   control.setAttribute('aria-invalid','true');control.dataset.errorId=id;
   control.setAttribute('aria-describedby',[control.getAttribute('aria-describedby'),id].filter(Boolean).join(' '));control.after(hint);
  });
  if(card)feedbackError(card,`${invalid.length===1?'One field needs':`${invalid.length} fields need`} attention. ${validationMessage(invalid[0])}`,'Please check your entries');
  invalid[0].focus();return;
 }
 lastSubmitButton=event.submitter;
},true);
function updateFieldFeedback(event){
 const control=event.target;if(!control.matches('input,select,textarea')||!control.validity.valid)return;
 clearFieldError(control);const form=control.form,card=form?.querySelector('.error');if(card?.dataset.feedbackType!=='validation')return;
 const remaining=[...form.querySelectorAll('[aria-invalid="true"]')];
 if(!remaining.length){card.replaceChildren();delete card.dataset.feedbackMessage;delete card.dataset.feedbackType}
 else{card.querySelector('.error-body>span').textContent=`${remaining.length===1?'One field needs':`${remaining.length} fields need`} attention. ${validationMessage(remaining[0])}`;card.dataset.feedbackMessage=card.textContent}
}
document.addEventListener('input',updateFieldFeedback);
document.addEventListener('change',updateFieldFeedback);
new MutationObserver(enhanceFeedback).observe(document.getElementById('app'),{childList:true,subtree:true});
new MutationObserver(enhanceFeedback).observe(document.getElementById('dialog-content'),{childList:true,subtree:true});
function requestFeedback(method){
 let bar=document.getElementById('request-loader');
 if(!bar){bar=document.createElement('div');bar.id='request-loader';bar.innerHTML='<span class="loader-spinner" aria-hidden="true"></span><span>Working…</span>';bar.setAttribute('role','status');bar.setAttribute('aria-live','polite');document.body.append(bar)}
 activeRequests++;bar.hidden=false;document.getElementById('app').setAttribute('aria-busy','true');
 const button=lastSubmitButton?.isConnected?lastSubmitButton:document.activeElement?.closest('button');lastSubmitButton=null;
 const original=button&&!button.dataset.loading?{html:button.innerHTML,label:button.getAttribute('aria-label'),disabled:button.disabled}:null;
 if(original){
  button.dataset.loading='true';button.setAttribute('aria-busy','true');button.setAttribute('aria-label',original.label||button.textContent.trim());button.disabled=true;
  button.innerHTML=`<span class="loader-spinner" aria-hidden="true"></span><span>${method==='GET'?'Loading…':/sign in/i.test(original.html)?'Signing in…':/save/i.test(original.html)?'Saving…':'Processing…'}</span>`;
 }
 return ()=>{
  if(original){button.innerHTML=original.html;button.disabled=original.disabled;button.removeAttribute('aria-busy');delete button.dataset.loading;if(original.label===null)button.removeAttribute('aria-label');else button.setAttribute('aria-label',original.label)}
  activeRequests=Math.max(0,activeRequests-1);if(!activeRequests){bar.hidden=true;document.getElementById('app').removeAttribute('aria-busy')}
 };
}
function initialLoadFailure(){
 if(document.querySelector('#login-form'))return;
 document.getElementById('app').innerHTML='<main class="startup-loader"><section class="startup-card"><img class="startup-logo" src="/adventist-logo-forest.svg" alt="Seventh-day Adventist Church" width="643" height="173"><h1>Unable to open your workspace</h1><div class="error" role="alert"></div><button class="primary" id="startup-retry">Try again</button></section></main>';
 feedbackError(document.querySelector('.startup-card .error'),'Check your connection and try again. The free hosting service may need a moment to wake up.');
 document.getElementById('startup-retry').onclick=()=>refresh().catch(initialLoadFailure);
}
enhanceFeedback();
