from typing import Any
import os
import requests
import urllib3
import time
import csv

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

token = os.environ.get('TOKEN')

API_SERVER = 'https://www.robotevents.com/api/v2'

headers = {
    'Authorization': f'Bearer {token}',
    'Accept': 'application/json'
}

def get_api_paginated(url: str, params: dict):
    """
    Fetches paginated data from a given API URL with the option to handle rate
    limiting and server errors using retry logic. The function collects and
    aggregates all paginated responses into a single list and stops when there
    are no further records to fetch.

    :param url: The base URL of the API endpoint to fetch data from.
    :type url: str
    :param params: Dictionary of query parameters to be included in the request.
    :type params: dict
    :return: A list containing aggregated data from all paginated API responses.
    :rtype: list
    """
    all_data = []
    page = 1
    retry_attempts = 0
    max_retries = 7

    while True:
        try:
            params['page'] = page
            response = requests.get(url, headers=headers, params=params, verify=False)

            if response.status_code == 429 or response.status_code >= 500:
                if retry_attempts < max_retries:
                    retry_after = int(
                        response.headers.get('Retry-After', 1))
                    backoff_time = retry_after * (3 ** retry_attempts)
                    print(f"Rate limit or server error. Attempt {retry_attempts}. "
                          f"Retrying after {backoff_time} seconds...")
                    time.sleep(backoff_time)
                    retry_attempts += 1
                    continue
                else:
                    print("Max retries exceeded. Unable to fetch data.")
                    break


            response.raise_for_status()
            data = response.json()
            teams = data.get('data', [])
            all_data.extend(teams)

            meta = data.get('meta', {})
            if not meta.get('next_page_url'):
                break

            page += 1
        except requests.exceptions.RequestException as e:
            print(f"Error fetching data: {e}")
            break
    return all_data


def get_event_by_sku(sku: str):
    """
    Fetches the first event data for a given SKU (stock keeping unit) from the
    API server. This function utilizes an HTTP GET request to retrieve the
    event details and processes the response.

    :param sku: The unique stock keeping unit identifier for which the
                event data is to be fetched.
    :type sku: str
    :return: A dictionary containing the first event data fetched from
             the API server if the request is successful. Returns None
             in case of any request failure or error.
    :rtype: dict or None
    :raises requests.exceptions.RequestException: Raised for any issues
             occurring during the HTTP GET request process.
    """
    params = {'sku': sku}
    url = f"{API_SERVER}/events"
    try:
        response = requests.get(url, headers=headers, params=params,
                                verify=False)  # `verify=False` ignores SSL warnings
        response.raise_for_status()  # Raise an error for HTTP codes >= 400
        return response.json()['data'][0]
    except requests.exceptions.RequestException as e:
        print(f"Error: {e}")
        return None


def get_event_id_by_sku(sku: str):
    """
    Retrieves the event ID associated with a given SKU (Stock Keeping Unit). The
    provided SKU is used to fetch the corresponding event details from a data
    source. If a matching event is found, its associated ID is returned.
    Otherwise, the function will return None.

    :param sku: Stock Keeping Unit identifier used to query the event.
    :type sku: str
    :return: Event ID if found, otherwise None.
    :rtype: Optional[str]
    """
    response = get_event_by_sku(sku)
    return response['id'] if response else None


def get_season_id_by_event_sku(sku: str):
    """
    Retrieve the season ID associated with a given event SKU.

    This function fetches the event data corresponding to the provided SKU
    and extracts the season ID from the response. If no event data is found
    for the SKU, the function returns `None`.

    :param sku: Unique identifier for the event.
    :type sku: str
    :return: Season ID associated with the event if found, otherwise None.
    :rtype: Optional[int]
    """
    response = get_event_by_sku(sku)
    return response['season']['id'] if response else None


def get_team_list_for_event(event_id: str):
    """
    Retrieves the list of teams for a given event using its unique identifier.

    The method fetches all the teams participating in the specified event by
    making paginated API calls to the server. The function returns the
    complete list of teams for the event.

    :param event_id: The unique identifier for the event.
    :type event_id: str
    :return: A list containing all the teams for the specified event.
    :rtype: list
    """
    url = f"{API_SERVER}/events/{event_id}/teams"
    all_teams = get_api_paginated(url, {})
    return all_teams


def get_team(team_name: str = None):
    """
    Fetches details of a team based on the provided team name from the external API.

    Raises a ValueError if no team name is provided.
    Performs an HTTP GET request to the specified API server, sending the
    team name as a query parameter. Handles exceptions during the HTTP
    request and logs the error if a failure occurs.

    :param team_name: The name of the team for which details are requested.
    :type team_name: str, optional
    :return: JSON response containing team details if the request is successful,
             None if the request encounters an error.
    :rtype: dict or None
    :raises ValueError: If no team name is provided.
    """
    if not team_name:
        raise ValueError("Please provide a team name.")
    params = {'number': team_name}
    url = f"{API_SERVER}/teams"
    try:
        response = requests.get(url, headers=headers, params=params,
                                verify=False)  # `verify=False` ignores SSL warnings
        response.raise_for_status()  # Raise an error for HTTP codes >= 400
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"Error: {e}")
        return None


def get_team_id(team_name: str) -> Any | None:
    """
    Retrieves the unique identifier (ID) of a team based on its name.

    This function looks up the team information by its name using the `get_team`
    function. If the team is found, it extracts and returns the ID value from
    the resulting data.

    :param team_name: The name of the team to search for.
    :type team_name: str
    :return: The unique ID of the team retrieved from the data.
    :rtype: int
    :raises KeyError: If the 'id' key is not present in the data structure.
    :raises IndexError: If the team data list is empty or not properly formatted.
    """
    teams_data = get_team(team_name)
    if teams_data:
        return teams_data['data'][0]['id']


