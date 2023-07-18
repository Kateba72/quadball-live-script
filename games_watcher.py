import socketio
import requests
import game
import datetime
import secrets

REMOTE_SERVER = 'https://quadball.live/'
LOG_SIO = 'log.txt'


class GamesWatcher:
    def __init__(self):
        sio = self.sio = socketio.Client(logger=True)
        self._public_ids = []
        self.game_data = {}
        self.event_listeners = {}
        self._next_event_listener_id = 1
        self.tournament_id = None

        @sio.event
        def connect():
            log('Connected, authenticating...')
            payload = {'auth': secrets.QUADBALL_LIVE_AUTH, 'games': self.public_ids}
            if self.tournament_id:
                payload['all_games_at_once'] = True
            sio.emit('auth', payload)

        @sio.event
        def connect_error(data):
            log("The connection failed!", data)

        @sio.event
        def disconnect():
            log("The application disconnected.")

        @sio.event
        def status(data):
            if data['status'] == 'success':
                log('Connected and receiving data!')
            else:
                log('Status: ', data)

        @sio.event
        def complete(data):
            if LOG_SIO:
                log(data)
            self.game_data[data['public_id']].apply_change(data, None, None)

        @sio.on('all games at once')
        def all_games_at_once(data):
            if LOG_SIO:
                log(data)
            for game_data in data['data']:
                self.game_data[game_data['public_id']].apply_change(game_data, None, None)

        @sio.event
        def delta(data):
            if LOG_SIO:
                log(data)
            self.game_data[data['public_id']].apply_change(data['modified'], data['added'], data['removed'])

        @sio.event
        def alive(data):
            if LOG_SIO:
                log(data)
            self.game_data[data['public_id']].apply_change(data, None, None)

    @property
    def public_ids(self):
        return self._public_ids

    @public_ids.setter
    def public_ids(self, new_public_ids):
        self._public_ids = new_public_ids
        self.game_data = {public_id: game.Game(self, public_id) for public_id in new_public_ids}

    def listen(self, event, callback, *args):
        if event not in self.event_listeners:
            self.event_listeners[event] = {}
        self.event_listeners[event][self._next_event_listener_id] = (callback, args)

    def emit(self, event_game, event):
        callbacks = self.event_listeners.get(event[0], {})
        for callback in callbacks.values():
            func, args = callback
            func(event, event_game, *args)

    def connect_public_id(self, public_id):
        self.public_ids = [public_id]
        self.sio.connect(REMOTE_SERVER)

    def connect_tournament_id(self, tournament_id):
        r = requests.get(
            f"{REMOTE_SERVER}administration/getAllTournamentPublicGameIdsAndTimes.php",
            json={'tournament': str(tournament_id)}
        )
        self.public_ids = r.json()['public_game_ids']
        self.tournament_id = tournament_id
        self.sio.connect(REMOTE_SERVER)


def log(*data):
    print(*data)
    text = ' '.join(map(str, data))
    if LOG_SIO:
        with open(LOG_SIO, 'a') as logfile:
            logfile.write(f"{datetime.datetime.now()}: {text}\n")
