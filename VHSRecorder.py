import sqlite3 
import requests
import json
from datetime import datetime
import time
import re
import atexit
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

        self.preservation_society =True
        

    def check_race_ended(self,last_race,last_cup):
        ret = requests.get(url = self.race_url) 
        self.raw_race = ret.json()
        #check the race has finished by comparing the length of the feed
        #print(self.raw_race["lastfeeditem"], len(self.raw_race["feed"]))
        if self.raw_race["cup"]["racenum"] != last_race and self.raw_race["cup"]["name"] != last_cup:
            if self.raw_race["over"]:
                return True
            else:
                return False
        else:
            return False
         
    def parse_race(self):
        #incase anouther process is running we want to give race parsing priority
        race_record = self.raw_race["feed"]

        if self.preservation_society:
            cup = self.raw_race["cup"]["name"]
            race = self.raw_race["cup"]["racenum"]
            with open('%s%s_%i.json'%('./json/',cup,race), 'w') as outfile:
                json.dump(self.raw_race,outfile)
                print('new VHS taped! %s %i'%(cup,race))
                
            self.cur.execute("UPDATE handler_data SET Last_cup = ?, Last_Race = ?",
                             (cup,race))
            self.conn.commit()
        racers_id =[]
        emojis = []
        teams = []

        #read in start of race, this is of known format and establishes who's racing
        #could also use ["players"] list, but much is the same
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


        #race time feed parsing 
        for line in race_record[9:]:
            pass

        #post race event parsing
        if self.raw_race["cup"]["racenum"] == 3:
            self.raw_stats = requests.get(url = self.stats_url).json()
            for team in self.raw_stats['teams'].items():
                self.cur.execute("UPDATE Teams SET cup_wins = ? WHERE Name = ?",(team[1]['score'],team[0]))
                self.conn.commit() 
            print("cup totals updated")
            
        return 


    def update_racers(self):
        #update or insert all record of active racers
        ret = requests.get(url = self.racers_url) 
        self.raw_racers = ret.json()
        allplayer_list = [self.raw_racers["inactive"],self.raw_racers["active"]]

        for active_status, player_sublist in enumerate(allplayer_list):
            for player in player_sublist.items():
                name = player[0]
                info = player[1]
                stats = info['stats']
                if active_status:
                    team = player[1]['team']
                    self.cur.execute("SELECT ID from Teams WHERE Name = ?",(team,))
                    team_id_r = self.cur.fetchone()
                    team_id = team_id_r[0]
                else:
                    team_id = 0

                self.cur.execute("INSERT OR REPLACE INTO Racers (ACTIVE, NAME, EMOJI, TEAM_ID,ORIGINS,COLOUR,"+
                "STAT_ED,STAT_BU,STAT_VP,STAT_LF,STAT_CH,STAT_CT,"+
                "STAT_HL,STAT_SG,STAT_MG,STAT_EY,STAT_AG,"+
                "CUPS, SCORE, SSCORE)"+
                "VALUES (?,?,?,?,?, ?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                                 (active_status, name,info['emoji'],team_id,info['origins'],info['color'],
                                  stats['ED'],stats['BU'],stats['VP'],stats['LF'],stats['CH'],
                                  stats['CT'],stats['HL'],stats['SG'],stats['MG'],stats['EY'],stats['AG'],
                                  info['cups'],info['score'],info['sscore']
                                  ))
                self.conn.commit()




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

    db.update_racers()


    #rough sync to be ~5-10ms accurate to the minute
    #while datetime.now().time().minute:
    #    time.sleep(0.05)
    db.cur.execute('SELECT Last_Cup, Last_Race FROM handler_data')
    ret = db.cur.fetchone()

    prev_cup = ret[0]
    prev_race = ret[1]

    print('begin logging')
    while True:
        #check twice a minute if race has ended 
        if db.check_race_ended(prev_race,prev_cup):
            #if so update racers and parse the race
            db.update_racers()
            db.parse_race()
            time.sleep(120)#sleep for two minutes 
        else:
            time.sleep(60)
