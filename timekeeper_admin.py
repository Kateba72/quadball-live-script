import random
from datetime import datetime, date, time
from zoneinfo import ZoneInfo
import requests
import threading
import google_credentials
import secrets

from googleapiclient.discovery import build

PRIVATE_SCHEDULE_DATA_RANGE = 'Tabellenblatt1!A2:M116'
WRITE_DATA_RANGE = 'Tabellenblatt1!G2:M116'
ADMIN_URL = 'https://quadball.live/administration/syncModelTournamentAdmin.php'
RESET_URL = f'https://quadball.live/tournamentadmin.php?code={secrets.QUADBALL_LIVE_AUTH}&section=modifygame&id='


def new_random_secret_id():
    options = '123456789abcdefghijkmnopqrstuvwxyzABCDEFGHJKLMNPQRSTUVWXYZ'
    return ''.join(random.choices(options, k=6))


class GamesList:
    def __init__(self):
        self.games = []
        self.all_games = []
        self.games_by_public_id = {}
        self.games_by_name = {}
        self.import_all()
        self.update_timer = None

    def update_all(self):
        self.write_to_google()
        update_timer = random.random()
        self.update_timer = update_timer
        threading.Timer(30, GamesList.update_all_timer, [self, update_timer]).start()

    def update_all_timer(self, timer):
        if self.update_timer != timer:
            return
        self.import_all()
        self.write_to_live_admin()

    def import_all(self):
        service = build('sheets', 'v4', credentials=google_credentials.get_google_credentials())
        sheet = service.spreadsheets()
        result = sheet.values().get(spreadsheetId=secrets.PRIVATE_SCHEDULE, range=PRIVATE_SCHEDULE_DATA_RANGE).execute()
        values = result.get('values', [])

        if not values:
            print('No data found.')
            raise

        self.all_games = [
            (len(row) > 3 and row[3] != 'no match')
            and Game(row, index)
            or NoGame(row, index)
            for index, row in enumerate(values)
        ]
        self.games = [game for game in self.all_games if not isinstance(game, NoGame)]
        self.games_by_public_id = {game.public_id: game for game in self.games}
        self.games_by_name = {game.game_info['basic']: game for game in self.games if game.game_info['specification']}

    def write_to_live_admin(self):
        body = {
            "code": secrets.QUADBALL_LIVE_AUTH,
            "data": {
                game.secret_id: game.to_live_admin() for game in self.games
            }
        }
        response = requests.post(ADMIN_URL, json=body)
        return response

    def write_to_google(self):
        service = build('sheets', 'v4', credentials=google_credentials.get_google_credentials())
        sheet = service.spreadsheets()
        body = {
            'range': WRITE_DATA_RANGE,
            'majorDimension': 'ROWS',
            'values': [
                [
                    game.team_a_points_int, game.team_a_snitch, game.team_b_points_int,
                    game.team_b_snitch, game.public_id, game.secret_id, game.betting_form,
                ] for game in self.all_games
            ]
        }
        sheet.values().update(
            spreadsheetId=secrets.PRIVATE_SCHEDULE, range=WRITE_DATA_RANGE, valueInputOption='RAW', body=body).execute()

    def create_betting_form(self, form_title, deadlines=False):
        games_needing_form = [game for game in self.games if game.needs_betting_form()]
        service = build('forms', 'v1', credentials=google_credentials.get_google_credentials('betting_form'))
        new_form = {
            'info': {
                'title': f'Tippspiel DQP 2023 – {form_title}',
                'document_title': form_title,
            }
        }
        create_result = service.forms().create(body=new_form).execute()
        form_id = create_result['formId']
        service.forms().batchUpdate(formId=form_id, body = {
            'requests': [
                {
                    'createItem': {
                        'item': {
                            'title': 'Name',
                            'description': 'Damit wir deine Antworten auch über mehrere Formulare zuordnen können.',
                            'questionItem': {
                                'question': {
                                    'required': True,
                                    'textQuestion': {
                                        'paragraph': False,
                                    },
                                },
                            },
                        },
                        'location': { 'index': 0 },
                    },
                },
                {
                    'createItem': {
                        'item': {
                            'title': 'Team',
                            'questionItem': {
                                'question': {
                                    'required': True,
                                    'textQuestion': {
                                        'paragraph': False,
                                    },
                                },
                            },
                        },
                        'location': { 'index': 1 },
                    },
                },
            ] + [
                {
                    'createItem': {
                        'item': {
                            'title': game.german_description,
                            'description': deadlines and f"Deadline: {game.time:%H:%M}" or '',
                            'questionItem': {
                                'question': {
                                    'required': True,
                                    'choiceQuestion': {
                                        'type': 'RADIO',
                                        'options': [
                                            { 'value': game.team_a["name"] },
                                            { 'value': game.team_b["name"] },
                                        ]
                                    },
                                },
                            },
                        },
                        'location': { 'index': index + 2 },
                    },
                } for index, game in enumerate(games_needing_form)
            ]
        }).execute()

        drive_service = build('drive', 'v3', credentials=google_credentials.get_google_credentials('betting_form'))
        file = drive_service.files().get(fileId=form_id, fields='parents').execute()
        file = drive_service.files().update(fileId=form_id, addParents=secrets.BETTING_FORM_FOLDER, removeParents=",".join(file.get('parents')),fields="id, parents").execute()

        text_response_games = "\n".join(f"{game.team_a['name']} – {game.team_b['name']}{deadlines and f' (Deadline: {game.time:%H:%M})' or ''}" for game in games_needing_form)
        text_response = f"""Es gibt ein neues Formular für die folgenden Spiele:
{text_response_games}

Jetzt tippen unter {create_result['responderUri']}"""
        for game in games_needing_form:
            game.betting_form = create_result['responderUri']
        return text_response

