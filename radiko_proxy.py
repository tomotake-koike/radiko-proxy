import sys
import socket
import ssl
import time
import re
import xml.etree.ElementTree as ET
from threading import Thread

regex = re.compile(r'\r\nHost:\s(.+):(\d+)\r\n')

def tprint( str ):
    print( f'{time.time():.{3}f}' , str )

def hexdump(src, length=16):
    result = []

    for i in range(0, len(src), length):
        s = src[i:i+length]
        hexa = ' '.join(['{:02X}'.format(x) for x in s])
        text = ''.join([chr(x) if x >= 32 and x < 127 else '.' for x in s])
        result.append('{:04X}   {}{}    {}'.format(i, hexa, ((length-len(s))*3)*' ', text))
    for s in result:
        print(s)

def received_from(connection):
    buffer = b''
    connection.settimeout(5)
    try:
        recv_len = 1
        while recv_len:
            data = connection.recv(4096 * 16)
            buffer += data
            recv_len = len(data)
            if recv_len < 4096 * 16:
                break
    except Exception as e:
        print( e )
        print( connection )
        pass

    return buffer


def modify_urls_xml( xbuffer ):

    try:
        xml = ET.fromstring( xbuffer.decode() )
        del_e = []

        # DEBUG tprint( xbuffer.decode() )
        
        for e in xml.iter( 'url' ):
            if e.find( 'playlist_create_url' ).text.startswith('https://radiko.jp'):
                e.set( 'playlist_create_url', e.find( 'playlist_create_url' ).text.replace( 'https://', 'http://' ) )
                e.set( 'areafree', '0' )
            elif e.find( 'playlist_create_url' ).text.startswith('https://'):
                del_e.append( e )
            else:
                e.set( 'areafree', '0' )
                
        for e in del_e:
            xml.remove( e )
            
        new_buffer = xbuffer.split( b'>', 1 )[0] + b'>\n' + ET.tostring( xml )
        new_buffer = new_buffer + f'{0: {len(xbuffer) - len(new_buffer) }}'[:-1].encode() + b'\n'

        # DEBUG tprint( new_buffer.decode() )
       
        return new_buffer
    
    except UnicodeDecodeError as e:
        print( e )
        pass
    
    return xbuffer


def buffer_handler( buffer, is_request ):

    if is_request == False:
        # DEBUG print( buffer )

        if buffer.startswith(b'<?xml '):
            if buffer.split( b'>\n', 1 )[1].startswith( b'<urls>' ):
                return modify_urls_xml( buffer )
        
        elif buffer.startswith(b'HTTP/1.1 200 OK ') and buffer.split( b'\r\n\r\n' )[1].startswith(b'<?xml '):
            buffers = buffer.split( b'\r\n\r\n' )[1]
            if buffers.split( b'>\n', 1 )[1].startswith( b'<urls>' ):
                return buffers[0] + modify_urls_xml( buffers[1] )
        
    return buffer


def proxy_handler( client_socket, remote_socket, client_forward ):

    if client_forward:
        rx_sock = client_socket
        tx_sock = remote_socket
        dst_str = 'client -> server'
    else:
        rx_sock = remote_socket
        tx_sock = client_socket
        dst_str = 'server -> client'

    while True:
        buffer = received_from( rx_sock )
        if len( buffer ):
            tprint('[{}] Received {} bytes.'.format( dst_str, len( buffer )))
            new_buffer = buffer_handler( buffer, client_forward )
            if buffer != new_buffer:
                tprint('[{}] before modify {} bytes.'.format( dst_str, len( buffer )))
                hexdump( buffer, 32 )
                tprint('[{}] after modify {} bytes.'.format( dst_str, len( new_buffer )))
                hexdump( new_buffer, 32 )
            tx_sock.send( new_buffer )
        else:
            tprint('[{}] [Thread] END'.format( dst_str) )
            break

    
def server_loop( local_host, local_port ):
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

    try:
        server.bind((local_host, local_port))
    except:
        tprint('[E] Failed to listen on {}:{}'.format(local_host, local_port))
        sys.exit(0)

    tprint('[*] Listening on {}:{}'.format(local_host, local_port))
    server.listen(5)

    while True:
        client_socket, addr = server.accept()

        tprint('[client -> server] [] Received incoming connection' )
        remote_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

        buffer = received_from(client_socket)
        if len( buffer ):
            tprint('[client -> server] FIRST Received {} bytes.'.format(len( buffer )))
            m = regex.search( buffer.decode() )
            if m:
                remote_host = m.group( 1 )
                remote_port = int( m.group( 2 ) )
            else:
                client_socket.close()
                continue

        # DEBUG print( buffer )

        if buffer.startswith( b'GET /v2/api/playlist_create/INT' ):
            print('Start media-stream')
            context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
            context.load_verify_locations('/etc/ssl/certs/ca-certificates.crt')
            remote_socket = context.wrap_socket(remote_socket, server_hostname='radiko.jp')
            remote_socket.connect(('radiko.jp', 443))
        else:
            remote_socket.connect((remote_host, remote_port))
            tprint('[client -> server] [] Connected {}:{}'.format(remote_host, remote_port) )

        remote_socket.send( buffer )

        tx_proxy_thread = Thread(target=proxy_handler,
                        args=[client_socket, remote_socket, True])
        rx_proxy_thread = Thread(target=proxy_handler,
                        args=[client_socket, remote_socket, False])

        tx_proxy_thread.start()
        rx_proxy_thread.start()


def main():

    server_loop( '0.0.0.0', 80 )

if __name__ == '__main__':
    main()
