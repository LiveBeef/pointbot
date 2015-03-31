#/u/GoldenSights
import praw # simple interface to the reddit API, also handles rate limiting of requests
import time
import sqlite3
import traceback

'''USER CONFIGURATION'''

USERNAME  = "checks_for_checks"
#This is the bot's Username. In order to send mail, he must have some amount of Karma.
PASSWORD  = "[REDACTED]"
#This is the bot's Password.
USERAGENT = "/u/Livebeef's /r/theydidthemath checkmark checker"
#This is a short description of what the bot does. For example "/u/GoldenSights' Newsletter bot"
SUBREDDIT = "Theydidthemath"
#This is the sub or list of subs to scan for new posts. For a single sub, use "sub1". For multiple subreddits, use "sub1+sub2+sub3+..."
TITLETAG = "[Request]"
#If this is non-blank, then this string must be in the title or flair of the post to work
TRIGGERS = ["thanks", "thank you", "awesome", "well done", "cool"]
TRIGGERS2 = ["&gt; ✓", "&gt;✓"]
#These are lists of strings that the bot will scan for to determine whether to send the corresponding REPLYSTRING below
TRIGGERREQUIRED = True
#If this is True, the comment must contain a trigger to post
#If this is False, the comment will be posted as long as there are no anti-triggers
ANTITRIGGERS = ["but", "wouldn't", "shouldn't", "couldn't", "?", "however", "edit", "fix", "bot", "check", "aren't"]
#Anti-triggers will ALWAYS deny the post.
CHECKS = ["✓", "!point"]
#These are scanned for in the message body and act as antitriggers while also whitelisting OP from future replies.
REPLYSTRING1 = "If you're satisfied with a user's math answer, don't forget to reply to their comment with a\n\n> ✓\n\nto award a request point! (Must make a new comment, can't edit into this one. Can't be indented, like the one in this message.) See the sidebar for more info!\n\n---\n\n^^I ^^am ^^a ^^bot ^^run ^^by ^^/u/Livebeef, ^^please ^^let ^^him ^^know ^^if ^^I'm ^^acting ^^up!"
REPLYSTRING2 = "Did you mean to award a request point for another user's math? If so, please make a **new** reply (as in, **don't change this one**) to their comment with the checkmark unindented (without the '>' or bar in front of it). The indentation keeps the request point from being awarded.\n\n---\n\n^^I ^^am ^^a ^^bot ^^run ^^by ^^/u/Livebeef, ^^please ^^let ^^him ^^know ^^if ^^I'm ^^acting ^^up!"
#These are the strings sent if their corresponding triggers are found and other conditions are met
MAXPOSTS = 100
#This is how many posts you want to retrieve all at once. PRAW can download 100 at a time.
WAIT = 50
#This is how many seconds you will wait between cycles. The bot is completely inactive during this time.


'''All done!'''




WAITS = str(WAIT)
try:
	import bot #This is a file in my python library which contains my Bot's username and password. I can push code to Git without showing credentials
	USERNAME = bot.uG
	PASSWORD = bot.pG
	USERAGENT = bot.aG
except ImportError:
	pass

sql = sqlite3.connect('sql.db')
print('Loaded SQL Database')
cur = sql.cursor()

cur.execute('CREATE TABLE IF NOT EXISTS oldposts(ID TEXT)')	# Table containing comments already parsed
cur.execute('CREATE TABLE IF NOT EXISTS postedthreads(ID TEXT, RESPONSE INT)')	# Table containing two whitelists. An OP will be placed on one of these
																				# whitelists if they are sent a corresponding string declared above.
																				# It is not desirable to send the same OP the same message over and over
																				# again, as one message informing them of the system and one message in
																				# case they accidentally indent their checkmark is sufficient to cover
																				# the bot's entire scope of purpose.
print('Loaded Completed tables')

sql.commit()

r = praw.Reddit(USERAGENT)
r.login(USERNAME, PASSWORD)

