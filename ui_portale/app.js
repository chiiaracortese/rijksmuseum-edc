'use strict';
const $ = (s) => document.querySelector(s);
let snapshot = null;
let chosenIdentity = null;
let busy = false;
let toastHandle;
const application = {
  identity: $('#identitySelect'), identityTrigger: $('#identityTrigger'),
  identityMenu: $('#identityMenu'), apply: $('#applyIdentity'), discover: $('#discoverButton'),
  datasetGrid: $('#datasetGrid'), offer: $('#negotiateButton'), transfer: $('#transferButton'),
  verify: $('#verifyButton'), gallery: $('#galleryButton'), newRequest: $('#newRequest')
};
const safe = (x) => String(x ?? '');
function showMessage(message, error=false) {
  const node = $('#toast'); node.textContent = message; node.classList.toggle('error', error);
  node.hidden = false; clearTimeout(toastHandle);
  toastHandle = setTimeout(() => {node.hidden = true;}, error ? 7500 : 4100);
}
async function call(action, body={}) {
  if (busy) return;
  busy=true; renderBusy();
  try {
    const res = await fetch('/api/' + action, {
      method:'POST', headers:{'Content-Type':'application/json','X-Portal-Token': window.PORTAL_TOKEN},
      body: JSON.stringify(body), cache:'no-store'
    });
    const payload = await res.json();
    if (!res.ok) throw new Error(payload.error || 'Operazione non riuscita');
    snapshot = payload;
    chosenIdentity = snapshot.identity;
    render();
    const notices = {identity:'Identità Consumer applicata.',discover:'Catalogo EDC ricevuto.',offer:'Offerta selezionata.',negotiate:'Negoziazione EDC conclusa.',transfer:'Processo di trasferimento avviato.',verify:'JSON ricevuto e verificato.',new:'Nuova richiesta pronta.'};
    showMessage(notices[action] || 'Operazione completata.');
    if (action === 'discover') $('#catalogSection').scrollIntoView({behavior:'smooth',block:'start'});
    if (action === 'offer') $('#offerSection').scrollIntoView({behavior:'smooth',block:'start'});
    if (action === 'negotiate') $('#accessSection').scrollIntoView({behavior:'smooth',block:'start'});
  } catch (e) { showMessage(e.message, true); }
  finally { busy=false; render(); }
}
function renderBusy() {
  closeIdentityMenu();
  for (const el of [application.apply, application.discover, application.offer, application.transfer,
                    application.verify, application.newRequest, application.identity, application.identityTrigger])
    el.disabled=true;
  $('#connectState').innerHTML='<i></i> OPERAZIONE IN CORSO';
}
function el(tag, css, text) { const n=document.createElement(tag); if(css)n.className=css; if(text!==undefined)n.textContent=text; return n; }
// Dropdown in stile demo: nomi pubblici chiari, ID EDC invariati e disponibili solo nei dettagli.
function resetIdentityOptions(profiles, current) {
  const saved = chosenIdentity ?? current;
  const nativeFragment = document.createDocumentFragment();
  for (const profile of profiles) {
    const option = el('option', '', profile.name);
    option.value = profile.id;
    nativeFragment.appendChild(option);
  }
  application.identity.replaceChildren(nativeFragment);
  const exists = profiles.some(profile => profile.id === saved);
  chosenIdentity = exists ? saved : current;
  application.identity.value = chosenIdentity;

  const menu = application.identityMenu;
  menu.replaceChildren();
  const groups = ['Partecipanti principali', 'Altri profili di prova'];
  for (const groupName of groups) {
    const groupProfiles = profiles.filter(p => (p.group || groups[0]) === groupName);
    if (!groupProfiles.length) continue;
    const group = el('div', 'identity-choice-group');
    group.setAttribute('role', 'group');
    group.setAttribute('aria-label', groupName);
    const heading = el('div', 'identity-choice-heading', groupName);
    heading.setAttribute('aria-hidden', 'true');
    group.appendChild(heading);
    for (const profile of groupProfiles) {
      const item = el('button', 'identity-choice-item');
      item.type = 'button';
      item.setAttribute('role', 'option');
      item.setAttribute('aria-selected', 'false');
      item.dataset.identity = profile.id;
      item.appendChild(el('span', 'identity-choice-name', profile.name));
      item.appendChild(el('small', 'identity-choice-hint', profile.credentials));
      item.addEventListener('click', () => {
        chosenIdentity = profile.id;
        application.identity.value = profile.id;
        closeIdentityMenu(true);
        render();
      });
      group.appendChild(item);
    }
    menu.appendChild(group);
  }
}
function syncIdentityChoice(profiles) {
  const selected = profiles.find(p => p.id === chosenIdentity);
  $('#identityChoiceText').textContent = selected?.name || 'Seleziona il partecipante';
  $('#identityTechnicalId').textContent = selected?.id || '—';
  for (const item of application.identityMenu.querySelectorAll('.identity-choice-item')) {
    const active = item.dataset.identity === chosenIdentity;
    item.setAttribute('aria-selected', active ? 'true' : 'false');
    item.classList.toggle('is-selected', active);
  }
}
function closeIdentityMenu(restoreFocus=false) {
  application.identityMenu.hidden = true;
  application.identityTrigger.setAttribute('aria-expanded', 'false');
  $('#identityPicker').classList.remove('is-open');
  application.identityMenu.classList.remove('opens-up');
  if (restoreFocus) application.identityTrigger.focus();
}
function openIdentityMenu(focusSelection=false) {
  if (application.identityTrigger.disabled || busy) return;
  const triggerBox = application.identityTrigger.getBoundingClientRect();
  const mainBox = $('#main').getBoundingClientRect();
  const availableBelow = mainBox.bottom - triggerBox.bottom;
  const availableAbove = triggerBox.top - mainBox.top;
  application.identityMenu.classList.toggle('opens-up', availableBelow < 270 && availableAbove > availableBelow);
  application.identityMenu.hidden = false;
  application.identityTrigger.setAttribute('aria-expanded', 'true');
  $('#identityPicker').classList.add('is-open');
  if (focusSelection) {
    const selected = application.identityMenu.querySelector('.identity-choice-item.is-selected');
    (selected || application.identityMenu.querySelector('.identity-choice-item'))?.focus();
  }
}
application.identityTrigger.addEventListener('click', () => {
  if (application.identityMenu.hidden) openIdentityMenu();
  else closeIdentityMenu();
});
application.identityTrigger.addEventListener('keydown', e => {
  if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
    e.preventDefault();
    openIdentityMenu(true);
  }
});
application.identityMenu.addEventListener('keydown', e => {
  const choices = [...application.identityMenu.querySelectorAll('.identity-choice-item')];
  const index = choices.indexOf(document.activeElement);
  if (['ArrowDown', 'ArrowUp', 'Home', 'End'].includes(e.key)) {
    e.preventDefault();
    let next = index;
    if (e.key === 'ArrowDown') next = (index + 1) % choices.length;
    if (e.key === 'ArrowUp') next = (index - 1 + choices.length) % choices.length;
    if (e.key === 'Home') next = 0;
    if (e.key === 'End') next = choices.length - 1;
    choices[next]?.focus();
  } else if (e.key === 'Escape') {
    e.preventDefault();
    closeIdentityMenu(true);
  } else if (e.key === 'Tab') {
    closeIdentityMenu();
  }
});
document.addEventListener('pointerdown', e => {
  if (!e.target.closest('#identityPicker')) closeIdentityMenu();
});
document.addEventListener('keydown', e => {
  if (e.key === 'Escape' && !application.identityMenu.hidden) closeIdentityMenu(true);
});
function render() {
  if (!snapshot || busy) return;
  $('#connectState').innerHTML='<i></i> CONSUMER CONFIGURATO';
  const s = snapshot;
  const currentProfile=s.profiles.find(p=>p.id===s.identity);
  const selectedProfile=s.profiles.find(p=>p.id===chosenIdentity);
  $('#activeIdentity').textContent=currentProfile?.name || 'Consumer configurato';
  $('#activeIdentityLabel').textContent=currentProfile?.credentials || 'Profilo sperimentale attivo';
  if (application.identity.options.length !== s.profiles.length) resetIdentityOptions(s.profiles,s.identity);
  else if (chosenIdentity) application.identity.value=chosenIdentity;
  syncIdentityChoice(s.profiles);
  $('#identityDescription').textContent = !selectedProfile ? 'Seleziona un partecipante' :
    chosenIdentity !== s.identity
      ? 'Profilo scelto: ' + selectedProfile.credentials + '. Premi «Applica identità» per renderlo attivo.'
      : 'Profilo attivo: ' + selectedProfile.credentials + '.';
  application.identityTrigger.disabled = false;
  application.apply.disabled=!chosenIdentity || chosenIdentity===s.identity;
  application.discover.disabled=chosenIdentity!==s.identity;
  $('#countDatasets').textContent=s.catalog?.datasets ?? '—';
  $('#countOffers').textContent=s.catalog?.offers ?? '—';
  $('#catalogStatus').textContent=s.catalog ? 'Catalogo ricevuto dal Provider' : 'Catalogo non ancora interrogato';
  $('#catalogCounter').textContent=s.catalog ? s.catalog.assets.length + ' dataset disponibili' : '';
  renderCatalog(s);
  renderOffer(s);
  renderAccess(s);
  application.newRequest.disabled=!s.catalog && !s.offer && !s.neg;
}
function renderCatalog(s) {
  const grid=application.datasetGrid; grid.replaceChildren();
  if (!s.catalog) {grid.appendChild(el('div','empty-state','Il catalogo apparirà qui dopo la richiesta al Provider.'));return;}
  for (const asset of s.catalog.assets) {
    const button=el('button','dataset-item'); button.type='button';button.disabled=!!s.neg || chosenIdentity!==s.identity;
    if(s.offer?.asset_id===asset.id)button.classList.add('is-selected');
    const label=el('strong','',asset.label);
    const subtitle=el('small','','Dataset JSON · offerta EDC disponibile');
    const arrow=el('span','dataset-arrow','↗');arrow.setAttribute('aria-hidden','true');
    button.append(label,subtitle,arrow);
    button.addEventListener('click',()=>call('offer',{asset_id:asset.id}));
    grid.appendChild(button);
  }
}
function renderOffer(s) {
  const offer=s.offer;
  $('#selectedLabel').textContent=offer?.label || 'Nessun dataset selezionato';
  $('#offerNumber').textContent=offer ? `${offer.numero_offerte} offerta contrattuale${offer.numero_offerte===1?'':'i'}` : 'Nessuna offerta selezionata';
  $('#offerId').textContent=offer?.offer_ids?.join('\n') || 'Non disponibile';
  application.offer.disabled=!offer || !!s.neg || chosenIdentity!==s.identity;
}
function renderAccess(s) {
  const neg=s.neg; const allowed=neg?.state==='FINALIZED' && neg?.outcome==='AUTHORIZED';
  const rejected=neg?.state==='TERMINATED';
  $('#grantedTile').classList.toggle('active',Boolean(allowed));
  $('#deniedTile').classList.toggle('active',Boolean(rejected));
  const msg=$('#resultMessage');
  msg.textContent= !neg ? 'La negoziazione non è ancora stata richiesta.' :
     allowed ? 'Il Provider ha autorizzato la richiesta. L’accordo contrattuale è stato concluso.' :
     rejected ? 'Il Provider ha rifiutato la richiesta: le condizioni contrattuali non sono soddisfatte. Nessun trasferimento consentito.' :
     'Esito della negoziazione: '+neg.outcome;
  application.transfer.disabled=!allowed || !!s.transfer || chosenIdentity!==s.identity;
  application.verify.disabled=!s.transfer || !!s.verified || chosenIdentity!==s.identity;
  application.gallery.hidden=!s.verified;
  $('#flowTransfer').classList.toggle('done',Boolean(s.transfer));
  $('#flowVerify').classList.toggle('done',Boolean(s.verified));
  $('#flowGallery').classList.toggle('done',Boolean(s.verified));
  $('#transferInfo').textContent=s.verified ? 'Verifica completata: il dataset ricevuto è ora consultabile.' :
       s.transfer ? 'Il processo è avviato. Verifica la ricezione e l’integrità del file JSON.' :
       rejected ? 'La negoziazione è stata rifiutata. Non è possibile trasferire i dati.' :
       'Disponibile dopo un accordo autorizzato e un trasferimento verificato.';
  const list=$('#traceList');list.replaceChildren();
  for (const item of s.events.length?s.events:['In attesa della prima operazione.']) list.appendChild(el('li','',item));
  const ids=[];
  if(neg?.negotiation_id) ids.push('Negotiation ID: '+neg.negotiation_id);
  if(neg?.agreement_id) ids.push('Agreement ID: '+neg.agreement_id);
  if(s.transfer?.transfer_id) ids.push('Transfer Process ID: '+s.transfer.transfer_id);
  if(s.verified?.sha256) ids.push('SHA-256: '+s.verified.sha256);
  $('#evidenceMeta').textContent=ids.join('\n');
}
application.identity.addEventListener('change', () => { chosenIdentity = application.identity.value; render(); });
application.apply.addEventListener('click',()=>call('identity',{identity:chosenIdentity}));
application.discover.addEventListener('click',()=>call('discover'));
application.offer.addEventListener('click',()=>call('negotiate'));
application.transfer.addEventListener('click',()=>call('transfer'));
application.verify.addEventListener('click',()=>call('verify'));
application.newRequest.addEventListener('click',()=>call('new'));
(async function init(){
  try {const res=await fetch('/api/status',{cache:'no-store'});if(!res.ok)throw Error('Server locale non raggiungibile');snapshot=await res.json();chosenIdentity=snapshot.identity;resetIdentityOptions(snapshot.profiles,snapshot.identity);render();}
  catch(e){showMessage('Impossibile leggere il Consumer: '+e.message,true);}
})();
