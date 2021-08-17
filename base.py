import sqlite3 
import requests
import json
from datetime import datetime
import time
import re
#"base" rename to json->database parser


pattern = re.compile("(?<=\*\*)(.*)(?=\*\*)")

class database_handler(object):
    #object for storing a common state within the program
    #useful if turn into a bot that requires asyncronous reading/writing of data
    def __init__(self,database_conn,race_url, racers_url, stats_url):
        self.race_url = race_url
        self.racers_url = racers_url
        self.stats_url = stats_url

        
        self.conn = database_conn
        self.cur = database_conn.cursor()
        

    def check_race_ended(self,last_race):
        ret = requests.get(url = self.race_url) 
        self.raw_race = ret.json()
        #check the race has finished by comparing the length of the feed
        #print(self.raw_race["lastfeeditem"], len(self.raw_race["feed"]))
        if self.raw_race["cup"]["racenum"] != last_race:
            if self.raw_race["lastfeeditem"] < len(self.raw_race["feed"])+1:
                return True
            else:
                return False
        else:
            return False
         
    def parse_race(self):
        #incase anouther process is running we want to give race parsing priority
        race_record = self.raw_race["feed"]

        racers_id =[]
        emojis = []
        teams = []

        #read in start of race, this is of known format
        weather = race_record[0]
        for line in race_record[1:9]:
            teams.append(line[0])
            emojis.append(line[2])
            queryterm = pattern.findall(line)[0]
            #self.cur.execute("SELECT ID From Racers WHERE NAME LIKE ?",(queryterm,))
            self.cur.execute("SELECT ID From Racers WHERE EMOJI = ?",(line[2],))
            ret = self.cur.fetchone()
            racers_id.append(ret[0])

        racers = dict( zip(emojis, racers_id))
        for line in race_record[9:]:
            pass#event parsing needed
        
        return

    def parse_racers(self):
        #update or insert all record of active racers
        ret = requests.get(url = self.racers_url) 
        self.raw_racers = ret.json()
        allplayer_list = [self.raw_racers["inactive"],self.raw_racers["active"]]

        for active_status, player_sublist in enumerate(allplayer_list):
            for player in player_sublist.items():
                name = player[0]
                if active_status:
                    team = player[1]['team']
                    self.cur.execute("SELECT ID from Teams WHERE Name = ?",(team,))
                    team_id_r = self.cur.fetchone()
                    team_id = team_id_r[0]
                else:
                    team_id = 0

                emoji = player[1]['emoji']

                self.cur.execute("INSERT OR REPLACE INTO Racers (ACTIVE, NAME, EMOJI, TEAM_ID) VALUES (?,?,?,?)",
                                 (active_status,name,emoji,team_id))
                self.conn.commit()
    def parse_stats(self):
        return




if __name__ == "__main__":
    #passive script mode, just open up database and write into it
    database = './racerbase.db'
    conn = sqlite3.connect(database)
    cur = conn.cursor()
    #urls 
    race_url = "https://splortle.azurewebsites.net/game.json"
    racers_url = "https://splortle.azurewebsites.net/peeps.json"
    stats_url =  "https://splortle.azurewebsites.net/othervar.json"

    db = database_handler(conn, race_url, racers_url, stats_url)

    db.parse_racers()

    print('Logging Starts')
    #rough sync to be ~5-10ms accurate to the minute
    #while datetime.now().time().minute:
    #    time.sleep(0.05)
    prev_race = -1
    while True:
        #check twice a minute if race has ended 
        if db.check_race_ended(prev_race):
            db.parse_racers()
            db.parse_race()
            print('race logged')
            time.sleep(120)#sleep for two minutes 
        else:
            time.sleep(60)
