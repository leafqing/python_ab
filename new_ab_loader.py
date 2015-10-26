#!/usr/bin/env python 
"""
this script aims to test the http server performance,
the function of which similar to ab(apache benchmark).
thirdparty lib "gevent" is needed for this script.
"""
import time
import sys
import argparse

import gevent
from gevent.pool import Pool
from gevent import monkey
monkey.patch_all()

import requests
from requests import RequestException

from collections import defaultdict
import logging
log_debug=logging.DEBUG
log_format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
log_datefmt="%Y-%m-%d %H:%M:%S"
log_filename="test_performance.log"
logging.basicConfig(level=log_debug, format=log_format, filename=log_filename, datefmt=log_datefmt)
logger=logging.getLogger("test_performance")


SUPPORT_METHODS = ('get', 'head', 'post', 'put', 'delete', 'options')

"""
there are 2 classes in this script:
1, Running_Loader, this class response to running the test.
2, Result_Info, this class response to calculate and output the result.
"""
class Running_Loader(object):
	def __init__(self, url, number, conncurrency, timeout, method, proxies, ct, headers, auth, cookies, files, data):
		self.url=url
		self.number=number
		self.conncurrency=conncurrency
		self.timeout=timeout
		self.method=method
		self.proxies=proxies
		self.ct=ct
		self.headers=headers
		self.auth=auth
		self.cookies=cookies
		self.files=files
		self.data=data
		self.result=Result_Info()
	
	def one_req(self):
		start=time.time()
	
		session=requests.Session()
		session.headers.update(self.headers)
		session.cookies.update(self.cookies)
		session.proxies.update(self.proxies)
		METHOD=getattr(session, self.method)	
		try:
			response=METHOD(self.url, auth=self.auth)
			#logger.info("new request, url: %s" %self.url)
		except RequestException as err:
			self.result.errors.append(err)
		else:
			duration = time.time() - start
			self.result.status_code_counter[response.status_code].append(duration)
			logger.info("response code is: %d" % response.status_code)
			logger.info("the request spent time:%f" %duration)
	def loop_test_runner(self):
		self.result.start_time = time.time()
		
		pool=Pool(self.conncurrency)
		
		try:
			if self.number > 0 :
				print("The input request number is: %d, conncurrency number is %d " % (self.number, self.conncurrency))
				while self.number:
					pool.spawn(self.one_req)
					self.number-=1
			else:
				print("The input timeout is %d, conncurrency number is %d " % (self.timeout, self.conncurrency))
				with gevent.Timeout(self.timeout, False):
					while True:
						pool.spawn(self.one_req)
		except KeyboardInterrupt:
			pass
		finally:
			self.result.end_time = time.time()

class Result_Info(object):
	def __init__(self):
		self.status_code_counter = defaultdict(list)
		self.errors=[]
		self.start_time=0.0
		self.end_time=0.0
		self.total_time=0.0
		self.rps=0

	def cal_res(self):
		self.total_time=self.end_time - self.start_time
		self.code_num={}
		request_time_list=[]
		for key, value in self.status_code_counter.items():
			self.code_num[key]=len(value)
			request_time_list.extend(value)

		self.total_request_number = len(request_time_list)
		if self.total_time != 0:
			self.rps=self.total_request_number/float(self.total_time)

		self.all_request_spend_time=sum(request_time_list)
		if self.total_request_number == 0:
			self.avg_time=0
		else:
			self.avg_time=self.all_request_spend_time/float(self.total_request_number)
		time_list_sorted=sorted(request_time_list)
	
		
	def print_res(self):
		self.cal_res()
		print('the testing result is as below:')
		print('the total request number is: %d' % self.total_request_number)
		print('the start request time is: %f' % self.start_time)
		print('the end request time is: %f' % self.end_time)
		print('the total request time is: %f' % self.total_time)
		print('the request code and number is: \n')
		for key in self.code_num:
			print("reponse code: %s, times: %d" % (key, self.code_num[key]))
		print("request-per-seconds:%f" % self.rps)


def get_OptionParser():
	parser = argparse.ArgumentParser(description='test http load performance.')
	parser.add_argument('-m', '--method', help='HTTP Method', type=str, default='GET', choices=SUPPORT_METHODS)
	parser.add_argument('-u', '--url', help='target url for testing', required=True, type=str)
	parser.add_argument('-n', '--number', help='number of requests', type=int)
	parser.add_argument('-c', '--concurrency', help='concurrency number', default=1, type=int)
	parser.add_argument('-t', '--timeout', help='testing time(s) of a cycle', default=5, type=int)
	parser.add_argument('-a', '--auth', help='user:passwd', default=None, type=str)
	parser.add_argument('-C', '--cookie', help='give the cookie by key:value format', default=None, type=str)
	parser.add_argument('-p', '--proxy', help='set the proxy, such as: http://10.228.163.119:8080', default=None, type=str)
	parser.add_argument('-d', '--data', help='post or put data', default=None, type=str)
	parser.add_argument('--content-type', help='Content-type', type=str, default='text/plain')
	parser.add_argument('--header', help='customer header, name:value', action='append', type=str)
	parser.add_argument('--file', help='the upload file, afford with absolute path', default=None, type=file)

	return parser

	
def run():
	parser = get_OptionParser()
	vals = parser.parse_args()
	
	if vals.number < 0 :
		print("the number should be larger thah 0. the test will go on with timeout 5s.")
	if not (vals.url.startswith("http://") or vals.url.startswith("https://")):
		print("the url has no schema, please input url like, http:// or https://")
		logger.debug("url input is not right!")
		sys.exit(0)

	headers={}
	if vals.header is not None:
		for hdr in vals.header:
			str = hdr.split(':')
			if len(str) != 2:
				print("header format is name:value.")
				logger.debug("header format is not right,  should be like name:value")
				sys.exit(0)
			headers[str[0]]=str[1]
		print(headers)
	
	if vals.auth is None:
		http_auth=None
	else:
		user, passwd = vals.auth.split(':')
		from requests.auth import HTTPBasicAuth
		http_auth=HTTPBasicAuth(user, passwd)
		logger.debug("http auth was set. user:%s" %user)

	proxies={}
	if vals.proxy is not None:
		schema=vals.proxy.split(":",1)[0]
		proxies[schema]=vals.proxy
		logger.debug("proxy was set, proxy: %s" % proxies)

	cookies={}
	if vals.cookie is not None:
		key=vals.cookie.split(":",1)[0]
		cookies[key]=vals.cookie.split(":",1)[1]
		logger.debug("cookies was set, cookie: %s" %cookies)


	if vals.file is None:
		file_upload=None
	else:
		file_upload={'file': open(vals.file, 'rb')}
		logger.debug("upload file: %s" %vals.file)

	if vals.data is not None and vals.method not in ('put', 'post'):
		print("just post and put method accept data!")
		logger.debug("just post and put method need accept data")
		sys.exit(0)
	
	try:
		runner = Running_Loader(vals.url, vals.number, vals.concurrency, vals.timeout, vals.method.lower(), proxies, vals.content_type, headers, http_auth, cookies, file_upload, vals.data)
		logger.debug("performance testing start!")
		runner.loop_test_runner()	
	except RequestException as e:
		print(str(e))
		sys.exit(1)
		
	runner.result.print_res()
if __name__ == '__main__':
	run()
