import json
import numpy as np
import pickle as pkl
import requests
import time

item_costs = {}
with open("item_data.json", 'r') as f:
    item_costs = json.loads(f.readline())["itemdata"]

def get_item_cost(key):
    return item_costs.get(key, {"cost": 0})["cost"]

class Player:
    def __init__(self, player_name):
        self.gold_t = []
        self.purchase_log = []
        self.buyback_t = []
        self.player_name = player_name

    def get_buyback_cost(self, times):
        buyback_costs_t = np.zeros(len(times))
        for b in self.buyback_t:
            i = b // 60
            if i < 0:
                i = 0
            elif i >= len(times):
                i = len(times) - 1
            buyback_costs_t[i] += 100 + self.gold_t[i]//13
        return buyback_costs_t

    def get_purchase_cost(self, times):
        purchases_cost_t = np.zeros(len(times))
        for p in self.purchase_log:
            if p["time"] < 0:
                p["time"] = 0
            i = p["time"] // 60 - 1
            if i < 0:
                i = 0
            elif i >= len(times):
                i = len(times) - 1
            purchases_cost_t[i] += get_item_cost(p["key"])
        return purchases_cost_t


class Team:
    num_players = 5
    def __init__(self, team_name):
        self.players = []
        self.team_name = team_name

    def calculate_team_gold(self, times):
        team_gold_t = np.zeros(len(times))
        # for p in self.players:
            # print ("Player gold ", p.gold_t)
        for t in range(len(times)):
            for player in self.players:
                team_gold_t[t] += player.gold_t[t]
        # print ("team gold ", team_gold_t)
        return team_gold_t

    def calculate_team_buybacks(self, times):
        team_buybacks_t = np.zeros(len(times))
        buyback_costs = []
        for player in self.players:
            buyback_costs.append(player.get_buyback_cost(times))
        for t in range(len(times)):
            for bc in buyback_costs:
                team_buybacks_t[t] += bc[t]
        return team_buybacks_t

    def calculate_team_purchases(self, times):
        team_purchases_t = np.zeros(len(times))
        purchase_costs = []
        for player in self.players:
            purchase_costs.append(player.get_purchase_cost(times))
        for t in range(len(times)):
            for pc in purchase_costs:
                team_purchases_t[t] += pc[t]
        return team_purchases_t

r = 'radiant'
d = 'dire'

class Match:
    def __init__(self, match_json):
    
        self.team_r = Team(r)
        self.team_d = Team(d)
        self.times = None

    
        self.match_id = match_json.get("match_id", -1)
        if self.match_id == -1:
            raise Exception("Error parsing match: {}".format(match_json))
        self.radiant_win = match_json.get("radiant_win", True)
        self.radiant_gold_adv = match_json.get("radiant_gold_adv", [])
        self.radiant_exp_adv = match_json.get("radiant_exp_adv", [])

        print ("Match id: {}".format(self.match_id))
        print ("RWin: {}".format(self.radiant_win))

        if self.populate_players(match_json) == -1:
            return None

        self.radiant_gold_t = self.team_r.calculate_team_gold(self.times)
        self.dire_gold_t = self.team_d.calculate_team_gold(self.times)

        self.radiant_buybacks_t = self.team_r.calculate_team_buybacks(self.times)
        self.dire_buybacks_t = self.team_d.calculate_team_buybacks(self.times)

        self.radiant_purchases_t = self.team_r.calculate_team_purchases(self.times)
        self.dire_purchases_t = self.team_d.calculate_team_purchases(self.times)

    def populate_players(self, js):
        players = js.get("players", None)
        if not players:
            return -1

        for p in players:
            player = Player(p.get("name", "~~Empty name~~"))

            if not self.times:
                times = p.get("times", [])
                if not times:
                    return -1
                self.times = times
            gold_t = p.get("gold_t", [])
            if not gold_t:
                return -1
            player.gold_t = gold_t
            
            buyback_log = p.get("buyback_log", [])
            if not buyback_log:
                return -1
            for b in buyback_log:
                player.buyback_t.append(b.get("time"))

            purchase_log = p.get("purchase_log", [])
            if not purchase_log:
                return -1
            player.purchase_log = purchase_log
            
            if p["isRadiant"]:
                self.team_r.players.append(player)
            else:
                self.team_d.players.append(player)
        return 0

def make_request(url, num_requests, params=None):
    i = 0
    while True:
        if i == 10:
            break
        i += 1
        num_requests += 1
        if params:
                r = requests.get(url = url, params=params)
        else:
            r = requests.get(url = url)
        try: 
            match_json = r.json()
        except Exception err:
            print ("Exception occured when parsing response: {}".format(err))
            continue
        if not(isinstance(match_json, dict) and match_json.get("error", "") == "rate limit exceeded"):
            return match_json, num_requests
        time.sleep(5)
    return None, num_requests
        


def main():

    matches_parsed = {}
    set_matches_parsed = set()

    pro_matches_URL = "https://api.opendota.com/api/proMatches"
    match_URL = "https://api.opendota.com/api/matches/{}"
    num_requests = 5004
    last_mid = 4316944059
    i = 2
    while num_requests < 45000:
        if last_mid != -1:
            matches_file, num_requests = make_request(pro_matches_URL, num_requests, params={"less_than_match_id":last_mid})
        else:
            matches_file, num_requests = make_request(pro_matches_URL, num_requests)
        if not matches_file:
            break
        for m in matches_file:
            mid = m["match_id"]
            last_mid = mid
            if mid not in set_matches_parsed:
                match_json, num_requests = make_request(match_URL.format(mid), num_requests)
                if not match_json:
                    continue
                with open("matches/{}.json".format(mid), "w") as f:
                    json.dump(match_json, f)
                matches_parsed[mid] = Match(match_json)
                set_matches_parsed.add(mid)
        if num_requests > i * 5000:
            i += 1
            with open("matches_parsed_{}.pkl".format(num_requests), "wb") as f:
                pkl.dump(matches_parsed, f)
            del matches_parsed
            matches_parsed = {}
    with open("matches_parsed_{}.pkl".format(num_requests), "wb") as f:
        pkl.dump(matches_parsed, f)

    # with open("sample_match.json", 'r') as f:
    #     match_json = json.loads(f.readline())
    # match = Match(match_json)
    # print ("Radiant gold:", match.radiant_gold_t)
    # print ("Dire gold:", match.dire_gold_t)
    
    # print ("Radiant buybacks:", match.radiant_buybacks_t)
    # print ("Dire buybacks:", match.dire_buybacks_t)
    
    # print ("Radiant purchases:", match.radiant_purchases_t)
    # print ("Dire purchases:", match.dire_purchases_t)
    
main()  

            