def generate_team_info(description):
    if '(TBD)' in description:
        description = description[:-6]
        team = { "name": description, "shortname": description, "logo": "default.svg", "jersey": "jersey_ffffff" }
    else:
        team = secrets.TEAMS[description]
    return team


class Game:
    def __init__(self, row, index):
        row += [None] * 12
        self.changes_made = False
        self.index = index
        self.slot = row[2]
        if int(self.slot) <= 10:
            self.date = date(2023, 7, 29)
        else:
            self.date = date(2023, 7, 30)
        if row[0]:
            hours, minutes = row[0].split(':')
            self.time = time(int(hours.lstrip('0')), int(minutes), tzinfo=ZoneInfo('Europe/Berlin'))
        else:
            raise 'No time given'
        self.datetime = datetime.combine(self.date, self.time)
        self.pitch = f"Pitch {row[1]}"
        self._game_info = {'basic': None}
        self.game_info = row[3]
        self.team_a = generate_team_info(row[4])
        self.team_b = generate_team_info(row[5])
        self.team_a_points = row[6]
        self.team_a_snitch = row[7]
        self.team_b_points = row[8]
        self.team_b_snitch = row[9]
        self.public_id = row[10]
        self.secret_id = row[11]
        self.betting_form = row[12]
        if not self.secret_id:
            self.secret_id = new_random_secret_id()

    @property
    def team_a_points_int(self):
        if self.team_a_points or self.team_a_points == 0:
            return int(self.team_a_points)
        return None

    @property
    def team_b_points_int(self):
        if self.team_b_points or self.team_b_points == 0:
            return int(self.team_b_points)
        return None

    def reset_timekeeper(self):
        response = requests.post(RESET_URL + self.secret_id, data={'form': 'reset_prepared_game', 'id': self.secret_id})

    @property
    def game_info(self):
        return self._game_info

    @game_info.setter
    def game_info(self, new_value):
        if self._game_info['basic'] == new_value:
            return

        self._game_info['basic'] = new_value

        if 'Group ' in new_value:
            self._game_info['group'] = new_value
            self.german_description = new_value.replace('Group', 'Gruppe')
            self._game_info['specification'] = ''
        elif 'Play-off' in new_value:
            _play_off, place = new_value.split()
            place = int(place)
            if place < 17:
                self._game_info['group'] = 'Upper Bracket'
            else:
                self._game_info['group'] = 'Lower Bracket'
            if place == 3:
                self._game_info['specification'] = 'Bronze Medal Match'
            else:
                if place in [23]:
                    ordinal = '23rd'
                elif place in [21]:
                    ordinal = '21st'
                else:
                    ordinal = f"{place}th"
                self.game_info['specification'] = f"{ordinal} Place Play-Off"
            self.german_description = f"Spiel um Platz #{place}"
        elif 'Final' in new_value:
            if new_value == 'Final':
                self._game_info['group'] = 'Upper Bracket'
                self._game_info['specification'] = 'Final'
                self.german_description = "Finale"
            elif new_value == 'LB Final':
                self._game_info['group'] = 'Lower Bracket'
                self._game_info['specification'] = 'Lower Bracket Final'
                self.german_description = "Lower Bracket Finale"
            else:
                raise f"Unknown value {new_value}"
        else:
            group, stage, game = new_value.split()
            participating = {
                'SF': 4,
                'R2': 8,
                'R1': 16
            }[stage]
            if group == 'UB':
                self._game_info['group'] = 'Upper Bracket'
                self.german_description = 'Upper Bracket '
            elif group == 'LB':
                self._game_info['group'] = 'Lower Bracket'
                self.german_description = 'Lower Bracket '
            else:
                # consolidation match
                consolidation_first = int(group[1:])
                consolidation_last = consolidation_first + participating - 1
                if consolidation_first < 17:
                    bracket = 'Upper'
                else:
                    bracket = 'Lower'
                self._game_info['group'] = f"{bracket} Bracket – Consolidation " \
                                           f"{consolidation_first}–{consolidation_last}"
                self.german_description = f"Platzierungsspiele {consolidation_first}-{consolidation_last} – "
            stage_description = {
                'SF': 'Semi-Final',
                'R2': 'Round of 8 Game',
                'R1': f"Round of {stage == 'LB' and 14 or 16} Game"
            }[stage]
            self._game_info['specification'] = f"{stage_description} {game}"
            self.german_description += { 'SF': 'Halbfinale ', 'R2': 'Viertelfinale ', 'R1': 'Achtelfinale ' }[stage]
            self.german_description += str(game)

    def to_live_admin(self):
        return {
            "teams": {
                "A": self.team_a,
                "B": self.team_b
            },
            "timestamp": int(self.datetime.timestamp()),
            "group": self.game_info['group'],
            "pitch": self.pitch,
            "specification": self.game_info['specification'],
            "cancelled": False,
            "cancelled_reason": None,
            "suspended": False,
            "suspended_reason": None
        }

    def needs_betting_form(self):
        return (not self.betting_form) and (self.team_a.get('id')) and (self.team_b.get('id'))

class NoGame:
    def __init__(self, row, index):
        self.index = index
        self.row = row
        self.team_a_points = None
        self.team_a_snitch = None
        self.team_b_points = None
        self.team_b_snitch = None
        self.public_id = None
        self.secret_id = None
        self.team_a_points_int = None
        self.team_b_points_int = None
        self.betting_form = None
