#! /usr/bin/python
'''
A python script to Upgrade the IOS on a switch. IP addresses are gotten from ios_upgrade_ips.csv 
Steps are:
	1. Fork new process and telnet to IP address in column 1.
	2. Backup running config to tftp
	3. Copy IOS (column 2) from TFTP to flash.
	4. Verify IOS with md5 hash (column 3)
	5. Set boot system path to flash:/IOS (column 2)
	6. Save configuration
	7. Reboot Switch
	8. Confirm switch booted into new IOS.
	9. Delete old IOS
'''


import re
import os
import sys
import threading
from telnetlib import Telnet
import getpass
from networktools import ping
import time
from datetime import datetime


USER = 'username'	# Change this
PORT = 23
TIMEOUT = 6
READ_TIMEOUT = 6
COPY_TIMEOUT = 720
PWD = getpass.getpass()
TFTP_SERVER = '10.1.1.1'	# Change this

def main():
	f = open('ios_test_ips.csv', 'r')
	if not os.path.exists('./ios_upgrade_output'):
		os.mkdir('ios_upgrade_output')
	allTheads = []
	outputfile = 'ios_upgrade_output/ios_upgrade_output_' + datetime.now().strftime('%Y%m%d') + '.csv'
	with open(outputfile, 'w') as outfile:
		error_file = open('error_file', 'w')
		outfile.write('%s,%s,%s,%s,%s,\n' % ('IP Address', 'Copied', 'Verified', 'System Boot', 'Delete'))
		for line in f.readlines():
			# For each switch in file ios_upgrade_ips.csv, start new thread
			singleThread = threading.Thread(target=threadFunction, args=(line.strip(), outfile, error_file))
			allTheads.append(singleThread)
			singleThread.start()
		for singleThread in allTheads:
			singleThread.join()
	error_file.close()
	f.close()


def telnetWrite(tn, command, wait=1):
	tn.write(command + '\n')
	time.sleep(wait)


def telnetLogon(switch_ip):
	# Telnet to Switch 
	try:
		tn = Telnet(switch_ip, PORT, TIMEOUT)
	except:
		err = switch_ip + ":\tConnection Error\n"
		error_file.write(err)
		sys.exit(1)
	try:
		tn.read_until("username: ", READ_TIMEOUT)
		tn.write(USER + "\n")
	except:
		err = switch_ip + ':\tLogin Prompt Error\n'  
		error_file.write(err)
		sys.exit(1)
	try:
		tn.read_until("password: ", READ_TIMEOUT)
		tn.write(PWD + "\n")
	except:
		err = switch_ip + ':\tPassword Prompt Error\n'
		error_file.write(err)
		sys.exit(1)
	time.sleep(1)

	return tn
	
	
def threadFunction(line, target, error_file):
	copied, verified, boot, deleted = ['No']*4
	verify_output = ''
	ping_coutner = 1
	switch_ip, new_ios, md5hash, old_ios_path = line.split(',')
	
	tn = TelnetLogon(switch_ip)

	telnetWrite(tn, "terminal length 0")
	
	# Backup startup config
	telnetWrite(tn, "copy run tftp")
	telnetWrite(tn, TFTP_SERVER, 5)
	print switch_ip + ': Copying running config to tftp'
	
	# Copy IOS to flash
	telnetWrite(tn, "copy tftp flash")
	telnetWrite(tn, TFTP_SERVER)
	telnetWrite(tn, TFTP_SERVER)
	telnetWrite(tn, new_ios)
	telnetWrite(tn, new_ios, 1000)
	print '{}: Copying IOS to flash'.format(switch_ip)
	
	# Gather output from verify IOS with md5 hash. If Verified is not in output string, close telnet session and thread
	tn.write("verify /md5 flash:{} {}\n".format(new_ios, md5hash))
	print '{}: Verifying flash'.format(switch_ip)
	
	try:
		while True:
			verify_output += tn.read_some()
	except:
		pass
	
	if 'Verified' not in verify_output:
		yerr = switch_ip + ':\tFailed to verify IOS\n'
		error_file.write(err)
		tn.close()
		sys.exit(1)
	else:
		copied, verified = ['Yes']*2
	
	telnetWrite(tn, 'conf t')
	telnetWrite(tn, 'boot system flash:{}'.format(new_ios))
	print '{}: Configuring system boot path'.format(switch_ip)
	
	# Save running configuration to NVRAM
	telnetWrite(tn, 'do write mem', 5)
	print '{}: Writing to memory'.format(switch_ip)

	# Reboot Switch in 1 minute
	telnetWrite(tn, 'do reload in 1')
	print '{}: Rebooting in 1 minute'.format(switch_ip)
	telnet.Write(tn , '', 65)
	print '{}: Rebooting... '.format(switch_ip)
	tn.close()
	# Wait  minutes for switch to reboot before telneting onto switch
	time.sleep(300)
	
	while True:
		if ping(switch_ip) == 0:
			print switch_ip + ': System rebooted successfully'
			break
		else:
			ping_coutner += 1
			print switch_ip + ': System offline... # {}'.format(ping_coutner)
			time.sleep(30)
			if ping_coutner == 10: 
				err = switch_ip + ':\tSWITCH DOWN!!!!\n'
				error_file.write(err)
				sys.exit(1)
				break
	
	tn = telnetLogon(switch_ip)
	
	telnetWrite(tn, "terminal length 0")
		
	# Verify system booted into new IOS
	telnetWrite(tn , "show version")
		
	
	if 'System image file is \"flash:{}\"'.format(new_ios) in tn.read_very_eager():
		# Delete old IOS
		print switch_ip + ': Deleting OLD IOS'
		telnetWrite(tn, "delete /force {}".format(old_ios_path), 5)
		boot, deleted = ['Yes']*2
	else:
		err = switch_ip + ':\tNew IOS not set in boot system path\n'
		error_file.write(err)
	
	tn.close()
	
	target.write('%s,%s,%s,%s,%s\n'% (switch_ip, copied, verified, boot, deleted))

	
if __name__ == "__main__":
        main()