def get_team_rankings(vrc_team_id: int, season_id: int) -> tuple[int | Any, int | Any, int | Any]:
    """
    Fetches the win, loss, and tie rankings of a specific team for a given season based on data
    retrieved from the API. The function queries a paginated API endpoint and computes the totals
    for each result type across all retrieved games.

    :param vrc_team_id: Unique identifier of the team whose rankings are to be fetched.
    :type vrc_team_id: int
    :param season_id: Unique identifier of the season for which the rankings are calculated.
    :type season_id: int
    :return: A tuple where the first element is the total number of wins, the second element
        is the total number of losses, and the third element is the total number of ties
        retrieved from the API data.
    :rtype: tuple[int | Any, int | Any, int | Any]
    """
    url = f"{API_SERVER}/teams/{vrc_team_id}/rankings"
    params = {'season': season_id}
    wins_num = 0
    losses_num = 0
    ties_num = 0

    games = get_api_paginated(url, params)
    for game in games:
        wins_num = wins_num + game['wins']
        losses_num = losses_num + game['losses']
        ties_num = ties_num + game['ties']
    return wins_num, losses_num, ties_num


def get_team_skills_ranking(vrc_team_id: int, season_id: int) -> tuple[int | Any, int | Any, int | Any]:
    """
    Retrieves the skills ranking for a specific team in a given season by fetching
    and aggregating the top scores for driver and programming attempts.

    :param vrc_team_id: Identifier of the team to compute skills ranking for
    :type vrc_team_id: int
    :param season_id: Identifier of the season to retrieve skills data for
    :type season_id: int
    :return: A tuple representing the sum of the best driver and programming skills
             scores, the best driver score, and the best programming score
    :rtype: tuple[int | Any, int | Any, int | Any]
    """
    url = f"{API_SERVER}/teams/{vrc_team_id}/skills"
    params = {'season': season_id}
    vrc_skills = get_api_paginated(url, params)
    driver = 0
    auton = 0
    for attempt in vrc_skills:
        if attempt['type'] == 'driver' and attempt['score'] > driver:
            driver = attempt['score']
        if attempt['type'] == 'programming' and attempt['score'] > auton:
            auton = attempt['score']
    return auton + driver, driver, auton

def get_team_awards(vrc_team_id: int, season_id: int) -> list[dict]:
    """
    Fetches the list of awards received by a specific team during a particular season.
    Awards are extracted from the API response and compiled into a list of award titles.

    :param vrc_team_id: Unique identifier for the team.
    :type vrc_team_id: int
    :param season_id: Identifier for the season to filter the awards.
    :type season_id: int
    :return: A list of dictionaries containing the 'title' of each award received by the team.
    :rtype: list[dict]
    """
    url = f"{API_SERVER}/teams/{vrc_team_id}/awards"
    params = {'season': season_id}
    awards_list = []
    vrc_awards = get_api_paginated(url, params)
    for received_award in vrc_awards:
        awards_list.append(received_award['title'])
    return awards_list


# noinspection PyTypeChecker
def write_dict_to_csv(filepath, dictionary, fieldnames):
    """
    Writes a dictionary to a CSV file.

    Args:
        filepath (str): The name of the CSV file to write to.
        dictionary (list): The list of dictionaries to write.
        fieldnames (list): A list of keys that will be used as column headers.
    """
    with open(filepath, 'w', newline='') as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames, dialect='excel', quoting=csv.QUOTE_ALL)
        # writer.writeheader()
        writer.writerows(dictionary)


if __name__ == "__main__":

    EVENT_SKU = 'RE-V5RC-24-7329'

#    """
    event_info = get_event_by_sku(EVENT_SKU)
    if not event_info:
        print("Event not found.")
        exit(1)
    requested_event_id = event_info['id']
    current_season_id = event_info['season']['id']
    team_list = get_team_list_for_event(requested_event_id)

    final_team_list = {}
    team_skills = {}
    team_wins = {}
    team_awards = {}
    for team in team_list:
        team_id = team['id']
        awards = get_team_awards(team_id, current_season_id)
        wins = get_team_rankings(team_id, current_season_id)
        skills = get_team_skills_ranking(team_id, current_season_id)

        final_team_list[team_id] = (team['number'], team['team_name'], team['organization'], team['location']['city'])
        team_wins[team_id] = wins
        team_skills[team_id] = skills
        team_awards[team_id] = awards

