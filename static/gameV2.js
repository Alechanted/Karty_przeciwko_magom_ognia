class GameApiClient {
    constructor(ws) {
        this.ws = ws;
    }

    send(message) {
        this.ws.send(JSON.stringify(message));
    }

    setNickname(nickname) {
        if (!nickname) return;
        this.send({ type: 'SET_NICK', nickname: nickname });
    }

    sendChatMessage(message) {
        if (!message) return;
        this.send({ type: 'CHAT_MSG', message: message });
    }

    getDecks() {
        this.send({ type: 'GET_DECKS' });
    }

    createRoom({ name, password, maxPlayers, handSize, pointsToWin, waitForAll, timeout, anyoneCanStart, decks }) {
        this.send({
            type: 'CREATE_ROOM',
            settings: {
                name: name,
                decks: decks,
                password: password,
                hand_size: handSize,
                win_score: pointsToWin,
                max_players: maxPlayers,
                anyone_can_start: anyoneCanStart,
                timeout: waitForAll ? null : timeout,
            }
        });
    }

    joinRoom(roomName, password) {
        if (!roomName) return;
        this.send({ type: 'JOIN_ROOM', name: roomName, password: password });
    }

    leaveRoom() {
        this.send({ type: 'LEAVE_ROOM' });
    }

    startGame() {
        this.send({ type: 'START_GAME' });
    }

    submitCards(cards) {
        if (!cards || cards.length === 0) return;
        this.send({ type: 'SUBMIT_CARDS', cards });
    }

    pickWinner(index) {
        if (index === undefined || index < 0) return;
        this.send({ type: 'PICK_WINNER', index });
    }

    setReady() {
        this.send({ type: 'PLAYER_READY' });
    }
}

function on(eventType, callback) {
    window.addEventListener(eventType, callback);
}

function initialize() {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    ws = new WebSocket(`${protocol}//${window.location.host}/ws`);
    ws.onopen = () => console.log("WS Connected");
    ws.onmessage = (e) => {
        let message = JSON.parse(e.data);
        let event = new CustomEvent(message.type, { detail: message });
        window.dispatchEvent(event);
    };
    ws.onclose = () => { alert("Rozłączono!"); location.reload(); };
    Alpine.store('texts', TEXTS);

    gameApiClient = new GameApiClient(ws);

    on('ERROR', (e) => alert(e.detail.message));

    createLogin(gameApiClient);
    createRoomList(gameApiClient);
    createChat(gameApiClient);
    createRoomCreator(gameApiClient);
    createRoomPasswordModal(gameApiClient);
    createGameRoom(gameApiClient);
    createSoundPlayer();
}

function createLogin(gameApiClient) {
    Alpine.data('login', () => ({
        show: true,
        nickname: "",
        loginError: "",

        init() {
            on('NICK_OK', () => this.show = false);
        },

        login() {
            gameApiClient.setNickname(this.nickname);
            Alpine.store('nickname', this.nickname);
        }
    }));
}

function createRoomList(gameApiClient) {
    Alpine.data('roomList', () => ({
        show: false,
        rooms: [],
        players: [],
        showRoomList: false,
        loading: true,
        nickname: "UNSET",

        init() {
            on('NICK_OK', () => this.show = true);

            on('JOIN_ROOM_OK', () => this.show = false);

            on('LEFT_ROOM', () => this.show = true);

            on('ROOM_LIST', (e) => this.updateRoomList(e.detail));

            on('LOBBY_PLAYERS', (e) => this.updatePlayerList(e.detail));

            on('ROOM_UPDATE', (e) => this.updateRoom(e.detail));
        },

        updateRoomList({ rooms, players }) {
            if (rooms) this.rooms = rooms.map(models.roomListItem);
            if (players) this.updatePlayerList({ players });
            this.loading = false;
        },

        updateRoom({ room }) {
            if (!room) return;

            const index = this.rooms.findIndex(r => r.name === room.name);
            if (index !== -1) {
                this.rooms[index].players = room.players;
                this.rooms[index].maxPlayers = room.max;
                this.rooms[index].hasPassword = room.has_password;
            }
        },

        updatePlayerList({ players }) {
            if (!players) return;

            this.players = players.map(models.lobbyPlayer);
        },

        createRoom() {
            gameApiClient.getDecks();
        },

        joinRoom(room) {
            if (room.hasPassword) {
                let modal = Alpine.store('passwordModal')
                console.log(modal);
                modal.showModal(room.name);
            } else {
                gameApiClient.joinRoom(room.name, null);
            }
        }
    }));
}

