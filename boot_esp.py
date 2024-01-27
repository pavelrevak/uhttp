import time
import network


def do_connect():
    print('boot...')
    wlan = network.WLAN(network.STA_IF)
    print('NETWORK: activating...')
    wlan.active(True)
    # print('NETWORK: scanning...')
    # print(wlan.scan())
    print('NETWORK: connecting...')
    wlan.connect('766c6b', 'siberianhuskie')
    while not wlan.isconnected():
        time.sleep(1)
        print('.', end='')
    print('NETWORK:', wlan.ifconfig())


if __name__ == '__main__':
    do_connect()
