(function(){
  const ws = new WebSocket((location.protocol==='https:'?'wss:':'ws:')+'//'+location.host+'/ws');
  const select = document.getElementById('server-deck-select');
  const loadBtn = document.getElementById('load-server-deck');
  const localFile = document.getElementById('local-file');
  const newDeckBtn = document.getElementById('new-deck');
  const downloadBtn = document.getElementById('download-deck');

  let currentDeck = null;

  ws.addEventListener('open', ()=>{
    ws.send(JSON.stringify({type:'GET_DECKS'}));
  });
  ws.addEventListener('message', ev=>{
    try{
      const data = JSON.parse(ev.data);
      if(data.type==='DECK_LIST'){
        populateDecks(data.decks||[]);
      }
    }catch(e){console.error(e)}
  });

  function populateDecks(list){
    select.innerHTML = '<option value="">-- wybierz --</option>';
    list.forEach(n=>{
      const o = document.createElement('option'); o.value=n; o.textContent=n; select.appendChild(o);
    });
  }

  loadBtn.addEventListener('click', ()=>{
    const name = select.value; if(!name) return alert('Wybierz deck');
    fetch('/decks/'+encodeURIComponent(name)+'.json').then(r=>{
      if(!r.ok) throw new Error('Nie można pobrać');
      return r.json();
    }).then(j=>{ loadDeck(j); }).catch(e=>alert('Błąd ładowania: '+e));
  });

  localFile.addEventListener('change', e=>{
    const f = e.target.files[0]; if(!f) return;
    const reader = new FileReader();
    reader.onload = ()=>{
      try{ const j = JSON.parse(reader.result); loadDeck(j); }
      catch(err){ alert('Błąd parsowania JSON'); }
    };
    reader.readAsText(f, 'utf-8');
  });

  newDeckBtn.addEventListener('click', ()=>{
    const blank = {format_version:'1.0', meta:{name:'new_deck',display_name:'Nowy deck',authors:[],description:'',language:'pl',tags:[],version:''}, cards:{white:[],black:[]}};
    loadDeck(blank);
  });

  downloadBtn.addEventListener('click', ()=>{
    if(!currentDeck) return alert('Brak decku');
    const name = (currentDeck.meta && currentDeck.meta.name) ? currentDeck.meta.name : 'deck';
    const blob = new Blob([JSON.stringify(currentDeck,null,2)],{type:'application/json;charset=utf-8'});
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a'); a.href=url; a.download = name + '.json'; document.body.appendChild(a); a.click(); a.remove(); URL.revokeObjectURL(url);
  });

  document.querySelectorAll('.tab').forEach(btn=>btn.addEventListener('click', ()=>{
    document.querySelectorAll('.tab').forEach(t=>t.classList.remove('active'));
    document.querySelectorAll('.tab-panel').forEach(p=>p.classList.remove('active'));
    btn.classList.add('active'); document.getElementById(btn.dataset.tab+'-tab').classList.add('active');
  }));

  function loadDeck(j){
    currentDeck = j;
    document.getElementById('meta-name').value = j.meta.name || '';
    document.getElementById('meta-display').value = j.meta.display_name || '';
    document.getElementById('meta-authors').value = (j.meta.authors||[]).join(', ');
    document.getElementById('meta-language').value = j.meta.language || 'pl';
    document.getElementById('meta-desc').value = j.meta.description || '';
    (currentDeck.cards.black||[]).forEach(b=>{
      try{ b.slots = detectSlots(b.template || ''); b.pick = (b.slots && b.slots.length) || 1; }catch(e){}
    });
    renderLists();
  }

  function detectSlots(template){
    if(!template) return [];
    const re = /<([A-Z]+)>/g;
    const arr = [];
    let m;
    while((m = re.exec(template)) !== null){ arr.push(m[1]); }
    return arr;
  }

  function renderLists(){
    const wl = document.getElementById('white-list'); wl.innerHTML = '';
    const bl = document.getElementById('black-list'); bl.innerHTML = '';
    (currentDeck.cards.white||[]).forEach((w,idx)=>{
      const li = document.createElement('li'); li.innerHTML = `<strong>${escapeHtml((w.forms&&w.forms.M)||w.forms?.M||w.forms?.[0]||'')}</strong><div class="meta">${(w.theme||[]).join(', ')}</div><button data-i="${idx}" class="edit-white">Edytuj</button>`;
      wl.appendChild(li);
    });
    (currentDeck.cards.black||[]).forEach((b,idx)=>{
      const li = document.createElement('li'); li.innerHTML = `<strong>${escapeHtml(b.template||'')}</strong><div class="meta">slots: ${JSON.stringify(b.slots||[])}</div><button data-i="${idx}" class="edit-black">Edytuj</button>`;
      bl.appendChild(li);
    });
    document.querySelectorAll('.edit-white').forEach(btn=>btn.addEventListener('click', e=>{
      const i = +e.target.dataset.i; openWhiteEditor(i);
    }));
    document.querySelectorAll('.edit-black').forEach(btn=>btn.addEventListener('click', e=>{
      const i = +e.target.dataset.i; openBlackEditor(i);
    }));
  }

  function openWhiteEditor(index){
    const modal = document.getElementById('editor-modal'); const body = document.getElementById('modal-body');
    const card = currentDeck.cards.white[index] || {forms:{M:''}};
    body.innerHTML = '';
    const CASES = [
      ['M','Mianownik','kto? co?'],
      ['D','Dopełniacz','kogo? czego?'],
      ['C','Celownik','komu? czemu?'],
      ['B','Biernik','kogo? co?'],
      ['N','Narzędnik','z kim? z czym?'],
      ['MSC','Miejscownik','o kim? o czym?'],
      ['W','Wołacz','(wołacz)']
    ];
    CASES.forEach(([k, label, hint])=>{
      const wrapper = document.createElement('div'); wrapper.className='case-field';
      const lab = document.createElement('label'); lab.textContent = `${k} — ${label}`;
      const hintEl = document.createElement('div'); hintEl.className='hint'; hintEl.textContent = hint;
      const inp = document.createElement('input'); inp.value = (card.forms && card.forms[k])?card.forms[k]: (card.forms?card.forms[0]: ''); inp.id='f_'+k;
      wrapper.appendChild(lab); wrapper.appendChild(hintEl); wrapper.appendChild(inp);
      body.appendChild(wrapper);
    });
    const theme = document.createElement('input'); theme.placeholder='theme (comma)'; theme.value=(card.theme||[]).join(', '); theme.id='f_theme'; body.appendChild(theme);
    document.getElementById('modal-title').textContent = 'Edytuj białą kartę';
    modal.classList.remove('hidden');
    document.getElementById('modal-save').onclick = ()=>{
      const forms = {};
      ['M','D','C','B','N','MSC','W'].forEach(k=>forms[k]=document.getElementById('f_'+k).value);
      const newCard = {id: card.id || ('w'+Date.now()), forms:forms, theme: document.getElementById('f_theme').value.split(',').map(s=>s.trim()).filter(Boolean), tags:[], weight:1};
      if(index >= (currentDeck.cards.white||[]).length) currentDeck.cards.white.push(newCard); else currentDeck.cards.white[index]=newCard;
      modal.classList.add('hidden'); renderLists();
    };
    document.getElementById('modal-cancel').onclick = ()=>{ modal.classList.add('hidden'); };
  }

  function openBlackEditor(index){
    const modal = document.getElementById('editor-modal'); const body = document.getElementById('modal-body');
    const card = currentDeck.cards.black[index] || {template:'',slots:[]};
    body.innerHTML = '';

    const desc = document.createElement('div'); desc.style.marginBottom = '8px'; desc.innerHTML = '<strong>Format placeholderów:</strong> użyj &lt;M&gt;, &lt;D&gt;, &lt;C&gt;, &lt;B&gt;, &lt;N&gt;, &lt;MSC&gt;, &lt;W&gt; w tekście, np. "Znalazłem &lt;M&gt; i oddałem &lt;B&gt;". Placeholdery określają, której formy białej karty użyć (np. &lt;B&gt; = biernik, kogo? co?).';
    body.appendChild(desc);

    const ta = document.createElement('textarea'); ta.style.width='100%'; ta.style.minHeight='120px'; ta.value = card.template || ''; ta.id='b_template'; body.appendChild(ta);

    const detected = document.createElement('div'); detected.style.marginTop = '8px'; detected.className = 'meta';
    function updateDetected(){ const s = detectSlots(ta.value); detected.textContent = 'Wykryte sloty: ' + (s.length ? s.join(', ') : '(brak)') + ' — pick=' + (s.length||1); }
    updateDetected(); body.appendChild(detected);

    document.getElementById('modal-title').textContent = 'Edytuj czarną kartę';
    modal.classList.remove('hidden');

    ta.addEventListener('input', updateDetected);

    document.getElementById('modal-save').onclick = ()=>{
      const template = document.getElementById('b_template').value;
      const slots = detectSlots(template);
      const newCard = {id: card.id || ('b'+Date.now()), template: template, slots: slots, pick: slots.length || 1, tags:[], weight:1};
      if(index >= (currentDeck.cards.black||[]).length) currentDeck.cards.black.push(newCard); else currentDeck.cards.black[index]=newCard;
      modal.classList.add('hidden'); renderLists();
    };
    document.getElementById('modal-cancel').onclick = ()=>{ modal.classList.add('hidden'); };
  }

  document.getElementById('add-white').addEventListener('click', ()=> openWhiteEditor((currentDeck.cards.white||[]).length));
  document.getElementById('add-black').addEventListener('click', ()=> openBlackEditor((currentDeck.cards.black||[]).length));

  function escapeHtml(s){ return (s||'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;'); }

})();
