from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.properties import ColorProperty, StringProperty, ObjectProperty
from kivy.clock import Clock


class MainFrame(BoxLayout):
    completed_games = ObjectProperty(None)
    running_games = ObjectProperty(None)
    requesting_reset = ObjectProperty(None, allownone=True)
    betting_modal = ObjectProperty(None)
    betting_text_input = ObjectProperty(None)

    def __init__(self, **kwargs):
        self.watcher = kwargs.pop('watcher')
        self.games_list = kwargs.pop('games_list')
        self.games = {}
        super().__init__(**kwargs)
        for public_id, game_data in self.watcher.game_data.items():
            self.insert_new_game(public_id, game_data)

        self.watcher.listen('score', lambda *args: Clock.schedule_once(lambda dt: self.score_changed(*args)))
        self.watcher.listen('data_available', lambda *args: Clock.schedule_once(lambda dt: self.game_status_changed(*args)))
        self.watcher.listen('game_over', lambda *args: Clock.schedule_once(lambda dt: self.game_status_changed(*args)))

    def score_changed(self, event, game):
        ui_game = self.games.get(game.public_id, None)
        if ui_game:
            if event[1] == 'A':
                ui_game.team_a_score = event[2]
            if event[1] == 'B':
                ui_game.team_b_score = event[2]

    def game_status_changed(self, _event, game):
        public_id = game.public_id
        current_widget = self.games.pop(public_id, None)
        if current_widget:
            current_widget.parent.remove_widget(current_widget)
        self.insert_new_game(game.public_id, game)

    def insert_new_game(self, public_id, game_data):
        if game_data.game_over:
            if not self.games_list.games_by_public_id[public_id].team_a_points:
                game = CompletedGame(public_id=public_id, mainframe=self)
                self.assign_game_variables(game, public_id, game_data)
                self.completed_games.add_widget(game)
        elif game_data.data_available:
            game = RunningGame(public_id=public_id, mainframe=self)
            self.assign_game_variables(game, public_id, game_data)
            self.running_games.add_widget(game)

    def assign_game_variables(self, game, public_id, game_data):
        game.team_a_name = game_data.teams['A'].name
        game.team_a_score = game_data.teams['A'].score_str
        game.team_b_name = game_data.teams['B'].name
        game.team_b_score = game_data.teams['B'].score_str
        self.games[public_id] = game

    def confirm(self, ui_game):
        admin_game = self.games_list.games_by_public_id[ui_game.public_id]
        watcher_game = self.watcher.game_data[ui_game.public_id]
        admin_game.team_a_points = watcher_game.teams['A'].points_total
        admin_game.team_a_snitch = ['', '*'][watcher_game.teams['A'].snitch_caught]
        admin_game.team_b_points = watcher_game.teams['B'].points_total
        admin_game.team_b_snitch = ['', '*'][watcher_game.teams['B'].snitch_caught]
        self.games_list.update_all()
        ui_game.parent.remove_widget(ui_game)
        del self.games[ui_game.public_id]

    def request_reset(self, game):
        self.requesting_reset = game

    def accept_reset(self):
        game = self.games_list.games_by_public_id[self.requesting_reset.public_id]
        game.reset_timekeeper()
        self.requesting_reset = None

    def deny_reset(self):
        self.requesting_reset.reset_denied()
        self.requesting_reset = None

    def import_schedule(self):
        self.games_list.import_all()
        print('Schedule imported')

    def export_schedule(self):
        self.games_list.write_to_live_admin()
        print('Schedule exported')

    def export_results(self):
        self.games_list.write_to_google()
        print('Results exported')

    def create_betting_form(self):
        form_name = self.betting_text_input.text
        self.betting_modal.opacity = 0
        self.betting_text_input.text = ""
        print(self.games_list.create_betting_form(form_name, deadlines=True))
        self.games_list.write_to_google()

    def show_betting_form(self):
        self.betting_modal.opacity = 1

    def abort_betting_form(self):
        self.betting_modal.opacity = 0
        self.betting_text_input.text = ""


class UIGame(BoxLayout):
    button_color = ColorProperty()
    button_text = StringProperty()
    button = ObjectProperty(None)
    score_color = ColorProperty()
    team_a_name = StringProperty()
    team_b_name = StringProperty()
    team_a_score = StringProperty()
    team_b_score = StringProperty()


class CompletedGame(UIGame):
    def __init__(self, **kwargs):
        self.public_id = kwargs.pop('public_id')
        self.mainframe = kwargs.pop('mainframe')
        super().__init__(**kwargs)
        self.button_color = [0.15, 1, 0.15, 1]
        self.button_text = "Confirm"
        self.score_color = [1, 1, 1, 1]

    def button_pressed(self):
        self.mainframe.confirm(self)


class RunningGame(UIGame):
    def __init__(self, **kwargs):
        self.public_id = kwargs.pop('public_id')
        self.mainframe = kwargs.pop('mainframe')
        super().__init__(**kwargs)
        self.button_color = [1, 0.15, 0.15, 1]
        self.button_text = "Reset"
        self.score_color = [0.15, 1, 0.15, 1]

    def button_pressed(self):
        self.mainframe.request_reset(self)
        self.button.disabled = True

    def reset_denied(self):
        self.button.disabled = False


class TimekeeperApp(App):
    def __init__(self, **kwargs):
        self.games_list = kwargs.pop('games_list')
        self.watcher = kwargs.pop('watcher')
        super().__init__(**kwargs)

    def build(self):
        return MainFrame(games_list=self.games_list, watcher=self.watcher)
