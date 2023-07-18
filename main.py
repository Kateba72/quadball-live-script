import games_watcher
import timekeeper_admin
import ui
import secrets


def start():
    games_list = timekeeper_admin.GamesList()
    watcher = games_watcher.GamesWatcher()
    watcher.connect_tournament_id(secrets.QUADBALL_LIVE_TOURNAMENT_ID)
    ui.TimekeeperApp(watcher=watcher, games_list=games_list).run()


if __name__ == '__main__':
    start()
