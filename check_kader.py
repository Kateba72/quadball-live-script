import google_credentials
from googleapiclient.discovery import build

SCOPES = ['https://www.googleapis.com/auth/spreadsheets']


def check_squad(squad, team):
    squad_data = import_squad(squad)
    team_name, team_data = import_team(team)
    print_color(team_name, '1;42')
    for identification, extra_data in squad_data.items():
        if identification in team_data:
            teamlist_extra_data = team_data[identification]
            if teamlist_extra_data[1]:
                print_color(f'{identification[0]}, {identification[1]} hat Zweitteam: {teamlist_extra_data[1]}', 33)
            if teamlist_extra_data[2]:
                print_color(f'{identification[0]}, {identification[1]} wird bald gelöscht', 31)
            if teamlist_extra_data[3]:
                print_color(f'{identification[0]}, {identification[1]} hat Bemerkung: {teamlist_extra_data[3]}', 36)
            if teamlist_extra_data[0] != extra_data[0]:
                print_color(f'{identification[0]}, {identification[1]} hat unterschiedliches Geburtsdatum: '
                            f'{teamlist_extra_data[0]} (TL) vs {extra_data[0]} (Kader)', 31)
        else:
            print_color(f'{identification[0]}, {identification[1]} wurde nicht gefunden.', 31)
            if extra_data[1]:
                print_color(f'  Rufname: {extra_data[1]}', 31)
            if extra_data[2]:
                print(f'  Bemerkung: {extra_data[2]}')
    print_color('Sonst alles in Ordnung!', 32)
    print()


def main():
    while True:
        squad = good_input('Kaderliste: ')
        team = good_input('Teamliste: ')
        check_squad(squad, team)


def good_input(query):
    text = None
    while not text:
        text = input(query).strip()
    return text


def import_team(table):
    service = build('sheets', 'v4', credentials=google_credentials.get_google_credentials())
    sheet = service.spreadsheets()
    table_id = table.replace('https://docs.google.com/spreadsheets/d/', '').replace('/edit#gid=0', '').replace('/edit?usp=drive_link', '')
    result = sheet.values().get(spreadsheetId=table_id, range='Tabellenblatt1!B6:F70').execute()
    values = result.get('values', [])
    people = {}
    for row in values:
        if len(row) == 0:
            break
        row += (6 - len(row)) * ['']
        people[(row[0].strip(), row[1].strip())] = (row[2], row[3], row[4])
    return people


def import_squad(table):
    service = build('sheets', 'v4', credentials=google_credentials.get_google_credentials())
    sheet = service.spreadsheets()
    table_id = table.replace('https://docs.google.com/spreadsheets/d/', '').replace('/edit#gid=0', '')
    result = sheet.values().get(spreadsheetId=table_id, range='Tabellenblatt1!B2:G32').execute()
    values = result.get('values', [])
    team_name = values[0][1]
    values = values[3:]
    names = [(replace_umlauts(row[0].strip()), replace_umlauts(row[1].strip())) for row in values[:21] if len(row) > 1]
    if names != sorted(names):
        print_color('List not sorted', 31)
    values = values[:21] + values[24:]
    people = {}
    for row in values:
        if len(row) == 0:
            continue
        row += (7 - len(row)) * ['']
        people[(row[0].strip(), row[1].strip())] = (row[3], row[2])
    return team_name, people


def replace_umlauts(text):
    return text.replace('ä', 'a').replace('ö', 'o').replace('ü', 'u').replace('Ä', 'A').replace('Ö', 'O')\
        .replace('Ü', 'U')


def print_color(text, color):
    print(f"\033[{color}m{text}\033[0m")


if __name__ == '__main__':
    main()
