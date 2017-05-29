#!/usr/bin/env python
from flask import Flask, Response, request, redirect, jsonify
from flup.server.fcgi import WSGIServer
from werkzeug.debug import DebuggedApplication
from sync import Sync
import requests, os, time, re, threading, json

try:
    import cPickle as pickle
except:
    import pickle

HOST_STR = "https://orkestra.co/ethbot/%s"
BOT_ID = open('.botid').read().strip()
TYPES = {
    ">": (lambda x, y: x>y),
    "<": (lambda x, y: x<y)
}
closing = threading.Event()

#retrieve previous data
try:
    print "recovering environment:",
    env_file = open('env', 'rb')
    environ = pickle.load(env_file)
    offset = environ['offset']
    alarms = Sync(environ['alarms'])
    chats = Sync(environ['chats'])
    last_price = environ['last_price']
    env_file.close()
    print "success"
except Exception as e:
    env_file = open('env', 'wb')
    alarms = Sync({})
    chats = Sync({})
    offset = 0
    last_price = 0
    environ = {'offset':offset, 'alarms':alarms.container, 'chats':chats.container, 'last_price': last_price}
    pickle.dump(environ, env_file)
    env_file.close()
    print "fail"

def check_price():
    global environ, closing
    interval = 10
    while True:
        try:
            #get eth price
            last_price = float(requests.get('https://cex.io/api/last_price/ETH/USD').json()['lprice'])
            #check alarms
            for key, alarm in alarms.items():
                if TYPES[alarm[0]](last_price, alarm[1]):
                    #find the users with alarm and notify them
                    for chat in chats[key]:
                        requests.get('https://api.telegram.org/%s/sendMessage'%BOT_ID,params={'chat_id':chat,'text':'alarm: %f %s %f'%(last_price, alarm[0], alarm[1])})
                    #remove the alarm
                    del chats[key]
                    del alarms[key]
            #update interval
            interval = min(interval+1, 15) if last_price==environ['last_price'] else max(interval-1, 5)
            #save data
            environ = {'offset':offset, 'last_price':last_price, 'alarms':alarms.container, 'chats':chats.container}
            with open('env', 'wb') as env_file:
                pickle.dump(environ, env_file)
            time.sleep(interval)
        except: pass

app = Flask(__name__)
app.debug = True
app.wsgi_app = DebuggedApplication(app.wsgi_app, True)

@app.route('/ethbot/')
def index():
    return str(last_price)

@app.route('/ethbot/%s'%BOT_ID,methods=['POST'])
def handle_message():
    aformat = re.compile(r'([<>])(\d+(?:\.\d+)*)')
    rformat = re.compile(r'([%])([+-]\d+(?:\.\d+)*)')
    try:
        update = json.loads(request.data)
        msgc = update['message']['text']
        chid = update['message']['chat']['id']
        if msgc.startswith('/setalarm'):
            akey, aid, av = aformat.search(msgc).group(0,1,2) 
            alarms[akey] = (aid, float(av))
            chats[akey] = chats.get(akey,set([])) | set([chid])
            requests.get('https://api.telegram.org/%s/sendMessage'%BOT_ID,params={'chat_id':chid,'text':'alarm set for "price %s %s"'%(aid, av)})
        if msgc=='/price':
            requests.get('https://api.telegram.org/%s/sendMessage'%BOT_ID,params={'chat_id':chid,'text':'price: %f'%last_price})
        return 'ok'
    except Exception as e:
        with open('error.log','a') as ef:
            ef.write(repr(e))

if __name__ == '__main__':
    #set webhook
    requests.post('https://api.telegram.org/%s/setWebhook'%BOT_ID,params={'url':HOST_STR%BOT_ID})

    #run price checker
    t = threading.Thread(target=check_price)
    t.daemon = True
    t.start()
    WSGIServer(app).run()
