import datetime
from os import path


class Game:
    def __init__(self, watcher, public_id):
        self.watcher = watcher
        self.public_id = public_id

        self.cancelled = False
        self.suspended = False
        self.data_available = False
        self.alive_timestamp = None

        self.teams = {'A': Team(self, 'A'), 'B': Team(self, 'B')}

        self.gametime_last_stop = 0
        self.gametime_last_start = None
        self.gametime_running = False

        self.game_over = False
        self.winner = None
        self.in_overtime = False
        self.overtime_setscore = None
        self.forfeit = None
        self.concede = None

        self.score_events = []
        self.timeout_events = []
        self.snitch_events = []
        self.snitch_under_review_events = []
        self.penalty_events = []

        self.scheduled_events = []

    def apply_change(self, modified, added, removed):
        modified = modified or {}
        for key, value in modified.items():
            match key:
                case 'cancelled_reason':
                    self.cancelled = value
                case 'suspended_reason':
                    self.suspended = value
                case 'data_available':
                    old_value = self.data_available
                    self.data_available = value
                    if old_value != value:
                        self.emit_event('data_available', value)
                case 'alive_timestamp':
                    self.alive_timestamp = value
                case 'teams':
                    if 'A' in value:
                        self.teams['A'].apply_team_change(value['A'])
                    if 'B' in value:
                        self.teams['B'].apply_team_change(value['B'])
                case 'gametime':
                    if 'last_stop' in value:
                        self.gametime_last_stop = value['last_stop']
                    if 'last_start' in value:
                        self.gametime_last_start = value['last_start']
                    if 'running' in value:
                        self.gametime_running = value['running']
                case 'game_over':
                    old_value = self.game_over
                    self.game_over = value
                    if old_value != value:
                        self.emit_event('game_over', value)
                case 'winner':
                    self.winner = value
                case 'in_overtime':
                    self.in_overtime = value
                case 'overtime_setscore':
                    self.overtime_setscore = value
                case 'forfeit':
                    self.forfeit = value
                case 'concede':
                    self.concede = value
                case 'score':
                    if 'A' in value:
                        self.teams['A'].apply_score_change(value['A'])
                    if 'B' in value:
                        self.teams['B'].apply_score_change(value['B'])
                case 'events':
                    self.apply_events_change(value)
        if added:
            self.apply_events_change(added['events'])
        if removed:
            self.apply_events_removed(removed['events'])
        self.log_current_state()
        self.emit_events()

    def apply_events_change(self, data):
        for event_type, value1 in data.items():
            if isinstance(value1, list):
                for index, value2 in enumerate(value1):
                    self._apply_event_change(event_type, index, value2)
            else:
                for index, value2 in value1.items():
                    self._apply_event_change(event_type, int(index), value2)

    def _apply_event_change(self, event_type, index, value):
        if index >= len(self.__getattribute__(f"{event_type}_events")):
            new_event = event_type_class(event_type)(value, self)
            self.__getattribute__(f"{event_type}_events").append(new_event)
            self.log_event(('add', new_event.event_type, str(index), *new_event.current_state()))
        else:
            event = self.__getattribute__(f"{event_type}_events")[index]
            event.apply_change(value)
            self.log_event(('mod', event.event_type, str(index), *event.current_state()))

    def apply_events_removed(self, data):
        for event_type, value1 in data.items():
            if isinstance(value1, list):
                for index, event in enumerate(self.__getattribute__(f"{event_type}_events")):
                    self.log_event(('del', event.event_type, index, *event.current_state()))
                self.__setattr__(f"{event_type}_events", [])
            else:
                for index in value1.keys():
                    event = self.__getattribute__(f"{event_type}_events").pop(int(index))
                    self.log_event(('del', event.event_type, index, *event.current_state()))

    def log_current_state(self):
        current_state = [
            datetime.datetime.now().isoformat(),
            self.public_id,
            self.data_available,
            self.alive_timestamp,
            self.cancelled,
            self.suspended,
            self.gametime_last_stop,
            self.gametime_last_start,
            self.gametime_running,
            self.in_overtime,
            self.overtime_setscore,
            self.game_over,
            self.winner,
            self.forfeit,
            self.concede,
            self.teams['A'].name,
            self.teams['A'].id,
            self.teams['A'].quaffel_points_regular,
            self.teams['A'].quaffel_points_overtime,
            self.teams['A'].quaffel_points_concede,
            self.teams['A'].snitch_caught,
            self.teams['A'].snitch_points,
            self.teams['A'].points_total,
            self.teams['B'].name,
            self.teams['B'].id,
            self.teams['B'].quaffel_points_regular,
            self.teams['B'].quaffel_points_overtime,
            self.teams['B'].quaffel_points_concede,
            self.teams['B'].snitch_caught,
            self.teams['B'].snitch_points,
            self.teams['B'].points_total,
        ]
        line = ','.join(str(x).replace(',', '') for x in current_state) + '\n'
        file_name = f'game_logs/{self.public_id}.csv'
        if path.exists(file_name):
            with open(file_name, 'a') as f:
                f.write(line)
        else:
            with open(file_name, 'w') as f:
                f.write("Time,PublicId,DataAvailable,AliveTimestamp,Cancelled,Suspended,GT Last Stop,GT Last Start,"
                        "GT Running,in overtime,OT Set Score,GameOver,Winner,Forfeit,Concede,"
                        "NameA,IdA,QP Regular A,QP OT A,QP Concede A,SnitchCaughtA,SnitchPointsA,PointsTotalA,"
                        "NameB,IdB,QP Regular B,QP OT B,QP Concede B,SnitchCaughtB,SnitchPointsB,PointsTotalB\n")
                f.write(line)

    def log_event(self, data):
        line = ','.join((datetime.datetime.now().isoformat(), *map(str, data))) + '\n'
        file_name = f'game_logs/{self.public_id}_events.csv'
        if path.exists(file_name):
            with open(file_name, 'a') as f:
                f.write(line)
        else:
            with open(file_name, 'w') as f:
                f.write("Time,What,Type,Index,Period,Gametime,Team,P-Number,P-Name,Increment,Color,Reason\n")
                f.write(line)

    def emit_event(self, *args):
        self.scheduled_events.append(args)

    def emit_events(self):
        for event in self.scheduled_events:
            self.watcher.emit(self, event)

        self.scheduled_events = []


