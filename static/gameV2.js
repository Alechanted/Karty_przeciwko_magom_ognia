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

    setReady(){
        this.send({ type: 'PLAYER_READY' });
    }
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

    createLogin(gameApiClient);
    createRoomList(gameApiClient);
    createChat(gameApiClient);
    createRoomCreator(gameApiClient);
    createGameRoom(gameApiClient);
    createRoomPasswordModal(gameApiClient);

    window.addEventListener('PLAY_SOUND', (e) => {
        if (e.detail.src) {
            try {
                const audio = new Audio(e.detail.src);
                audio.volume = 0.5;
                audio.play().catch(e => console.warn("Audio blocked:", e));
            } catch (e) { console.error(e); }
        }
    });
}

function createLogin(gameApiClient) {
    Alpine.data('login', () => ({
        show: true,
        nickname: "",
        loginError: "",

        init() {
            window.addEventListener('NICK_OK', () => {
                this.show = false;
            });

            window.addEventListener('ERROR', (e) => {
                this.loginError = e.detail.message;
            });
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
            window.addEventListener('NICK_OK', () => {
                this.show = true;
            });
            window.addEventListener('JOIN_ROOM_OK', () => {
                this.show = false;
            });
            window.addEventListener('LEFT_ROOM', () => {
                this.show = true;
            });
            window.addEventListener('ROOM_LIST', (e) => {
                this.updateRoomList(e.detail);
            });
            window.addEventListener('LOBBY_PLAYERS', (e) => {
                this.updatePlayerList(e.detail);
            });
            window.addEventListener('ROOM_UPDATE', (e) => {
                this.updateRoom(e.detail);
            });
        },

        updateRoomList({ rooms, players }) {
            if (rooms) this.rooms = rooms.map(r => new RoomListItem(r.name, r.players, r.max, r.has_password));
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

            this.players = players.map(p => new PlayerListItem(p.nick, p.room));
        },

        createRoom() {
            gameApiClient.getDecks();
        },

        joinRoom(room) {
            if (room.hasPassword) {
                let modal = Alpine.store('passwordModal')
                console.log(modal);
                modal.show(room.name);
            } else {
                gameApiClient.joinRoom(room.name, null);
            }
        },

        joinRoomWithPassword() {
            gameApiClient.joinRoom(this.roomToJoin, this.password);
            this.roomToJoin = null;
        },

        hidePasswordModal() {
            this.roomToJoin = null;
            this.password = null;
        }
    }));
}

function createRoomPasswordModal(gameApiClient) {
    Alpine.store('passwordModal', {
        show: false,
        roomToJoin: null,
        password: null,

        joinRoom() {
            if (!this.roomToJoin) return;

            gameApiClient.joinRoom(this.roomToJoin, this.password);
            this.hide();
        },

        show(roomName) {
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
    Alpine.data('chat', () => ({
        messages: [],
        newMessage: "",

        init() {
            window.addEventListener('CHAT', (e) => {
                let message = new ChatMessage(e.detail.author, e.detail.message);
                this.messages.push(message);
                // todo scroll to bottom of chat
            });

            window.addEventListener('JOIN_ROOM_OK', () => {
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
            window.addEventListener('DECK_LIST', (e) => {
                this.show = true;
                this.decks = e.detail.decks.map(d => new DeckItem(d));
            });

            window.addEventListener('JOIN_ROOM_OK', () => {
                this.cancel();
            });
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
            window.addEventListener('JOIN_ROOM_OK', (e) => {
                this.onRoomJoined(e.detail.room);
            });
            window.addEventListener('LEFT_ROOM', () => {
                this.show = false;
                this.updateGameState({ phase: "LOBBY", hand: [], submissions: [], players_list: [] });
            });
            window.addEventListener('GAME_UPDATE', (e) => { 
                this.updateGameState(e.detail);
            });
        },

        onRoomJoined(room) {
            this.show = true;
            this.roomName = room;
        },

        leaveRoom() {
            gameApiClient.leaveRoom();
        },

        updateGameState(gameState) {
            this.phase = gameState.phase;
            this.isCzar = gameState.is_czar;
            this.isReady = gameState.am_i_ready;
            this.hand = [...gameState.hand].map(c => new HandCard(c.id, c.text));
            this.readyStatus = gameState.ready_status;
            this.blackCard = gameState.black_card;
            this.submissions = [...gameState.submissions].map(s => new PlayerEntry(s.id, s.full_text, s.author, s.is_winner));
            this.canStartGame = gameState.can_start_game;
            this.hasSubmittedCards = gameState.has_submitted;
            this.gameWinner = gameState.winner;

            if (this.phase === "SUMMARY") {
                this.awaitingSubmission = false;
                this.selected = [];
                this.winner = null;
            }
            
            this.showLobby = this.phase === "LOBBY";
            this.showWaitingRoom = this.hand.length === 0 && !this.isCzar;
            this.showPlayView = !this.showLobby && !this.showWaitingRoom;
            this.showSubmitButton = !this.awaitingSubmission && this.phase === "SELECTING" && this.hand.length > 0 && !this.isCzar;
            this.statusMessage = this.statusDictionary[this.phase](this);
            
            this.updatePlayerList(gameState.players_list);
        },

        updatePlayerList(players) {
            if (!players) return;
            this.players = players.map(p => new LobbyPlayer(p.nick, p.is_czar, p.score));
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
            if (this.isCzar) {
                this.winner = submission;
            }
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

class RoomListItem {
    constructor(name, players, maxPlayers, hasPassword) {
        this.name = name;
        this.players = players;
        this.maxPlayers = maxPlayers;
        this.hasPassword = hasPassword;
    }
}

class PlayerListItem {
    constructor(nick, room) {
        this.nick = nick;
        this.room = room;
    }
}

class LobbyPlayer {
    constructor(nick, isCzar, score) {
        this.nick = nick;
        this.isCzar = isCzar;
        this.score = score;
    }
}

class ChatMessage {
    constructor(author, message) {
        this.author = author;
        this.message = message;
    }
}

class DeckItem {
    constructor(name) {
        this.name = name;
        this.selected = true;
    }
}

class HandCard {
    constructor(id, text) {
        this.id = id;
        this.text = text;
    }
}

class PlayerEntry {
    constructor(id, text, author, winner) {
        this.id = id;
        this.text = text;
        this.author = author;
        this.winner = winner;
    }
}

document.addEventListener('alpine:init', () => {
    initialize();
});