#"""
  #  final_team_list = {153991: ('393V', 'Legacy - Venom', 'LEGACY MAGNET ACADEMY', 'Tustin'), 129724: ('393W', 'Legacy - W Rizz', 'LEGACY MAGNET ACADEMY', 'Tustin'), 129725: ('393X', 'Legacy Xtra Sigma', 'LEGACY MAGNET ACADEMY', 'Tustin'), 129726: ('393Y', 'Legacy - Yellow Fishes', 'LEGACY MAGNET ACADEMY', 'Tustin'), 129727: ('393Z', 'Legacy - Zer0', 'LEGACY MAGNET ACADEMY', 'Tustin'), 110647: ('462A', 'Wolverines', 'HARVARD-WESTLAKE', 'Los Angeles'), 124323: ('462B', 'Wolverines', 'HARVARD-WESTLAKE', 'Los Angeles'), 174418: ('462K', 'Wolverines', 'HARVARD-WESTLAKE SCHOOL', 'Los Angeles'), 142455: ('462T', 'Wolverines', 'HARVARD-WESTLAKE SCHOOL', 'Los Angeles'), 119950: ('462V', 'Wolverines', 'HARVARD-WESTLAKE', 'Los Angeles'), 119951: ('462X', 'Wolverines', 'HARVARD-WESTLAKE', 'Los Angeles'), 114797: ('462Z', 'Wolverines', 'HARVARD-WESTLAKE', 'Los Angeles'), 163079: ('1281B', 'K!ND - Radiant', 'Radiant Robotics', 'Arcadia'), 170823: ('1281C', 'Yellow Calculator - Radiant', 'Radiant Robotics', 'Arcadia'), 182035: ('1281Z', 'Radiant Robotics', 'Radiant Robotics', 'Arcadia'), 97601: ('1469E', 'bunny frogs', 'OLIVER WENDELL HOLMES MIDDLE', 'Northridge'), 26506: ('1469X', 'Pneumatic Python', 'OLIVER WENDELL HOLMES MIDDLE', 'Northridge'), 173748: ('1537A', 'RuiGuan Irvine Team 1537A', 'RuiGuan Irvine', 'Irvine'), 173749: ('1537Z', 'RuiGuan Irvine Team 1537Z', 'RuiGuan Irvine', 'Irvine'), 156341: ('1590A', 'Blue Army', 'Innovagine Robotics', 'Rancho Cucamonga'), 179724: ('1592A', 'Irvine Ruiguan', 'Irvine Ruiguan', 'Irvine'), 169681: ('2399A', 'STEM Sirens', 'GPSRSC', 'North Hills'), 163848: ('2681A', 'YellowBot - Radiant', 'Radiant Robotics', 'Irvine'), 61235: ('2822A', 'Spartan Design Leonidas', 'STAUFFER MIDDLE', 'Downey'), 62509: ('2822B', 'Spartan Design Baja Blast', 'STAUFFER (MARY R.) MIDDLE', 'Downey'), 65339: ('2822C', 'Spartan Design Cronos', 'STAUFFER (MARY R.) MIDDLE', 'Downey'), 69406: ('2822D', 'Spartan Design Daytona', 'STAUFFER (MARY R.) MIDDLE', 'Downey'), 70351: ('2822E', 'Spartan Design Butterflies', 'STAUFFER (MARY R.) MIDDLE', 'Downey'), 70352: ('2822F', 'Spartan Design Fancy', 'STAUFFER (MARY R.) MIDDLE', 'Downey'), 153523: ('2899A', 'Shooting Stars', '', 'Arcadia'), 173646: ('3221Z', 'Salt and Pepper', 'Diamond Bar Robotics Lab', 'Diamond Bar'), 170053: ('3299C', 'Atlantis', 'Atlantis', 'Torrance'), 81719: ('3324B', 'Supernova Moonshot', 'SCIENCE ACADEMY STEM MAGNET', 'North Hollywood'), 83079: ('3324E', 'Etherea', 'SCIENCE ACADEMY STEM MAGNET', 'North Hollywood'), 142318: ('3324H', 'Supernova Hyperspeeders', 'SCIENCE ACADEMY STEM MAGNET', 'Los Angeles'), 114566: ('3324M', 'Supernova MetaStorm', 'SCIENCE ACADEMY STEM MAGNET', 'Los Angeles'), 124413: ('3324S', 'Supernova shwei', 'SCIENCE ACADEMY STEM MAGNET', 'Los Angeles'), 141029: ('3324T', 'Supernova Titanium', 'SCIENCE ACADEMY STEM MAGNET', 'Los Angeles'), 83025: ('3324V', 'Supernova Valor', 'SCIENCE ACADEMY STEM MAGNET', 'North Hollywood'), 81722: ('3324X', 'Supernova Xfinity', 'SCIENCE ACADEMY STEM MAGNET', 'North Hollywood'), 95808: ('3324Z', 'Supernova Circuit BreakerZ', 'SCIENCE ACADEMY STEM MAGNET', 'North Hollywood'), 172903: ('3515X', 'Xtra', 'Irvine Robotics', 'Irvine'), 169936: ('3588Y', 'Cyber Spacers', 'Edubot Inc.', 'Torrance'), 172904: ('4520Y', 'YES', 'Irvine Robotics', 'Irvine'), 62734: ('4863A', 'Ark-Toad-Us Symus', 'Irving STEAM Magnet', 'Los Angeles'), 63429: ('4863B', 'B3arz', 'Irving STEAM Magnet', 'Los Angeles'), 70650: ('4863F', 'Fabrikatorz', 'Irving STEAM Magnet', 'Los Angeles'), 169812: ('4863J', 'Jabbawokez', 'WASHINGTON IRVING MID SCH MATH MUSIC AND ENGR MAGNET', 'Los Angeles'), 49154: ('6007X', 'Quantum Flux', 'Rolling Robots West LA', 'Los Angeles'), 50205: ('6446A', 'Royal Robotics 6446A', 'RANCHO DEL REY MIDDLE', 'Chula Vista'), 50546: ('6446B', 'Royal Robotics 6446B', 'RANCHO DEL REY MIDDLE', 'Chula Vista'), 56222: ('6446C', 'Royal Robotics 6446C', 'RANCHO DEL REY MIDDLE', 'Chula Vista'), 50083: ('6517A', 'TRITONBOTS-A', 'EASTLAKE MIDDLE', 'Chula Vista'), 51692: ('6636A', 'RoboWaves', 'Manhattan Beach Middle School', 'Manhattan Beach'), 50827: ('6722A', 'Cyber Cats - KIT', 'Pioneer Middle School', 'Tustin'), 82488: ('6722C', 'Cyber Cats - SyndiCat', 'Pioneer Middle School', 'Tustin'), 131390: ('6722E', 'Cyber Cats - Toygers', 'Pioneer Middle School', 'Tustin'), 175173: ('7314A', 'Rolling Robots - The Seven Pies', 'Rolling Robots', 'Pasadena'), 50470: ('7700A', 'Rolling Robots', 'Rolling Robots', 'Rolling Hills Estates'), 50694: ('7700B', 'Rolling Robots', 'Rolling Robots', 'Rolling Hills Estates'), 63953: ('7700E', 'Rolling Robots Electric Eels', 'Rolling Robots', 'Rolling Hills Estates'), 174458: ('7700F', 'Rolling Robots', 'Rolling Robots', 'Rolling Hills Estates'), 142585: ('7700H', 'Rolling Robots Humuhumunukunukuapua', 'Rolling Robots', 'Rolling Hills Estates'), 72790: ('7700N', 'Rolling Robots Noodle Fish', 'Rolling Robots', 'Rolling Hills Estates'), 83403: ('7700P', 'Rolling Robots Platypuses', 'ROLLING ROBOTS', 'Rolling Hills Estate'), 143160: ('7700T', 'Rolling Robots', 'Rolling Robots', 'Rolling Hills Estates'), 71575: ('7700X', 'Rolling Robots', 'Rolling Robots', 'Rolling Hills Estates'), 153732: ('7899A', 'Rolling Robots Torpedo Rays', 'Rolling Robots', 'Irvine'), 155496: ('7899B', 'Rolling Robots Barracudas', 'Rolling Robots', 'Irvine'), 157111: ('7899C', 'Rolling Robots Devil Ray', 'Rolling Robots', 'Irvine'), 173590: ('7899G', 'Rolling Robots Raptors', 'Rolling Robots', 'Irvine'), 173232: ('7899K', 'Rolling Robots Ka-Chow', 'Rolling Robots', 'Irvine'), 55589: ('8838A', 'Robohawks - Aurelia', 'ORCHARD HILLS', 'Irvine'), 63521: ('8838B', 'Robohawks - Century', 'ORCHARD HILLS', 'Irvine'), 63522: ('8838C', 'Robohawks - Celestial', 'ORCHARD HILLS', 'Irvine'), 63523: ('8838D', 'Robohawks - Amirite', 'ORCHARD HILLS', 'Irvine'), 80242: ('8838E', 'Robohawks - Eclipse', 'ORCHARD HILLS', 'Irvine'), 55611: ('8929A', 'Hewes Team Star Glazers', 'HEWES MIDDLE', 'Santa Ana'), 157077: ('9078N', 'Dinosaur Train', 'GRIFFITHS MIDDLE', 'Downey'), 141387: ('9078W', 'Umizoomi', 'GRIFFITHS MIDDLE', 'Downey'), 70318: ('9078X', 'Tacos De Lengua', 'GRIFFITHS MIDDLE', 'Downey'), 129890: ('9078Z', 'Flying Nimbus', 'GRIFFITHS MIDDLE', 'Downey'), 81390: ('9413D', 'J.I.G.A.A.A.B', 'STEAM ACADEMY @ BURKE', 'Pico Rivera'), 181344: ('13889B', '0 TO 1', 'EDUCATION EMPOWERMENT ASIA', 'Diamond Bar'), 181910: ('13889X', 'ELIXIR', 'EDUCATION EMPOWERMENT ASIA', 'Diamond Bar'), 81591: ('68689A', 'Xob Diov', 'BP STEM Academy', 'Baldwin Park'), 172542: ('68689C', "I Don't Know My Name", 'BP STEM Academy', 'Baldwin Park'), 72185: ('77938B', 'MVA Robotics', 'MAR VISTA ACADEMY', 'San Diego'), 162265: ('84949V', 'Filet Mignon', 'SUSSMAN (EDWARD A.) MIDDLE', 'Downey'), 172322: ('85884A', 'Juicy Boba', 'HAPPY KIDS ROBOTICS', 'Glendora'), 107410: ('91625C', 'Brea Botcats Sabatours', 'Brea Junior High School', 'Brea'), 171635: ('91625F', 'Brea Botcats', 'Brea Junior High School', 'Brea'), 83806: ('96140A', 'Woodcrest Turbo Tuners', 'WOODCREST SCHOOL', 'Tarzana'), 142086: ('96140B', 'Gilmore Gears', 'WOODCREST SCHOOL', 'Tarzana'), 169522: ('96140Z', 'Woodcrest Robotics Zee Team', 'WOODCREST SCHOOL', 'Tarzana')}
  #  team_wins = {153991: (52, 9, 0), 129724: (35, 13, 0), 129725: (36, 18, 1), 129726: (34, 26, 1), 129727: (30, 22, 3), 110647: (18, 23, 1), 124323: (21, 15, 0), 174418: (10, 11, 1), 142455: (18, 13, 0), 119950: (11, 28, 1), 119951: (25, 23, 1), 114797: (35, 26, 1), 163079: (17, 21, 0), 170823: (24, 13, 1), 182035: (12, 10, 0), 97601: (20, 22, 1), 26506: (22, 19, 2), 173748: (30, 6, 0), 173749: (32, 16, 2), 156341: (49, 20, 1), 179724: (11, 5, 0), 169681: (12, 13, 0), 163848: (36, 10, 0), 61235: (40, 13, 0), 62509: (35, 26, 4), 65339: (32, 15, 0), 69406: (40, 23, 3), 70351: (18, 25, 4), 70352: (42, 22, 1), 153523: (42, 17, 0), 173646: (28, 11, 0), 170053: (51, 9, 0), 81719: (65, 11, 1), 83079: (21, 34, 4), 142318: (33, 20, 0), 114566: (26, 20, 0), 124413: (15, 22, 0), 141029: (30, 21, 1), 83025: (7, 11, 0), 81722: (11, 22, 0), 95808: (7, 17, 0), 172903: (37, 12, 0), 169936: (40, 10, 0), 172904: (22, 17, 0), 62734: (30, 13, 1), 63429: (24, 14, 0), 70650: (29, 14, 1), 169812: (19, 12, 0), 49154: (3, 14, 1), 50205: (24, 29, 4), 50546: (29, 26, 2), 56222: (34, 21, 2), 50083: (20, 12, 3), 51692: (4, 8, 0), 50827: (16, 15, 0), 82488: (13, 12, 0), 131390: (13, 11, 1), 175173: (9, 16, 0), 50470: (7, 13, 0), 50694: (26, 25, 0), 63953: (28, 12, 1), 174458: (6, 12, 0), 142585: (23, 10, 0), 72790: (16, 8, 0), 83403: (12, 15, 1), 143160: (17, 15, 0), 71575: (14, 10, 0), 153732: (27, 25, 2), 155496: (26, 29, 1), 157111: (11, 14, 1), 173590: (23, 5, 0), 173232: (26, 17, 0), 55589: (12, 27, 1), 63521: (24, 14, 2), 63522: (25, 14, 1), 63523: (17, 16, 0), 80242: (26, 13, 1), 55611: (7, 12, 0), 157077: (36, 20, 3), 141387: (28, 24, 1), 70318: (24, 29, 6), 129890: (27, 24, 2), 81390: (17, 10, 1), 181344: (7, 12, 0), 181910: (23, 6, 0), 81591: (18, 12, 4), 172542: (15, 17, 2), 72185: (18, 14, 4), 162265: (27, 12, 1), 172322: (21, 17, 0), 107410: (24, 10, 0), 171635: (17, 5, 0), 83806: (15, 12, 0), 142086: (15, 12, 0), 169522: (10, 9, 0)}
  #  team_skills = {153991: (105, 53, 52), 129724: (74, 46, 28), 129725: (64, 39, 25), 129726: (87, 49, 38), 129727: (55, 31, 24), 110647: (62, 38, 24), 124323: (56, 35, 21), 174418: (43, 35, 8), 142455: (45, 37, 8), 119950: (51, 30, 21), 119951: (62, 41, 21), 114797: (86, 41, 45), 163079: (84, 50, 34), 170823: (91, 48, 43), 182035: (83, 39, 44), 97601: (44, 26, 18), 26506: (53, 30, 23), 173748: (110, 54, 56), 173749: (99, 59, 40), 156341: (97, 55, 42), 179724: (83, 51, 32), 169681: (49, 39, 10), 163848: (130, 68, 62), 61235: (70, 44, 26), 62509: (65, 37, 28), 65339: (50, 37, 13), 69406: (51, 41, 10), 70351: (24, 24, 0), 70352: (55, 47, 8), 153523: (82, 56, 26), 173646: (83, 48, 35), 170053: (115, 62, 53), 81719: (87, 62, 25), 83079: (82, 48, 34), 142318: (67, 47, 20), 114566: (58, 46, 12), 124413: (51, 36, 15), 141029: (57, 44, 13), 83025: (37, 29, 8), 81722: (42, 29, 13), 95808: (51, 39, 12), 172903: (90, 53, 37), 169936: (107, 61, 46), 172904: (63, 48, 15), 62734: (45, 42, 3), 63429: (34, 26, 8), 70650: (65, 50, 15), 169812: (0, 0, 0), 49154: (44, 32, 12), 50205: (35, 26, 9), 50546: (37, 26, 11), 56222: (35, 25, 10), 50083: (32, 23, 9), 51692: (36, 28, 8), 50827: (26, 26, 0), 82488: (41, 38, 3), 131390: (33, 29, 4), 175173: (46, 31, 15), 50470: (45, 29, 16), 50694: (80, 47, 33), 63953: (64, 43, 21), 174458: (46, 35, 11), 142585: (66, 46, 20), 72790: (65, 46, 19), 83403: (45, 34, 11), 143160: (61, 42, 19), 71575: (44, 36, 8), 153732: (60, 41, 19), 155496: (87, 52, 35), 157111: (51, 42, 9), 173590: (46, 41, 5), 173232: (72, 55, 17), 55589: (16, 16, 0), 63521: (60, 51, 9), 63522: (62, 46, 16), 63523: (59, 48, 11), 80242: (60, 48, 12), 55611: (36, 36, 0), 157077: (46, 38, 8), 141387: (52, 37, 15), 70318: (49, 34, 15), 129890: (54, 39, 15), 81390: (37, 29, 8), 181344: (40, 40, 0), 181910: (80, 56, 24), 81591: (41, 32, 9), 172542: (59, 41, 18), 72185: (0, 0, 0), 162265: (52, 38, 14), 172322: (81, 44, 37), 107410: (32, 29, 3), 171635: (47, 36, 11), 83806: (65, 33, 32), 142086: (44, 44, 0), 169522: (47, 39, 8)}
  #  team_awards = {153991: ['Robot Skills Champion (VRC/VEXU/VAIRC)', 'Innovate Award (VRC/VEXU/VAIRC)', 'Excellence Award (VRC/VEXU/VAIRC)', 'Robot Skills Champion (VRC/VEXU/VAIRC)', 'Robot Skills Champion (VRC/VEXU/VAIRC)', 'Tournament Finalists (VRC/VEXU/VAIRC)', 'Tournament Champions (VRC/VEXU/VAIRC)', 'Robot Skills Champion (VRC/VEXU/VAIRC)', 'Robot Skills Champion (VRC/VEXU/VAIRC)', 'Amaze Award (VRC/VEXU/VAIRC)', 'Tournament Finalists (VRC/VEXU/VAIRC)', 'Excellence Award (VRC/VEXU/VAIRC)', 'Tournament Finalists (VRC/VEXU/VAIRC)', 'Robot Skills Champion (VRC/VEXU/VAIRC)', 'Tournament Champions (VRC/VEXU/VAIRC)', 'Robot Skills Champion (VRC/VEXU/VAIRC)', 'Tournament Finalists (VRC/VEXU/VAIRC)', 'Robot Skills Champion (VRC/VEXU/VAIRC)'], 129724: ['Design Award (VRC/VEXU/VAIRC)', 'Think Award (VRC/VEXU/VAIRC)', 'Tournament Finalists (VRC/VEXU/VAIRC)', 'Think Award (VRC/VEXU/VAIRC)'], 129725: ['Build Award (VRC/VEXU/VAIRC)', 'Amaze Award (VRC/VEXU/VAIRC)', 'Excellence Award (VRC/VEXU/VAIRC)'], 129726: ['Design Award (VRC/VEXU/VAIRC)', 'Judges Award (VRC/VEXU/VAIC/ADC/VAIRC)', 'Design Award (VRC/VEXU/VAIRC)', 'Tournament Champions (VRC/VEXU/VAIRC)'], 129727: ['Amaze Award (VRC/VEXU/VAIRC)'], 110647: ['Excellence Award - Middle School (VRC)', 'Amaze Award (VRC/VEXU/VAIRC)'], 124323: ['Innovate Award (VRC/VEXU/VAIRC)'], 174418: [], 142455: [], 119950: ['Create Award (VRC/VEXU/VAIRC)'], 119951: ['Create Award (VRC/VEXU/VAIRC)'], 114797: ['Excellence Award (VRC/VEXU/VAIRC)', 'Tournament Champions (VRC/VEXU/VAIRC)', 'Excellence Award (VRC/VEXU/VAIRC)', 'Robot Skills Champion (VRC/VEXU/VAIRC)', 'Excellence Award (VRC/VEXU/VAIRC)', 'Tournament Finalists (VRC/VEXU/VAIRC)', 'Think Award (VRC/VEXU/VAIRC)'], 163079: [], 170823: [], 182035: [], 97601: ['Innovate Award (VRC/VEXU/VAIRC)'], 26506: ['Judges Award (VRC/VEXU/VAIC/ADC/VAIRC)'], 173748: ['Tournament Champions (VRC/VEXU/VAIRC)', 'Think Award (VRC/VEXU/VAIRC)', 'Tournament Champions (VRC/VEXU/VAIRC)', 'Tournament Champions (VRC/VEXU/VAIRC)'], 173749: ['Tournament Champions (VRC/VEXU/VAIRC)', 'Tournament Finalists (VRC/VEXU/VAIRC)', 'Robot Skills Champion (VRC/VEXU/VAIRC)'], 156341: ['Tournament Champions (VRC/VEXU/VAIRC)', 'Tournament Champions (VRC/VEXU/VAIRC)', 'Think Award (VRC/VEXU/VAIRC)', 'Tournament Champions (VRC/VEXU/VAIRC)', 'Robot Skills Champion (VRC/VEXU/VAIRC)', 'Robot Skills Champion (VRC/VEXU/VAIRC)', 'Amaze Award (VRC/VEXU/VAIRC)', 'Think Award (VRC/VEXU/VAIRC)'], 179724: ['Tournament Champions (VRC/VEXU/VAIRC)'], 169681: ['Innovate Award (VRC/VEXU/VAIRC)', 'Innovate Award (VRC/VEXU/VAIRC)'], 163848: ['Robot Skills Champion (VRC/VEXU/VAIRC)', 'Tournament Champions (VRC/VEXU/VAIRC)', 'Robot Skills Champion (VRC/VEXU/VAIRC)', 'Tournament Champions (VRC/VEXU/VAIRC)', 'Robot Skills Champion (VRC/VEXU/VAIRC)', 'Amaze Award (VRC/VEXU/VAIRC)', 'Judges Award (VRC/VEXU/VAIC/ADC/VAIRC)', 'Tournament Champions (VRC/VEXU/VAIRC)', 'Robot Skills Champion (VRC/VEXU/VAIRC)'], 61235: ['Think Award (VRC/VEXU/VAIRC)', 'Excellence Award (VRC/VEXU/VAIRC)', 'Robot Skills Champion (VRC/VEXU/VAIRC)', 'Robot Skills Champion (VRC/VEXU/VAIRC)', 'Excellence Award (VRC/VEXU/VAIRC)', 'Tournament Champions (VRC/VEXU/VAIRC)', 'Robot Skills Champion (VRC/VEXU/VAIRC)', 'Think Award (VRC/VEXU/VAIRC)', 'Tournament Champions (VRC/VEXU/VAIRC)', 'Innovate Award (VRC/VEXU/VAIRC)'], 62509: ['Innovate Award (VRC/VEXU/VAIRC)', 'Innovate Award (VRC/VEXU/VAIRC)'], 65339: ['Judges Award (VRC/VEXU/VAIC/ADC/VAIRC)', 'Tournament Finalists (VRC/VEXU/VAIRC)', 'Tournament Champions (VRC/VEXU/VAIRC)'], 69406: [], 70351: ['Design Award (VRC/VEXU/VAIRC)', 'Design Award (VRC/VEXU/VAIRC)', 'Judges Award (VRC/VEXU/VAIC/ADC/VAIRC)'], 70352: ['Design Award (VRC/VEXU/VAIRC)', 'Innovate Award (VRC/VEXU/VAIRC)', 'Tournament Champions (VRC/VEXU/VAIRC)', 'Judges Award (VRC/VEXU/VAIC/ADC/VAIRC)', 'Tournament Champions (VRC/VEXU/VAIRC)', 'Design Award (VRC/VEXU/VAIRC)'], 153523: ['Tournament Finalists (VRC/VEXU/VAIRC)', 'Tournament Champions (VRC/VEXU/VAIRC)', 'Tournament Champions (VRC/VEXU/VAIRC)', 'Tournament Champions (VRC/VEXU/VAIRC)', 'Tournament Champions (VRC/VEXU/VAIRC)', 'Tournament Champions (VRC/VEXU/VAIRC)'], 173646: ['Excellence Award - Middle School (VRC)', 'Innovate Award (VRC/VEXU/VAIRC)'], 170053: ['Robot Skills Champion (VRC/VEXU/VAIRC)', 'Judges Award (VRC/VEXU/VAIC/ADC/VAIRC)', 'Robot Skills 2nd Place (VRC/VEXU/VAIRC)', 'Judges Award (VRC/VEXU/VAIC/ADC/VAIRC)', 'Tournament Champions (VRC/VEXU/VAIRC)', 'Robot Skills Champion (VRC/VEXU/VAIRC)', 'Tournament Finalists (VRC/VEXU/VAIRC)', 'Robot Skills Champion (VRC/VEXU/VAIRC)', 'Tournament Champions (VRC/VEXU/VAIRC)', 'Robot Skills Champion (VRC/VEXU/VAIRC)', 'Tournament Champions (VRC/VEXU/VAIRC)'], 81719: ['Tournament Champions (VRC/VEXU/VAIRC)', 'Amaze Award (VRC/VEXU/VAIRC)', 'Tournament Champions (VRC/VEXU/VAIRC)', 'Innovate Award (VRC/VEXU/VAIRC)', 'Build Award (VRC/VEXU/VAIRC)', 'Tournament Champions (VRC/VEXU/VAIRC)', 'Tournament Champions (VRC/VEXU/VAIRC)', 'Innovate Award (VRC/VEXU/VAIRC)', 'Tournament Champions (VRC/VEXU/VAIRC)', 'Excellence Award (VRC/VEXU/VAIRC)', 'Tournament Champions (VRC/VEXU/VAIRC)', 'Innovate Award (VRC/VEXU/VAIRC)'], 83079: ['Judges Award (VRC/VEXU/VAIC/ADC/VAIRC)', 'Design Award (VRC/VEXU/VAIRC)'], 142318: ['Tournament Champions (VRC/VEXU/VAIRC)', 'Create Award (VRC/VEXU/VAIRC)', 'Excellence Award (VRC/VEXU/VAIRC)', 'Tournament Finalists (VRC/VEXU/VAIRC)', 'Judges Award (VRC/VEXU/VAIC/ADC/VAIRC)', 'Design Award (VRC/VEXU/VAIRC)', 'Tournament Finalists (VRC/VEXU/VAIRC)', 'Innovate Award (VRC/VEXU/VAIRC)', 'Create Award (VRC/VEXU/VAIRC)'], 114566: ['Build Award (VRC/VEXU/VAIRC)', 'Tournament Champions (VRC/VEXU/VAIRC)', 'Excellence Award - Middle School (VRC)'], 124413: [], 141029: ['Design Award (VRC/VEXU/VAIRC)', 'Tournament Champions (VRC/VEXU/VAIRC)', 'Build Award (VRC/VEXU/VAIRC)', 'Design Award (VRC/VEXU/VAIRC)'], 83025: [], 81722: [], 95808: [], 172903: ['Think Award (VRC/VEXU/VAIRC)', 'Design Award (VRC/VEXU/VAIRC)', 'Tournament Champions (VRC/VEXU/VAIRC)', 'Think Award (VRC/VEXU/VAIRC)'], 169936: ['Tournament Champions (VRC/VEXU/VAIRC)', 'Robot Skills Champion (VRC/VEXU/VAIRC)', 'Tournament Finalists (VRC/VEXU/VAIRC)', 'Tournament Champions (VRC/VEXU/VAIRC)', 'Robot Skills Champion (VRC/VEXU/VAIRC)'], 172904: ['Tournament Finalists (VRC/VEXU/VAIRC)', 'Tournament Finalists (VRC/VEXU/VAIRC)'], 62734: ['Tournament Champions (VRC/VEXU/VAIRC)', 'Build Award (VRC/VEXU/VAIRC)', 'Tournament Finalists (VRC/VEXU/VAIRC)', 'Tournament Champions (VRC/VEXU/VAIRC)', 'Excellence Award (VRC/VEXU/VAIRC)'], 63429: ['Tournament Champions (VRC/VEXU/VAIRC)', 'Design Award (VRC/VEXU/VAIRC)'], 70650: ['Tournament Finalists (VRC/VEXU/VAIRC)', 'Tournament Champions (VRC/VEXU/VAIRC)', 'Innovate Award (VRC/VEXU/VAIRC)', 'Innovate Award (VRC/VEXU/VAIRC)', 'Tournament Finalists (VRC/VEXU/VAIRC)', 'Innovate Award (VRC/VEXU/VAIRC)'], 169812: ['Tournament Champions (VRC/VEXU/VAIRC)'], 49154: [], 50205: ['Innovate Award (VRC/VEXU/VAIRC)', 'Judges Award (VRC/VEXU/VAIC/ADC/VAIRC)', 'Tournament Champions (VRC/VEXU/VAIRC)', 'Innovate Award (VRC/VEXU/VAIRC)'], 50546: ['Judges Award (VRC/VEXU/VAIC/ADC/VAIRC)', 'Tournament Finalists (VRC/VEXU/VAIRC)', 'Robot Skills Champion (VRC/VEXU/VAIRC)', 'Think Award (VRC/VEXU/VAIRC)'], 56222: ['Design Award (VRC/VEXU/VAIRC)'], 50083: ['Create Award (VRC/VEXU/VAIRC)', 'Excellence Award (VRC/VEXU/VAIRC)'], 51692: ['Judges Award (VRC/VEXU/VAIC/ADC/VAIRC)'], 50827: ['Tournament Champions (VRC/VEXU/VAIRC)', 'Design Award (VRC/VEXU/VAIRC)'], 82488: ['Judges Award (VRC/VEXU/VAIC/ADC/VAIRC)', 'Excellence Award - Middle School (VRC)'], 131390: ['Tournament Champions (VRC/VEXU/VAIRC)'], 175173: [], 50470: [], 50694: [], 63953: ['Innovate Award (VRC/VEXU/VAIRC)'], 174458: [], 142585: ['Excellence Award (VRC/VEXU/VAIRC)', 'Tournament Finalists (VRC/VEXU/VAIRC)', 'Design Award (VRC/VEXU/VAIRC)'], 72790: [], 83403: ['Excellence Award - Middle School (VRC)'], 143160: ['Design Award (VRC/VEXU/VAIRC)'], 71575: [], 153732: [], 155496: ['Think Award (VRC/VEXU/VAIRC)'], 157111: [], 173590: ['Tournament Finalists (VRC/VEXU/VAIRC)'], 173232: ['Tournament Finalists (VRC/VEXU/VAIRC)'], 55589: ['Judges Award (VRC/VEXU/VAIC/ADC/VAIRC)', 'Design Award (VRC/VEXU/VAIRC)', 'Build Award (VRC/VEXU/VAIRC)'], 63521: ['Excellence Award (VRC/VEXU/VAIRC)', 'Amaze Award (VRC/VEXU/VAIRC)'], 63522: ['Innovate Award (VRC/VEXU/VAIRC)', 'Judges Award (VRC/VEXU/VAIC/ADC/VAIRC)', 'Tournament Finalists (VRC/VEXU/VAIRC)', 'Create Award (VRC/VEXU/VAIRC)'], 63523: ['Design Award (VRC/VEXU/VAIRC)', 'Innovate Award (VRC/VEXU/VAIRC)'], 80242: ['Excellence Award (VRC/VEXU/VAIRC)', 'Tournament Champions (VRC/VEXU/VAIRC)', 'Design Award (VRC/VEXU/VAIRC)'], 55611: [], 157077: ['Excellence Award (VRC/VEXU/VAIRC)', 'Tournament Finalists (VRC/VEXU/VAIRC)', 'Excellence Award (VRC/VEXU/VAIRC)'], 141387: ['Judges Award (VRC/VEXU/VAIC/ADC/VAIRC)', 'Excellence Award (VRC/VEXU/VAIRC)'], 70318: [], 129890: ['Robot Skills 3rd Place (VRC/VEXU/VAIRC)'], 81390: [], 181344: [], 181910: ['Tournament Finalists (VRC/VEXU/VAIRC)', 'Think Award (VRC/VEXU/VAIRC)', 'Excellence Award - Middle School (VRC)', 'Tournament Champions (VRC/VEXU/VAIRC)'], 81591: [], 172542: ['Robot Skills 2nd Place (VRC/VEXU/VAIRC)'], 72185: ['Tournament Champions (VRC/VEXU/VAIRC)', 'Create Award (VRC/VEXU/VAIRC)'], 162265: ['Excellence Award (VRC/VEXU/VAIRC)', 'Robot Skills Champion (VRC/VEXU/VAIRC)'], 172322: ['Tournament Finalists (VRC/VEXU/VAIRC)', 'Sportsmanship Award (VRC/VEXU/VAIRC)', 'Tournament Semifinalists (VRC/VEXU/VAIRC)'], 107410: ['Tournament Champions (VRC/VEXU/VAIRC)', 'Tournament Finalists (VRC/VEXU/VAIRC)', 'Tournament Finalists (VRC/VEXU/VAIRC)'], 171635: ['Tournament Champions (VRC/VEXU/VAIRC)', 'Tournament Finalists (VRC/VEXU/VAIRC)', 'Judges Award (VRC/VEXU/VAIC/ADC/VAIRC)'], 83806: ['Excellence Award (VRC/VEXU/VAIRC)'], 142086: ['Design Award (VRC/VEXU/VAIRC)', 'Design Award (VRC/VEXU/VAIRC)', 'Judges Award (VRC/VEXU/VAIC/ADC/VAIRC)'], 169522: []}

    # combine all together
    csv_list = []
    for team_id, team_info in final_team_list.items():
        win = team_wins[team_id][0]
        loss = team_wins[team_id][1]
        ties = team_wins[team_id][2]

        driver_skills = team_skills[team_id][1]
        auto_skills = team_skills[team_id][2]
        total_skills = team_skills[team_id][0]

        all_awards = team_awards[team_id]
        awards_join = ''
        if all_awards:
            for team_award in all_awards:
                team_award = (team_award.replace('(VRC/VEXU/VAIRC)', '').
                              replace('(VRC/VEXU/VAIC/ADC/VAIRC)', '').replace('(VRC)',''))
                awards_join = awards_join + team_award + '\n'


        csv_list.append({'id': team_info[0], 'name': team_info[1], 'org':team_info[2], 'wins': win,
        'losses': loss, 'ties': ties, 'dskills': driver_skills, 'askills': auto_skills,
        'tskills': total_skills, 'awards': awards_join})

    # export to CSV file
    header = ['Team ID', 'Team Name', 'Organisation', 'Wins', 'Losses', 'Ties', 'Driver Skills', 'Auton Skills', 'Skills Total', 'Team Awards']
    keys = list(csv_list[0].keys())
    header_dict = {}
    for key,value in zip(keys,header):
        header_dict[key] = value
    csv_list.insert(0,header_dict)
    write_dict_to_csv(f'teams-{EVENT_SKU}-data.csv', csv_list, keys)