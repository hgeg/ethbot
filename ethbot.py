import requests, os, time, re
from pprint import pprint

try:
    import cPickle as pickle
except:
    import pickle

BOT_ID = open('.botid').read()
TYPES = {
    ">": (lambda x, y: x>y),
    "<": (lambda x, y: x<y)
}

if __name__ == '__main__':
    #lock the process
    try:
        pid = open('.pid','r').read()
        if os.path.isdir('/proc/%s'%pid):
            print 'another process is running.'
            exit()
    except Exception as e: 
        lock = open('.pid','w+')
        lock.write('%d'%os.getpid())
        lock.close()

    #retrieve previous data
    try:
        print "recovering environment:",
        env_file = open('env', 'rb')
        environ = pickle.load(env_file)
        offset = environ['offset']
        alarms = environ['alarms']
        chats = environ['chats']
        last_price = environ['last_price']
        env_file.close()
        print "success"
    except Exception as e:
        env_file = open('env', 'wb')
        alarms = {}
        chats = {}
        offset = 0
        last_price = 0
        environ = {'offset':offset, 'alarms':alarms, 'chats':chats, 'last_price': last_price}
        pickle.dump(environ, env_file)
        env_file.close()
        print "fail"

    try:
        env_file = open('env', 'wb')
        aformat = re.compile(r'([<>])(\d+(?:\.\d+)*)')
        rformat = re.compile(r'([%])([+-]\d+(?:\.\d+)*)')
        interval = 10
        while True:
            print 'getting updates...'
            updates = requests.get('https://api.telegram.org/%s/getUpdates'%BOT_ID, params={'offset':offset+1}).json()
            if updates['ok']: 
                for update in updates['result']:
                    #set the offset
                    if(update['update_id']>offset):
                        offset = update['update_id']
                    #check alarms
                    try:
                        msgc = update['message']['text']
                        chid = update['message']['chat']['id']
                        if msgc.startswith('/setalarm'):
                            print '  setting alarm:',
                            akey, aid, av = aformat.search(msgc).group(0,1,2) 
                            alarms[akey] = (aid, float(av))
                            chats[akey] = set(chats.get(akey,[]) + [chid])
                            requests.get('https://api.telegram.org/%s/sendMessage'%BOT_ID,params={'chat_id':chid,'text':'alarm set: "price %s %s"'%(aid, av)})
                            print alarms[akey]
                        if msgc=='/price':
                            requests.get('https://api.telegram.org/%s/sendMessage'%BOT_ID,params={'chat_id':chid,'text':'price: %f'%last_price})

                    except Exception as e: 
                        print e
                        continue
            #get eth price
            last_price = float(requests.get('https://cex.io/api/last_price/ETH/USD').json()['lprice'])
            print "price:",last_price
            #check alarms
            for key, alarm in alarms.items():
                if TYPES[alarm[0]](last_price, alarm[1]):
                    #find the users with alarm and notify them
                    for chat in chats[key]:
                        requests.get('https://api.telegram.org/%s/sendMessage'%BOT_ID,params={'chat_id':chid,'text':'alarm: %f %s %f'%(last_price, alarm[0], alarm[1])})
                    #remove the alarm
                    del chats[key]
                    del alarms[key]
            #update interval
            interval = min(interval+1, 15) if last_price==environ['last_price'] else max(interval-1, 8)
            #save data
            environ = {'offset':offset, 'last_price':last_price, 'alarms':alarms, 'chats':chats}
            pickle.dump(environ, env_file)
            print 'saved.'

            time.sleep(interval)
    finally:
        env_file.close()
        os.remove('.pid')