# This is the parsing function. It is called every WAITS seconds.
def scanSub():
	print('Searching /r/'+ SUBREDDIT + '...')
	subreddit = r.get_subreddit(SUBREDDIT)
	posts = subreddit.get_comments(limit=MAXPOSTS)
	for post in posts:
		pid = post.fullname
		cur.execute('SELECT * FROM oldposts WHERE ID=?', [pid])
		if not cur.fetchone():
			if not post.is_root: # filters out top-level comments
				print('Parsing comment ' + pid + ' : ', end="")
				submission = post.submission
				if not submission.link_flair_text:
					submission.link_flair_text = ""
				stitle = submission.title.lower()+' '+submission.link_flair_text.lower()
				if TITLETAG == "" or TITLETAG.lower() in stitle:	# filters out non-TITLETAG posts
					try:
						pauthor = post.author.name
						sauthor = submission.author.name
						if pauthor == sauthor:	# filters out comments by non-OPs
							parentcomment = r.get_info(thing_id=post.parent_id)
							parentauthor = parentcomment.author.name
							if parentauthor != "checks_for_checks":	# filters out replies to the bot itself
								if len(parentcomment.body) < 250:	# filters out too short "low effort" comments
									print('Skipping: Parent too short')
									log(0, pid, 'Skipped: Parent too short', submission.title, sauthor)
								elif any(trig.lower() in post.body.lower() for trig in TRIGGERS2):	# First check: is there a trigger from TRIGGERS2 in the body?
																									# Done in this order because indented checkmarks are always an
																									# indicator that OP knows about the RP system and are happy with
																									# a reply, but their RP was held up by TDTMbot's syntax
									cur.execute('SELECT * FROM postedthreads WHERE ID=? AND RESPONSE=?', [submission.id, 2])
									if not cur.fetchone():	# filters out OPs on whitelist 2
										fire(post, submission.id, 2, pauthor, pid)
										log(1, pid, 'Failed RP award (indented)', submission.title, sauthor)
									else:
										print('Skipping (OP: Whitelist 2)')
										log(0, pid, 'Skipped: OP (Whitelist 2)', submission.title, sauthor)
								elif any(check.lower() in post.body.lower() for check in CHECKS):	# Second check: did OP correctly award a RP? This would eliminate
																									# any use of the bot for the post and would land OP on whitelist 1
									cur.execute('SELECT * FROM postedthreads WHERE ID=? AND RESPONSE=?', [submission.id, 1])
									if not cur.fetchone():	# filters out OPs on whitelist 1; if they are not already
															# on the list, they will be put on it as they have demonstrated
															# knowledge of the RP system and how to correctly award one
										print('Skipping (OP: RP correctly awarded, whitelisting)')
										cur.execute('INSERT INTO postedthreads VALUES(?, ?)', [submission.id, 1])
										sql.commit()
										log(0, pid, 'Skipped: OP (RP correctly awarded, whitelisted)', submission.title, sauthor)
									else:
										print('Skipping (OP: Whitelist 1)')
										log(0, pid, 'Skipped: OP (Whitelist 1)', submission.title, sauthor)
								elif any(atrig.lower() in post.body.lower() for atrig in ANTITRIGGERS):	# Third check: are there any antitriggers in the message body?
																										# If defined above and present in the message body, these will
																										# always cause the bot to pass over the comment.
									print('Skipping (OP: antitrigger found)')
									log(0, pid, 'Skipped: OP (Antitrigger found)', submission.title, sauthor)
								elif TRIGGERREQUIRED ==False or any(trig.lower() in post.body.lower() for trig in TRIGGERS):	# Fourth check: is there a trigger from TRIGGERS in the body?
																																# Last check because there is the most amount of checks that
																																# must be performed to determine if a reply is needed.
									cur.execute('SELECT * FROM postedthreads WHERE ID=? AND RESPONSE=?', [submission.id, 1])
									if not cur.fetchone():	# filters out OPs on whitelist 1
										fire(post, submission.id, 1, pauthor, pid)
										log(1, pid, 'Thanked but no RP awarded', submission.title, sauthor)
									else:
										print('Skipping (OP: Whitelist 1)')
										log(0, pid, 'Skipped: OP (Whitelist 1)', submission.title, sauthor)
								else:
									print('Skipping (OP: no triggers found)')
									log(0, pid, 'Skipped: OP (No triggers found)', submission.title, sauthor)
							else: # TODO: Add handle for bot replies
								print('Skipping (OP: replied to bot)')
								log(0, pid, 'Skipped: OP (Replied to bot)', submission.title, sauthor)
						else:
							print('Skipping (not OP)')
							log(0, pid, 'Skipped: Not OP', submission.title, sauthor)
					except Exception as e:
						traceback.print_exc()
				else:
					print('Not a ' + TITLETAG + ' post')
					log(0, pid, 'Skipped: Not a ' + TITLETAG + ' post', submission.title, sauthor)
			cur.execute('INSERT INTO oldposts VALUES(?)', [pid])
			sql.commit()

# This subroutine is activated when scanSub() has determined that a comment warrants a reply.
# It takes 5 fields containing comment information and returns nothing.
def fire(post, subID, replID, pauthor, pid):
	print('\nReplying to ' + pauthor + ', comment ' + pid, end="")
	if replID==1:
		print(', thanked but no RP awarded')
		post.reply(REPLYSTRING1)
	elif replID==2:
		print(', failed RP award (indented)')
		post.reply(REPLYSTRING2)
	else:
		print(', ERROR')
		pass
	cur.execute('INSERT INTO postedthreads VALUES(?, ?)', [subID, replID])
	sql.commit()

# This subroutine is activated for every comment that is parsed by the bot.
# It takes 5 parameters: whether it fired, the short-form post ID, a string describing the outcome
# of the parse, and the title and author of the submission for ease of debugging. It will append
# a file named LogFile.txt in the directory with the outcome of every parse for future debugging
# and reference.
def log(didFire, pid, action, stitle, sauthor):
	if didFire == 0:
		didFire = "   "
	else:
		didFire = " ! "
	i = datetime.datetime.now()
	with open('LogFile.txt', 'a') as LogFile:
		LogFile.write(i.strftime('%Y/%m/%d %H:%M:%S') + didFire + pid + ' "' + stitle + '" by ' + sauthor + ' ' + action + '\n')

# Closest thing to a main() method. Throws all exceptions as Reddit servers being fucky
while True:
	try:
		scanSub()
		print('Search complete, running again in ' + WAITS + ' seconds \n')
	except Exception as e:
		print('EXCEPTION! Reddit servers unreachable. Trying again in ' + WAITS + ' seconds \n')
	sql.commit()
	time.sleep(WAIT)