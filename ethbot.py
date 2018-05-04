#!/usr/bin/env python
#-*- coding: utf-8 -*-
from flask import Flask, Response, request, redirect, jsonify
from flup.server.fcgi import WSGIServer
from werkzeug.debug import DebuggedApplication
from sync import Sync
import requests, os, time, re, threading, json

try:
    import cPickle as pickle
except:
    import pickle

try:
        UNICODE_EXISTS = bool(type(unicode))
except NameError:
        unicode = lambda s: str(s)

HOST_STR = "https://orkestra.co/ethbot/%s"
BOT_ID = open('.botid').read().strip()
TYPES = {
    ">": (lambda x, y: x>y),
    "<": (lambda x, y: x<y),
}
CUR_SYMS = {
    "usd": "$",
    "btc": "฿".decode('utf-8')
}

ALARM_FORMAT = re.compile(r'([<>])(\d+(?:\.\d+)*) (btc|usd)')
closing = threading.Event()

def send(to, msg):
    requests.get('https://api.telegram.org/%s/sendMessage'%BOT_ID,
                  params = {'chat_id':to, 'text':unicode.encode(msg, 'utf-8')}
                )

#retrieve previous data
try:
    print "recovering environment:",
    env_file = open('env', 'rb')
    environ = pickle.load(env_file)
    offset = environ['offset']
    alarms = Sync(environ['alarms'])
    chats = Sync(environ['chats'])
    last_price_btc = environ['last_price_btc']
    last_price_usd = environ['last_price_usd']
    env_file.close()
    print "success"
except Exception as e:
    env_file = open('env', 'wb')
    alarms = Sync({})
    chats = Sync({})
    offset = 0
    last_price_btc = 0
    last_price_usd = 0
    environ = {'offset':offset, 'alarms':alarms.container, 'chats':chats.container, 'last_price_btc': last_price_btc, 'last_price_usd':last_price_usd}
    pickle.dump(environ, env_file)
    env_file.close()
    print "fail"

def check_price():
    global environ, closing
    interval = 20
    while True:
        try:
            #get eth price
            last_prices = {
                'usd': float(requests.get('https://cex.io/api/last_price/ETH/USD').json()['lprice']),
                'btc': float(requests.get('https://cex.io/api/last_price/ETH/BTC').json()['lprice'])
                }
            #check alarms
            for key, alarm in alarms.items():
                if TYPES[alarm[0]](last_prices[alarm[2]], alarm[1]):
                    #find the users with alarm and notify them
                    for chat in chats[key]:
                        send(chat, u'ATTENTION: %s%f %s %s%f 🔥🔥‼️📈📊‼️🔔📢🔥🔥'%(CUR_SYMS[alarm[2]],last_prices[alarm[2]], alarm[0], CUR_SYMS[alarm[2]], alarm[1]))
                    #remove the alarm
                    del chats[key]
                    del alarms[key]
            #update interval
            interval = min(interval+1, 30) if last_prices['usd']==environ['last_price_usd'] else max(interval-1, 10)
            #save data
            environ = {'offset':offset, 'last_price_btc':last_prices['btc'], 'last_price_usd':last_prices['usd'], 'alarms':alarms.container, 'chats':chats.container}
            with open('env', 'wb') as env_file:
                pickle.dump(environ, env_file)
        except Exception as e:
            interval = 30
            with open('check.log','a') as ef:
                ef.write(repr(e) + '\n')
        finally:
            time.sleep(interval)

app = Flask(__name__)
app.debug = True
app.wsgi_app = DebuggedApplication(app.wsgi_app, True)

@app.route('/ethbot/')
def index():
    return '$%f\n฿%f'%(environ['last_price_usd'], environ['last_price_btc'])

@app.route('/ethbot/%s'%BOT_ID,methods=['POST'])
def handle_message():
    try:
        update = json.loads(request.data)
        assert("channel_post" not in update)
        msgc = update['message']['text']
        chid = update['message']['chat']['id']
        if msgc.startswith('/setalarm '):
            akey, aid, av, cur= ALARM_FORMAT.search(msgc).group(0,1,2,3) 
            alarms[akey] = (aid, float(av), cur)
            chats[akey] = chats.get(akey,set([])) | set([chid])
            send(chid,'alarm set for "price %s %s%s"'%(aid, CUR_SYMS[cur], av))
        elif msgc== '/price':
            send(chid,'$%f\n฿%f'%(environ['last_price_usd'], environ['last_price_btc']))
        else: 
            send(chid,'I don\'t understand.')
        return 'ok'
    except AssertionError as e: return
    except Exception as e:
        send(chid,'I don\'t understand.')
        with open('error.log','a') as ef:
            ef.write(repr(update) + '\n')
            ef.write(repr(e) + '\n')
        return 'fail'

if __name__ == '__main__':
    #set webhook
    requests.post('https://api.telegram.org/%s/setWebhook'%BOT_ID,params={'url':HOST_STR%BOT_ID})

    #run price checker
    t = threading.Thread(target=check_price)
    t.daemon = True
    t.start()
    WSGIServer(app).run()
