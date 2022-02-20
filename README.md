# DynamicIpTables
设置动态防火墙，用于抵御国外的IP攻击，例如腾讯云服务器使用时经常遭到国外IP攻击,lastb可查看到很多登陆失败的境外ip

原理： 监控`/var/log/secure`文件，记录每个ip失败的次数和时间，符合设置规则的加入至防火墙（iptables）中

TODO 程序整理

## 1. 使用
### 1.1 下载
在release中下载`DynamicIpTables.tar`，内含可执行文件`DynamicIpTables`和`config.yaml`
### 1.2 运行
以下执行都是在CentOS 7.6的操作系统下执行的，其它操作系统可能需要自己重新编译为适合自己系统的`DynamicIpTables`，参考第3点，另仅适合使用iptables作为防火墙表的系统
执行 `nohup ./DynamicIpTables -c config.yaml &`就运行了
执行 `tail -f dynamic_log.txt` 可实时查看日志
### 1.3有关配置
```yaml
# 系统安全日志文件
secure_log: /var/log/secure
# 打印日志
log_file: /var/log/dynamiciptables.log

# ip白名单 强烈建议配置，因为如果不配置，若别人和你在同一公网ip下，他多次尝试登陆并失败，会使得ip被封，使得你自己也无法访问
allow_ip:
  - 127.0.0.1
  - 202.197.74.82
  - 119.28.22.215 # 腾讯云ssh
  - 39.144.0.0/16

# 规则访问 该程序，处理通过22端口尝试登陆访问的ip
rules:
  # 地区以 http://ip-api.com/json/?lang=zh-CN 查询的结果为准
  # 中国ip 120秒超过5次 加入防火墙 port可填只封锁22端口，填-1则为封锁此ip访问所有端口
  -
    port: -1
    country: 中国
    regionName:
    city:
    time: 120
    count: 5

  # 其它地区ip 直接加入防火墙
  -
    port: -1
    country:
    regionName:
    city:
    time: 1
    count: 0
```
## 2 创建service
可以`nohup ./DynamicIpTables -c config.yaml &`启动，也可以创建service
### 2.1 创建
`vi /etc/systemd/system/dynamiciptables.service`，内容如下,其中执行路径改成自己的
```bash
[Unit]
Description=dynamic ip tables daemon
After=syslog.target  network.target
Wants=network.target

[Service]
Type=simple
ExecStart=/path/to/DynamicIpTables -c /path/to/config.yml
Restart= always
RestartSec=1min

[Install]
WantedBy=multi-user.target
```
### 2.2 运行
启动前应先将刚才nohup启动的进程kill掉，`ps -aux| grep DynamicIpTables`获取到进程id再kill
1. `systemctl enable dynamiciptables`
2. `systemctl start dynamiciptables`

## 3. 如果使用自己的服务器编译
`pyinstaller -F DynamicIpTables.py`
将会生成一个build和一个dist的文件夹

生成的可执行为文件在dist中
ps:运行时用ps查看进程会发现有两个进程，原因是当指明-F参数构建时，程序被解压缩到一个临时目录并从那里运行。第二个进程是实际的程序，而第一个进程是在程序退出或崩溃后清理临时目录。因此, 去除 -F参数时, 就可以显示一个进程, 但是如果只有一个进程，那么在崩溃的情况下就无法清理临时目录