function createRoomPasswordModal(gameApiClient) {
    Alpine.store('passwordModal', {
        show: false,
        roomToJoin: null,
        password: null,

        init() {
            on('JOIN_ROOM_OK', () => this.hide());
        },

        joinRoom() {
            if (!this.roomToJoin) return;

            gameApiClient.joinRoom(this.roomToJoin, this.password);
        },

        showModal(roomName) {
            this.roomToJoin = roomName;
            this.show = true;
        },

        hide() {
            this.show = false;
            this.roomToJoin = null;
            this.password = null;
        }
    });
}

function createChat(gameApiClient) {
    Alpine.store('chat', () => ({
        messages: [],
        newMessage: "",

        init() {
            on('CHAT', (e) => {
                let message = models.chatMessage(e.detail);
                this.messages.push(message);
                // todo scroll to bottom of chat
            });

            on('JOIN_ROOM_OK', () => {
                this.newMessage = "";
                this.messages = [];
            });

            on('LEFT_ROOM', () => {
                this.newMessage = "";
                this.messages = [];
            });
        },

        sendMessage() {
            if (this.newMessage.trim() === "") return;

            gameApiClient.sendChatMessage(this.newMessage);
            this.newMessage = "";
        }
    }));
}

function createRoomCreator(gameApiClient) {
    Alpine.data('roomCreator', () => ({
        show: false,
        roomName: "",
        password: null,
        maxPlayers: 8,
        handSize: 10,
        pointsToWin: 5,
        waitForAll: true,
        timeout: 60,
        anyoneCanStart: false,
        decks: [],

        init() {
            on('DECK_LIST', (e) => {
                this.show = true;
                this.decks = e.detail.decks.map(models.deck);
            });

            on('JOIN_ROOM_OK', () => this.cancel());
        },

        createRoom() {
            if (!this.roomName.trim()) {
                alert("Podaj nazwę pokoju!");
                return;
            }

            const selectedDecks = this.decks.filter(d => d.selected).map(d => d.name);
            if (selectedDecks.length === 0) {
                alert("Wybierz przynajmniej jedną talię!");
                return;
            }

            if (!this.waitForAll && this.timeout <= 0) {
                alert("Wybierz poprawny timeout lub czekaj!");
                return;
            }

            gameApiClient.createRoom({
                name: this.roomName,
                decks: selectedDecks,
                timeout: this.timeout,
                password: this.password,
                handSize: this.handSize,
                waitForAll: this.waitForAll,
                maxPlayers: this.maxPlayers,
                pointsToWin: this.pointsToWin,
                anyoneCanStart: this.anyoneCanStart,
            });
        },

        cancel() {
            this.show = false;
        }
    }));
}

