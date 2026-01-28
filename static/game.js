document.addEventListener("DOMContentLoaded", () => {
    // --- LOKALIZACJA STATYCZNA (HTML) ---
    function applyTranslations() {
        // Mapowanie ID elementu -> Klucz w TEXTS
        const map = {
            'game-main-title': 'GAME_TITLE',
            'nickname-input': ['placeholder', 'LOGIN_PLACEHOLDER'], // Inputy obsługujemy inaczej
            'set-nick-btn': 'LOGIN_BTN',
            'rooms-header': 'ROOM_LIST_HEADER',
            'create-room-btn': 'CREATE_ROOM_BTN',
            'refresh-rooms': 'REFRESH_BTN',
            'modal-create-title': 'MODAL_CREATE_TITLE',
            'lbl-room-name': 'LBL_ROOM_NAME',
            'lbl-pass': 'LBL_PASS',
            'lbl-max': 'LBL_MAX',
            'lbl-hand': 'LBL_HAND',
            'lbl-win': 'LBL_WIN',
            'lbl-timeout': 'LBL_TIMEOUT',
            'header-decks': 'HEADER_DECKS',
            'confirm-create-room': 'BTN_CREATE_CONFIRM',
            'cancel-create-room': 'BTN_CANCEL',
            'modal-pass-title': 'MODAL_PASS_TITLE',
            'confirm-join-pass': 'JOIN_BTN',
            'cancel-join-pass': 'BTN_CANCEL',
            'leave-room-btn': 'LEAVE_ROOM_BTN',
            'lobby-waiting-title': 'LOBBY_WAITING_TITLE',
            'lobby-waiting-desc': 'LOBBY_WAITING_DESC',
            'start-game-btn': 'START_GAME_BTN',
            'waiting-room-title': 'WAITING_ROOM_TITLE',
            'waiting-room-desc': 'WAITING_ROOM_DESC',
            'players-header': 'SIDEBAR_PLAYERS',
            'chat-header': 'SIDEBAR_CHAT', // Jeśli masz nagłówek chatu
            'chat-input': ['placeholder', 'CHAT_PLACEHOLDER'],

            // Panic Overlay
            'panic-btn': 'PANIC_BTN',
            'panic-title': 'PANIC_TITLE',
            'panic-desc': 'PANIC_DESC',
            'avatar-1': 'PANIC_AVATAR_1',
            'avatar-2': 'PANIC_AVATAR_2',
            'avatar-3': 'PANIC_AVATAR_3'
        };

        for (const [id, key] of Object.entries(map)) {
            const el = document.getElementById(id);
            if (!el) continue;

            if (Array.isArray(key)) {
                // Np. input placeholder
                el[key[0]] = TEXTS[key[1]];
            } else {
                el.innerHTML = TEXTS[key];
            }
        }
    }

    // Uruchom tłumaczenie od razu
    applyTranslations();

    // --- LOGIKA GRY ---
    let ws;
    let myNick = "";
    let currentRoom = null;
    let selectedCards = [];
    let requiredPick = 1;
    let currentHand = [];

    // Elementy (bez zmian zmiennych, używamy ich poniżej)
    const loginScreen = document.getElementById('login-screen');
    const roomListScreen = document.getElementById('room-list-screen');
    const gameScreen = document.getElementById('game-screen');
    const createRoomModal = document.getElementById('create-room-modal');
    const passwordModal = document.getElementById('password-modal');
    const lobbyView = document.getElementById('lobby-view');
    const playView = document.getElementById('play-view');
    const waitingRoomView = document.getElementById('waiting-room-view');
    const nickInput = document.getElementById('nickname-input');
    const roomsContainer = document.getElementById('rooms-container');
    const deckListContainer = document.getElementById('deck-list');
    const newRoomName = document.getElementById('new-room-name');
    const newRoomPass = document.getElementById('new-room-pass');
    const joinRoomPass = document.getElementById('join-room-pass');
    let pendingJoinRoomName = null;
    const chatInput = document.getElementById('chat-input');
    const chatMsgs = document.getElementById('chat-messages');
    const playerList = document.getElementById('player-list');
    const blackCardText = document.getElementById('black-card-text');
    const roleInfo = document.getElementById('role-info');
    const handContainer = document.getElementById('hand-container');

    function connect() {
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        ws = new WebSocket(`${protocol}//${window.location.host}/ws`);
        ws.onopen = () => console.log("WS Connected");
        ws.onmessage = (e) => handleMessage(JSON.parse(e.data));
        ws.onclose = () => { alert("Rozłączono!"); location.reload(); };
    }

    function handleMessage(data) {
        switch(data.type) {
            case 'NICK_OK':
                loginScreen.classList.add('hidden');
                roomListScreen.classList.remove('hidden');
                document.getElementById('lobby-user-display').innerText = `Gracz: ${myNick}`;
                break;
            case 'ROOM_LIST': renderRoomList(data.rooms); break;
            case 'DECK_LIST': renderDeckList(data.decks); break;
            case 'JOIN_ROOM_OK':
                currentRoom = data.room;
                roomListScreen.classList.add('hidden');
                createRoomModal.classList.add('hidden');
                passwordModal.classList.add('hidden');
                gameScreen.classList.remove('hidden');
                const label = TEXTS['ROOM_HEADER'] || "Pokój";
                document.getElementById('room-display').innerText = `${TEXTS['ROOM_LIST_HEADER']}: ${currentRoom}`;
                lobbyView.classList.remove('hidden');
                playView.classList.add('hidden');
                waitingRoomView.classList.add('hidden');
                chatMsgs.innerHTML = '';
                break;
            case 'GAME_UPDATE':
                renderGame(data);
                if (data.players_list) renderPlayerList(data.players_list);
                break;
            case 'CHAT': addChatMessage(data.author, data.message); break;
            case 'LEFT_ROOM':
                gameScreen.classList.add('hidden');
                roomListScreen.classList.remove('hidden');
                currentRoom = null;
                break;
            case 'ERROR':
                const msg = TEXTS[data.message] || data.message; // Próba tłumaczenia błędu z klucza
                if (!loginScreen.classList.contains('hidden')) document.getElementById('login-error').innerText = msg;
                else alert(msg);
                break;
        }
    }

    // Eventy przycisków
    document.getElementById('set-nick-btn').onclick = () => {
        myNick = nickInput.value.trim();
        if(!myNick) return;
        if(!ws || ws.readyState !== WebSocket.OPEN) {
            connect();
            setTimeout(() => ws.send(JSON.stringify({ type: 'SET_NICK', nickname: myNick })), 500);
        } else {
            ws.send(JSON.stringify({ type: 'SET_NICK', nickname: myNick }));
        }
    };

    document.getElementById('refresh-rooms').onclick = () => ws.send(JSON.stringify({ type: 'GET_ROOMS' }));
    document.getElementById('create-room-btn').onclick = () => { ws.send(JSON.stringify({ type: 'GET_DECKS' })); createRoomModal.classList.remove('hidden'); };
    document.getElementById('cancel-create-room').onclick = () => createRoomModal.classList.add('hidden');
    document.getElementById('confirm-create-room').onclick = () => {
        const name = newRoomName.value.trim();
        if (!name) return alert("Podaj nazwę pokoju");
        const checkedDecks = Array.from(document.querySelectorAll('.deck-checkbox:checked')).map(cb => cb.value);
        if (checkedDecks.length === 0) return alert("Wybierz talię!");
        const settings = {
            max_players: document.getElementById('conf-max').value,
            hand_size: document.getElementById('conf-hand').value,
            win_score: document.getElementById('conf-win').value,
            timeout: document.getElementById('conf-timeout').value,
            decks: checkedDecks
        };
        ws.send(JSON.stringify({ type: 'CREATE_ROOM', name: name, password: newRoomPass.value, settings: settings }));
    };

    document.getElementById('confirm-join-pass').onclick = () => ws.send(JSON.stringify({ type: 'JOIN_ROOM', name: pendingJoinRoomName, password: joinRoomPass.value }));
    document.getElementById('cancel-join-pass').onclick = () => passwordModal.classList.add('hidden');
    document.getElementById('leave-room-btn').onclick = () => ws.send(JSON.stringify({ type: 'LEAVE_ROOM' }));
    document.getElementById('start-game-btn').onclick = () => ws.send(JSON.stringify({ type: 'START_GAME' }));
    document.getElementById('send-chat').onclick = sendChat;
    document.getElementById('chat-input').onkeypress = (e) => { if(e.key === 'Enter') sendChat(); };

    function sendChat() {
        const msg = chatInput.value.trim();
        if(!msg) return;
        ws.send(JSON.stringify({ type: 'CHAT_MSG', message: msg }));
        chatInput.value = '';
    }

    // --- RENDERY ---

    function renderRoomList(rooms) {
        roomsContainer.innerHTML = '';
        if (rooms.length === 0) {
            roomsContainer.innerHTML = `<p>${TEXTS['NO_ROOMS']}</p>`;
            return;
        }
        rooms.forEach(room => {
            const div = document.createElement('div');
            div.className = 'room-card';
            div.innerHTML = `
                <h4>${room.name}</h4>
                <div class="room-info">
                    ${TEXTS['ROOM_PLAYERS']}: ${room.players}/${room.max}<br>
                    Hasło: ${room.has_password ? TEXTS['ROOM_PASS_YES'] : TEXTS['ROOM_PASS_NO']}
                </div>
                <button class="join-btn">${TEXTS['JOIN_BTN']}</button>
            `;
            div.querySelector('.join-btn').onclick = () => tryJoinRoom(room);
            roomsContainer.appendChild(div);
        });
    }

    function tryJoinRoom(room) {
        if (room.has_password) {
            pendingJoinRoomName = room.name;
            joinRoomPass.value = '';
            passwordModal.classList.remove('hidden');
        } else {
            ws.send(JSON.stringify({ type: 'JOIN_ROOM', name: room.name }));
        }
    }

    function renderDeckList(decks) {
        deckListContainer.innerHTML = '';
        decks.forEach(deck => {
            const div = document.createElement('div');
            div.className = 'deck-option';
            div.innerHTML = `<input type="checkbox" class="deck-checkbox" value="${deck}" checked> ${deck}`;
            deckListContainer.appendChild(div);
        });
    }

function renderGame(data) {
        currentHand = data.hand || [];

        // --- FIX WIDOKÓW ---
        // Sterujemy widocznością wyłącznie na podstawie FAZY GRY
        if (data.phase === 'LOBBY') {
            lobbyView.classList.remove('hidden');
            playView.classList.add('hidden');
            waitingRoomView.classList.add('hidden');

            // Aktualizacja licznika graczy w Lobby (obok przycisku start)
            // Musimy to robić tutaj, bo update przychodzi live
            const startBtnInfo = document.getElementById('lobby-players-count');
            if (startBtnInfo && data.players_list) {
                startBtnInfo.innerText = `Graczy w pokoju: ${data.players_list.length}`;
            }

        } else if (data.phase === 'GAME_OVER') {
            lobbyView.classList.add('hidden');
            playView.classList.remove('hidden');
            waitingRoomView.classList.add('hidden');
            renderGameOver(data.winner);
            return;

        } else {
            lobbyView.classList.add('hidden');
            const amIParticipating = currentHand.length > 0 || data.is_czar;

            if (amIParticipating) {
                playView.classList.remove('hidden');
                waitingRoomView.classList.add('hidden');
            } else {
                playView.classList.add('hidden');
                waitingRoomView.classList.remove('hidden');
            }
        }
        // -------------------

        blackCardText.innerHTML = data.black_card ? data.black_card.text : "...";
        requiredPick = data.black_card ? data.black_card.pick : 1;
        handContainer.innerHTML = '';

        // Sprzątanie guzików
        const oldBtn = document.getElementById('confirm-selection-btn'); if(oldBtn) oldBtn.remove();
        const rBtn = document.getElementById('ready-container'); if(rBtn) rBtn.remove();

        // LOGIKA FAZ
        if (data.phase === 'SUMMARY') {
            roleInfo.innerText = TEXTS['SUMMARY_TITLE'];
            renderSummary(data.submissions);
            renderReadyButton(data.ready_status, data.am_i_ready);

        } else if (data.phase === 'JUDGING') {
            const czarTitle = TEXTS['ROLE_CZAR'];
            const msgCzar = TEXTS['INFO_JUDGING_CZAR'].replace('{czar}', czarTitle);
            const msgPlayer = TEXTS['INFO_JUDGING_PLAYER'].replace('{czar}', czarTitle);

            roleInfo.innerText = data.is_czar ? msgCzar : msgPlayer;
            renderSubmissions(data.submissions, data.is_czar);

        } else if (data.phase === 'SELECTING') {
            if (data.is_czar) {
                const czarTitle = TEXTS['ROLE_CZAR'];
                roleInfo.innerText = TEXTS['INFO_CZAR_WAIT'].replace('{czar}', czarTitle);
                handContainer.innerHTML = `<p style="color:#aaa; text-align:center; width:100%">${TEXTS['INFO_CZAR_DESC']}</p>`;
            } else if (data.has_submitted) {
                roleInfo.innerText = TEXTS['INFO_PLAYER_WAIT'];
                handContainer.innerHTML = `<p style="color:#aaa; text-align:center; width:100%">${TEXTS['CARD_SENT_MSG']}</p>`;
            } else {
                roleInfo.innerText = TEXTS['INFO_PICK_CARDS'].replace('{count}', requiredPick);
                renderHand(currentHand);
                renderConfirmButton();
            }
        }
    }

    function renderHand(cards) {
        cards.forEach(card => {
            const div = document.createElement('div');
            div.className = 'card';
            div.dataset.id = card.id;
            div.innerHTML = `<div class="card-content">${card.text}</div>`;
            if (selectedCards.indexOf(card.id) !== -1) {
                div.classList.add('selected');
                div.innerHTML += `<div class="selection-badge">${selectedCards.indexOf(card.id)+1}</div>`;
            }
            div.onclick = () => toggleCard(card.id);
            handContainer.appendChild(div);
        });
    }

    function toggleCard(id) {
        const idx = selectedCards.indexOf(id);
        if (idx !== -1) selectedCards.splice(idx, 1);
        else {
            if (selectedCards.length < requiredPick) selectedCards.push(id);
            else { selectedCards.pop(); selectedCards.push(id); }
        }
        handContainer.innerHTML = ''; renderHand(currentHand); renderConfirmButton();
    }

    function renderConfirmButton() {
        if (selectedCards.length === requiredPick) {
            const btn = document.createElement('button');
            btn.id = 'confirm-selection-btn';
            btn.className = 'big-green-btn';
            btn.innerText = TEXTS['BTN_CONFIRM_SELECTION'];
            btn.onclick = () => { ws.send(JSON.stringify({ type: 'SUBMIT_CARDS', cards: selectedCards })); selectedCards = []; };
            handContainer.after(btn);
        }
    }

    function renderSubmissions(submissions, isCzar) {
        submissions.forEach(sub => {
            const div = document.createElement('div');
            div.className = 'card black-card-render';
            div.style.background = '#ddd'; div.style.color = '#333';
            div.innerHTML = `<div class="card-content">${sub.full_text}</div><div class="card-footer">${isCzar ? TEXTS['CARD_FOOTER_CZAR'] : ''}</div>`;
            if (isCzar) {
                div.style.cursor = 'pointer';
                div.onclick = () => { if(confirm(TEXTS['BTN_CONFIRM_SELECTION'] + "?")) ws.send(JSON.stringify({ type: 'PICK_WINNER', index: sub.id })); };
            }
            handContainer.appendChild(div);
        });
    }

    function renderSummary(submissions) {
        submissions.forEach(sub => {
            const div = document.createElement('div');
            div.className = 'card black-card-render';
            div.style.background = '#ddd'; div.style.color = '#333';
            let extra = sub.is_winner ? `<div class="winner-badge">${TEXTS['WINNER_BADGE']}</div>` : '';
            if(sub.is_winner) div.classList.add('winner-card');
            div.innerHTML = `${extra}<div class="card-content">${sub.full_text}</div><div class="card-footer">${TEXTS['AUTHOR_LABEL']} ${sub.author}</div>`;
            handContainer.appendChild(div);
        });
    }

    function renderReadyButton(status, amIReady) {
        const div = document.createElement('div');
        div.id = 'ready-container';
        div.style.width='100%'; div.style.textAlign='center';
        const btn = document.createElement('button');
        btn.className = 'big-green-btn';
        if(amIReady) {
            btn.innerText = `${TEXTS['BTN_WAITING']} (${status.ready}/${status.total})`;
            btn.disabled=true; btn.style.background='#555';
        } else {
            btn.innerText = `${TEXTS['BTN_NEXT_SHIFT']} (${status.ready}/${status.total})`;
            btn.onclick = () => ws.send(JSON.stringify({type: 'PLAYER_READY'}));
        }
        div.appendChild(btn);
        handContainer.after(div);
    }

    function renderGameOver(winner) {
        const msgWinner = TEXTS['MSG_WINNER'].replace('{nick}', winner);
        handContainer.innerHTML = `
            <div style="text-align:center; color:gold; width:100%">
                <h2>${TEXTS['GAME_OVER_TITLE']}</h2>
                <h3>${winner} ${TEXTS['GAME_OVER_SUBTITLE']}</h3>
                <p>${TEXTS['GAME_OVER_GLORY']}</p>
                <button class="big-green-btn" onclick="location.reload()">${TEXTS['BTN_BACK_LOBBY']}</button>
            </div>
        `;
    }

    function renderPlayerList(players) {
        playerList.innerHTML = '';
        players.forEach(p => {
            const li = document.createElement('li');
            li.innerText = `${p.is_czar ? '👑 ' : ''}${p.nick} (${p.score})`;
            if(p.nick === myNick) { li.style.fontWeight = 'bold'; li.style.color = '#4CAF50'; }
            playerList.appendChild(li);
        });
    }

    function addChatMessage(author, msg) {
        const div = document.createElement('div');
        div.innerHTML = `<strong>${author}:</strong> ${msg}`;
        chatMsgs.appendChild(div);
        chatMsgs.scrollTop = chatMsgs.scrollHeight;
    }

    // Panic
    document.getElementById('panic-btn').onclick = () => document.getElementById('panic-overlay').classList.remove('hidden');
    document.getElementById('panic-overlay').onclick = () => document.getElementById('panic-overlay').classList.add('hidden');

    connect();
});