from bottle import route,run,redirect

@route('/')
def radiko():
    redirect('radiko.jp/')

run(host='192.168.29.1', port=50080)
    