class Team:
    def __init__(self, game: Game, letter: str):
        self.game = game
        self.letter = letter
        self.name = ''
        self.shortname = ''
        self.logo = 'default.svg'
        self.id = None
        self.jersey = 'jersey_ffffff'
        self.jersey_primary_color = '#FFFFFF'
        self.jersey_secondary_color = '#FFFFFF'
        self.jersey_text_color = '#000000'

        self.quaffel_points_regular = 0
        self.quaffel_points_overtime = 0
        self.quaffel_points_concede = 0
        self.snitch_caught = False
        self.snitch_points = 0
        self.points_total = 0
        self.score_str = '0'

    def apply_team_change(self, data):
        for key, value in data.items():
            match key:
                case 'name':
                    self.name = value
                case 'shortname':
                    self.shortname = value or ''
                case 'logo':
                    self.logo = value
                case 'id':
                    self.id = value
                case 'jersey':
                    self.jersey = value
                case 'jersey_primary_color':
                    self.jersey_primary_color = value
                case 'jersey_secondary_color':
                    self.jersey_secondary_color = value
                case 'jersey_text_color':
                    self.jersey_text_color = value

    def apply_score_change(self, data):
        for key, value in data.items():
            match key:
                case 'quaffel_points':
                    if 'regular' in value:
                        self.quaffel_points_regular = value['regular']
                    if 'overtime' in value:
                        self.quaffel_points_overtime = value['overtime']
                    if 'concede' in value:
                        self.quaffel_points_concede = value['concede']
                case 'snitch_caught':
                    self.snitch_caught = value
                    self.emit_event('snitch_caught', value)
                case 'snitch_points':
                    self.snitch_points = value
                case 'total':
                    self.emit_event('score_changed', value)
                    self.points_total = value
            self.calculate_score_str()
        self.emit_event('score', self.score_str)

    def calculate_score_str(self):
        self.score_str = str(self.points_total)
        if self.snitch_points:
            self.score_str += '*'

    def emit_event(self, event_type, *args):
        self.game.emit_event(event_type, self.letter, *args)


class Event:
    def __init__(self, data, game):
        self.game = game

        self.period = data.get('period', None)
        self.gametime = data.get('gametime', None)

        self.team = data.get('team', None)
        self.player_number = data.get('player_number', None)
        self.player_name = data.get('player_name', None)

        self.color = data.get('color', None)
        self.increment = data.get('increment', None)
        self.reason = data.get('reason', None)

    def apply_change(self, data):
        for key, value in data.items():
            match key:
                case 'period':
                    self.period = value
                case 'team':
                    self.team = value
                case 'gametime':
                    self.gametime = value
                case 'player_number':
                    self.player_number = value
                case 'player_name':
                    self.player_name = value
                case 'increment':
                    self.increment = value
                case 'color':
                    self.color = value
                case 'reason':
                    self.reason = value

    def current_state(self):
        return (str(x).replace(',', '') for x in (
            self.period,
            self.gametime,
            self.team,
            self.player_number,
            self.player_name,
            self.increment,
            self.color,
            self.reason
        ))


class ScoreEvent(Event):
    event_type = 'score'


class TimeoutEvent(Event):
    event_type = 'timeout'


class SnitchEvent(ScoreEvent):
    event_type = 'snitch'


class SnitchUnderReviewEvent(ScoreEvent):
    event_type = 'snitch_uner_review'


class PenaltyEvent(Event):
    event_type = 'penalty'


def event_type_class(event_type):
    return {
        'score': ScoreEvent,
        'timeout': TimeoutEvent,
        'snitch': SnitchEvent,
        'snitch_under_review': SnitchUnderReviewEvent,
        'penalty': PenaltyEvent,
    }[event_type]
