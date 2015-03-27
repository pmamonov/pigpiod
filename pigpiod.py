#!/usr/bin/python
import os, sys, time, argparse, signal, ctypes, socket, threading
import RPi.GPIO as gpio

pins = {0:11, 1:13, 2:15, 3:16}

timers = map(lambda i: None, range(len(pins)))

# tcp socket to listen
soc = None

# connetion socket
conn = None

def timestamp():
	t = time.localtime()
	return "%d-%02d-%02d_%02d:%02d:%02d> " % (t.tm_year, t.tm_mon, t.tm_mday, t.tm_hour, t.tm_min, t.tm_sec)

def tsprint(s):
	print timestamp() + s

def quit(sig, fr):
	if type(conn) is socket.socket: 
		conn.close()
		tsprint("Close connection")
	if type(soc) is socket.socket: 
		soc.close()
		tsprint("Close socket")
	tsprint("Daemon exits")
	sys.exit(0)

def gpio_set(out):
	gpio.output(pins[out], gpio.HIGH)
	tsprint("%d ON" % out)

def gpio_reset(out):
	gpio.output(pins[out], gpio.LOW)
	tsprint("%d OFF" % out)

def process_cmd(c):
	ret = "ERROR"
	tsprint(c)
	t = c.split()
	if len(t) > 0:
		if t[0] == 'enable':
			try:
				out, tim = map(int, t[1:])
				if type(timers[out]) is threading._Timer:
					timers[out].cancel()
					timers[out].join()
				gpio_set(out)
				timers[out] = threading.Timer(1e-3 * tim, lambda o=out: gpio_reset(o))
				timers[out].start()
				ret = "OK"
			except:
				pass
	tsprint(ret)
	return ret

# workaround signal handling in python
libc = ctypes.cdll.LoadLibrary("libc.so.6")
mask = '\x00' * 17 # 16 byte empty mask + null terminator 
libc.sigprocmask(2, mask, None)

# parse arguments
prs = argparse.ArgumentParser(description="")
prs.add_argument('-x', dest="pidf", metavar='FILENAME', type=str, help='PID file', default='pigpiod.pid')
prs.add_argument('-d', dest="daemon",	action="store_true", help='daemonize')
prs.add_argument('-l', dest="log", metavar='FILE', type=str, help='log file')
prs.add_argument('-p', dest="port", metavar='PORT', type=int, help='port number to listen',default=6660)
prs.add_argument('-i', dest="iface", metavar='INTERFACE', type=str, help='hostname or ip adress to listen',default='0.0.0.0')
args = prs.parse_args()

# daemonize if requested
if args.daemon:
	if os.fork() > 0:
		sys.exit(0)
	os.setsid()
	if os.fork() > 0:
		sys.exit(0)
	os.umask(0)
	import resource		# Resource usage information.
	maxfd = resource.getrlimit(resource.RLIMIT_NOFILE)[1]
	if (maxfd == resource.RLIM_INFINITY):
		maxfd = 1024
	for fd in range(0, maxfd):
		try:
			os.close(fd)
		except OSError:	# ERROR, fd wasn't open to begin with (ignored)
			pass

# set SIGTERM signal handler
signal.signal(signal.SIGTERM, quit)
signal.signal(signal.SIGINT, quit)

# redirect stdout,stderr to log file
sys.stdin = open('/dev/null', 'r')
if args.log:
	sys.stdout = open(args.log, 'w', 0)
	sys.stderr = open(args.log, 'w', 0)

# write pid to file
f = open(args.pidf, 'w')
f.write(str(os.getpid()))
f.close()

# create socket to listen
try:
	soc = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
	soc.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
	soc.bind((args.iface, args.port))
except socket.error as err:
	print err
	quit(0,0)

soc.listen(1)

tsprint("Daemon started")

# use board pins numbers
gpio.setmode(gpio.BOARD)

# configure pins as outputs
for out in pins.values():
	gpio.setup(out, gpio.OUT)

while 1:
	conn = None
	conn, addr = soc.accept()
	tsprint("Accept connection from %s" % str(addr))
	buf = ''
	while 1:
		d = conn.recv(4096)
		if not d:
			break
		buf += d
		while 1:
			stop = buf.find('\n')
			if stop >= 0:
				stop += 1
				cmd = buf[:stop]
				buf = buf[stop:]
				conn.send(process_cmd(cmd.strip()) + '\n')
			else:
				break

	tsprint("Connection closed")
