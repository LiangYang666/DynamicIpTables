#!/usr/bin/env python
#-*- coding=utf-8 -*-
import os
import datetime
import pyinotify
import logging
import yaml
import requests
import time
import sys
import re
import argparse

pos = 1     # 读取文件位置,起始位置设为1 因为第secure第1行为空，从第0位置读会直接break

block_ips = []
faild_ips_dict = {}

pattern_str = ['Failed password for root from 125.123.88.221 port 59120 ssh2',
                'Failed password for invalid user admin from 218.255.12.54 port 51541 ssh2']

def get_ip_info(ip='202.197.74.82'):
    url = f'http://ip-api.com/json/{ip}?lang=zh-CN'
    # print(url)
    r = requests.post(url=url).json()

    if isinstance(r, dict):
        info = {'country': 'unknow', 'regionName': 'unknow'}
        if 'country' in r.keys():
            info['country'] = r['country']
            info['regionName'] = r['regionName']
    return r, info

def check_if_block(ip, info):
    global config
    if ip not in faild_ips_dict.keys():
        faild_ips_dict[ip] = []
    faild_ips_dict[ip].append(int(time.time()))
    config_rule = None
    for rule in config['rules']:    # 一级检索
        if info['country'] == rule['country'] and info['regionName'] == rule['regionName']:
            config_rule = rule
    if config_rule==None:
        for rule in config['rules']:    # 二级检索
            if info['country'] == rule['country'] and rule['regionName'] is None:
                config_rule = rule
        if config_rule==None:         
            for rule in config['rules']:    # 三级检索
                if rule['country'] is None:
                    config_rule = rule
    if config_rule==None or config_rule['count']==None or config_rule['time']==None or config_rule['port']==None:
        logging.error("[error] config.yaml is not right")
        return False

    if faild_ips_dict[ip].__len__()>config_rule['count']:
        if faild_ips_dict[ip][-1]-faild_ips_dict[ip][-config_rule['count']-1]<config_rule['time']:
            return config_rule['port']
    return False

def handle_ip(ip):
    rs, info  = get_ip_info(ip=ip)
    if info['country'] != 'unknow':
        port = check_if_block(ip, info)
        if port:
            add_to_iptables(ip, port, info)
    else:
        logging.warn(f"[error]\tThe ip result is not right {rs}")


def add_to_iptables(ip, port, info):
    assert 'allow_ip' in config.keys()
    if ip in config['allow_ip']:
        logging.info(f"[allow]\tTry to block, but the ip {ip} is allowed")
        return
    #TODO 设置使用ip掩码进行匹配
    global block_ips, faild_ips_dict
    command = ""
    if port==-1:
        command = f"iptables -I INPUT -s {ip} -j DROP"
    else:
        command = f"iptables -I INPUT -s {ip} -p tcp --dport 22 -j DROP"
    logging.info("[run]\t run command "+command)
    os.system(command)
    logging.info("[run]\t successful ")
    block_ips.append(ip)
    del faild_ips_dict[ip]
    logging.info(f"[block]\tBlock the ip {ip} [{info['country']}, {info['regionName']}] to iptables {port}")

def handle_new_line(line: str):
    str1 = 'Failed password for'
    if str1 in line:
        strings = line.split("from")[1]
        ip =re.search(r'((2[0-4]\d|25[0-5]|[01]{0,1}\d{0,1}\d)\.){3}(2[0-4]\d|25[0-5]|[01]{0,1}\d{0,1}\d)', strings).group()
        handle_ip(ip)
    elif "Accepted" in line:
        user = line.split('for')[1].split('from')[0].strip()      
        strings = line.split("from")[1]  
        ip =re.search(r'((2[0-4]\d|25[0-5]|[01]{0,1}\d{0,1}\d)\.){3}(2[0-4]\d|25[0-5]|[01]{0,1}\d{0,1}\d)', strings).group()
        _, info = get_ip_info(ip)
        logging.info(f"[allow]\t Get a successful connection of {user} from {info['country']},{info['regionName']}[{ip}]")
    else:
        print("Not handle :\t"+line)

def get_new_log(file, first=False):
    global pos
    try:
        fd = open(file)
        if pos != 0:
            fd.seek(pos,0)
        while True:
            line = fd.readline()
            if line.strip():
                if not first:
                    # print(f"-pos: {pos}-")
                    handle_new_line(line.strip())
                pos = pos + len(line)
            if not line.strip():
                break
        fd.close()
    except Exception as e:
        logging.error(str(e))
        
class MyEventHandler(pyinotify.ProcessEvent):
    def process_IN_MODIFY(self,event):
        try:
            get_new_log(monitoring_file, first=False)
        except Exception as e:
            logging.error(str(e))

def main():
    get_new_log(monitoring_file,first=True)
    logging.info(f"----pos: {pos}------")
    logging.info("--------------begin monitoring --------------")
    wm = pyinotify.WatchManager()
    wm.add_watch(monitoring_file, pyinotify.ALL_EVENTS,rec=True)
    eh = MyEventHandler()
    notifier = pyinotify.Notifier(wm,eh)
    notifier.loop()

def read_config(file="config.yaml"):
    with open(file, 'r') as f:
        config = yaml.load(f, Loader=yaml.FullLoader)
    return config

def config_glob(config):
    global monitoring_file
    assert 'secure_log' in config.keys()
    monitoring_file = config['secure_log']


def logger_init(filename='log.txt', stdout=True):
    fmt = '%(message)s' 
    fmt = '%(asctime)s %(filename)s[line:%(lineno)d] %(levelname)s: %(message)s'
    logging.basicConfig(level=logging.INFO, filename=filename, format=fmt, filemode='a')
    if stdout:
        console = logging.StreamHandler(stream=sys.stdout)
        console.setLevel(logging.INFO)
        formatter = logging.Formatter(fmt)
        console.setFormatter(formatter)
        logging.getLogger('').addHandler(console)
    return logging

if __name__ == "__main__":
    
    parser = argparse.ArgumentParser(description='Train a FewShot model')
    parser.add_argument('-c', default='config.yaml',help='train config file path')
    args = parser.parse_args()

    monitoring_file = ""
    config_file=args.c
    config = read_config(config_file)
    config_glob(config)
    logger_init(filename=config['log_file'])
    logging.info("\n")
    logging.info("--------------new start--------------")
    logging.info(f"Config file {os.path.abspath(config_file)}")
    logging.info(config)
    main()