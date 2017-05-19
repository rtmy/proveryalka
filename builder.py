import http.server
import os
import subprocess
import time
import json
import git
import re
import postgresql

class RequestHandler(http.server.CGIHTTPRequestHandler):
	def do_GET(self):
		self.send_response(200)
		self.send_header('Content-type', 'text/html')
		self.end_headers()

		self.wfile.write(bytes('{"status":"error", "content":{"text":"Please send POST"}}', "utf8"))
	def do_POST(self):
		# Send response status
		self.send_response(200)		

		self.send_header('Content-type','application/json')
		self.end_headers()

		data = self.rfile.read(65535).decode()
		print(data)
		
		contents = json.loads(data)

		action = contents["type-action"]
		repository = contents["repository"]

		if not action or not repository:
			self.wfile.write(bytes('{"status":"error", "content":{"text":"post, please"}}', "utf8"))
			return

		print(repository)
		pattern = re.compile("https:\/\/github\.com\/(?P<user>[A-z]+)\/(?P<repo>[A-z]+)")

		match = pattern.match(repository)

		if not match:
			self.wfile.write(bytes('{"status":"error", "content":{"text":"repo not compatible"}}', "utf8"))
			return

		user = match.group('user')
		repo = match.group('repo')

		if action == "build":
			url = 'https://github.com/' + user + '/' + repo 
			repodir = gitget(url)
			output = build(repodir)
		elif action == "retrieve":
			print('retrieve')
			output = retrieve(repo)
		else:
			output = {'status':'error', 'content':{'text':'requested action is unknown'}}

		encoder = json.JSONEncoder()
		output = encoder.encode(output)

		self.wfile.write(bytes(output, "utf8"))
		print('sent')
		return

def run(server_class=http.server.HTTPServer, handler_class=RequestHandler):
	server_address = ('', 8000)
	httpd = server_class(server_address, handler_class)
	httpd.serve_forever()

def gitget(url):
	reponame = os.path.basename(url)
	repodir = os.path.join(os.getcwd(), reponame + time.strftime("%Y%m%d%H%M%S"))
	repo = git.Repo.init(repodir)
	origin = repo.create_remote('origin', url)
	origin.fetch()
	repo.create_head('master', origin.refs.master).set_tracking_branch(origin.refs.master).checkout()
	origin.pull()
	return repodir

def build(repodir):
	cflags = ['--std=c89', '-Wall', '-Werror']
	global username
	for dir in next(os.walk(repodir))[1]:
		if dir != '.git':
			username = dir

	print(username)
	with open(os.path.join(repodir, username, 'build.json')) as data_file: 
		if data_file:   
			data = json.load(data_file)
		else:
			return {'status':'error', 'content':{'text':'automatic check is not supported by this repo'}}

	print(username)
	lang = data["lang"]
	if lang == "lang_C":
		gcc = 'gcc'
	elif lang == "lang_C++":
		gcc = 'g++'
	else:
		return {'status':'error', 'content':{'text':'language is not supported'}}

	## проверять флаги
	flags = data["flags"]
	for flag in flags:
		if flag not in cflags:
			cflags.append(flag)
		else:
			return {'status':'error', 'content':{'text':'flag overriding is not allowed'}}

	files = data["files"]
	formatversion = data["format-version"]
	appversion = data["app-version"]
	appbuild = data["app-build"]

	if not os.path.exists('logs'):
		os.makedirs('logs')

	result = []
	logfile = open(os.path.join('logs', os.path.basename(repodir))+'.log', "wb")
	for f in files:
		proc = subprocess.Popen([gcc, *cflags, os.path.join(repodir, username, f)], stderr=subprocess.PIPE)
		output = proc.stderr.read().decode()
		result.append({"filename":f, "output":output})

	print(username)
	result = json.dumps(result)
	## TODO: время в виде Unix Timestamp
	ins(username, time.time(), result)
	## logfile.write(bytes(result, "utf8"))
	## logfile.close()
	return {'status':'ok', 'content':{'text':'...'}}

def retrieve(reponame, date='latest'):
	## TODO: переделать для работы с БД
	for filename in next(os.walk('logs'))[2]:
		print(filename)
		if reponame in filename:
			logfile = filename
	try:
		logfile
	except NameError: ## ??!?
		return {'status':'error', 'content':{'text':'logfile not found'}}

	logfile = open(os.path.join('logs', logfile))
	output =  logfile.read()
	logfile.close()
	return {'status':'ok', 'content':{'filename':filename, 'text':output}}


## TODO: скрипт для разворачивания БД, проверка перед записью
db = postgresql.open('pq://builderpy:blogger@localhost/logs')
ins = db.prepare("INSERT INTO logs (username, time, logs) VALUES ($1, $2, $3)")
run()
