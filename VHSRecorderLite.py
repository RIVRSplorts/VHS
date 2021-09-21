import sqlite3 
import requests
import json
from datetime import datetime
import time
import re
import atexit
import subprocess

'''
Simplified script to run the recorder compared to the more complex database injestor 

Future databse injestor to use the json files instead
'''

class database_handler(object):
    #object for storing a common state within the program
    #useful if turn into a bot that requires asyncronous reading/writing of data
    def __init__(self,database_conn,race_url, racers_url, stats_url):
        self.race_url = race_url
        self.racers_url = racers_url
        self.stats_url = stats_url

        self.conn = database_conn
        self.cur = database_conn.cursor()

    def check_race_ended(self,last_race,last_cup):
        ret = requests.get(url = self.race_url)
        
        self.raw_race = ret.json()
        
        #check the race has finished by comparing the length of the feed


        if self.raw_race["cup"]["name"] != last_cup or self.raw_race["cup"]["racenum"] != last_race:
            if self.raw_race["over"]:
                if self.raw_race["scorestotalled"]:
                    return True
                else:
                    return False
                    
            else:
                return False
        else:
            return False
        
    def tape_race(self):

        curtime = datetime.now()
        cup = self.raw_race["cup"]["name"]
        race = self.raw_race["cup"]["racenum"]
            
        with open('%s%s_%s_%i.json'%('../json/races/',curtime.strftime("%Y-%m-%d %H:%M:%S"),cup,race+1), 'w') as outfile:
            json.dump(self.raw_race,outfile)
                
        ret = requests.get(url = self.racers_url) 
        self.raw_racers = ret.json()
        with open('%sracer_stats_%s.json'%('../json/racers/',curtime.strftime("%Y-%m-%d %H:%M:%S")), 'w') as outfile:
            json.dump(self.raw_racers,outfile)
                
        ret = requests.get(url = self.stats_url)
        self.raw_stats = ret.json()
        with open('%smisc_stats_%s.json'%('../json/misc/',curtime.strftime("%Y-%m-%d %H:%M:%S")), 'w') as outfile:
            json.dump(self.raw_stats,outfile)
                
        self.cur.execute("UPDATE handler_data SET Last_cup = ?, Last_Race = ?",
                         (cup,race))
        self.conn.commit()
        print('new VHS taped! %s %i'%(cup,race+1))

    def adv_stats(self):
        with open("secret.txt") as f:
            api_key = f.readline().strip()
        with open("last_commit.txt") as f:
            last_commit = f.readline().strip()

        
        subprocess.run('python3 ../Vexologist/main.py', shell=True)
        files = {
            'apikey': (None, api_key),
            'commit': (None, last_commit),
            'file': ('Season.db', open('Season.db', 'rb')),
            'dbname': (None, 'Season.db'),
        }
        response = requests.post('https://api.dbhub.io/v1/upload', files=files)
        print(response.status_code) #print the response
        if response.status_code == 201:
            with open("last_commit.txt", "w") as f:
                content = json.loads(response.text)
                f.write(content["commit"])

if __name__ == "__main__":
    #passive script mode, just open up database and write into it
    database = './VHSRecorder.db'
    conn = sqlite3.connect(database)
    cur = conn.cursor()
    #urls 
    race_url = "https://splortle.azurewebsites.net/game.json"
    racers_url = "https://splortle.azurewebsites.net/peeps.json"
    stats_url =  "https://splortle.azurewebsites.net/othervar.json"

    db = database_handler(conn, race_url, racers_url, stats_url)


    db.adv_stats()
 
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

                db.tape_race()
                Fail = 0
                #run advanced stats
                try:
                    db.adv_stats()
                except:
                    pass
                
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
            