function createGameRoom(gameApiClient) {
    Alpine.data('gameRoom', () => ({
        show: false,
        showLobby: true,
        showPlayView: false,
        showWaitingRoom: false,
        showSubmitButton: false,
        id: null,
        canStartGame: false,
        roomName: "UNSET",
        phase: "LOBBY",
        statusMessage: "UNSET",
        isCzar: false,
        isReady: false,
        readyStatus: { ready: 0, total: 0 },
        hasSubmittedCards: false,
        awaitingSubmission: false,
        players: [],
        selected: [],
        hand: [],
        submissions: [],
        blackCard: null,
        winner: null,
        gameWinner: null,

        init() {
            on('JOIN_ROOM_OK', (e) => this.onRoomJoined(e.detail));
            
            on('GAME_UPDATE', (e) => this.updateGameState(e.detail));
            
            on('LEFT_ROOM', () => {
                this.show = false;
                this.updateGameState({ phase: "LOBBY", hand: [], submissions: [], players_list: [] });
            });
        },

        onRoomJoined({room, connection_id}) {
            this.id = connection_id;
            this.roomName = room;
            this.show = true;
        },

        leaveRoom() {
            gameApiClient.leaveRoom();
        },

        updateGameState(gameState) {
            this.phase = gameState.phase;
            this.isCzar = gameState.is_czar;
            this.isReady = gameState.am_i_ready;
            this.hand = [...gameState.hand].map(models.handCard);
            this.readyStatus = gameState.ready_status;
            this.blackCard = gameState.black_card;
            this.submissions = [...gameState.submissions].map(models.submission);
            this.canStartGame = gameState.can_start_game;
            this.hasSubmittedCards = gameState.has_submitted;
            this.gameWinner = gameState.winner;

            if (this.phase === "SUMMARY") {
                this.awaitingSubmission = false;
                this.selected = [];
                this.winner = null;
            }

            this.showLobby = this.phase === "LOBBY";
            this.showWaitingRoom = this.hand.length === 0 && this.phase !== "LOBBY";
            this.showPlayView = !this.showLobby && !this.showWaitingRoom;
            this.showSubmitButton = !this.awaitingSubmission && this.phase === "SELECTING" && this.hand.length > 0 && !this.isCzar;
            this.statusMessage = this.statusDictionary[this.phase](this);

            this.updatePlayerList(gameState.players_list);
        },

        updatePlayerList(players) {
            if (!players) return;
            this.players = players.map(models.roomPlayer);
        },

        startGame() {
            if (!this.canStartGame) return;
            gameApiClient.startGame();
        },

        selectWhiteCard(card) {
            if (this.isCzar || this.awaitingSubmission || this.hasSubmittedCards) return;

            if (this.selected.indexOf(card) !== -1) {
                this.selected.splice(this.selected.indexOf(card), 1);
            }
            else if (this.selected.length < this.blackCard.pick) {
                this.selected.push(card);
            }
        },

        submitCards() {
            if (this.selected.length === this.blackCard.pick && !this.awaitingSubmission) {
                gameApiClient.submitCards(this.selected.map(c => c.id));
                this.awaitingSubmission = true;
            }
        },

        selectWinner(submission) {
            if (!this.isCzar) return;

            this.winner = this.winner == submission ? null : submission;
        },

        submitWinner() {
            if (this.isCzar && this.winner && !this.awaitingSubmission) {
                this.awaitingSubmission = true;
                const index = this.submissions.indexOf(this.winner);
                gameApiClient.pickWinner(index);
            }
        },

        setReady() {
            gameApiClient.setReady();
        },

        leaveRoom() {
            gameApiClient.leaveRoom();
        },

        statusDictionary: {
            "LOBBY": () => "",
            "GAME_OVER": () => "",
            "SUMMARY": () => Alpine.store('texts')['SUMMARY_TITLE'],
            "JUDGING": (c) => c.isCzar
                ? Alpine.store('texts')['INFO_JUDGING_CZAR'].replace('{czar}', Alpine.store('texts')['ROLE_CZAR'])
                : Alpine.store('texts')['INFO_JUDGING_PLAYER'].replace('{czar}', Alpine.store('texts')['ROLE_CZAR']),
            "SELECTING": (c) => {
                if (c.isCzar) {
                    return Alpine.store('texts')['INFO_CZAR_WAIT'].replace('{czar}', Alpine.store('texts')['ROLE_CZAR']);
                }
                else if (c.hasSubmittedCards || c.awaitingSubmission) {
                    return Alpine.store('texts')['INFO_PLAYER_WAIT'];
                }
                else {
                    return Alpine.store('texts')['INFO_PICK_CARDS'].replace('{count}', c.blackCard ? c.blackCard.pick : '1');
                }
            }
        }
    }));
}

function createSoundPlayer() {
    Alpine.data('soundPlayer', () => ({
        mute: false,

        init() {
            on('PLAY_SOUND', (e) => this.playSound(e.detail.src));
            this.mute = localStorage.getItem('mute_sounds') === 'true';
        },

        playSound(src) {
            if (localStorage.getItem('mute_sounds') === 'true') return;

            try {
                const audio = new Audio(src);
                audio.volume = 0.5;
                audio.play().catch(e => console.warn("Audio blocked:", e));
            } catch (e) { console.error(e); }
        },

        toggleMute() {
            this.mute = !this.mute;
            localStorage.setItem('mute_sounds', this.mute);
        }
    }));
}

const models = {
    roomListItem: (data) => ({
        name: data.name,
        maxPlayers: data.max,
        players: data.players,
        hasPassword: data.has_password,
    }),

    lobbyPlayer: (data) => ({
        nick: data.nick,
        room: data.room,
    }),

    roomPlayer: (data) => ({
        id: data.id,
        nick: data.nick,
        score: data.score,
        isCzar: data.is_czar,
    }),

    chatMessage: (data) => ({
        author: data.author,
        message: data.message,
    }),

    deck: (data) => ({
        selected: true,
        name: data,
    }),

    handCard: (data) => ({
        id: data.id,
        text: data.text
    }),

    submission: (data) => ({
        id: data.id,
        text: data.full_text,
        author: data.author,
        winner: data.is_winner,
    }),
}

document.addEventListener('alpine:init', () => {
    initialize();
});