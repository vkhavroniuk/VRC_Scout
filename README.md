# VRC V5 Scout  

## Overview  
VRC V5 Scout is a tool designed to streamline scouting for upcoming VEX Robotics events. It retrieves event data from [RobotEvents.com](https://www.robotevents.com) using an event code (e.g., `RE-V5RC-24-5524`) and compiles key statistics for registered teams.  

## Features  
- Fetches a list of all registered teams for a given event.  
- Retrieves match results, skills scores, and award history for each team.  
- Generates a CSV file containing essential scouting information.  

## CSV Output Format  
The generated CSV file includes the following fields:  

| Field Name         | Description                           |
|--------------------|---------------------------------------|
| `Team ID`         | Unique identifier for the team       |
| `Team Name`       | Official name of the team            |
| `Organization`    | Affiliated school or organization    |
| `Wins`           | Number of matches won                |
| `Losses`         | Number of matches lost               |
| `Ties`           | Number of matches tied               |
| `Driver Skills`  | Driver skills challenge score        |
| `Auton Skills`   | Autonomous skills challenge score    |
| `Skills Total`   | Combined skills score                |
| `Team Awards`    | Awards won by the team               |

## Setup & Requirements  
To use this tool, you must obtain an API access token from [RobotEvents.com](https://www.robotevents.com). Once acquired, export the token as a system environment variable:  

```sh
export TOKEN=your_api_access_token
