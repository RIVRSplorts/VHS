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
        self.cur.execute('SELECT Last_Cup, Last_Race FROM handler_data')
        ret = self.cur.fetchone()
        prev_cup = ret[0]
        prev_race = ret[1]

    def check_race_ended(self,last_race,last_cup):
        ret = requests.get(url = self.race_url) 
        self.raw_race = ret.json()
        
        #check the race has finished by comparing the length of the feed


        if self.raw_race["cup"]["name"] != last_cup or self.raw_race["cup"]["racenum"] != last_race:
            if self.raw_race["over"]:
                return True
            else:
                return False

        else:
            return False

    def tape_race(self):

        if self.preservation_society:
            curtime = datetime.now()
            cup = self.raw_race["cup"]["name"]
            race = self.raw_race["cup"]["racenum"]
            
            with open('%s%s_%i_%s.json'%('./json/races/',cup,race+1,curtime.strftime("%Y-%m-%d %H:%M:%S")), 'w') as outfile:
                json.dump(self.raw_race,outfile)
                

            with open('%sracer_stats_%s.json'%('./json/racers/',curtime.strftime("%Y-%m-%d %H:%M:%S")), 'w') as outfile:
                json.dump(self.raw_racers,outfile)
                
            ret = requests.get(url = self.stats_url)
            self.raw_stats = ret.json()
            with open('%smisc_stats_%s.json'%('./json/misc/',curtime.strftime("%Y-%m-%d %H:%M:%S")), 'w') as outfile:
                json.dump(self.raw_stats,outfile)
                
            self.cur.execute("UPDATE handler_data SET Last_cup = ?, Last_Race = ?",
                             (cup,race))
            self.conn.commit()
            print('new VHS taped! %s %i'%(cup,race+1))
        
    def parse_race(self):
        race_record = self.raw_race["feed"]

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
            self.cur.execute("SELECT ID From Racers WHERE NAME LIKE ?",(queryterm,))
            #self.cur.execute("SELECT ID From Racers WHERE EMOJI = ?",(line[2],))
            ret = self.cur.fetchone()
            racers_id.append(ret[0])
            
        racers = dict(zip(queryterm, racers_id))


        #race time feed parsing 
        for line in race_record[9:]:
            pass

        #post race event parsing
        if self.raw_race["cup"]["racenum"] == 3:
            wait = 0
            while wait <5:
                
                ret = requests.get(url = self.race_url) 
                self.raw_race = ret.json()
                self.raw_stats = requests.get(url = self.stats_url).json()
            
                for team in self.raw_stats['teams'].items():

                    self.cur.execute("UPDATE Teams SET cup_wins = ? WHERE Name = ?",(team[1]['score'],team[0]))
                    self.conn.commit() 

                try:
                    winner = self.raw_race["cupranking"][0]
                    snd = self.raw_race["cupranking"][1]
                    last = self.raw_race["cupranking"][-1]
         
                    self.cur.execute("SELECT CUPS,TEAM_ID FROM Racers WHERE NAME = ?",(winner,))
                    ret = self.cur.fetchone()
                    self.cur.execute("SELECT cup_wins FROM Teams WHERE ID = ?",(ret[1],))
                    ret2 = self.cur.fetchone()
                    self.cur.execute("UPDATE Racers SET CUPS = ? WHERE NAME = ?",(ret[0]+1, winner,))
                    self.cur.execute("UPDATE Teams SET cup_wins = ? WHERE ID =?",(ret2[0]+1, ret[1]))
                    self.conn.commit()
                
                    self.cur.execute("SELECT Cup_2nds,TEAM_ID FROM Racers WHERE NAME = ?",(snd,))
                    ret = self.cur.fetchone()
                    self.cur.execute("SELECT cup_2nds FROM Teams WHERE ID = ?",(ret[1],))
                    ret2 = self.cur.fetchone()
                    self.cur.execute("UPDATE Racers SET cup_2nds = ? WHERE NAME = ?",(ret[0]+1, snd,))
                    self.cur.execute("UPDATE Teams SET cup_2nds = ? WHERE ID =?",(ret2[0]+1, ret[1]))
                    self.conn.commit()
                
                    self.cur.execute("SELECT Cup_Lasts,TEAM_ID FROM Racers WHERE NAME = ?",(last,))
                    ret = self.cur.fetchone()
                    self.cur.execute("SELECT cup_8ths FROM Teams WHERE ID = ?",(ret[1],))
                    ret2 = self.cur.fetchone()
                    self.cur.execute("UPDATE Racers SET cup_Lasts = ? WHERE NAME = ?",(ret[0]+1, last,))
                    self.cur.execute("UPDATE Teams SET cup_8ths = ? WHERE ID =?",(ret2[0]+1, ret[1]))
                    self.conn.commit()

                    print("cup totals updated")
                    wait = 10
                    
                    
                except:
                    time.sleep(5)
                    wait += 1
                
  

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


    print('begin logging')
    down_detect = True #arm down detector
    while True:
        #check twice a minute if race has ended
        #note check race ended also downloads the race state!
        db.cur.execute('SELECT Last_Cup, Last_Race FROM handler_data')
        ret = db.cur.fetchone()
        prev_cup = ret[0]
        prev_race = ret[1]

        try:
            if db.check_race_ended(prev_race,prev_cup):
                #if so update racers and parse the race
                db.update_racers()
                db.tape_race()
                Fail = 0

                
                db.parse_race()
                time.sleep(5)
            else:
                nowtime = datetime.now().minute
                if nowtime > 30:
                    delta = 60 - nowtime
                else:
                    delta = 30 - nowtime

                if delta > 120/60:
                    time.sleep(60)
                elif delta > 15/60:
                    time.sleep(10)
                else:
                    time.sleep(2)
            down_detect = True #disarm
        except requests.exceptions.Timeout: #might be splortle down
            if down_detect:#detect if should send a message 
                curtime = datetime.now()
                print('Can\'t reach splortle at %s'%(curtime.strftime("%Y-%m-%d %H:%M:%S"),))
                down_detect = False#flag message been sent
        except:
            print('An error occured, things might not been recorded properly')
            
            time.sleep(30)#sleep for a bit before trying
