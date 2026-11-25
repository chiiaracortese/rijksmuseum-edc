'use strict';
/* V1.6: cronologia di lettura; gestione offerte confermata e protetta su API dedicate. */
const byId = id => document.getElementById(id);
let providerData = null;
let selectedAssetId = null;
let pendingOfferAction = null;
const text = (id, value) => { byId(id).textContent = value ?? 'Non verificabile'; };
const node = (tag, className, content) => {
  const element = document.createElement(tag);
  if (className) element.className = className;
  if (content != null) element.textContent = String(content);
  return element;
};
function append(parent, tag, cls, content) {
  const element = node(tag, cls, content);
  parent.appendChild(element);
  return element;
}
async function postProvider(action, payload) {
  const response = await fetch('/api/provider/' + action, {
    method: 'POST', credentials: 'same-origin', cache: 'no-store',
    headers: {'Content-Type':'application/json', 'X-Portal-Token': window.PORTAL_TOKEN || ''},
    body: JSON.stringify(payload || {})
  });
  const json = await response.json();
  if (!response.ok) throw new Error(json.error || 'Operazione non disponibile');
  return json;
}
function authVisible(authenticated) {
  byId('providerLogin').hidden = authenticated;
  byId('providerDashboard').hidden = !authenticated;
}
function showAsset(id) {
  const a = providerData?.assets.find(x => x.id === id);
  if (!a) return;
  selectedAssetId = a.id;
  text('providerSelectedName', a.name);
  text('providerSelectedId', a.id);
  text('providerSelectedWorks', a.works ?? 'Non verificabile');
  text('providerSelectedRegistered', a.registered == null ? 'Non verificabile' : a.registered ? 'Sì' : 'No');
  const source = String(a.source || 'Non verificabile');
  text('providerSelectedSource', source === 'JSON LOCALE DISPONIBILE' ? 'JSON locale disponibile' :
    source === 'NON VERIFICATA' ? 'Non verificabile' : source);
  const gallery = byId('providerGallery');
  gallery.hidden = a.source !== 'JSON LOCALE DISPONIBILE';
  if (!gallery.hidden) gallery.href = '/provider/gallery/' + encodeURIComponent(a.id);
  byId('providerGalleryHint').textContent = gallery.hidden ?
    'JSON originale non individuato con certezza. Vedi README per la mappatura locale opzionale.' :
    'Apri la galleria approvata, leggendo il JSON originale del Provider (nessuna negoziazione).';
  byId('providerDatasetGrid').querySelectorAll('button').forEach(button =>
    button.classList.toggle('is-selected', button.dataset.assetId === id));
}
function technicalDetails(parent, pairs) {
  const details = append(parent, 'details', 'technical');
  append(details, 'summary', '', 'Dettagli tecnici EDC');
  for (const [name, value] of pairs) {
    append(details, 'code', '', name + ': ' + (value == null ? 'Non disponibile' :
      typeof value === 'string' ? value : JSON.stringify(value)));
  }
  return details;
}
// L'asset è associato solo se il selector dichiara esplicitamente un ID noto,
// mai deducendolo dalla posizione in elenco o da un semplice frammento di nome.
function idsFromSelector(raw, knownIds) {
  let selector = raw;
  if (typeof selector === 'string') {
    try { selector = JSON.parse(selector); } catch { return []; }
  }
  const found = new Set();
  function walk(item, depth) {
    if (depth > 12 || !item || typeof item !== 'object') return;
    if (Array.isArray(item)) { for (const value of item) walk(value, depth + 1); return; }
    const left = item.operandLeft;
    const right = item.operandRight;
    const op = item.operator;
    if (typeof left === 'string' && /(?:^|[/#])id$/.test(left) &&
        (op === '=' || op === 'eq' || op === 'EQ') &&
        typeof right === 'string' && knownIds.has(right)) found.add(right);
    for (const [key, value] of Object.entries(item)) {
      if (key !== 'operandLeft' && key !== 'operandRight') walk(value, depth + 1);
    }
  }
  walk(selector, 0);
  return [...found];
}
function renderPolicies(data) {
  const summary = byId('providerPolicySummary');
  const shared = byId('providerSharedPolicy');
  const grid = byId('providerContractsUnified');
  shared.replaceChildren(); grid.replaceChildren();
  if (data.policy_count == null || data.contract_count == null) {
    summary.textContent = 'Definizioni contrattuali non disponibili: interrogazione del Provider non riuscita.';
    append(shared, 'p', '', 'Impossibile verificare le associazioni tra dataset e policy.');
    return;
  }
  const policyIds = new Set((data.policies || []).map(p => p.id).filter(Boolean));
  const contracts = data.contracts || [];
  const accessNames = [...new Set(contracts.map(c => c.access_policy).filter(Boolean))];
  summary.textContent = `${data.contract_count} definizioni contrattuali e ${data.policy_count} policy rilevate nel Provider.`;
  append(shared, 'span', 'eyebrow', 'ACCESSO AL CATALOGO');
  if (accessNames.length === 1) {
    const name = accessNames[0];
    append(shared, 'h4', '', 'Una policy di accesso comune');
    append(shared, 'p', '', `Le ${contracts.length} definizioni contrattuali recuperate richiamano la stessa policy per l’accesso al catalogo.`);
    if (!policyIds.has(name)) append(shared, 'p', 'provider-note', 'Il riferimento non compare tra le Policy Definition restituite.');
    technicalDetails(shared, [['Identificativo Access Policy', name]]);
  } else if (accessNames.length > 1) {
    append(shared, 'h4', '', 'Policy di accesso differenti');
    append(shared, 'p', '', 'Non tutte le definizioni utilizzano la stessa policy di accesso al catalogo.');
    technicalDetails(shared, accessNames.map((x, i) => ['Access Policy ' + (i+1), x]));
  } else {
    append(shared, 'h4', '', 'Accesso al catalogo');
    append(shared, 'p', '', 'Nessun identificativo di Access Policy disponibile nelle definizioni restituite.');
  }
  const assetMap = new Map((data.assets || []).map(a => [a.id, a]));
  const known = new Set(assetMap.keys());
  for (const c of contracts) {
    const match = idsFromSelector(c.asset_selector, known);
    const asset = match.length === 1 ? assetMap.get(match[0]) : null;
    const card = append(grid, 'article', 'provider-contract-card');
    append(card, 'span', 'eyebrow', 'DEFINIZIONE CONTRATTUALE');
    append(card, 'h5', '', asset ? asset.name : 'Dataset non determinabile');
    const dl = append(card, 'dl', 'provider-contract-meta');
    const addFact = (name, value) => {
      const line = append(dl, 'div', '');
      append(line, 'dt', '', name);
      append(line, 'dd', '', value);
    };
    const isScenarioA = typeof c.contract_policy === 'string' &&
      c.contract_policy.startsWith('policy-scenario-a-') && policyIds.has(c.contract_policy);
    addFact('Condizioni contrattuali', isScenarioA ? 'Scenario A · policy associata' :
      c.contract_policy ? 'Policy associata (vedi dettagli)' : 'Non disponibile');
    addFact('Dataset selezionati', match.length === 1 ? '1 dataset' :
      match.length > 1 ? String(match.length) + ' dataset' : 'Non determinabile');
    if (accessNames.length > 1) addFact('Accesso al catalogo', c.access_policy || 'Non disponibile');
    technicalDetails(card, [
      ['Contract Definition ID', c.id],
      ['Access Policy ID', c.access_policy],
      ['Contract Policy ID', c.contract_policy],
      ['Asset Selector originale', c.asset_selector]
    ]);
  }
  if (!contracts.length) append(grid, 'p', 'provider-note', 'Nessuna Contract Definition restituita dalle API.');
  // Gli eventuali riferimenti non risolti sono evidenziati solo quando presenti.
  // Non esponiamo una sezione diagnostica permanente nella vista per la tesi.
  const used = new Set(contracts.flatMap(c => [c.access_policy, c.contract_policy]).filter(Boolean));
  const orphanIds = [...policyIds].filter(id => !used.has(id));
  if (orphanIds.length) append(shared, 'p', 'provider-note',
    `${orphanIds.length} policy non associate alle definizioni contrattuali restituite; dettagli da verificare nel registro EDC.`);
}
const HUMAN_STATE = {
  FINALIZED: ['Finalizzata', 'Accordo contrattuale concluso.'],
  TERMINATED: ['Terminata', 'Negoziazione non finalizzata; lo stato non identifica, da solo, la causa.'],
  STARTED: ['Avviato', 'Processo avviato. Non certifica ricezione del JSON o SHA-256.'],
  COMPLETED: ['Completato (EDC)', 'Processo EDC completato. Integrità e ricezione richiedono evidenze separate.'],
  INITIAL: ['Iniziale', 'Processo nelle prime fasi.'],
  VERIFIED: ['Verificata', 'Stato restituito da EDC.']
};
const REJECTION_REASON = {
  policy: 'Condizioni di accesso non soddisfatte (verifica EDC).',
  credentials: 'Verifica delle credenziali non superata (risposta EDC).',
  authorization: 'Autorizzazione negata (risposta EDC).'
};
function isExplicitlyRejected(record) {
  return String(record?.state || '').toUpperCase() === 'TERMINATED' &&
    Object.hasOwn(REJECTION_REASON, String(record?.failure_kind || ''));
}
function stageEntry(parent, record, type) {
  const box = append(parent, 'div', 'provider-stage-entry');
  const raw = String(record.state ?? 'Non disponibile');
  const rejected = type === 'neg' && isExplicitlyRejected(record);
  const friendly = rejected ? ['Rifiutata', REJECTION_REASON[record.failure_kind]] :
    (HUMAN_STATE[raw] || [raw, 'Stato restituito dalle API EDC.']);
  append(box, 'strong', 'provider-stage-status' + (rejected ? ' provider-rejected' : ''), friendly[0]);
  append(box, 'span', 'provider-stage-code', 'Stato EDC: ' + raw);
  append(box, 'span', 'provider-stage-code',
    (type === 'neg' ? 'Negotiation ID: ' : 'Transfer Process ID: ') + (record.id || 'Non disponibile'));
  if (type === 'neg') append(box, 'span', 'provider-stage-code',
    'Rilevata nel: ' + (record.origin === 'Consumer' ? 'Consumer EDC' : 'Provider EDC'));
  append(box, 'span', 'provider-stage-explain', friendly[1]);
}
// Non deduciamo la cronologia dagli UUID; preferiamo l'ultima transizione EDC
// (updatedAt/stateTimestamp), e usiamo createdAt quando manca.
function parsedTime(raw) {
  if (raw == null || raw === '') return null;
  let value;
  if (typeof raw === 'number') value = raw;
  else if (typeof raw === 'string' && /^\d+$/.test(raw.trim())) value = Number(raw);
  else if (typeof raw === 'string') value = Date.parse(raw);
  else return null;
  if (!Number.isFinite(value)) return null;
  if (value < 100_000_000_000) value *= 1000;
  const earliest = Date.UTC(2000, 0, 1), latest = Date.UTC(2100, 0, 1);
  return value >= earliest && value <= latest ? value : null;
}
function activityTime(record) {
  return parsedTime(record?.updated_at) ?? parsedTime(record?.state_timestamp) ??
    parsedTime(record?.created_at);
}
function renderWorkflows(data) {
  const list = byId('providerWorkflowList');
  const summary = byId('providerWorkflowSummary');
  list.replaceChildren();
  const knownN = data.available?.negotiations === true;
  const knownT = data.available?.transfers === true;
  const providerNeg = knownN ? (data.negotiations || []) : [];
  const consumerNeg = data.consumer_history_available === true ?
    (data.consumer_negotiations || []) : [];
  // Evita la doppia visualizzazione di accordi già tracciati sul Provider.
  // Per i TERMINATED senza Agreement non inventiamo correlazioni fra ID diversi.
  const providerAgreementIds = new Set(providerNeg.map(n => n.agreement_id).filter(Boolean));
  const providerRecordIds = new Set(providerNeg.map(n => n.id).filter(Boolean));
  const neg = [...providerNeg, ...consumerNeg.filter(n =>
    !(n.agreement_id && providerAgreementIds.has(n.agreement_id)) &&
    !(n.id && providerRecordIds.has(n.id)))];
  const trans = knownT ? (data.transfers || []) : [];
  if (!knownN && !knownT) {
    summary.textContent = 'Cronologia non disponibile.';
    append(list, 'p', 'provider-note', 'Il Provider non ha restituito la cronologia delle operazioni.');
    return;
  }
  const groups = [], byAgreement = new Map();
  function groupFor(record, kind, i) {
    const agreement = typeof record.agreement_id === 'string' && record.agreement_id.trim() &&
      record.agreement_id !== 'Non disponibile' ? record.agreement_id.trim() : null;
    // Ogni negoziazione senza accordo è un record autonomo: un rifiuto non può
    // essere abbinato per posizione a un trasferimento diverso.
    const key = agreement ? 'agreement:' + agreement : kind + ':unlinked:' + i;
    let group = byAgreement.get(key);
    if (!group) {
      group = { agreement, neg: [], trans: [], originalIndex: groups.length };
      byAgreement.set(key, group);
      groups.push(group);
    }
    return group;
  }
  neg.forEach((r,i) => groupFor(r,'neg',i).neg.push(r));
  trans.forEach((r,i) => groupFor(r,'transfer',i).trans.push(r));
  const records = [...neg,...trans];
  const allDated = records.length > 0 && records.every(r => activityTime(r) != null);
  for (const g of groups) {
    const times = [...g.neg,...g.trans].map(activityTime).filter(x => x != null);
    g.recentTime = times.length ? Math.max(...times) : null;
  }
  groups.sort((a,b) => (b.recentTime ?? -Infinity)-(a.recentTime ?? -Infinity) ||
    a.originalIndex-b.originalIndex);
  const visible = groups.slice(0, 3);
  const chronological = knownN && knownT && allDated && !data.potentially_incomplete_history;
  // Una sola frase, senza conteggi o avvisi tecnici ingombranti.
  // In mancanza di date, non chiamare con certezza "ultimi" i primi tre.
  summary.textContent = chronological ? 'Sono rappresentati gli ultimi tre log effettuati.' :
    'Sono rappresentati fino a tre log disponibili.';
  if (!groups.length) {
    append(list, 'p', 'provider-note', 'Nessuna negoziazione o trasferimento restituito dalle API.');
    return;
  }
  const assetNames = new Map((data.assets || []).map(a => [a.id, a.name]));
  visible.forEach((group, i) => {
    const article = append(list, 'article', 'provider-workflow-card');
    const header = append(article, 'div', 'provider-workflow-card-header');
    append(header, 'span', 'eyebrow', 'OPERAZIONE ' + String(i + 1).padStart(2, '0'));
    const ids = [...new Set([...group.neg,...group.trans].map(r => r.asset_id).filter(Boolean))];
    const label = ids.length === 1 ? (assetNames.get(ids[0]) || ids[0]) :
      ids.length > 1 ? 'Dataset diversi nei processi' : 'Dataset non indicato nel record EDC';
    append(header, 'h4', '', label);
    const rejected = group.neg.some(isExplicitlyRejected);
    const terminatedWithoutAgreement = !group.agreement && group.neg.some(r => r.state === 'TERMINATED');
    if (rejected) append(header, 'span', 'provider-workflow-outcome', 'ACCESSO NEGATO');
    else if (terminatedWithoutAgreement)
      append(header, 'span', 'provider-workflow-outcome', 'NEGOZIAZIONE TERMINATA');
    if (group.recentTime != null) {
      const date = new Intl.DateTimeFormat('it-IT', {dateStyle:'medium',timeStyle:'short'})
        .format(new Date(group.recentTime));
      append(header, 'span', 'provider-workflow-date', 'Ultima attività: ' + date);
    }
    append(header, 'span', 'provider-workflow-agreement',
      'Agreement ID: ' + (group.agreement || (terminatedWithoutAgreement ?
      'Non generato' : 'Non disponibile')));
    const stages = append(article, 'div', 'provider-stage-grid');
    const left = append(stages, 'div', 'provider-stage');
    append(left, 'h5', '', '01 · Negoziazione');
    if (!knownN) append(left, 'p', 'provider-stage-missing', 'Interrogazione non disponibile.');
    else if (!group.neg.length) append(left, 'p', 'provider-stage-missing', 'Nessuna negoziazione correlabile nelle API.');
    else group.neg.forEach(r => stageEntry(left,r,'neg'));
    append(stages, 'span', 'provider-workflow-link', '→');
    const right = append(stages, 'div', 'provider-stage');
    append(right, 'h5', '', '02 · Trasferimento');
    if (!knownT) append(right, 'p', 'provider-stage-missing', 'Interrogazione non disponibile.');
    else if (!group.trans.length && terminatedWithoutAgreement) {
      append(right, 'strong', 'provider-stage-status', 'Non avviato');
      append(right, 'p', 'provider-stage-missing',
        'Nessun Transfer Process associato alla negoziazione non finalizzata.');
    } else if (!group.trans.length)
      append(right, 'p', 'provider-stage-missing', 'Nessun trasferimento correlabile nelle API.');
    else group.trans.forEach(r => stageEntry(right,r,'transfer'));
    if (group.agreement && group.neg.length && group.trans.length)
      append(article, 'p', 'provider-workflow-relation', 'Fasi associate mediante Agreement ID identico.');
    else if (terminatedWithoutAgreement)
      append(article, 'p', 'provider-workflow-relation',
        'Nessun accordo contrattuale: il Provider non segnala un trasferimento per questa richiesta.');
    else if (!group.agreement)
      append(article, 'p', 'provider-workflow-relation',
        'Senza Agreement ID non è possibile collegare le due fasi.');
    else append(article, 'p', 'provider-workflow-relation',
      'Una fase non risulta correlabile tra le risposte API.');
  });
}
function closeOfferConfirmation() {
  pendingOfferAction = null;
  byId('providerOfferConfirmation').hidden = true;
  byId('providerConfirmPhrase').value = '';
  byId('providerConfirmPassword').value = '';
}
function renderOffers(data) {
  const grid = byId('providerOffersGrid');
  const notice = byId('providerOffersNotice');
  grid.replaceChildren();
  if (!data.available) {
    notice.textContent = 'Gestione delle offerte non disponibile: ' + (data.error || 'Impossibile interrogare EDC.');
    return;
  }
  notice.textContent = 'Le offerte sono verificate sulle Contract Definition attualmente registrate in EDC.';
  for (const item of (data.items || [])) {
    const card = append(grid, 'article', 'provider-offer-card');
    const header = append(card, 'div', 'provider-offer-card-head');
    append(header, 'h5', '', item.name || item.id);
    const statuses = {published:'Pubblicata', revoked:'Revocata', not_published:'Non pubblicata', unknown:'Da verificare'};
    append(header, 'span', 'provider-offer-pill ' + (item.status === 'published' ? 'is-live' :
      item.status === 'revoked' ? 'is-revoked' : 'is-neutral'), statuses[item.status] || 'Non verificabile');
    append(card, 'p', 'provider-offer-asset', 'Asset ID: ' + item.id);
    if (item.definition_id) append(card, 'p', 'provider-offer-asset',
      'Contract Definition: ' + item.definition_id);
    if (item.reason) append(card, 'p', 'provider-offer-note', item.reason);
    const actions = append(card, 'div', 'provider-offer-actions');
    if (item.can_revoke || item.can_restore) {
      const operation = item.can_revoke ? 'revoke' : 'restore';
      const btn = append(actions, 'button', 'btn ' + (operation === 'revoke' ? 'btn-outline' : 'btn-gold'),
        operation === 'revoke' ? 'Revoca offerta' : 'Ripubblica offerta');
      btn.type = 'button';
      btn.addEventListener('click', () => prepareOffer(item.id, operation));
    } else {
      append(actions, 'span', 'provider-offer-no-action',
        'Nessuna modifica disponibile per questa configurazione.');
    }
  }
}
async function reloadOffers() {
  const notice = byId('providerOffersNotice');
  try {
    const response = await fetch('/api/provider/offers', {credentials:'same-origin', cache:'no-store'});
    const result = await response.json();
    if (!response.ok) throw new Error(result.error || 'Interrogazione non riuscita');
    renderOffers(result);
  } catch (error) {
    notice.textContent = 'Impossibile recuperare le offerte: ' + error.message;
  }
}
async function prepareOffer(assetId, operation) {
  closeOfferConfirmation();
  const notice = byId('providerOffersNotice');
  try {
    const result = await postProvider('offers/prepare', {asset_id:assetId, operation});
    pendingOfferAction = result;
    byId('providerConfirmHeading').textContent = operation === 'revoke' ?
      'Revoca dell’offerta' : 'Ripubblicazione dell’offerta';
    byId('providerConfirmDescription').textContent = result.message +
      ' Per confermare scrivi ' + result.confirm_word + ' e inserisci nuovamente la chiave Provider.';
    byId('providerConfirmDefinition').textContent =
      'Asset ID: ' + result.asset_id + ' · Contract Definition: ' + result.definition_id;
    byId('providerOfferConfirmation').hidden = false;
    byId('providerOfferConfirmation').scrollIntoView({block:'center',behavior:'smooth'});
  } catch (error) {
    notice.textContent = 'Operazione non preparata: ' + error.message;
  }
}
async function commitOffer(e) {
  e.preventDefault();
  if (!pendingOfferAction) return;
  const button = byId('providerCommitButton');
  button.disabled = true;
  const notice = byId('providerOffersNotice');
  try {
    const result = await postProvider('offers/commit', {
      ticket: pendingOfferAction.ticket,
      confirmation: byId('providerConfirmPhrase').value,
      password: byId('providerConfirmPassword').value
    });
    closeOfferConfirmation();
    await reloadProvider();
    notice.textContent = result.message + ' Verifica la nuova discovery dal Consumer.';
  } catch (error) {
    closeOfferConfirmation();
    await reloadOffers();
    notice.textContent = 'Operazione non confermata da EDC: ' + error.message +
      ' Lo stato dell’offerta non è stato dichiarato modificato. Verificare prima di riprovare.';
    notice.scrollIntoView({block:'center', behavior:'smooth'});
  } finally {
    button.disabled = false;
  }
}
function renderProvider(data) {
  providerData = data;
  const rawId = data.provider_id;
  text('providerId', rawId ? rawId[0].toUpperCase() + rawId.slice(1) : 'Non verificabile');
  const cp = data.controlplane_state || 'Non verificabile';
  text('providerCP', cp.toLowerCase() === 'api management raggiungibile' ?
    'Api management raggiungibile' : cp.toLowerCase() === 'non verificato' ? 'Non verificabile' :
    cp.charAt(0).toUpperCase() + cp.slice(1).toLowerCase());
  text('providerConfigured', data.configured_count);
  text('providerRegistered', data.registered_count ?? 'Non verificabile');
  text('providerPolicyCount', data.policy_count ?? 'Non verificabile');
  text('providerContractCount', data.contract_count ?? 'Non verificabile');
  const diagnostics = byId('providerDiagnostics');
  diagnostics.replaceChildren();
  const actualIssues = (data.messages || []).filter(message =>
    !/^Stato del Data Plane:/i.test(message) &&
    !/^Offerte pubblicate:/i.test(message) &&
    !/^Stato Control Plane e Data Plane non verificato\./i.test(message));
  for (const message of actualIssues) diagnostics.appendChild(node('p', '', message));
  diagnostics.hidden = actualIssues.length === 0;
  const grid = byId('providerDatasetGrid');
  grid.replaceChildren();
  if (!data.assets.length) grid.appendChild(node('div', 'empty-state', 'Nessun asset nel registro.'));
  for (const item of data.assets) {
    const button = node('button', 'dataset-item');
    button.type = 'button'; button.dataset.assetId = item.id;
    button.appendChild(node('strong', '', item.name));
    button.appendChild(node('small', '', item.registered === true ? 'Registrato' :
      item.registered === false ? 'Non registrato' : 'Registrazione non verificata'));
    button.appendChild(node('span', 'dataset-arrow', '↗'));
    button.addEventListener('click', () => showAsset(item.id));
    grid.appendChild(button);
  }
  renderPolicies(data);
  renderWorkflows(data);
  if (selectedAssetId && data.assets.some(a => a.id === selectedAssetId)) showAsset(selectedAssetId);
  else if (data.assets.length) showAsset(data.assets[0].id);
}
async function reloadProvider() {
  const button = byId('providerReload');
  button.disabled = true;
  try {
    const response = await fetch('/api/provider/data', {credentials: 'same-origin',cache:'no-store'});
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || 'Accesso Provider non autorizzato');
    renderProvider(data);
    await reloadOffers();
  } catch (e) {
    const diagnostics = byId('providerDiagnostics');
    diagnostics.replaceChildren(node('p','', 'Impossibile caricare informazioni reali: ' + e.message));
    if (/autorizzat|autentic/i.test(e.message)) authVisible(false);
  } finally { button.disabled = false; }
}
byId('providerLoginForm').addEventListener('submit', async e => {
  e.preventDefault();
  const password = byId('providerPassword').value;
  try {
    await postProvider('login', {password});
    byId('providerPassword').value = '';
    authVisible(true);
    await reloadProvider();
  } catch (error) { text('loginNotice', error.message); }
});
byId('providerReload').addEventListener('click', reloadProvider);
byId('providerOfferConfirmForm').addEventListener('submit', commitOffer);
byId('providerCancelOffer').addEventListener('click', closeOfferConfirmation);
byId('providerLogout').addEventListener('click', async () => {
  try { await postProvider('logout'); } finally { closeOfferConfirmation(); authVisible(false); providerData = null; }
});
(async function init() {
  try {
    const response = await fetch('/api/provider/session', {cache:'no-store'});
    const data = await response.json();
    authVisible(Boolean(data.authenticated));
    if (data.authenticated) await reloadProvider();
  } catch (error) { authVisible(false); text('loginNotice', 'Server locale non disponibile: ' + error.message); }
})();
