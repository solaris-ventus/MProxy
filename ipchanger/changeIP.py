#!/usr/bin/env python3

import os
import subprocess
import time
from typing import Any

from huawei_lte_api.Client import Client
from huawei_lte_api.Connection import Connection

wait_time = 20 # количество секунд ожидания поднятия модема после смены IP

# Функция вывода модема из пула балансировки haproxy
def removeModemFromPull(modem):
    result = os.system('echo "set server ' + modem.rstrip() + '/' + modem.rstrip() + ' state drain" | socat stdio tcp4-connect:127.0.0.1:1350')  # выведем текущий сервер из пула haproxy

# Функция возврата модема в пул балансировки haproxy
def returnModemToPull(modem):
    result = os.system('echo "set server ' + modem.rstrip() + '/' + modem.rstrip() + ' state ready" | socat stdio tcp4-connect:127.0.0.1:1350')  # вернем текущий сервер в пул haproxy

# Функция смены IP-адреса модема. При успешном выполнении возвращает True, иначе False
def changeModemIP(modem) -> bool:
    with Connection("http://admin:Password01*@" + modem.rstrip()) as connection:
        client = Client(connection)
        if int(client.monitoring.traffic_statistics().get('CurrentConnectTime')) <= 300:
            return True
        else:
            # если модем работает более 5 минут, то сменим ему IP-адрес
            # но сначала выведем его из пула haproxy
            removeModemFromPull(modem)
            client.net.set_net_mode("7FFFFFFFFFFFFFFF", "3FFFFFFF", "02") # 3G
            client.net.set_net_mode("7FFFFFFFFFFFFFFF", "3FFFFFFF", "03") # LTE
            # подождем wait_time секунд, чтобы модем подключился к сети. Если за половину отведенного времени не подключился,
            # то делаем модему выкл/вкл и ждем оставшуюся половину времени
            for i in range(wait_time):
                status = client.monitoring.status()
                if status.get('ConnectionStatus') == '901':
                    break
                if i >= wait_time/2:
                    client.dial_up.set_mobile_dataswitch(0)
                    time.sleep(1)
                    client.dial_up.set_mobile_dataswitch(1)
                time.sleep(1)
    #если так и не дождались подключения к сети, то сдаемся и возвращаем False
    if status.get('ConnectionStatus') == '901':
        returnModemToPull(modem)
        return True
    else:
        return False

# Основной сценарий

# получим список модемов из конфиг файла ltemodems.cfg
with open('ltemodems.cfg', 'r') as f:
    Modems = f.readlines()

def checkModemConnection(modem):
    command1 = "echo \"show servers state\" | socat stdio tcp4-connect:127.0.0.1:1350 | grep -E \"(" + modem.rstrip() + ".*){2}\" | cut -d \" \" -f 5,19"
    response1 = subprocess.check_output(command1, shell=True, text=True)
    proxy = response1.split()
    command2 = "curl -sx http://" + proxy[0] + ":" + proxy[1] + " http://2ip.ru"
    response2 = subprocess.check_output(command2, shell=True, text=True)

    if response2:
        return True
    else:
        return False

# для каждого модема по списку, если после последней смены IP-адреса прошло более 5 минут, выполним вывод из пула haproxy, сменим IP-адрес,
# удостоверимся, что модем точно подключен к интернету и что полученный IP-адрес уникален, и вернем его в пул.
# Если модем не подключился или адрес не уникален, то повторим процедуру смены адреса (максимум 3 повтора).
for modem in Modems:
    for i in range(3):
        if changeModemIP(modem):
            if checkModemConnection(modem):
                break
        else:
            break


